"""Testes das protecoes que o OWASP ZAP apontou como ausentes.

Nao adianta corrigir e nao ter teste: sem isto, qualquer refatoracao futura
pode remover um cabecalho sem ninguem perceber ate o proximo scan.
"""

import re

import pytest


@pytest.fixture
def navegador(aplicacao, contexto):
    """Cliente HTTP de teste, com sessao propria."""
    return aplicacao.test_client()


def extrair_token(html: str) -> str:
    achado = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert achado, "o formulario deveria trazer o campo _csrf"
    return achado.group(1)


# ---------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------

def test_post_sem_token_csrf_e_recusado(navegador):
    """O cenario do ataque: POST vindo de fora, sem o token."""
    resposta = navegador.post(
        "/cadastro",
        data={"nome": "Invasor", "email": "x@y.com", "senha": "12345678"},
    )
    assert resposta.status_code == 400


def test_post_com_token_errado_e_recusado(navegador):
    navegador.get("/cadastro")   # cria a sessao e o token
    resposta = navegador.post(
        "/cadastro",
        data={
            "nome": "Invasor",
            "email": "x@y.com",
            "senha": "12345678",
            "_csrf": "token-chutado",
        },
    )
    assert resposta.status_code == 400


def test_post_com_token_valido_passa(navegador):
    pagina = navegador.get("/cadastro")
    token = extrair_token(pagina.get_data(as_text=True))

    resposta = navegador.post(
        "/cadastro",
        data={
            "nome": "Cliente Legitimo",
            "email": "legitimo@exemplo.com",
            "senha": "senha-de-teste-123",
            "_csrf": token,
        },
    )
    # 302 = cadastrou e redirecionou
    assert resposta.status_code == 302


def test_todo_formulario_tem_campo_csrf(navegador, catalogo):
    """Varre as paginas com formulario e cobra o campo escondido."""
    for caminho in ["/login", "/cadastro", f"/produto/{catalogo['farto'].id}"]:
        html = navegador.get(caminho).get_data(as_text=True)
        assert 'name="_csrf"' in html, f"{caminho} tem formulario sem token"


def test_get_nao_exige_token(navegador):
    """Leitura nunca deve ser barrada — GET nao altera estado."""
    assert navegador.get("/").status_code == 200


# ---------------------------------------------------------------------
# Cabecalhos de seguranca
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "cabecalho, esperado",
    [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ],
)
def test_cabecalhos_de_seguranca_presentes(navegador, cabecalho, esperado):
    assert navegador.get("/").headers.get(cabecalho) == esperado


def test_content_security_policy_bloqueia_script(navegador):
    csp = navegador.get("/").headers.get("Content-Security-Policy", "")

    # A loja nao usa JavaScript, entao da para proibir por completo.
    assert "script-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp

    # O Google Fonts precisa continuar liberado, senao a tipografia quebra.
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp


def test_hsts_so_aparece_sobre_https(navegador):
    sem_tls = navegador.get("/")
    assert "Strict-Transport-Security" not in sem_tls.headers

    # Simula o proxy do Railway, que encaminha o protocolo original.
    com_tls = navegador.get("/", headers={"X-Forwarded-Proto": "https"})
    assert "max-age=31536000" in com_tls.headers.get(
        "Strict-Transport-Security", ""
    )


# ---------------------------------------------------------------------
# Cookie de sessao
# ---------------------------------------------------------------------

def test_cookie_de_sessao_tem_httponly_e_samesite(navegador):
    pagina = navegador.get("/cadastro")
    token = extrair_token(pagina.get_data(as_text=True))
    resposta = navegador.post(
        "/cadastro",
        data={
            "nome": "Teste Cookie",
            "email": "cookie@exemplo.com",
            "senha": "senha-de-teste-123",
            "_csrf": token,
        },
    )

    cookie = next(
        (c for c in resposta.headers.getlist("Set-Cookie") if "session=" in c),
        "",
    )
    assert "HttpOnly" in cookie      # JavaScript nao le
    assert "SameSite=Lax" in cookie  # nao viaja em POST de outro site


def test_pagina_de_cliente_logado_nao_vai_para_cache(navegador):
    pagina = navegador.get("/cadastro")
    token = extrair_token(pagina.get_data(as_text=True))
    navegador.post(
        "/cadastro",
        data={
            "nome": "Teste Cache",
            "email": "cache@exemplo.com",
            "senha": "senha-de-teste-123",
            "_csrf": token,
        },
    )

    # Em computador compartilhado, o botao voltar nao pode mostrar o
    # historico de quem acabou de sair.
    assert navegador.get("/").headers.get("Cache-Control") == "no-store"
