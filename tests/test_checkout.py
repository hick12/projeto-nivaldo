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
