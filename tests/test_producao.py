"""Testes do modo de producao — Projeto Final.

A regra que estes testes travam: em producao, `SECRET_KEY` e
`DATABASE_URL` NAO tem valor padrao.

Por que isso importa mais do que parece. A SECRET_KEY assina o cookie de
sessao. Se ela cair no valor padrao do codigo-fonte, que esta num
repositorio publico no GitHub, qualquer pessoa consegue FORJAR um cookie
de sessao valido e entrar como qualquer cliente — inclusive como o
gestor, bastando acertar o `cliente_id`. Nao e vazamento de dado: e
autenticacao quebrada por completo.

A DATABASE_URL padrao aponta para `postgres:postgres@localhost`, que em
producao ou nao existe (e a loja cai com erro feio) ou existe e e o banco
errado.

O comportamento correto, e o que se testa aqui: a aplicacao sobe, nao
atende pedido nenhum, responde 503 e diz qual variavel falta — o NOME
dela, nunca o valor.
"""

import pytest

from app import (
    criar_app,
    em_producao,
    mascarar_email,
    mascarar_url,
    segredos_ausentes,
)


# ---------------------------------------------------------------------
# 1. Deteccao do ambiente
# ---------------------------------------------------------------------

def test_sem_variavel_nenhuma_nao_e_producao(monkeypatch):
    monkeypatch.delenv("AMBIENTE", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    assert em_producao() is False


def test_ambiente_producao_marca_producao(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setenv("AMBIENTE", "producao")

    assert em_producao() is True


def test_railway_environment_marca_producao(monkeypatch):
    """O Railway injeta esta variavel sozinho em todo servico.

    E a rede de seguranca: o modo de producao vale mesmo que alguem
    esqueca de criar o AMBIENTE a mao.
    """
    monkeypatch.delenv("AMBIENTE", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")

    assert em_producao() is True


def test_ambiente_com_outro_valor_nao_e_producao(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setenv("AMBIENTE", "homologacao")

    assert em_producao() is False


# ---------------------------------------------------------------------
# 2. Segredos ausentes
# ---------------------------------------------------------------------

def test_segredos_ausentes_lista_o_que_falta(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@h:5432/b")

    assert segredos_ausentes() == ["SECRET_KEY"]

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert segredos_ausentes() == ["DATABASE_URL", "SECRET_KEY"]


def test_variavel_vazia_conta_como_ausente(monkeypatch):
    """`SECRET_KEY=` no painel do provedor e um erro comum, e silencioso.

    `os.getenv` devolve string vazia, que nao e None — sem o `.strip()` a
    aplicacao subiria com chave vazia e a assinaria com isso.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@h:5432/b")
    monkeypatch.setenv("SECRET_KEY", "   ")

    assert segredos_ausentes() == ["SECRET_KEY"]


# ---------------------------------------------------------------------
# 3. A aplicacao degradada — 503
# ---------------------------------------------------------------------

@pytest.fixture
def producao_sem_segredo(monkeypatch):
    """Producao com DATABASE_URL, mas sem SECRET_KEY."""
    monkeypatch.setenv("AMBIENTE", "producao")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://torra_app:senha-secreta@banco:5432/loja"
    )
    monkeypatch.delenv("SECRET_KEY", raising=False)

    # Sem config_teste: e exatamente assim que o gunicorn importa a app
    # em producao.
    return criar_app().test_client()


def test_producao_sem_secret_key_responde_503(producao_sem_segredo):
    resposta = producao_sem_segredo.get("/")

    assert resposta.status_code == 503


def test_a_pagina_503_nomeia_a_variavel_que_falta(producao_sem_segredo):
    pagina = producao_sem_segredo.get("/").get_data(as_text=True)

    assert "SECRET_KEY" in pagina
    assert "variável de ambiente" in pagina


def test_a_pagina_503_nao_vaza_valor_nenhum(producao_sem_segredo):
    """Diz o NOME do que falta. Nunca o valor de nada."""
    pagina = producao_sem_segredo.get("/").get_data(as_text=True)

    for proibido in [
        "senha-secreta",       # a senha do banco
        "torra_app:senha",     # usuario:senha da URL
        "postgresql://",       # a URL inteira
        "banco:5432",          # host e porta
    ]:
        assert proibido not in pagina, f"a pagina 503 vazou {proibido!r}"


def test_toda_rota_responde_503(producao_sem_segredo):
    """Nenhuma rota escapa — nem as que nao existiriam na app normal.

    O catch-all e proposital: sem ele, `/carrinho` daria 404 e quem
    estivesse comprando acharia que o problema era o endereco.
    """
    for caminho in ["/", "/carrinho", "/checkout", "/painel", "/rota/inventada"]:
        assert producao_sem_segredo.get(caminho).status_code == 503


def test_503_em_json_para_cliente_de_api(producao_sem_segredo):
    """Navegador recebe pagina; cliente de API recebe JSON."""
    for rota in ["/health", "/api/produtos", "/api/resumo"]:
        resposta = producao_sem_segredo.get(rota)

        assert resposta.status_code == 503
        assert resposta.is_json, f"{rota} deveria responder JSON"

        corpo = resposta.get_json()
        assert corpo["variaveis_ausentes"] == ["SECRET_KEY"]
        # O nome da variavel, nunca o valor.
        assert "senha-secreta" not in resposta.get_data(as_text=True)


def test_503_nao_e_cacheado(producao_sem_segredo):
    """Corrigida a variavel, ninguem pode continuar vendo a pagina de erro."""
    resposta = producao_sem_segredo.get("/")

    assert resposta.headers["Cache-Control"] == "no-store"
    assert resposta.headers["Retry-After"] == "120"


def test_escrita_tambem_e_barrada(producao_sem_segredo):
    """POST sem configuracao nao pode cair em 405.

    Sem sessao assinavel nao ha token CSRF possivel, e um 405 faria o
    cliente achar que o metodo e que estava errado.
    """
    resposta = producao_sem_segredo.post("/checkout", data={})

    assert resposta.status_code == 503


def test_producao_com_os_segredos_sobe_normal(monkeypatch):
    """O outro lado: com as variaveis no lugar, a app e a app de sempre."""
    monkeypatch.setenv("AMBIENTE", "producao")
    monkeypatch.setenv("SECRET_KEY", "uma-chave-longa-de-producao")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://torra_app:senha@banco:5432/loja"
    )

    app = criar_app()

    assert app.config["CONFIGURACAO_INCOMPLETA"] == ()
    assert app.config["SECRET_KEY"] == "uma-chave-longa-de-producao"

    # O catalogo existe de novo — nao e a app degradada de uma rota so.
    assert "catalogo" in app.view_functions
    assert "api.health" in app.view_functions


def test_fora_de_producao_o_padrao_de_desenvolvimento_vale(monkeypatch):
    """O `flask run` da maquina local nao pode exigir configuracao."""
    monkeypatch.delenv("AMBIENTE", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    app = criar_app()

    assert app.config["CONFIGURACAO_INCOMPLETA"] == ()
    assert app.config["SECRET_KEY"] == "dev-inseguro-trocar"


def test_cookie_e_secure_em_producao_mesmo_sem_flask_env(monkeypatch):
    """O Railway define RAILWAY_ENVIRONMENT, nao FLASK_ENV.

    Amarrar o cookie Secure so ao FLASK_ENV deixaria a sessao viajando em
    claro se alguem apagasse aquela variavel no painel do provedor.
    """
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("SECRET_KEY", "chave")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@h:5432/b")

    assert criar_app().config["SESSION_COOKIE_SECURE"] is True


# ---------------------------------------------------------------------
# 4. Mascaramento — "nenhuma credencial em log"
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "url, esperado",
    [
        (
            "postgresql://torra_app:segredo123@localhost:5432/torra_terra",
            "postgresql://torra_app:***@localhost:5432/torra_terra",
        ),
        (
            "postgresql+psycopg://torra_app:p@ss@host:5432/loja?sslmode=require",
            "postgresql+psycopg://torra_app:***@host:5432/loja",
        ),
        (
            "postgresql://host:5432/loja",
            "postgresql://host:5432/loja",
        ),
    ],
)
def test_mascarar_url_remove_a_senha(url, esperado):
    """A query sai inteira: `?password=` tambem e credencial."""
    assert mascarar_url(url) == esperado


def test_mascarar_url_nunca_devolve_a_senha(monkeypatch):
    """Teste de propriedade, nao de formato.

    O que importa nao e o formato exato da saida — e a garantia de que a
    senha nao esta nela, em nenhuma forma de entrada.
    """
    entradas = [
        "postgresql://u:SENHA_SECRETA@h:5432/b",
        "postgresql://u:SENHA_SECRETA@h/b?opt=SENHA_SECRETA",
        "postgres://u:SENHA_SECRETA@h:5432/b",
        "",
        None,
        "nao-e-url-nenhuma",
    ]

    for entrada in entradas:
        assert "SENHA_SECRETA" not in mascarar_url(entrada)


@pytest.mark.parametrize(
    "email, esperado",
    [
        ("ana.silva@exemplo.com", "an***@exemplo.com"),
        ("x@exemplo.com", "x***@exemplo.com"),
        ("sem-arroba", "se***"),
        ("", "(vazio)"),
        (None, "(vazio)"),
    ],
)
def test_mascarar_email(email, esperado):
    """Permite investigar forca bruta sem virar lista de e-mails no log."""
    assert mascarar_email(email) == esperado


# ---------------------------------------------------------------------
# 5. O log do erro 500
#
# O sexto evento que o briefing pede. Ele tem duas armadilhas do Flask, e
# as duas custam exatamente a informacao que faz o log existir.
# ---------------------------------------------------------------------

def test_erro_500_registra_a_excecao_de_verdade(monkeypatch, caplog):
    """O log precisa nomear a causa, nao o embrulho.

    O que chega ao handler de erro do Flask e um InternalServerError, que
    apenas EMBRULHA a falha original. Registrar o embrulho produziria um
    log que diz "500 Internal Server Error" — tecnicamente verdadeiro e
    inteiramente inutil para descobrir o que quebrou.
    """
    import logging

    monkeypatch.delenv("AMBIENTE", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    app = criar_app(
        {
            "SECRET_KEY": "chave",
            "TESTING": False,
            # Sem isto o Flask relanca a excecao em vez de chamar o
            # handler, e o teste nao exercitaria o caminho real.
            "PROPAGATE_EXCEPTIONS": False,
        }
    )

    @app.route("/rota-que-estoura")
    def estoura():
        raise RuntimeError("falha proposital")

    with caplog.at_level(logging.ERROR):
        resposta = app.test_client().get("/rota-que-estoura")

    assert resposta.status_code == 500

    registros = [r for r in caplog.records if "evento=erro_500" in r.getMessage()]
    assert registros, "o erro 500 precisa ser registrado"

    linha = registros[0]
    assert "rota=/rota-que-estoura" in linha.getMessage()
    assert "causa=RuntimeError" in linha.getMessage()

    # E o traceback precisa estar junto, e ser o da falha original.
    assert linha.exc_info is not None
    assert linha.exc_info[0] is RuntimeError


def test_pagina_de_erro_500_nao_mostra_traceback(monkeypatch):
    """Stack trace em pagina publica entrega estrutura de diretorio,
    versao de biblioteca e, as vezes, trecho de query."""
    monkeypatch.delenv("AMBIENTE", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    app = criar_app(
        {"SECRET_KEY": "chave", "TESTING": False, "PROPAGATE_EXCEPTIONS": False}
    )

    @app.route("/rota-que-estoura")
    def estoura():
        raise RuntimeError("segredo-no-traceback")

    pagina = app.test_client().get("/rota-que-estoura").get_data(as_text=True)

    assert "segredo-no-traceback" not in pagina
    assert "Traceback" not in pagina
    assert "RuntimeError" not in pagina
    # E diz ao cliente o que importa: nada foi gravado pela metade.
    assert "nada foi cobrado e nada foi gravado pela metade" in pagina
