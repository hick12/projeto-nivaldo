"""Testes da transacao de checkout e das constraints do banco.

Cobrem os cinco casos exigidos no briefing:

1. compra normal          -> pedido gravado, itens gravados, estoque reduzido
2. estoque insuficiente   -> rollback, nada gravado, estoque intacto
3. produto inexistente    -> pedido nao finalizado
4. constraint do banco    -> preco negativo levanta erro
5. senha                  -> nunca gravada em texto puro

Mais dois que decorrem do modelo: a moagem separando linhas do mesmo cafe e
o congelamento do preco_unitario.
"""

from decimal import Decimal

import pytest
from sqlalchemy.exc import DataError, IntegrityError
from werkzeug.security import check_password_hash

from app import (
    Cliente,
    EstoqueInsuficiente,
    ItemPedido,
    Pedido,
    Produto,
    ProdutoInexistente,
    db,
    finalizar_pedido,
)


# ---------------------------------------------------------------------
# 1. Compra normal
# ---------------------------------------------------------------------

def test_compra_normal_grava_pedido_itens_e_baixa_estoque(cliente, catalogo):
    produto = catalogo["farto"]
    estoque_antes = produto.estoque

    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": produto.id, "quantidade": 3, "moagem": "FINA"}],
    )

    assert pedido.id is not None
    assert pedido.status == "CRIADO"
    assert pedido.total == Decimal("267.00")  # 3 x 89,00

    itens = db.session.scalars(
        db.select(ItemPedido).where(ItemPedido.pedido_id == pedido.id)
    ).all()
    assert len(itens) == 1
    assert itens[0].quantidade == 3
    assert itens[0].moagem == "FINA"

    db.session.refresh(produto)
    assert produto.estoque == estoque_antes - 3


# ---------------------------------------------------------------------
# 2. Estoque insuficiente
# ---------------------------------------------------------------------

def test_estoque_insuficiente_faz_rollback_completo(cliente, catalogo):
    escasso = catalogo["escasso"]   # estoque 1
    farto = catalogo["farto"]       # estoque 10

    # O item que falha vem por ultimo de proposito: o primeiro ja teria
    # passado na validacao, e e isso que prova que o rollback desfaz a
    # transacao inteira, nao apenas o item problematico.
    with pytest.raises(EstoqueInsuficiente) as erro:
        finalizar_pedido(
            cliente.id,
            [
                {"produto_id": farto.id, "quantidade": 2, "moagem": "GRAO"},
                {"produto_id": escasso.id, "quantidade": 5, "moagem": "MEDIA"},
            ],
        )

    # A mensagem precisa dizer QUAL cafe faltou — criterio de aceite do RF05.
    assert escasso.nome in str(erro.value)
    assert erro.value.disponivel == 1
    assert erro.value.pedido == 5

    # Nada foi gravado.
    assert db.session.scalar(db.select(db.func.count(Pedido.id))) == 0
    assert db.session.scalar(db.select(db.func.count(ItemPedido.id))) == 0

    # E o estoque dos dois cafes ficou exatamente como estava.
    db.session.refresh(farto)
    db.session.refresh(escasso)
    assert farto.estoque == 10
    assert escasso.estoque == 1


# ---------------------------------------------------------------------
# 3. Produto inexistente
# ---------------------------------------------------------------------

def test_produto_inexistente_nao_finaliza_o_pedido(cliente, catalogo):
    with pytest.raises(ProdutoInexistente):
        finalizar_pedido(
            cliente.id,
            [
                {
                    "produto_id": catalogo["farto"].id,
                    "quantidade": 1,
                    "moagem": "GRAO",
                },
                {"produto_id": 999999, "quantidade": 1, "moagem": "FINA"},
            ],
        )

    assert db.session.scalar(db.select(db.func.count(Pedido.id))) == 0
    assert db.session.scalar(db.select(db.func.count(ItemPedido.id))) == 0

    db.session.refresh(catalogo["farto"])
    assert catalogo["farto"].estoque == 10


