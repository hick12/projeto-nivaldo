"""Testes da API JSON — Projeto Final.

O que importa aqui, em ordem de gravidade:

1. CONTROLE DE ACESSO. `/api/pedidos` nunca pode devolver pedido de outro
   cliente, e `/api/dashboard` nunca pode abrir para quem nao e gestor.
   Sao os dois testes que impedem a falha mais comum de API REST.
2. O CONTRATO. Erro sempre `{"erro": "..."}`, codigo certo para cada
   situacao, dinheiro como string decimal e nunca como float.
3. CSRF no PATCH, igual aos formularios da loja.
4. PRIVACIDADE do /api/resumo, que e publico.
"""

from decimal import Decimal

from app import db, finalizar_pedido

from conftest import EMAIL_CLIENTE, EMAIL_GESTOR, EMAIL_OUTRO


# ---------------------------------------------------------------------
# 1. /health
# ---------------------------------------------------------------------

def test_health_responde_ok_com_o_banco_no_ar(navegador):
    resposta = navegador.get("/health")

    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok", "banco": "ok"}


def test_health_nao_vaza_configuracao(navegador):
    """Health check e rota publica: nao diz onde nem como o banco roda."""
    corpo = navegador.get("/health").get_data(as_text=True)

    for proibido in ["postgres", "senha", "password", "localhost", "psycopg"]:
        assert proibido not in corpo.lower()


# ---------------------------------------------------------------------
# 2. Catalogo publico
# ---------------------------------------------------------------------

def test_categorias_lista_as_regioes(navegador, catalogo):
    dados = navegador.get("/api/categorias").get_json()

    assert dados["total"] == 1
    assert dados["categorias"][0]["nome"] == "Chapada Diamantina"
    assert dados["categorias"][0]["regiao"] == "Bahia"
    assert dados["categorias"][0]["cafes"] == 2


def test_produtos_devolve_o_catalogo(navegador, catalogo):
    dados = navegador.get("/api/produtos").get_json()

    assert dados["total"] == 2
    assert [p["nome"] for p in dados["produtos"]] == [
        "Chapada Geisha",
        "Piata Altitude",
    ]


def test_produtos_filtra_por_categoria(navegador, catalogo):
    categoria_id = catalogo["farto"].categoria_id

    dados = navegador.get(f"/api/produtos?categoria={categoria_id}").get_json()
    assert dados["total"] == 2

    # Categoria inexistente: 200 com lista vazia, nao 404. A consulta e
    # valida e o resultado e "nenhum cafe"; 404 diria que a ROTA nao existe.
    resposta = navegador.get("/api/produtos?categoria=98765")
    assert resposta.status_code == 200
    assert resposta.get_json()["total"] == 0


def test_preco_e_string_decimal_nunca_float(navegador, catalogo):
    """A mesma razao de o banco usar NUMERIC e nao FLOAT.

    Um numero JSON e um float IEEE 754. Serializar 148.00 como numero
    entrega a quem consome o tipo que este projeto recusou no banco.
    """
    produto = navegador.get("/api/produtos").get_json()["produtos"][0]

    assert isinstance(produto["preco"], str)
    assert produto["preco"] == "148.00"
    assert isinstance(produto["pontuacao_sca"], str)
    assert produto["pontuacao_sca"] == "91.00"

    # E o valor sobrevive a volta para Decimal sem perder nada.
    assert Decimal(produto["preco"]) == Decimal("148.00")


def test_produto_por_id(navegador, catalogo):
    produto = catalogo["escasso"]

    dados = navegador.get(f"/api/produtos/{produto.id}").get_json()

    assert dados["id"] == produto.id
    assert dados["nome"] == "Chapada Geisha"
    assert dados["torra"] == "CLARA"
    assert dados["regiao"] == "Bahia"


def test_produto_inexistente_devolve_404_em_json(navegador, catalogo):
    """404 com corpo JSON, nunca pagina HTML de erro e nunca 500."""
    resposta = navegador.get("/api/produtos/999999")

    assert resposta.status_code == 404
    assert resposta.is_json
    assert resposta.get_json() == {"erro": "Café #999999 não encontrado."}


# ---------------------------------------------------------------------
# 3. /api/pedidos — o teste de isolamento
# ---------------------------------------------------------------------

