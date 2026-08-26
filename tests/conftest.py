"""Fixtures dos testes.

Os testes rodam contra um PostgreSQL de verdade, num banco separado. Nao
usamos SQLite: `SELECT ... FOR UPDATE` e as constraints CHECK do schema sao
justamente o que precisa ser testado, e o SQLite trata os dois de forma
diferente. Testar contra outro banco daria confianca falsa.

Banco de teste — por padrao o mesmo da DATABASE_URL com o sufixo `_teste`,
ou o valor de TEST_DATABASE_URL. Crie-o uma vez com:

    createdb torra_terra_teste
"""

import os
from decimal import Decimal

import pytest
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from app import (
    Categoria,
    Cliente,
    Produto,
    _executar_script,
    criar_app,
    db,
    normalizar_url,
)

load_dotenv()


def url_de_teste() -> str:
    explicita = os.getenv("TEST_DATABASE_URL")
    if explicita:
        return explicita

    base = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/torra_terra",
    )
    # Sufixo no nome do banco, preservando host, porta e credenciais.
    base, _, query = base.partition("?")
    return f"{base}_teste" + (f"?{query}" if query else "")


@pytest.fixture(scope="session")
def aplicacao():
    app = criar_app(
        {
            "SQLALCHEMY_DATABASE_URI": normalizar_url(url_de_teste()),
            "TESTING": True,
            "SECRET_KEY": "chave-de-teste",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        # A estrutura vem do mesmo DDL da aplicacao. Se o schema.sql
        # quebrar, os testes quebram junto — que e o comportamento correto.
        _executar_script("schema.sql")
        yield app


@pytest.fixture
def contexto(aplicacao):
    """Cada teste comeca com o banco limpo."""
    with aplicacao.app_context():
        db.session.execute(
            db.text(
                "TRUNCATE TABLE itens_pedido, pedidos, produtos, categorias, "
                "clientes RESTART IDENTITY CASCADE"
            )
        )
        db.session.commit()
        yield
        db.session.rollback()


@pytest.fixture
def cliente(contexto) -> Cliente:
    registro = Cliente(
        nome="Ana Teste",
        email="ana@exemplo.com",
        senha_hash=generate_password_hash("senha-de-teste-123"),
    )
    db.session.add(registro)
    db.session.commit()
    return registro


@pytest.fixture
def catalogo(contexto) -> dict[str, Produto]:
    """Dois cafes: um com estoque folgado, outro com estoque 1."""
    categoria = Categoria(
        nome="Chapada Diamantina", regiao="Bahia", descricao="Altitude."
    )
    db.session.add(categoria)
    db.session.flush()

    farto = Produto(
        nome="Piata Altitude",
        preco=Decimal("89.00"),
        estoque=10,
        categoria_id=categoria.id,
        torra="CLARA",
        pontuacao_sca=Decimal("89.25"),
        peso_g=250,
    )
    escasso = Produto(
        nome="Chapada Geisha",
        preco=Decimal("148.00"),
        estoque=1,
        categoria_id=categoria.id,
        torra="CLARA",
        pontuacao_sca=Decimal("91.00"),
        peso_g=250,
    )

    db.session.add_all([farto, escasso])
    db.session.commit()

    return {"farto": farto, "escasso": escasso}