# ---------------------------------------------------------------------
# 4. Constraints do banco
# ---------------------------------------------------------------------

def test_preco_negativo_e_recusado_pelo_banco(catalogo):
    """A regra vive no banco, nao so na aplicacao (RNF01)."""
    invalido = Produto(
        nome="Cafe de preco impossivel",
        preco=Decimal("-10.00"),
        estoque=5,
        categoria_id=catalogo["farto"].categoria_id,
        torra="MEDIA",
        pontuacao_sca=Decimal("85.00"),
        peso_g=250,
    )
    db.session.add(invalido)

    with pytest.raises(IntegrityError) as erro:
        db.session.commit()

    assert "ck_produtos_preco" in str(erro.value)
    db.session.rollback()


def test_estoque_negativo_e_recusado_pelo_banco(catalogo):
    """Ultima linha de defesa contra venda a descoberto."""
    produto = catalogo["escasso"]
    produto.estoque = -1

    with pytest.raises(IntegrityError) as erro:
        db.session.commit()

    assert "ck_produtos_estoque" in str(erro.value)
    db.session.rollback()


def test_pontuacao_sca_fora_da_faixa_e_recusada(catalogo):
    """Cafe especial pontua 80+. Regra de negocio, nao de formulario."""
    invalido = Produto(
        nome="Cafe comum",
        preco=Decimal("20.00"),
        estoque=5,
        categoria_id=catalogo["farto"].categoria_id,
        torra="MEDIA",
        pontuacao_sca=Decimal("72.00"),
        peso_g=250,
    )
    db.session.add(invalido)

    with pytest.raises(IntegrityError) as erro:
        db.session.commit()

    assert "ck_produtos_sca" in str(erro.value)
    db.session.rollback()


def test_moagem_invalida_e_recusada_pelo_banco(cliente, catalogo):
    """A moagem so aceita GRAO, MEDIA ou FINA.

    O valor de teste precisa CABER em VARCHAR(6). Com uma palavra maior o
    banco recusa por tamanho (StringDataRightTruncation) antes de avaliar o
    CHECK — o dado seria barrado do mesmo jeito, mas por outra regra, e o
    teste nao provaria o que se propoe.
    """
    pedido = Pedido(cliente_id=cliente.id, status="CRIADO", total=Decimal("0"))
    db.session.add(pedido)
    db.session.flush()

    db.session.add(
        ItemPedido(
            pedido_id=pedido.id,
            produto_id=catalogo["farto"].id,
            quantidade=1,
            preco_unitario=Decimal("89.00"),
            moagem="MOIDA",   # cabe em VARCHAR(6), mas nao esta no dominio
        )
    )

    with pytest.raises(IntegrityError) as erro:
        db.session.commit()

    assert "ck_itens_moagem" in str(erro.value)
    db.session.rollback()


def test_moagem_longa_demais_e_recusada_pelo_tamanho(cliente, catalogo):
    """A outra defesa da mesma coluna: VARCHAR(6) barra por tamanho."""
    pedido = Pedido(cliente_id=cliente.id, status="CRIADO", total=Decimal("0"))
    db.session.add(pedido)
    db.session.flush()

    db.session.add(
        ItemPedido(
            pedido_id=pedido.id,
            produto_id=catalogo["farto"].id,
            quantidade=1,
            preco_unitario=Decimal("89.00"),
            moagem="EXTRAFINA",
        )
    )

    with pytest.raises(DataError):
        db.session.commit()

    db.session.rollback()


# ---------------------------------------------------------------------
# 5. Senha
# ---------------------------------------------------------------------

def test_senha_nunca_e_gravada_em_texto_puro(cliente):
    gravado = db.session.scalar(
        db.select(Cliente).where(Cliente.email == "ana@exemplo.com")
    )

    assert gravado.senha_hash != "senha-de-teste-123"
    assert "senha-de-teste-123" not in gravado.senha_hash
    assert gravado.senha_hash.startswith("scrypt:")
    assert check_password_hash(gravado.senha_hash, "senha-de-teste-123")


