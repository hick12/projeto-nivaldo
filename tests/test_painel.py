"""Testes do painel do gestor e da gestao de pedidos — Projeto Final.

Cobrem o que o manual da disciplina cobra nesta parte:

- controle de acesso: visitante, cliente comum e gestor
- "Dashboard: indicador apos inserir dados" — o indicador se move quando
  um checkout acontece
- conciliacao em zero depois de vários checkouts
- "Atualizacao: alterar status, antes e depois", com as transicoes
  validas e as invalidas
- cancelamento devolvendo estoque, e cancelamento recusado nao alterando
  nada
"""

from decimal import Decimal

import pytest

from app import (
    ItemPedido,
    Pedido,
    Produto,
    TransicaoInvalida,
    PedidoInexistente,
    alterar_status_pedido,
    db,
    finalizar_pedido,
    indicadores,
)

from conftest import EMAIL_CLIENTE, EMAIL_GESTOR


# ---------------------------------------------------------------------
# 1. Controle de acesso
# ---------------------------------------------------------------------

def test_painel_redireciona_visitante_para_o_login(navegador):
    """Sem sessao, 302 — e nao 403.

    403 para quem nao se identificou diria que a rota existe e que o
    problema e permissao. Quem nao esta logado primeiro se identifica.
    """
    resposta = navegador.get("/painel")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_painel_devolve_403_para_cliente_comum(navegador, entrar, cliente):
    """Logado, mas fora de ADMIN_EMAILS."""
    entrar(EMAIL_CLIENTE)

    resposta = navegador.get("/painel")
    pagina = resposta.get_data(as_text=True)

    assert resposta.status_code == 403
    # Pagina amigavel, nao o 403 cru do Werkzeug.
    assert "Esta área é do gestor da loja" in pagina
    # E nao entrega detalhe de configuracao ao cliente.
    assert "ADMIN_EMAILS" not in pagina


def test_painel_abre_para_o_gestor(navegador, entrar, gestor, catalogo):
    entrar(EMAIL_GESTOR)

    resposta = navegador.get("/painel")
    pagina = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "Painel do gestor" in pagina
    assert "Conciliação" in pagina


def test_link_do_painel_aparece_so_para_o_gestor(
    navegador, entrar, cliente, catalogo
):
    """O menu nao oferece ao cliente uma porta que vai fechar na cara dele."""
    entrar(EMAIL_CLIENTE)
    assert "/painel" not in navegador.get("/").get_data(as_text=True)


def test_link_do_painel_aparece_para_o_gestor(
    navegador, entrar, gestor, catalogo
):
    entrar(EMAIL_GESTOR)
    assert "/painel" in navegador.get("/").get_data(as_text=True)


def test_mudanca_de_status_e_negada_a_cliente_comum(
    navegador, entrar, token_da_sessao, cliente, catalogo
):
    """O 403 tambem vale para a ESCRITA, nao so para ver a tela.

    Esconder o link no menu e proteger a leitura nao basta: quem souber a
    URL pode montar o POST a mao. O token CSRF aqui e o da propria sessao
    do cliente — ele existe e e valido. O que barra e o papel, nao o token.
    """
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "FINA"}],
    )

    entrar(EMAIL_CLIENTE)

    resposta = navegador.post(
        f"/painel/pedidos/{pedido.id}/status",
        data={"status": "PAGO", "_csrf": token_da_sessao()},
    )

    assert resposta.status_code == 403

    db.session.refresh(pedido)
    assert pedido.status == "CRIADO"


# ---------------------------------------------------------------------
# 2. Os indicadores
# ---------------------------------------------------------------------

def test_indicador_se_move_depois_de_um_checkout(cliente, catalogo):
    """O "Dashboard: indicador apos inserir dados" que o manual pede.

    Le o indicador, faz uma compra, le de novo. Os numeros tem que andar —
    e andar exatamente o valor da compra, nao "mais ou menos".
    """
    antes = indicadores(dias=30)
    assert antes["pedidos"] == 0
    assert Decimal(antes["faturamento"]) == Decimal("0")

    finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 3, "moagem": "FINA"}],
    )

    depois = indicadores(dias=30)

    assert depois["pedidos"] == 1
    assert Decimal(depois["faturamento"]) == Decimal("267.00")  # 3 x 89,00
    assert Decimal(depois["ticket_medio"]) == Decimal("267.00")

    # E o indicador de vendas por regiao tambem: antes nao havia linha
    # nenhuma, agora ha a regiao do cafe comprado.
    assert [l["regiao"] for l in depois["vendas_por_regiao"]] == ["Bahia"]
    assert depois["vendas_por_regiao"][0]["unidades"] == 3
    assert depois["vendas_por_regiao"][0]["participacao"] == Decimal("100.0")


