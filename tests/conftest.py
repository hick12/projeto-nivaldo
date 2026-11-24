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
import re
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

# Credenciais dos testes. Sao fixtures, nao segredo: o banco de teste e
# derrubado e recriado a cada execucao.
SENHA_PADRAO = "senha-de-teste-123"
EMAIL_GESTOR = "gestor@exemplo.com"
EMAIL_CLIENTE = "ana@exemplo.com"
EMAIL_OUTRO = "bruno@exemplo.com"

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


# =====================================================================
# Fixtures do Projeto Final
# =====================================================================

@pytest.fixture
def navegador(aplicacao, contexto):
    """Cliente HTTP de teste, com sessao e cookies proprios."""
    return aplicacao.test_client()


def token_csrf_de(html: str) -> str:
    """Extrai o token do campo escondido de um formulario renderizado."""
    achado = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert achado, "o formulario deveria trazer o campo _csrf"
    return achado.group(1)


@pytest.fixture
def entrar(navegador):
    """Devolve uma funcao que faz login de verdade, pelo formulario.

    Passa pelo fluxo completo — GET /login para pegar o token, POST com o
    token — em vez de escrever `cliente_id` direto na sessao. Login
    fabricado na sessao testaria a autorizacao e deixaria a autenticacao
    de fora, que e metade do que se quer provar aqui.
    """

    def _entrar(email: str, senha: str = SENHA_PADRAO):
        pagina = navegador.get("/login").get_data(as_text=True)
        resposta = navegador.post(
            "/login",
            data={
                "email": email,
                "senha": senha,
                "_csrf": token_csrf_de(pagina),
            },
        )
        assert resposta.status_code == 302, (
            f"login de {email} falhou: {resposta.status_code}"
        )
        return resposta

    return _entrar


@pytest.fixture
def token_da_sessao(navegador):
    """O token CSRF da sessao atual, para o cabecalho X-CSRF-Token."""

    def _token() -> str:
        # Garante que a sessao existe antes de ler o token.
        navegador.get("/")
        with navegador.session_transaction() as sessao:
            return sessao.get("_csrf", "")

    return _token


@pytest.fixture
def gestor(aplicacao, contexto) -> Cliente:
    """Um cliente cujo e-mail esta em ADMIN_EMAILS.

    Mexe na config da app, que e de escopo de sessao, e por isso restaura
    o valor anterior no teardown — senao o primeiro teste que pedisse
    esta fixture transformaria o gestor em permanente para todos os
    outros, e o teste de 403 passaria a falhar por contagio.
    """
    anterior = aplicacao.config.get("ADMIN_EMAILS")
    aplicacao.config["ADMIN_EMAILS"] = frozenset({EMAIL_GESTOR})

    registro = Cliente(
        nome="Gestor Teste",
        email=EMAIL_GESTOR,
        senha_hash=generate_password_hash(SENHA_PADRAO),
    )
    db.session.add(registro)
    db.session.commit()

    yield registro

    aplicacao.config["ADMIN_EMAILS"] = anterior


@pytest.fixture
def outro_cliente(contexto) -> Cliente:
    """Um segundo cliente, para provar o isolamento entre contas."""
    registro = Cliente(
        nome="Bruno Teste",
        email=EMAIL_OUTRO,
        senha_hash=generate_password_hash(SENHA_PADRAO),
    )
    db.session.add(registro)
    db.session.commit()
    return registro