def test_pedidos_exige_login(navegador):
    """401 e nao 403: 401 quer dizer "identifique-se"."""
    resposta = navegador.get("/api/pedidos")

    assert resposta.status_code == 401
    assert resposta.get_json() == {
        "erro": "Faça login para acessar este recurso."
    }


def test_pedidos_nunca_devolve_pedido_de_outro_cliente(
    navegador, entrar, cliente, outro_cliente, catalogo
):
    """O teste mais importante desta suite.

    Dois clientes, um pedido cada. Logado como o primeiro, a resposta tem
    que conter SO o pedido dele — e o filtro vem da sessao, nao da URL.
    Nao existe `/api/pedidos?cliente=7` justamente por isso.
    """
    produto = catalogo["farto"]

    meu = finalizar_pedido(
        cliente.id,
        [{"produto_id": produto.id, "quantidade": 1, "moagem": "GRAO"}],
    )
    do_outro = finalizar_pedido(
        outro_cliente.id,
        [{"produto_id": produto.id, "quantidade": 2, "moagem": "FINA"}],
    )

    entrar(EMAIL_CLIENTE)
    dados = navegador.get("/api/pedidos").get_json()

    ids = [p["id"] for p in dados["pedidos"]]

    assert dados["cliente_id"] == cliente.id
    assert ids == [meu.id]
    assert do_outro.id not in ids

    # E o contrario tambem: o outro cliente nao ve o meu.
    entrar(EMAIL_OUTRO)
    ids_do_outro = [p["id"] for p in navegador.get("/api/pedidos").get_json()["pedidos"]]
    assert ids_do_outro == [do_outro.id]
    assert meu.id not in ids_do_outro


def test_pedidos_traz_moagem_e_preco_congelado(
    navegador, entrar, cliente, catalogo
):
    """Os dois atributos que fazem itens_pedido ser entidade."""
    from app import Produto

    produto = catalogo["farto"]

    finalizar_pedido(
        cliente.id,
        [
            {"produto_id": produto.id, "quantidade": 2, "moagem": "GRAO"},
            {"produto_id": produto.id, "quantidade": 1, "moagem": "FINA"},
        ],
    )

    # O cafe sobe de preco DEPOIS da compra.
    produto.preco = Decimal("129.00")
    db.session.commit()

    entrar(EMAIL_CLIENTE)
    pedido = navegador.get("/api/pedidos").get_json()["pedidos"][0]

    # Duas linhas do mesmo cafe, separadas pela moagem.
    assert len(pedido["itens"]) == 2
    assert {i["moagem"] for i in pedido["itens"]} == {"GRAO", "FINA"}

    # E o preco da epoca, nao o de hoje.
    assert all(i["preco_unitario"] == "89.00" for i in pedido["itens"])
    assert pedido["total"] == "267.00"

    # Conferencia: o total bate com a soma dos subtotais.
    soma = sum(Decimal(i["subtotal"]) for i in pedido["itens"])
    assert soma == Decimal(pedido["total"])

    # O preco ATUAL do produto, esse sim, mudou.
    atual = navegador.get(f"/api/produtos/{produto.id}").get_json()
    assert atual["preco"] == "129.00"


# ---------------------------------------------------------------------
# 4. /api/dashboard — acesso de gestor
# ---------------------------------------------------------------------

def test_dashboard_sem_login_devolve_401(navegador):
    resposta = navegador.get("/api/dashboard")

    assert resposta.status_code == 401
    assert "erro" in resposta.get_json()


def test_dashboard_para_cliente_comum_devolve_403(
    navegador, entrar, cliente, catalogo
):
    """Logado, mas fora de ADMIN_EMAILS. 403, com corpo JSON."""
    entrar(EMAIL_CLIENTE)
    resposta = navegador.get("/api/dashboard")

    assert resposta.status_code == 403
    assert resposta.get_json() == {"erro": "Acesso restrito ao gestor da loja."}