def test_pedido_cancelado_sai_do_faturamento_mas_fica_no_funil(
    cliente, catalogo
):
    """Cancelado nao e receita — mas continua existindo."""
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 2, "moagem": "GRAO"}],
    )

    assert indicadores()["pedidos"] == 1

    alterar_status_pedido(pedido.id, "CANCELADO")
    depois = indicadores()

    # Fora do faturamento.
    assert depois["pedidos"] == 0
    assert Decimal(depois["faturamento"]) == Decimal("0")

    # Dentro do funil de status.
    por_status = {l["status"]: l["pedidos"] for l in depois["pedidos_por_status"]}
    assert por_status["CANCELADO"] == 1

    # E ainda conferido na conciliacao: o cancelamento muda o status e
    # devolve estoque, mas nao reescreve o historico financeiro.
    assert depois["conciliacao"]["pedidos"] == 1
    assert depois["conciliacao"]["divergentes"] == 0


def test_conciliacao_fica_em_zero_depois_de_varios_checkouts(
    cliente, outro_cliente, catalogo
):
    """A prova ligada a dor do contexto: "falhas de conciliacao".

    Oito pedidos, dois clientes, moagens misturadas, incluindo o mesmo
    cafe em duas moagens no mesmo pedido. Nenhum pode ter `total`
    diferente da soma de `quantidade * preco_unitario` dos itens.
    """
    produto = catalogo["farto"]

    for volta in range(4):
        for quem in (cliente, outro_cliente):
            finalizar_pedido(
                quem.id,
                [
                    {
                        "produto_id": produto.id,
                        "quantidade": 1,
                        "moagem": "GRAO" if volta % 2 else "MEDIA",
                    }
                ],
            )

    d = indicadores()

    assert d["conciliacao"]["pedidos"] == 8
    assert d["conciliacao"]["conciliados"] == 8
    assert d["conciliacao"]["divergentes"] == 0

    # E a conferencia feita de novo, a mao, sem passar pela consulta do
    # painel: se as duas contas discordassem, uma das duas estaria errada.
    for pedido in db.session.scalars(db.select(Pedido)).all():
        soma = sum(
            (item.quantidade * item.preco_unitario for item in pedido.itens),
            Decimal("0"),
        )
        assert pedido.total == soma


def test_estoque_critico_respeita_o_limite(cliente, catalogo):
    """O café com estoque 1 aparece; o com estoque 10 não."""
    criticos = {l["nome"] for l in indicadores(dias=30)["estoque_critico"]}

    assert catalogo["escasso"].nome in criticos   # estoque 1
    assert catalogo["farto"].nome not in criticos  # estoque 10


def test_filtro_de_periodo_limita_o_valor_vindo_da_url(
    navegador, entrar, gestor, catalogo
):
    """`?dias=` absurdo cai no padrao, em vez de varrer a tabela inteira."""
    entrar(EMAIL_GESTOR)

    for valor, esperado in [
        ("7", "7 dias"),
        ("999999", "365 dias"),
        ("abacaxi", "30 dias"),
        ("-5", "1 dias"),
    ]:
        pagina = navegador.get(f"/painel?dias={valor}").get_data(as_text=True)
        assert esperado in pagina, f"?dias={valor} deveria virar {esperado}"


# ---------------------------------------------------------------------
# 3. Transicoes de status
# ---------------------------------------------------------------------

@pytest.fixture
def pedido_pronto(cliente, catalogo) -> Pedido:
    """Um pedido em CRIADO, com 2 unidades do cafe de estoque folgado."""
    return finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 2, "moagem": "MEDIA"}],
    )