# ---------------------------------------------------------------------
# Decorrencias do modelo
# ---------------------------------------------------------------------

def test_mesmo_cafe_em_moagens_diferentes_vira_duas_linhas(cliente, catalogo):
    """E o que faz itens_pedido ser entidade e nao tabela de ligacao."""
    produto = catalogo["farto"]

    pedido = finalizar_pedido(
        cliente.id,
        [
            {"produto_id": produto.id, "quantidade": 2, "moagem": "GRAO"},
            {"produto_id": produto.id, "quantidade": 1, "moagem": "FINA"},
        ],
    )

    itens = db.session.scalars(
        db.select(ItemPedido).where(ItemPedido.pedido_id == pedido.id)
    ).all()

    assert len(itens) == 2
    assert {item.moagem for item in itens} == {"GRAO", "FINA"}

    db.session.refresh(produto)
    assert produto.estoque == 10 - 3


def test_preco_unitario_fica_congelado_apos_reajuste(cliente, catalogo):
    """O pedido antigo mantem o valor da epoca."""
    produto = catalogo["farto"]

    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": produto.id, "quantidade": 1, "moagem": "MEDIA"}],
    )

    # O cafe sobe de preco depois da compra.
    produto.preco = Decimal("129.00")
    db.session.commit()

    item = db.session.scalar(
        db.select(ItemPedido).where(ItemPedido.pedido_id == pedido.id)
    )

    assert item.preco_unitario == Decimal("89.00")
    assert db.session.get(Produto, produto.id).preco == Decimal("129.00")

    db.session.refresh(pedido)
    assert pedido.total == Decimal("89.00")


def test_carrinho_vazio_nao_gera_pedido(cliente):
    from app import CarrinhoVazio

    with pytest.raises(CarrinhoVazio):
        finalizar_pedido(cliente.id, [])

    assert db.session.scalar(db.select(db.func.count(Pedido.id))) == 0


# ---------------------------------------------------------------------
# Regressao — os dois furos que o SELECT ... FOR UPDATE nao cobria
#
# Os testes abaixo existem porque a suite inteira passava com os dois
# defeitos presentes. Nenhum teste anterior exercitava a FRONTEIRA: o
# caso de estoque insuficiente usava um numero folgado acima do saldo, e
# o caso de duas moagens usava estoque de sobra. Bug de concorrencia e de
# limite mora exatamente na fronteira.
# ---------------------------------------------------------------------

def _conexao_crua():
    """Uma segunda conexao ao banco de teste, fora da sessao do ORM.

    Serve para simular o que outra pessoa comprando ao mesmo tempo faz:
    commitar uma mudanca que a nossa transacao ainda nao viu.
    """
    import psycopg
    from flask import current_app

    url = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def test_for_update_enxerga_o_estoque_de_outra_compra_ja_commitada(
    aplicacao, cliente, catalogo
):
    """O furo que invalidava a tese do trabalho inteiro.

    A rota /checkout chama `carrinho_detalhado()` antes de
    `finalizar_pedido()`, e aquilo ja carrega o Produto na sessao. Por
    padrao, o ORM devolve o objeto do identity map e DESCARTA a linha que
    o SELECT ... FOR UPDATE acabou de ler — entao o lock funcionava no
    banco e nao funcionava na aplicacao: a validacao decidia com o saldo
    anterior ao lock.

    O efeito era a venda em duplicidade que esta funcao existe para
    impedir, e ela so acontecia pelo navegador — o caminho que o cliente
    usa.
    """
    produto = catalogo["escasso"]   # estoque 1
    produto_id = produto.id

    # 1. O que a rota faz antes do checkout: le o produto para montar a
    #    tela do carrinho. A partir daqui ele esta na sessao.
    carregado = db.session.get(Produto, produto_id)
    assert carregado.estoque == 1

    # 2. Outra pessoa leva a ultima unidade e commita, noutra conexao.
    with _conexao_crua() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                "UPDATE produtos SET estoque = 0 WHERE id = %s", (produto_id,)
            )
        conexao.commit()

    # 3. Agora o checkout. Ele TEM que enxergar o saldo novo.
    with pytest.raises(EstoqueInsuficiente) as erro:
        finalizar_pedido(
            cliente.id,
            [{"produto_id": produto_id, "quantidade": 1, "moagem": "GRAO"}],
        )

    assert erro.value.disponivel == 0, (
        "a validacao decidiu com o estoque anterior ao lock"
    )

    # E nada foi gravado.
    assert db.session.scalar(db.select(db.func.count(Pedido.id))) == 0

    with _conexao_crua() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                "SELECT estoque FROM produtos WHERE id = %s", (produto_id,)
            )
            assert cursor.fetchone()[0] == 0, "o estoque nao pode ter mudado"