def test_dashboard_para_gestor_traz_os_sete_indicadores(
    navegador, entrar, gestor, cliente, catalogo
):
    finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 2, "moagem": "MEDIA"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.get("/api/dashboard?dias=30")

    assert resposta.status_code == 200
    d = resposta.get_json()

    # 1 e 2
    assert d["faturamento"]["pedidos"] == 1
    assert d["faturamento"]["valor"] == "178.00"
    assert d["ticket_medio"] == "178.00"
    # 3
    assert d["vendas_por_regiao"][0]["regiao"] == "Bahia"
    assert d["vendas_por_regiao"][0]["participacao_percentual"] == "100.0"
    # 4
    assert d["top_cafes"][0]["nome"] == "Piata Altitude"
    assert d["top_cafes"][0]["moagem_preferida"] == "MEDIA"
    # 5
    assert any(
        c["nome"] == "Chapada Geisha" for c in d["estoque_critico"]["cafes"]
    )
    # 6 — sempre os quatro status, mesmo os zerados
    assert [l["status"] for l in d["pedidos_por_status"]] == [
        "CRIADO",
        "PAGO",
        "ENVIADO",
        "CANCELADO",
    ]
    # 7
    assert d["conciliacao"]["divergentes"] == 0
    assert d["conciliacao"]["conciliados"] == d["conciliacao"]["pedidos"] == 1


def test_dashboard_e_painel_contam_a_mesma_coisa(
    navegador, entrar, gestor, cliente, catalogo
):
    """A tela e a API leem a mesma funcao, logo nao podem divergir."""
    from app import indicadores

    finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 3, "moagem": "FINA"}],
    )

    entrar(EMAIL_GESTOR)
    via_api = navegador.get("/api/dashboard?dias=30").get_json()
    direto = indicadores(dias=30)

    assert Decimal(via_api["faturamento"]["valor"]) == Decimal(
        direto["faturamento"]
    )
    assert via_api["faturamento"]["pedidos"] == direto["pedidos"]
    assert via_api["conciliacao"]["divergentes"] == direto["conciliacao"][
        "divergentes"
    ]


# ---------------------------------------------------------------------
# 5. PATCH de status
# ---------------------------------------------------------------------

def test_patch_sem_token_csrf_devolve_400(
    navegador, entrar, gestor, cliente, catalogo
):
    """A protecao CSRF vale para a API igual aos formularios."""
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status", json={"status": "PAGO"}
    )

    assert resposta.status_code == 400
    assert "X-CSRF-Token" in resposta.get_json()["erro"]

    db.session.refresh(pedido)
    assert pedido.status == "CRIADO", "nada pode ter mudado"


def test_patch_com_token_errado_devolve_400(
    navegador, entrar, gestor, cliente, catalogo
):
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status",
        json={"status": "PAGO"},
        headers={"X-CSRF-Token": "token-chutado"},
    )

    assert resposta.status_code == 400

    db.session.refresh(pedido)
    assert pedido.status == "CRIADO"


def test_patch_com_token_no_cabecalho_funciona(
    navegador, entrar, token_da_sessao, gestor, cliente, catalogo
):
    """O caminho feliz: X-CSRF-Token no cabecalho, e o antes/depois no corpo."""
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status",
        json={"status": "PAGO"},
        headers={"X-CSRF-Token": token_da_sessao()},
    )

    assert resposta.status_code == 200
    assert resposta.get_json() == {
        "pedido_id": pedido.id,
        "status_anterior": "CRIADO",
        "status_atual": "PAGO",
        "unidades_devolvidas_ao_estoque": 0,
    }

    db.session.refresh(pedido)
    assert pedido.status == "PAGO"


def test_patch_cancelamento_devolve_estoque(
    navegador, entrar, token_da_sessao, gestor, cliente, catalogo
):
    produto = catalogo["farto"]
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": produto.id, "quantidade": 3, "moagem": "MEDIA"}],
    )

    db.session.refresh(produto)
    assert produto.estoque == 7

    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status",
        json={"status": "CANCELADO"},
        headers={"X-CSRF-Token": token_da_sessao()},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["unidades_devolvidas_ao_estoque"] == 3

    db.session.refresh(produto)
    assert produto.estoque == 10


def test_patch_transicao_invalida_devolve_409(
    navegador, entrar, token_da_sessao, gestor, cliente, catalogo
):
    """409 e nao 400: a requisicao esta certa, o ESTADO e que impede."""
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status",
        json={"status": "ENVIADO"},
        headers={"X-CSRF-Token": token_da_sessao()},
    )

    assert resposta.status_code == 409
    assert "CRIADO" in resposta.get_json()["erro"]

    db.session.refresh(pedido)
    assert pedido.status == "CRIADO"