def test_transicao_valida_criado_para_pago(pedido_pronto):
    """O antes e o depois, que o manual pede como evidencia."""
    assert pedido_pronto.status == "CRIADO"

    resumo = alterar_status_pedido(pedido_pronto.id, "PAGO")

    assert resumo["de"] == "CRIADO"
    assert resumo["para"] == "PAGO"
    assert resumo["unidades_devolvidas"] == 0

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == "PAGO"


def test_transicao_valida_o_caminho_completo_ate_enviado(pedido_pronto):
    alterar_status_pedido(pedido_pronto.id, "PAGO")
    alterar_status_pedido(pedido_pronto.id, "ENVIADO")

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == "ENVIADO"


@pytest.mark.parametrize(
    "de, para",
    [
        ("CRIADO", "ENVIADO"),    # nao da para enviar sem pagar
        ("ENVIADO", "PAGO"),      # nao da para voltar
        ("ENVIADO", "CANCELADO"),  # nao da para cancelar o que ja saiu
        ("CANCELADO", "PAGO"),    # nao da para ressuscitar
    ],
)
def test_transicoes_invalidas_sao_recusadas(pedido_pronto, de, para):
    """A maquina de estados nao tem atalho nem marcha a re."""
    # Leva o pedido ao estado de partida pelo caminho legitimo.
    caminho = {
        "CRIADO": [],
        "PAGO": ["PAGO"],
        "ENVIADO": ["PAGO", "ENVIADO"],
        "CANCELADO": ["CANCELADO"],
    }[de]
    for passo in caminho:
        alterar_status_pedido(pedido_pronto.id, passo)

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == de

    with pytest.raises(TransicaoInvalida) as erro:
        alterar_status_pedido(pedido_pronto.id, para)

    # A mensagem precisa dizer o que e possivel, nao so que deu errado.
    assert de in str(erro.value)

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == de, "o status nao pode ter mudado"


def test_status_inexistente_e_recusado(pedido_pronto):
    """Valor fora do dominio da constraint ck_pedidos_status."""
    with pytest.raises(TransicaoInvalida):
        alterar_status_pedido(pedido_pronto.id, "ENTREGUE")

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == "CRIADO"


def test_repetir_o_mesmo_status_e_recusado(pedido_pronto):
    with pytest.raises(TransicaoInvalida) as erro:
        alterar_status_pedido(pedido_pronto.id, "CRIADO")
    assert "já está em CRIADO" in str(erro.value)


def test_pedido_inexistente_nao_muda_status(cliente, catalogo):
    with pytest.raises(PedidoInexistente):
        alterar_status_pedido(999999, "PAGO")


# ---------------------------------------------------------------------
# 4. Cancelamento e estoque
# ---------------------------------------------------------------------

def test_cancelamento_devolve_o_estoque(pedido_pronto, catalogo):
    """A outra metade do checkout: a baixa de estoque tem volta."""
    produto = catalogo["farto"]

    db.session.refresh(produto)
    assert produto.estoque == 8  # 10 - 2 da compra

    resumo = alterar_status_pedido(pedido_pronto.id, "CANCELADO")

    assert resumo["unidades_devolvidas"] == 2

    db.session.refresh(produto)
    assert produto.estoque == 10, "o estoque tem que voltar ao que era"

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == "CANCELADO"

    # O historico financeiro NAO foi reescrito: os itens e o total
    # continuam gravados, e por isso a conciliacao continua fechando.
    assert pedido_pronto.total == Decimal("178.00")
    assert len(pedido_pronto.itens) == 1


def test_cancelamento_devolve_estoque_de_todos_os_itens(cliente, catalogo):
    farto, escasso = catalogo["farto"], catalogo["escasso"]

    pedido = finalizar_pedido(
        cliente.id,
        [
            {"produto_id": farto.id, "quantidade": 3, "moagem": "GRAO"},
            {"produto_id": escasso.id, "quantidade": 1, "moagem": "FINA"},
        ],
    )

    db.session.refresh(farto)
    db.session.refresh(escasso)
    assert (farto.estoque, escasso.estoque) == (7, 0)

    resumo = alterar_status_pedido(pedido.id, "CANCELADO")
    assert resumo["unidades_devolvidas"] == 4

    db.session.refresh(farto)
    db.session.refresh(escasso)
    assert (farto.estoque, escasso.estoque) == (10, 1)