def test_mesmo_cafe_em_duas_moagens_respeita_o_estoque_somado(
    cliente, catalogo
):
    """O estoque e do CAFE, nao da moagem.

    Com estoque 1, uma linha em GRAO de 1 unidade e outra em FINA de 1
    passavam as duas na validacao, porque cada uma era comparada
    isoladamente com o saldo cheio. A fase 2 gravava estoque = -1, o
    CHECK do banco barrava com IntegrityError — que nao e ErroCheckout —
    e o cliente recebia uma pagina 500 em vez da mensagem dizendo qual
    cafe faltou.
    """
    escasso = catalogo["escasso"]   # estoque 1

    with pytest.raises(EstoqueInsuficiente) as erro:
        finalizar_pedido(
            cliente.id,
            [
                {"produto_id": escasso.id, "quantidade": 1, "moagem": "GRAO"},
                {"produto_id": escasso.id, "quantidade": 1, "moagem": "FINA"},
            ],
        )

    # A mensagem fala da soma, nao de uma das linhas.
    assert erro.value.disponivel == 1
    assert erro.value.pedido == 2
    assert escasso.nome in str(erro.value)

    assert db.session.scalar(db.select(db.func.count(Pedido.id))) == 0
    db.session.refresh(escasso)
    assert escasso.estoque == 1


def test_duas_moagens_do_mesmo_cafe_cabendo_no_estoque_passa(
    cliente, catalogo
):
    """O outro lado: a consolidacao nao pode recusar o que cabe."""
    farto = catalogo["farto"]   # estoque 10

    pedido = finalizar_pedido(
        cliente.id,
        [
            {"produto_id": farto.id, "quantidade": 6, "moagem": "GRAO"},
            {"produto_id": farto.id, "quantidade": 4, "moagem": "FINA"},
        ],
    )

    itens = db.session.scalars(
        db.select(ItemPedido).where(ItemPedido.pedido_id == pedido.id)
    ).all()

    # Duas linhas, porque a moagem difere — e uma baixa so de 10.
    assert len(itens) == 2
    assert {i.moagem for i in itens} == {"GRAO", "FINA"}

    db.session.refresh(farto)
    assert farto.estoque == 0

    # E o total continua batendo com a soma dos itens.
    assert pedido.total == sum(
        (i.quantidade * i.preco_unitario for i in itens), Decimal("0")
    )


def test_estoque_exato_e_aceito(cliente, catalogo):
    """A fronteira pelo lado de cima: pedir exatamente o que ha."""
    escasso = catalogo["escasso"]   # estoque 1

    pedido = finalizar_pedido(
        cliente.id,
        [{"produto_id": escasso.id, "quantidade": 1, "moagem": "FINA"}],
    )

    assert pedido.id is not None
    db.session.refresh(escasso)
    assert escasso.estoque == 0