def test_patch_em_pedido_inexistente_devolve_404(
    navegador, entrar, token_da_sessao, gestor, catalogo
):
    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        "/api/pedidos/999999/status",
        json={"status": "PAGO"},
        headers={"X-CSRF-Token": token_da_sessao()},
    )

    assert resposta.status_code == 404
    assert "erro" in resposta.get_json()


def test_patch_sem_campo_status_devolve_400(
    navegador, entrar, token_da_sessao, gestor, cliente, catalogo
):
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_GESTOR)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status",
        json={},
        headers={"X-CSRF-Token": token_da_sessao()},
    )

    assert resposta.status_code == 400
    # A mensagem lista os valores aceitos, em vez de só recusar.
    assert "CRIADO" in resposta.get_json()["erro"]


def test_patch_por_cliente_comum_devolve_403(
    navegador, entrar, token_da_sessao, cliente, catalogo
):
    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 1, "moagem": "GRAO"}],
    )

    entrar(EMAIL_CLIENTE)
    resposta = navegador.patch(
        f"/api/pedidos/{pedido.id}/status",
        json={"status": "PAGO"},
        headers={"X-CSRF-Token": token_da_sessao()},
    )

    assert resposta.status_code == 403

    db.session.refresh(pedido)
    assert pedido.status == "CRIADO"


# ---------------------------------------------------------------------
# 6. /api/resumo — publico, e por isso o conteudo e vigiado
# ---------------------------------------------------------------------

def test_resumo_e_publico(navegador, catalogo):
    resposta = navegador.get("/api/resumo")

    assert resposta.status_code == 200
    assert resposta.get_json()["cafes_no_catalogo"] == 2


def test_resumo_nao_vaza_faturamento_nem_cliente(
    navegador, cliente, outro_cliente, catalogo
):
    """A rota e aberta: o que ela devolve foi escolhido com cuidado.

    Participacao em porcentagem existe justamente para a pagina do
    Projeto Final desenhar o grafico de regioes sem vazar valor absoluto
    — 100% de um numero desconhecido nao revela o numero.
    """
    finalizar_pedido(
        cliente.id,
        [{"produto_id": catalogo["farto"].id, "quantidade": 2, "moagem": "GRAO"}],
    )

    resposta = navegador.get("/api/resumo")
    dados = resposta.get_json()
    bruto = resposta.get_data(as_text=True).lower()

    # O que sai.
    assert dados["pedidos_no_periodo"] == 1
    assert dados["cafes_vendidos"] == 2
    assert dados["participacao_por_regiao"] == [
        {"regiao": "Bahia", "percentual": 100.0}
    ]
    assert dados["conciliacao"] == {"pedidos": 1, "conciliados": 1}

    # O que NAO pode sair.
    assert "faturamento" not in dados
    assert "ticket_medio" not in dados
    for proibido in ["ana@exemplo.com", "ana teste", "bruno", "178", "89.00"]:
        assert proibido not in bruto, f"o resumo publico vazou {proibido!r}"


def test_resumo_aceita_o_parametro_dias(navegador, catalogo):
    assert navegador.get("/api/resumo?dias=7").get_json()["periodo_dias"] == 7
    # Valor absurdo cai no teto, nao derruba a consulta.
    assert (
        navegador.get("/api/resumo?dias=99999999").get_json()["periodo_dias"]
        == 365
    )
    assert (
        navegador.get("/api/resumo?dias=abacaxi").get_json()["periodo_dias"]
        == 30
    )


# ---------------------------------------------------------------------
# 7. O contrato de erro, uniforme
# ---------------------------------------------------------------------

def test_todo_erro_da_api_tem_a_mesma_forma(navegador, catalogo):
    """Sempre `{"erro": "..."}`, sempre JSON, sempre em português."""
    for rota in ["/api/produtos/999999", "/api/pedidos", "/api/dashboard"]:
        resposta = navegador.get(rota)

        assert resposta.status_code >= 400
        assert resposta.is_json, f"{rota} devolveu algo que nao e JSON"

        corpo = resposta.get_json()
        assert list(corpo) == ["erro"], f"{rota} fugiu do formato"
        assert isinstance(corpo["erro"], str) and corpo["erro"]