def test_cancelamento_recusado_nao_altera_nada(pedido_pronto, catalogo):
    """Tudo-ou-nada tambem vale aqui.

    Cancela uma vez (valido) e tenta cancelar de novo (invalido, porque
    CANCELADO e terminal). A segunda tentativa nao pode devolver estoque
    uma segunda vez — seria estoque fantasma, criado do nada por um clique
    repetido.
    """
    produto = catalogo["farto"]

    alterar_status_pedido(pedido_pronto.id, "CANCELADO")
    db.session.refresh(produto)
    estoque_depois_do_cancelamento = produto.estoque
    assert estoque_depois_do_cancelamento == 10

    with pytest.raises(TransicaoInvalida):
        alterar_status_pedido(pedido_pronto.id, "CANCELADO")

    db.session.refresh(produto)
    assert produto.estoque == estoque_depois_do_cancelamento, (
        "um cancelamento recusado nao pode devolver estoque de novo"
    )

    db.session.refresh(pedido_pronto)
    assert pedido_pronto.status == "CANCELADO"
    assert pedido_pronto.total == Decimal("178.00")


def test_cancelamento_pela_tela_do_painel(
    navegador, entrar, gestor, cliente, catalogo
):
    """O caminho de ponta a ponta: formulario POST, com CSRF, pelo painel."""
    from conftest import token_csrf_de

    produto = catalogo["farto"]
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": produto.id, "quantidade": 2, "moagem": "FINA"}],
    )

    entrar(EMAIL_GESTOR)
    pagina = navegador.get("/painel").get_data(as_text=True)

    # O botao de cancelar precisa estar na tela para o pedido em CRIADO.
    assert f"/painel/pedidos/{pedido.id}/status" in pagina

    resposta = navegador.post(
        f"/painel/pedidos/{pedido.id}/status",
        data={"status": "CANCELADO", "_csrf": token_csrf_de(pagina)},
        follow_redirects=True,
    )

    assert resposta.status_code == 200
    final = resposta.get_data(as_text=True)
    # A mensagem traz o antes e o depois, e quanto voltou ao estoque.
    assert "CRIADO → CANCELADO" in final
    assert "2 unidade(s) devolvida(s) ao estoque" in final

    db.session.refresh(produto)
    assert produto.estoque == 10


def test_transicao_invalida_pela_tela_mostra_mensagem_clara(
    navegador, entrar, gestor, cliente, catalogo
):
    from conftest import token_csrf_de

    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    pagina = navegador.get("/painel").get_data(as_text=True)

    resposta = navegador.post(
        f"/painel/pedidos/{pedido.id}/status",
        data={"status": "ENVIADO", "_csrf": token_csrf_de(pagina)},
        follow_redirects=True,
    )

    assert resposta.status_code == 200
    assert "Não é possível ir de CRIADO para ENVIADO" in resposta.get_data(
        as_text=True
    )

    db.session.refresh(pedido)
    assert pedido.status == "CRIADO"


# ---------------------------------------------------------------------
# 5. O painel renderizado
# ---------------------------------------------------------------------

def test_painel_nao_usa_style_inline_nem_javascript(
    navegador, entrar, gestor, cliente, catalogo
):
    """As duas restricoes que moldaram a pagina.

    A CSP da loja traz `script-src 'none'` e `style-src 'self'` sem
    'unsafe-inline'. Um style= no HTML seria descartado pelo navegador, e
    a barra do grafico simplesmente nao apareceria em producao — falha que
    nao da erro nenhum no console do servidor.
    """
    finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.get("/painel")
    pagina = resposta.get_data(as_text=True)

    assert 'style="' not in pagina, "estilo inline seria bloqueado pela CSP"
    assert "<script" not in pagina, "o painel nao executa JavaScript"

    # A barra existe, e a largura dela vem de atributo SVG — que a CSP
    # nao bloqueia, porque nao e CSS.
    assert 'class="barra-cheia"' in pagina

    # E a CSP da rota continua proibindo script.
    assert "script-src 'none'" in resposta.headers["Content-Security-Policy"]
