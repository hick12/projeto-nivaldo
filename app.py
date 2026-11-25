"""
Torra & Terra — e-commerce de cafe especial.

FACAMP · Tratamento e Armazenamento da Informacao
Professor: Nivaldo T. Marcusso

Configuracao, modelos ORM, rotas e comandos de linha de comando.

Sobre os modelos abaixo: eles ESPELHAM o SQL/schema.sql, que e a fonte da
verdade da estrutura do banco. `db.create_all()` nunca e chamado neste
projeto — as tabelas nascem do DDL escrito a mao, porque e la que as
constraints ficam visiveis e auditaveis.
"""

import logging
import os
import random
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from functools import lru_cache, wraps
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    has_request_context,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint, func, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

RAIZ = Path(__file__).resolve().parent


# ---------------------------------------------------------------------
# Ambiente e segredos
#
# Os valores padrao abaixo existem para o `flask run` da maquina local
# subir sem configuracao nenhuma. Em producao eles sao proibidos: uma
# SECRET_KEY conhecida publicamente permite forjar o cookie de sessao e
# entrar como qualquer cliente, e a DATABASE_URL padrao aponta para um
# banco que nao e o nosso.
# ---------------------------------------------------------------------
VARIAVEIS_OBRIGATORIAS = ("DATABASE_URL", "SECRET_KEY")

PADRAO_DESENVOLVIMENTO = {
    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/torra_terra",
    "SECRET_KEY": "dev-inseguro-trocar",
}


def em_producao() -> bool:
    """Diz se este processo esta rodando em producao.

    Duas fontes, nesta ordem: a variavel `AMBIENTE=producao`, que podemos
    definir em qualquer provedor, e a `RAILWAY_ENVIRONMENT`, que o Railway
    injeta sozinho em todo servico. A segunda garante que o modo de
    producao vale mesmo que alguem esqueca de criar a primeira.
    """
    if os.getenv("AMBIENTE", "").strip().lower() == "producao":
        return True
    return bool(os.getenv("RAILWAY_ENVIRONMENT", "").strip())


def segredos_ausentes() -> list[str]:
    """Nomes das variaveis obrigatorias que nao estao definidas."""
    return [
        nome
        for nome in VARIAVEIS_OBRIGATORIAS
        if not os.getenv(nome, "").strip()
    ]


def mascarar_url(url: str | None) -> str:
    """Tira usuario, senha e query de uma URL de conexao.

    Toda linha de log que mencione o banco passa por aqui. A DATABASE_URL
    carrega a senha do `torra_app` em texto puro; um log de inicializacao
    ou um traceback com ela dentro vaza a credencial para quem tiver
    acesso aos logs do provedor — que nao sao o cofre de segredos.

    A query sai inteira de proposito: parametros como `?password=` ou
    `?sslpassword=` tambem sao credencial, e nao ha nada ali que valha o
    risco de filtrar caso a caso.
    """
    if not url:
        return "(vazia)"

    try:
        partes = urlsplit(url)
    except ValueError:
        return "(url ilegivel)"

    if not partes.hostname:
        return "(url sem host)"

    destino = partes.hostname
    if partes.port:
        destino = f"{destino}:{partes.port}"
    if partes.username:
        # O usuario fica porque e util no diagnostico (o RNF04 exige que
        # seja `torra_app`, nao `postgres`). A senha nunca aparece.
        destino = f"{partes.username}:***@{destino}"

    return urlunsplit((partes.scheme, destino, partes.path, "", ""))


# ---------------------------------------------------------------------
# Logs
#
# Formato `chave=valor` numa linha so. Nao e enfeite: o log do Railway e
# uma lista de linhas sem estrutura, e `grep evento=checkout_recusado`
# resolve em um comando o que um texto corrido exigiria ler inteiro.
#
# A regra que vale para toda chamada de logger neste arquivo: NUNCA
# registrar senha, token CSRF, SECRET_KEY nem DATABASE_URL com credencial.
# E-mail e dado pessoal e entra mascarado (ver `mascarar_email`).
# ---------------------------------------------------------------------
FORMATO_LOG = "%(asctime)s %(levelname)s %(message)s"

# Metodos HTTP que a aplicacao reconhece. Usado pela app degradada, que
# precisa responder 503 em todos eles, e pela verificacao de CSRF.
TODOS_OS_METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")


def configurar_logs(app: Flask) -> None:
    """Liga o logger da aplicacao no stdout, em nivel INFO.

    O gunicorn captura o stdout e o Railway o mostra na aba Logs, entao
    nao ha arquivo de log para rotacionar. Em nivel INFO porque os eventos
    que interessam — login falho, CSRF barrado, 403, checkout recusado,
    mudanca de status — sao informacao de auditoria, nao erro.
    """
    app.logger.setLevel(logging.INFO)

    # O Flask instala um handler proprio; sem este guard, cada reload do
    # servidor de desenvolvimento duplicaria as linhas.
    if not any(
        isinstance(h, logging.StreamHandler) for h in app.logger.handlers
    ):
        destino = logging.StreamHandler()
        destino.setFormatter(logging.Formatter(FORMATO_LOG))
        app.logger.addHandler(destino)


def mascarar_email(email: str | None) -> str:
    """`ana.silva@exemplo.com` -> `an***@exemplo.com`.

    O log de login falho precisa permitir investigar um ataque de forca
    bruta (mesmo dominio? mesma conta repetida?) sem virar uma lista de
    e-mails de clientes em texto puro dentro do painel de logs.
    """
    if not email:
        return "(vazio)"

    usuario, _, dominio = email.partition("@")
    if not dominio:
        return (usuario[:2] or "?") + "***"
    return f"{usuario[:2]}***@{dominio}"


# ---------------------------------------------------------------------
# Conexao
# ---------------------------------------------------------------------
def normalizar_url(url: str) -> str:
    """Ajusta a string de conexao para o driver psycopg 3.

    Provedores de cloud (Railway, Render, Neon, Heroku) entregam a
    DATABASE_URL como `postgresql://...`, e alguns ainda usam o formato
    legado `postgres://`. O SQLAlchemy precisa do dialeto explicito
    `postgresql+psycopg://` para escolher o psycopg 3 em vez do psycopg2.

    Sem esta normalizacao o deploy sobe e quebra na primeira query com
    `Can't load plugin: sqlalchemy.dialects:postgres`.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def app_sem_configuracao(app: Flask, faltando: list[str]) -> Flask:
    """Aplicacao degradada: responde 503 em qualquer rota.

    Por que subir uma app em vez de levantar excecao na importacao: com
    excecao o gunicorn morre no boot, o Railway reinicia em laco e quem
    abre o site recebe a pagina generica do proxy, que nao diz nada. Aqui
    a loja fica fora do ar de forma honesta e informativa — a pagina diz
    exatamente qual variavel de ambiente falta.

    O que ela mostra e o NOME da variavel. Nunca o valor, nunca parte do
    valor: a pagina e publica.
    """
    app.config["CONFIGURACAO_INCOMPLETA"] = tuple(faltando)

    # Log sem valor nenhum — so os nomes.
    app.logger.critical(
        "evento=configuracao_incompleta ambiente=producao variaveis_ausentes=%s",
        ",".join(faltando),
    )

    @app.route("/", defaults={"caminho": ""}, methods=list(TODOS_OS_METODOS))
    @app.route("/<path:caminho>", methods=list(TODOS_OS_METODOS))
    def configuracao_incompleta(caminho: str):
        # Cliente de API recebe JSON; navegador recebe a pagina.
        if caminho == "health" or caminho.startswith("api/"):
            corpo = jsonify(
                {
                    "erro": "Aplicação sem configuração completa.",
                    "variaveis_ausentes": faltando,
                }
            )
        else:
            corpo = render_template("erro_configuracao.html", faltando=faltando)

        resposta = make_response(corpo, 503)
        resposta.headers["Cache-Control"] = "no-store"
        resposta.headers["Retry-After"] = "120"
        return resposta

    return app


def criar_app(config_teste: dict | None = None) -> Flask:
    """Fabrica da aplicacao.

    Recebe `config_teste` para que o pytest monte a app apontando para um
    banco separado, sem tocar no banco de desenvolvimento.
    """
    app = Flask(__name__)
    configurar_logs(app)

    # Em producao os segredos sao obrigatorios e nao tem fallback. Fora de
    # producao — e em qualquer execucao de teste, que traz a propria
    # configuracao — os padroes de desenvolvimento valem.
    producao = em_producao() and config_teste is None
    if producao:
        faltando = segredos_ausentes()
        if faltando:
            return app_sem_configuracao(app, faltando)
        url = os.environ["DATABASE_URL"]
        chave = os.environ["SECRET_KEY"]
    else:
        url = os.getenv("DATABASE_URL", PADRAO_DESENVOLVIMENTO["DATABASE_URL"])
        chave = os.getenv("SECRET_KEY", PADRAO_DESENVOLVIMENTO["SECRET_KEY"])

    app.config["CONFIGURACAO_INCOMPLETA"] = ()
    app.config["SQLALCHEMY_DATABASE_URI"] = normalizar_url(url)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = chave

    # Quem e gestor: lista de e-mails por variavel de ambiente, sem mexer
    # no schema. Ver a secao "Papel de gestor" mais abaixo.
    app.config["ADMIN_EMAILS"] = ler_admin_emails()

    # --- Cookie de sessao ------------------------------------------------
    # HttpOnly: JavaScript nao le o cookie, entao um XSS nao rouba a sessao.
    app.config["SESSION_COOKIE_HTTPONLY"] = True

    # SameSite=Lax: o navegador nao envia o cookie em POST vindo de outro
    # site. E a primeira barreira contra CSRF, antes mesmo do token.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Secure so em producao: em desenvolvimento local o Flask roda em http
    # e um cookie Secure simplesmente nao seria enviado, quebrando o login.
    # Olha as duas fontes porque o Railway define RAILWAY_ENVIRONMENT mas
    # nao define FLASK_ENV — depender so do FLASK_ENV deixaria o cookie
    # sem Secure em producao se alguem apagasse a variavel.
    app.config["SESSION_COOKIE_SECURE"] = (
        producao or os.getenv("FLASK_ENV", "development") == "production"
    )

    if config_teste:
        app.config.update(config_teste)

    db.init_app(app)
    registrar_comandos(app)
    registrar_rotas(app)
    app.register_blueprint(api)

    app.logger.info(
        "evento=aplicacao_iniciada producao=%s banco=%s gestores=%d",
        producao,
        mascarar_url(app.config["SQLALCHEMY_DATABASE_URI"]),
        len(app.config["ADMIN_EMAILS"]),
    )
    return app


db = SQLAlchemy()


# =====================================================================
# Modelos — espelho do SQL/schema.sql
# =====================================================================

class Categoria(db.Model):
    """Regiao produtora. Separada de produtos para respeitar a 3FN."""

    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    regiao = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text)

    produtos = db.relationship("Produto", back_populates="categoria")

    def __repr__(self) -> str:
        return f"<Categoria {self.nome}>"


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, server_default=func.now())

    pedidos = db.relationship("Pedido", back_populates="cliente")

    def __repr__(self) -> str:
        return f"<Cliente {self.email}>"


class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(140), nullable=False)
    descricao = db.Column(db.Text)

    # Numeric, nao Float: ponto flutuante binario nao representa 0,10 de
    # forma exata e o erro se acumula na soma dos itens do pedido.
    preco = db.Column(db.Numeric(10, 2), nullable=False)

    estoque = db.Column(db.Integer, nullable=False, default=0)
    categoria_id = db.Column(
        db.Integer, db.ForeignKey("categorias.id"), nullable=False
    )
    torra = db.Column(db.String(10), nullable=False)
    nota_sensorial = db.Column(db.String(200))
    pontuacao_sca = db.Column(db.Numeric(4, 2))
    peso_g = db.Column(db.Integer, nullable=False, default=250)

    categoria = db.relationship("Categoria", back_populates="produtos")

    # Espelho das constraints do DDL. Estao aqui como documentacao viva do
    # modelo — quem le o ORM ve as mesmas regras que o banco aplica.
    __table_args__ = (
        CheckConstraint("preco >= 0", name="ck_produtos_preco"),
        CheckConstraint("estoque >= 0", name="ck_produtos_estoque"),
        CheckConstraint(
            "pontuacao_sca BETWEEN 80 AND 100", name="ck_produtos_sca"
        ),
        CheckConstraint(
            "torra IN ('CLARA','MEDIA','ESCURA')", name="ck_produtos_torra"
        ),
        CheckConstraint("peso_g > 0", name="ck_produtos_peso"),
    )

    def __repr__(self) -> str:
        return f"<Produto {self.nome}>"


class Pedido(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer, db.ForeignKey("clientes.id"), nullable=False
    )
    status = db.Column(db.String(12), nullable=False, default="CRIADO")
    total = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0"))
    criado_em = db.Column(db.DateTime, nullable=False, server_default=func.now())

    cliente = db.relationship("Cliente", back_populates="pedidos")
    itens = db.relationship(
        "ItemPedido", back_populates="pedido", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('CRIADO','PAGO','ENVIADO','CANCELADO')",
            name="ck_pedidos_status",
        ),
        CheckConstraint("total >= 0", name="ck_pedidos_total"),
    )

    def __repr__(self) -> str:
        return f"<Pedido {self.id} {self.status}>"


class ItemPedido(db.Model):
    """Entidade de verdade, nao tabela de ligacao.

    Carrega dois atributos que nao pertencem nem ao pedido nem ao produto:
    a moagem escolhida na compra e o preco congelado da epoca.
    """

    __tablename__ = "itens_pedido"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedidos.id", ondelete="CASCADE"),
        nullable=False,
    )
    produto_id = db.Column(
        db.Integer, db.ForeignKey("produtos.id"), nullable=False
    )
    quantidade = db.Column(db.Integer, nullable=False)

    # Congelado no momento da compra. Se o preco do cafe mudar amanha, o
    # pedido antigo mantem o valor da epoca — senao o historico se
    # reescreveria sozinho e o total deixaria de bater com a soma dos itens.
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)

    # Mora aqui e nao em produtos porque o cliente escolhe na compra. E este
    # atributo que faz de itens_pedido uma entidade.
    moagem = db.Column(db.String(6), nullable=False)

    pedido = db.relationship("Pedido", back_populates="itens")
    produto = db.relationship("Produto")

    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_itens_quantidade"),
        CheckConstraint("preco_unitario >= 0", name="ck_itens_preco"),
        CheckConstraint(
            "moagem IN ('GRAO','MEDIA','FINA')", name="ck_itens_moagem"
        ),
        UniqueConstraint(
            "pedido_id",
            "produto_id",
            "moagem",
            name="uq_itens_pedido_produto_moagem",
        ),
    )

    @property
    def subtotal(self) -> Decimal:
        return self.preco_unitario * self.quantidade

    def __repr__(self) -> str:
        return f"<ItemPedido pedido={self.pedido_id} produto={self.produto_id}>"


# =====================================================================
# Comandos de linha de comando
# =====================================================================

def _executar_script(nome: str) -> None:
    """Roda um arquivo .sql inteiro no banco configurado.

    Usa exec_driver_sql para entregar o script direto ao psycopg, que aceita
    varias instrucoes numa chamada so. Passar por text() do SQLAlchemy
    quebraria nos `$` e nos multiplos statements.
    """
    caminho = RAIZ / "SQL" / nome
    sql = caminho.read_text(encoding="utf-8")
    with db.engine.begin() as conn:
        conn.exec_driver_sql(sql)


# ---------------------------------------------------------------------
# Dados de demonstracao do Projeto Final
#
# Nomes inventados e e-mails em @exemplo.com — dominio que a RFC 2606
# reserva para documentacao e que nunca entrega mensagem a ninguem.
# Nenhum dado de pessoa real entra no banco.
# ---------------------------------------------------------------------
CLIENTES_DEMO = (
    ("Ana Bragança", "ana.braganca@exemplo.com"),
    ("Bruno Teixeira", "bruno.teixeira@exemplo.com"),
    ("Carla Nakamura", "carla.nakamura@exemplo.com"),
    ("Diego Fontes", "diego.fontes@exemplo.com"),
    ("Elisa Moraes", "elisa.moraes@exemplo.com"),
    ("Fábio Lousada", "fabio.lousada@exemplo.com"),
    ("Giovana Prado", "giovana.prado@exemplo.com"),
    ("Henrique Vilela", "henrique.vilela@exemplo.com"),
)

PEDIDOS_DEMO = 40

# Semente fixa: duas execucoes em bancos iguais produzem o mesmo retrato.
# Evidencia de relatorio que muda a cada execucao nao e evidencia.
SEMENTE_DEMO = 2026

# A demo nao toca em cafe com estoque apertado. E o que preserva o
# 'Chapada Geisha' com estoque 1, que o seed.sql deixa assim de proposito
# para a demonstracao do rollback.
ESTOQUE_MINIMO_DEMO = 4

# Senha das contas ficticias. Nao e segredo por definicao: o manual exige
# publicar as credenciais de demonstracao no README, para o professor
# entrar na loja. Pode ser trocada pela variavel SENHA_DEMO.
SENHA_DEMO_PADRAO = "demo-torra-e-terra-2026"


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db() -> None:
        """Cria a estrutura do banco a partir do SQL/schema.sql."""
        _executar_script("schema.sql")
        print("Estrutura criada a partir de SQL/schema.sql")

    @app.cli.command("seed-db")
    def seed_db() -> None:
        """Carrega os 12 cafes do SQL/seed.sql."""
        _executar_script("seed.sql")
        total = db.session.scalar(db.select(func.count(Produto.id)))
        print(f"Carga concluida: {total} cafes no catalogo")

    @app.cli.command("reset-db")
    def reset_db() -> None:
        """Dropa, recria e recarrega. Apenas para desenvolvimento."""
        _executar_script("schema.sql")
        _executar_script("seed.sql")
        total = db.session.scalar(db.select(func.count(Produto.id)))
        print(f"Banco recriado do zero: {total} cafes no catalogo")

    @app.cli.command("seed-demo")
    def seed_demo() -> None:
        """Projeto Final: pedidos de demonstracao dos ultimos 30 dias.

        O painel de indicadores precisa de historico para dizer algo. Com
        um pedido so, "vendas por regiao" e um retangulo e "ticket medio"
        e o valor daquele pedido.

        Tres garantias deste comando:

        1. NAO APAGA NADA. Nenhum TRUNCATE, nenhum DELETE. Ele soma ao que
           existe, e pode rodar num banco que ja tem clientes e pedidos
           reais. E a diferenca entre ele e o `seed-db`, que recarrega o
           catalogo e por isso derruba os pedidos.

        2. OS PEDIDOS PASSAM PELO CHECKOUT DE VERDADE. Cada um nasce de
           `finalizar_pedido`, com o mesmo SELECT ... FOR UPDATE, a mesma
           validacao de estoque e o mesmo congelamento de preco. Dado de
           demonstracao inserido por INSERT direto produziria um painel
           bonito e mentiroso: o indicador de conciliacao fecharia porque
           o INSERT caprichou no total, nao porque a transacao funciona.

        3. OS CANCELAMENTOS TAMBEM SAO DE VERDADE. Passam por
           `alterar_status_pedido`, que devolve o estoque na mesma
           transacao. Marcar `status = 'CANCELADO'` com UPDATE deixaria o
           estoque errado e o painel contaria uma historia impossivel.

        O que e simulado, e esta registrado como tal: a DATA. O pedido
        nasce agora e o `criado_em` e reescrito para uma data dentro dos
        ultimos 30 dias. Nao ha como fazer de outro jeito sem viajar no
        tempo, e sem espalhar as datas o filtro de periodo do painel nao
        teria o que filtrar.
        """
        aleatorio = random.Random(SEMENTE_DEMO)

        # --- 1. Clientes ficticios ------------------------------------
        #
        # Nomes inventados e dominio @exemplo.com, que a RFC 2606 reserva
        # justamente para documentacao e nunca entrega e-mail a ninguem.
        # Nenhum dado de pessoa real entra no banco de demonstracao.
        senha = os.getenv("SENHA_DEMO", SENHA_DEMO_PADRAO)
        criados = 0

        for nome, email in CLIENTES_DEMO:
            ja_existe = db.session.scalar(
                db.select(Cliente).where(Cliente.email == email)
            )
            if ja_existe:
                continue
            db.session.add(
                Cliente(
                    nome=nome,
                    email=email,
                    senha_hash=generate_password_hash(senha),
                )
            )
            criados += 1

        db.session.commit()

        clientes = db.session.scalars(
            db.select(Cliente)
            .where(Cliente.email.in_([e for _, e in CLIENTES_DEMO]))
            .order_by(Cliente.id)
        ).all()

        print(f"Clientes de demonstracao: {len(clientes)} ({criados} novos)")

        # --- 2. Quantos pedidos ainda faltam --------------------------
        #
        # Conta o que ja existe no periodo para rodar duas vezes nao gerar
        # oitenta pedidos. O alvo e um retrato de 30 dias, nao um acumulado.
        existentes = db.session.scalar(
            db.select(func.count(Pedido.id)).where(
                Pedido.cliente_id.in_([c.id for c in clientes])
            )
        ) or 0

        faltam = max(0, PEDIDOS_DEMO - existentes)
        if not faltam:
            print(
                f"Ja existem {existentes} pedidos de demonstracao. "
                "Nada a fazer."
            )
            return

        # --- 3. Os pedidos --------------------------------------------
        agora = datetime.now()
        gerados, recusados = [], 0

        for _ in range(faltam):
            # Cafes com folga de estoque. O filtro protege o 'Chapada
            # Geisha', que o seed.sql deixa com estoque 1 de proposito
            # para a demonstracao do rollback — se a demo o consumisse,
            # a evidencia mais importante do trabalho iria embora.
            disponiveis = db.session.scalars(
                db.select(Produto).where(Produto.estoque >= ESTOQUE_MINIMO_DEMO)
            ).all()

            if not disponiveis:
                print("Estoque insuficiente para continuar. Parando aqui.")
                break

            escolhidos = aleatorio.sample(
                disponiveis, k=min(len(disponiveis), aleatorio.randint(1, 3))
            )

            linhas = [
                {
                    "produto_id": p.id,
                    "quantidade": aleatorio.randint(1, 2),
                    "moagem": aleatorio.choice(MOAGENS_VALIDAS),
                }
                for p in escolhidos
            ]

            try:
                pedido = finalizar_pedido(
                    aleatorio.choice(clientes).id, linhas
                )
            except ErroCheckout:
                # Pode acontecer e nao e problema: o estoque e lido a cada
                # volta e outra compra pode ter esvaziado o cafe no meio.
                recusados += 1
                continue

            # A data, reescrita para dentro da janela de 30 dias. Hora
            # comercial para o retrato parecer com uma loja de verdade.
            pedido.criado_em = agora - timedelta(
                days=aleatorio.randint(0, DIAS_PADRAO - 1),
                hours=aleatorio.randint(8, 20),
                minutes=aleatorio.randint(0, 59),
            )
            db.session.commit()
            gerados.append(pedido.id)

        # --- 4. Os status, pelas transicoes de verdade ----------------
        #
        # Proporcao escolhida para o painel mostrar um funil plausivel: a
        # maioria entregue, uma parte paga esperando expedicao, alguns
        # recem-criados e uma minoria cancelada.
        caminhos = (
            ["CRIADO"] * 6
            + ["PAGO"] * 8
            + ["ENVIADO"] * 21
            + ["CANCELADO"] * 5
        )

        contagem = {status: 0 for status in STATUS_VALIDOS}
        contagem["CRIADO"] = len(gerados)
        devolvidas = 0

        for pedido_id in gerados:
            alvo = aleatorio.choice(caminhos)
            if alvo == "CRIADO":
                continue

            # ENVIADO exige passar por PAGO: a maquina de estados nao tem
            # atalho, e a demo nao pode usar um que a loja nao tem.
            passos = {
                "PAGO": ["PAGO"],
                "ENVIADO": ["PAGO", "ENVIADO"],
                "CANCELADO": [aleatorio.choice(["PAGO", None]), "CANCELADO"],
            }[alvo]

            for passo in [p for p in passos if p]:
                resumo = alterar_status_pedido(pedido_id, passo)
                devolvidas += resumo["unidades_devolvidas"]

            contagem["CRIADO"] -= 1
            contagem[alvo] += 1

        print(f"Pedidos criados agora: {len(gerados)}")
        if recusados:
            print(f"Tentativas recusadas por estoque: {recusados}")
        print(
            "Status: "
            + ", ".join(f"{s}={contagem[s]}" for s in STATUS_VALIDOS)
        )
        print(f"Unidades devolvidas pelos cancelamentos: {devolvidas}")
        print(f"Senha dos clientes de demonstracao: {senha}")
        print(
            "Pronto. Abra /painel com uma conta de gestor "
            "(e-mail listado em ADMIN_EMAILS)."
        )


# =====================================================================
# Apresentacao
# =====================================================================

MOAGENS_VALIDAS = ("GRAO", "MEDIA", "FINA")

# Metodos que alteram estado. Sao os unicos que exigem token CSRF — um GET
# nunca deveria mudar nada, e se mudasse o problema seria outro.
METODOS_QUE_ESCREVEM = ("POST", "PUT", "PATCH", "DELETE")


# ---------------------------------------------------------------------
# Protecao contra CSRF
#
# Sem isto, um site malicioso que voce visitasse enquanto logado poderia
# disparar um POST para /checkout usando o SEU cookie de sessao, e o pedido
# sairia de verdade. O navegador anexa o cookie automaticamente; ele nao
# sabe distinguir um formulario nosso de um formulario de outra pagina.
#
# A defesa e um segredo que so o nosso HTML conhece: o token vive na sessao
# e e reenviado num campo escondido. O site atacante nao consegue ler a
# sessao, entao nao consegue forjar o campo.
#
# Escrito a mao em vez de usar o Flask-WTF: sao vinte linhas, nao adiciona
# dependencia, e e codigo que o grupo consegue explicar na defesa.
# ---------------------------------------------------------------------

def token_csrf() -> str:
    """Devolve o token da sessao, criando na primeira vez."""
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def renovar_token_csrf() -> None:
    """Troca o token. Chamado no login, contra fixacao de sessao."""
    session["_csrf"] = secrets.token_urlsafe(32)


def login_obrigatorio(rota):
    """Protege rotas que exigem cliente autenticado.

    Guarda a URL pedida para devolver o cliente exatamente onde ele estava
    depois do login — quem clica em "finalizar compra" sem estar logado
    volta para o checkout, nao para a home.
    """

    @wraps(rota)
    def envelope(*args, **kwargs):
        if not session.get("cliente_id"):
            flash("Entre na sua conta para continuar.", "erro")
            return redirect(url_for("login", proximo=request.path))
        return rota(*args, **kwargs)

    return envelope


def cliente_atual() -> "Cliente | None":
    # has_request_context: as mesmas funcoes de negocio (mudanca de status,
    # por exemplo) rodam pela web e pelo `flask seed-demo`. Na linha de
    # comando nao existe sessao, e ler `session` fora de requisicao levanta
    # RuntimeError — aqui a resposta correta e simplesmente "ninguem logado".
    if not has_request_context():
        return None

    cliente_id = session.get("cliente_id")
    if not cliente_id:
        return None
    return db.session.get(Cliente, cliente_id)


# ---------------------------------------------------------------------
# Papel de gestor
#
# Sem coluna nova em `clientes` e sem tabela de papeis: a lista de e-mails
# com acesso ao painel vem da variavel de ambiente ADMIN_EMAILS.
#
# Por que nao mudar o schema: o `SQL/schema.sql` e a entrega avaliada do
# trabalho e ja esta aplicado no banco de producao. Acrescentar
# `clientes.papel` obrigaria a uma migracao de coluna num banco no ar
# para atender um requisito de OPERACAO, nao de modelagem. Quem pode abrir
# o painel e decisao de configuracao do deploy — da mesma natureza da
# SECRET_KEY, e por isso mora no mesmo lugar que ela.
#
# Limitacao aceita e registrada em docs/decisoes.md: trocar o gestor exige
# editar a variavel e reiniciar o servico. Com mais de um punhado de
# gestores, ou com papeis diferentes entre si, isso viraria tabela.
# ---------------------------------------------------------------------

def ler_admin_emails() -> frozenset[str]:
    """Le ADMIN_EMAILS: e-mails separados por virgula, em minusculas."""
    bruto = os.getenv("ADMIN_EMAILS", "")
    return frozenset(
        parte.strip().lower() for parte in bruto.split(",") if parte.strip()
    )


def eh_gestor(cliente: "Cliente | None") -> bool:
    """Um cliente logado cujo e-mail esta em ADMIN_EMAILS e gestor."""
    if cliente is None:
        return False
    gestores = current_app.config.get("ADMIN_EMAILS") or frozenset()
    return cliente.email.strip().lower() in gestores


def gestor_obrigatorio(rota):
    """Protege as rotas de pagina do painel.

    Visitante sem sessao vai para o login — e nao recebe 403, porque 403
    para quem nao se identificou revelaria que a rota existe e que o
    problema e permissao, nao endereco.

    Cliente logado que nao e gestor recebe 403 com pagina amigavel. A
    tentativa vai para o log, com o e-mail mascarado.
    """

    @wraps(rota)
    def envelope(*args, **kwargs):
        cliente = cliente_atual()

        if cliente is None:
            flash("Entre com a conta de gestor para abrir o painel.", "erro")
            return redirect(url_for("login", proximo=request.path))

        if not eh_gestor(cliente):
            current_app.logger.warning(
                "evento=acesso_negado_painel email=%s rota=%s",
                mascarar_email(cliente.email),
                request.path,
            )
            abort(403)

        return rota(*args, **kwargs)

    return envelope


# ---------------------------------------------------------------------
# Carrinho
#
# Mora na sessao, nao no banco. O carrinho e PROCESSO, nao entidade: existe
# so enquanto a compra nao fecha e nao tem valor historico. Ele vira
# entidade — pedidos + itens_pedido — no instante do checkout.
#
# Formato na sessao:
#     [{"produto_id": 3, "quantidade": 2, "moagem": "FINA"}, ...]
#
# Guardamos apenas o id, nunca o preco: o preco e lido do banco a cada
# exibicao e so e congelado no fechamento do pedido. Confiar num preco
# vindo da sessao deixaria o cliente alterar o valor pelo cookie.
# ---------------------------------------------------------------------

def ler_carrinho() -> list[dict]:
    return session.get("carrinho", [])


def gravar_carrinho(linhas: list[dict]) -> None:
    session["carrinho"] = linhas
    session.modified = True


def carrinho_detalhado() -> tuple[list[dict], Decimal]:
    """Junta as linhas da sessao com os produtos do banco.

    Linhas cujo produto sumiu do catalogo sao descartadas silenciosamente
    aqui — o checkout trata esse caso com mensagem explicita.
    """
    linhas, total = [], Decimal("0")

    for linha in ler_carrinho():
        produto = db.session.get(Produto, linha["produto_id"])
        if produto is None:
            continue

        subtotal = produto.preco * linha["quantidade"]
        total += subtotal
        linhas.append(
            {
                "produto": produto,
                "quantidade": linha["quantidade"],
                "moagem": linha["moagem"],
                "subtotal": subtotal,
            }
        )

    return linhas, total


# =====================================================================
# A transacao de checkout
#
# O coracao do trabalho. Tudo-ou-nada:
#
#     BEGIN
#      |- SELECT ... FOR UPDATE  (trava o estoque de cada cafe)
#      |- valida existencia e saldo de TODOS os itens
#      |- INSERT do pedido
#      |- INSERT de cada item, com preco_unitario congelado
#      |- UPDATE do estoque
#      +- COMMIT   ·   ROLLBACK em qualquer falha
# =====================================================================

class ErroCheckout(Exception):
    """Falha de negocio que impede o fechamento do pedido."""


class CarrinhoVazio(ErroCheckout):
    pass


class ProdutoInexistente(ErroCheckout):
    pass


class EstoqueInsuficiente(ErroCheckout):
    def __init__(self, nome: str, disponivel: int, pedido: int):
        self.nome = nome
        self.disponivel = disponivel
        self.pedido = pedido
        super().__init__(
            f"Estoque insuficiente de {nome}: você pediu {pedido} "
            f"e temos {disponivel} em estoque."
        )


def finalizar_pedido(cliente_id: int, linhas_carrinho: list[dict]) -> Pedido:
    """Transforma o carrinho em pedido persistido, em transacao unica.

    Ou grava tudo — pedido, itens e baixa de estoque — ou nao grava nada.
    Levanta ErroCheckout em qualquer falha de negocio, sempre depois de
    desfazer a transacao inteira.
    """
    if not linhas_carrinho:
        raise CarrinhoVazio("Seu carrinho está vazio.")

    try:
        # --- Fase 0: consolidar a demanda por PRODUTO ------------------
        #
        # O carrinho tem uma linha por (produto, moagem): meio quilo em
        # grao e meio quilo moido fino sao duas linhas do mesmo cafe. O
        # ESTOQUE, porem, e do cafe — nao da moagem.
        #
        # Validar linha a linha contra o estoque cheio deixava passar o
        # carrinho em que cada linha cabe sozinha mas a soma nao: com
        # estoque 1, uma linha GRAO de 1 e uma linha FINA de 1 passavam as
        # duas, e a fase 2 gravava estoque = -1. Quem barrava era o CHECK
        # do banco, com IntegrityError — que nao e ErroCheckout, entao o
        # cliente levava uma pagina 500 em vez da mensagem dizendo qual
        # cafe faltou.
        demanda = {}
        for linha in linhas_carrinho:
            produto_id = linha["produto_id"]
            demanda[produto_id] = demanda.get(produto_id, 0) + linha["quantidade"]

        # --- Fase 1: travar e validar TODOS os produtos ----------------
        #
        # Nada e inserido antes desta fase terminar. Assim o caso de erro
        # nao chega sequer a criar o cabecalho do pedido — o rollback
        # continua sendo obrigatorio, mas o banco trabalha menos.
        #
        # Trava sempre na mesma ordem crescente de id. Duas compras
        # simultaneas que travassem os mesmos cafes em ordens opostas
        # ficariam em deadlock, uma esperando o lock da outra; ordenar
        # elimina o ciclo antes que ele exista.
        travados = {}
        for produto_id in sorted(demanda):
            # with_for_update() gera o SELECT ... FOR UPDATE: segura a
            # linha do produto ate o fim da transacao. Sem isso, duas
            # compras simultaneas leem o mesmo estoque 1, ambas aprovam, e
            # o mesmo lote e vendido duas vezes.
            #
            # populate_existing() NAO e detalhe: sem ele o FOR UPDATE
            # protege no banco e nao protege na aplicacao. A rota de
            # checkout chama carrinho_detalhado() antes desta funcao, e
            # aquilo ja carregou o Produto na sessao. Por padrao o ORM
            # devolve o objeto que ja esta no identity map e DESCARTA a
            # linha recem-lida — entao `produto.estoque` continuava sendo
            # o valor de antes do lock. A compra concorrente commitava, o
            # FOR UPDATE esperava, lia o saldo novo, e a validacao decidia
            # com o saldo velho. Era a venda em duplicidade que esta
            # funcao existe para impedir.
            produto = db.session.scalar(
                db.select(Produto)
                .where(Produto.id == produto_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )

            if produto is None:
                raise ProdutoInexistente(
                    "Um dos cafés do seu carrinho não está mais disponível. "
                    "Revise o carrinho e tente de novo."
                )

            quantidade_pedida = demanda[produto_id]
            if produto.estoque < quantidade_pedida:
                raise EstoqueInsuficiente(
                    produto.nome, produto.estoque, quantidade_pedida
                )

            travados[produto_id] = produto

        # --- Fase 2: gravar -------------------------------------------
        pedido = Pedido(
            cliente_id=cliente_id, status="CRIADO", total=Decimal("0")
        )
        db.session.add(pedido)

        # flush envia o INSERT e recebe o id gerado pela sequence, sem
        # encerrar a transacao. O commit continua sendo o unico ponto em
        # que algo se torna definitivo.
        db.session.flush()

        # Uma linha de item por linha do carrinho: a moagem continua
        # separando as linhas, que e o que faz itens_pedido ser entidade.
        total = Decimal("0")
        for linha in linhas_carrinho:
            produto = travados[linha["produto_id"]]
            db.session.add(
                ItemPedido(
                    pedido_id=pedido.id,
                    produto_id=produto.id,
                    quantidade=linha["quantidade"],
                    # Congelado aqui, e so aqui, a partir da linha TRAVADA.
                    # Se o preco deste cafe mudar amanha, este pedido
                    # mantem o valor de hoje.
                    preco_unitario=produto.preco,
                    moagem=linha["moagem"],
                )
            )
            total += produto.preco * linha["quantidade"]

        # Uma baixa de estoque por PRODUTO, com a quantidade consolidada.
        for produto_id, quantidade_pedida in demanda.items():
            travados[produto_id].estoque -= quantidade_pedida

        pedido.total = total
        db.session.commit()
        return pedido

    except Exception:
        # Vale para o erro de negocio e para o inesperado: o banco nao fica
        # com pedido pela metade em nenhum dos dois casos.
        db.session.rollback()
        raise


def formatar_brl(valor) -> str:
    """Formata no padrao brasileiro: R$ 1.234,56.

    A troca dupla existe porque o Python formata no padrao americano
    (1,234.56) e nao ha locale pt-BR garantido no container do deploy —
    depender de `locale.setlocale` quebraria em producao.
    """
    if valor is None:
        return "R$ 0,00"
    inteiro = f"{Decimal(valor):,.2f}"
    return "R$ " + inteiro.replace(",", "_").replace(".", ",").replace("_", ".")


def decimal_em_texto(valor) -> str:
    """Devolve dinheiro como string decimal, para o JSON da API.

    `{"preco": 89.0}` em JSON e um float IEEE 754 — o mesmo tipo que o
    projeto rejeitou no banco por nao representar 0,10 exatamente. Quem
    consumir a API em JavaScript receberia 89.00000000000001 em algum
    caso de soma. Serializado como `"89.00"`, o valor chega exato e quem
    consome decide como quer somar.
    """
    if valor is None:
        return "0.00"
    return f"{Decimal(valor):.2f}"


# =====================================================================
# Painel de indicadores — Projeto Final
#
# As consultas NAO estao escritas aqui. Elas vivem em SQL/dashboard.sql,
# que e lido na primeira chamada e separado em blocos pelo marcador
# `-- @consulta: nome`.
#
# Por que ler de um arquivo .sql em vez de embutir as strings no Python:
#   1. O arquivo roda direto no psql, do jeito que esta, com `-v dias=30`.
#      O professor executa e ve o mesmo SQL que a tela executa.
#   2. Nao existe divergencia possivel entre "o SQL documentado" e "o SQL
#      que roda". Sao o mesmo texto.
#   3. O SQL fica comentado em SQL, com a pergunta de negocio e o indice
#      de cada consulta ao lado dela.
#
# Os parametros vao SEMPRE ligados por text(), nunca por f-string. O
# `?dias=` chega pela URL, e montar SQL por concatenacao com valor de URL
# e exatamente a receita de SQL injection.
# =====================================================================

MARCADOR_CONSULTA = "-- @consulta:"

DIAS_PADRAO = 30
DIAS_MAXIMO = 365
LIMITE_ESTOQUE_PADRAO = 5


@lru_cache(maxsize=1)
def consultas_do_painel() -> dict[str, str]:
    """Le SQL/dashboard.sql e devolve {nome: sql}.

    Tudo o que vem antes do primeiro marcador e descartado: e o cabecalho
    do arquivo, com os `\\set` do psql, que nao sao SQL e quebrariam aqui.

    O resultado fica em cache por processo. Editar o .sql exige reiniciar
    a aplicacao — o mesmo comportamento do schema.sql, e preferivel a ler
    o arquivo do disco em cada carregamento do painel.
    """
    bruto = (RAIZ / "SQL" / "dashboard.sql").read_text(encoding="utf-8")

    consultas: dict[str, str] = {}
    nome: str | None = None
    acumulado: list[str] = []

    for linha in bruto.splitlines():
        if linha.strip().startswith(MARCADOR_CONSULTA):
            if nome:
                consultas[nome] = "\n".join(acumulado).strip()
            nome = linha.split(":", 1)[1].strip()
            acumulado = []
        elif nome is not None:
            acumulado.append(linha)

    if nome:
        consultas[nome] = "\n".join(acumulado).strip()

    return consultas


def normalizar_dias(bruto) -> int:
    """Converte o `?dias=` da URL num inteiro dentro de uma faixa segura.

    Valor ausente, texto ou numero absurdo cai no padrao de 30 dias. O
    teto de 365 existe porque `?dias=99999999` faria o planejador varrer
    a tabela inteira sem usar o indice — e um jeito barato de derrubar o
    painel a partir da URL.
    """
    try:
        dias = int(bruto)
    except (TypeError, ValueError):
        return DIAS_PADRAO
    return max(1, min(dias, DIAS_MAXIMO))


def executar_consulta(nome: str, **parametros) -> list[dict]:
    """Roda uma consulta de SQL/dashboard.sql com parametros ligados."""
    sql = consultas_do_painel()[nome]
    linhas = db.session.execute(text(sql), parametros).mappings().all()
    return [dict(linha) for linha in linhas]


def _participacao(linhas: list[dict], campo: str) -> list[dict]:
    """Acrescenta a participacao percentual de cada linha no total.

    Calculado em Decimal, nao em float, pela mesma razao de sempre: o
    percentual sai de uma divisao de dinheiro.
    """
    total = sum((Decimal(linha[campo] or 0) for linha in linhas), Decimal("0"))

    for linha in linhas:
        if total > 0:
            fatia = (Decimal(linha[campo] or 0) / total) * 100
            linha["participacao"] = fatia.quantize(Decimal("0.1"))
        else:
            linha["participacao"] = Decimal("0.0")

    return linhas


def indicadores(
    dias: int = DIAS_PADRAO,
    limite_estoque: int = LIMITE_ESTOQUE_PADRAO,
) -> dict:
    """Roda os sete indicadores do painel e devolve tudo num dicionario.

    Uma consulta por indicador, de proposito. Daria para juntar
    faturamento e ticket medio num SELECT so, mas cada indicador tem uma
    pergunta de negocio propria e precisa poder ser lido, explicado e
    rodado no psql isoladamente.
    """
    cabecalho = executar_consulta("faturamento", dias=dias)[0]
    ticket = executar_consulta("ticket_medio", dias=dias)[0]
    regioes = _participacao(
        executar_consulta("vendas_por_regiao", dias=dias), "faturamento"
    )
    conciliacao = executar_consulta("conciliacao", dias=dias)[0]

    return {
        "dias": dias,
        "limite_estoque": limite_estoque,
        "gerado_em": datetime.now(),
        "pedidos": cabecalho["pedidos"],
        "faturamento": cabecalho["faturamento"],
        "ticket_medio": ticket["ticket_medio"],
        "vendas_por_regiao": regioes,
        "top_cafes": executar_consulta("top_cafes", dias=dias),
        "estoque_critico": executar_consulta(
            "estoque_critico", limite_estoque=limite_estoque
        ),
        "pedidos_por_status": executar_consulta("pedidos_por_status", dias=dias),
        "conciliacao": conciliacao,
    }


# =====================================================================
# Gestao de pedidos — a atualizacao de registro que o manual pede
#
# O ciclo de vida do pedido como maquina de estados. As transicoes estao
# aqui, e nao soltas na rota, para que a pagina e a API obedecam a mesma
# regra: um unico lugar define o que pode virar o que.
#
#     CRIADO ──pagamento──> PAGO ──expedicao──> ENVIADO
#        │                    │
#        └────── CANCELADO <──┘
#
# ENVIADO e CANCELADO sao terminais. Nao existe "des-enviar" um pedido
# que ja saiu, e nao existe ressuscitar um cancelado — o cancelamento
# devolveu o estoque, e reabrir o pedido venderia de novo um cafe que
# pode ter sido vendido para outra pessoa no meio do caminho.
# =====================================================================

STATUS_VALIDOS = ("CRIADO", "PAGO", "ENVIADO", "CANCELADO")

TRANSICOES_PERMITIDAS = {
    "CRIADO": ("PAGO", "CANCELADO"),
    "PAGO": ("ENVIADO", "CANCELADO"),
    "ENVIADO": (),
    "CANCELADO": (),
}


class ErroGestao(Exception):
    """Falha de negocio na gestao do pedido."""


class PedidoInexistente(ErroGestao):
    pass


class TransicaoInvalida(ErroGestao):
    pass


def alterar_status_pedido(pedido_id: int, novo_status: str) -> dict:
    """Muda o status do pedido; se for cancelamento, devolve o estoque.

    Transacao unica, pela mesma razao do checkout: cancelar e duas
    escritas — o status do pedido e o saldo de cada produto. Se o UPDATE
    do estoque falhasse depois do status ja ter mudado, a loja ficaria
    com um pedido cancelado cujo cafe continua reservado para ninguem.

    O SELECT ... FOR UPDATE aparece duas vezes:

      - no pedido, para dois gestores clicando "cancelar" ao mesmo tempo
        nao devolverem o estoque duas vezes. O segundo espera, encontra o
        pedido ja em CANCELADO e e recusado pela regra de transicao;
      - em cada produto, na ordem crescente de id, igual ao checkout.
        Mesma ordem nos dois lugares significa que um cancelamento e uma
        compra concorrentes nunca travam em ciclo.

    Devolve um resumo do que aconteceu, para o log e para a mensagem.
    """
    if novo_status not in STATUS_VALIDOS:
        raise TransicaoInvalida(
            f"Status '{novo_status}' não existe. "
            f"Os válidos são: {', '.join(STATUS_VALIDOS)}."
        )

    try:
        pedido = db.session.scalar(
            db.select(Pedido).where(Pedido.id == pedido_id).with_for_update()
        )

        if pedido is None:
            raise PedidoInexistente(f"Pedido #{pedido_id} não encontrado.")

        anterior = pedido.status

        if novo_status == anterior:
            raise TransicaoInvalida(
                f"O pedido #{pedido_id} já está em {anterior}."
            )

        permitidas = TRANSICOES_PERMITIDAS.get(anterior, ())
        if novo_status not in permitidas:
            if not permitidas:
                raise TransicaoInvalida(
                    f"O pedido #{pedido_id} está em {anterior}, que é um "
                    f"estado final. Não há mudança possível a partir dele."
                )
            raise TransicaoInvalida(
                f"Não é possível ir de {anterior} para {novo_status}. "
                f"De {anterior} só dá para ir para "
                f"{' ou '.join(permitidas)}."
            )

        devolvido = 0
        if novo_status == "CANCELADO":
            itens = db.session.scalars(
                db.select(ItemPedido)
                .where(ItemPedido.pedido_id == pedido.id)
                .order_by(ItemPedido.produto_id)
            ).all()

            for item in itens:
                produto = db.session.scalar(
                    db.select(Produto)
                    .where(Produto.id == item.produto_id)
                    .with_for_update()
                )
                if produto is None:
                    raise PedidoInexistente(
                        "Um dos cafés do pedido não existe mais no catálogo. "
                        "O cancelamento não pode devolver o estoque dele."
                    )
                produto.estoque += item.quantidade
                devolvido += item.quantidade

        pedido.status = novo_status
        db.session.commit()

        resumo = {
            "pedido_id": pedido.id,
            "de": anterior,
            "para": novo_status,
            "unidades_devolvidas": devolvido,
        }

        # O historico financeiro do pedido NAO e reescrito no
        # cancelamento: itens e total continuam como estavam, e e por isso
        # que o indicador de conciliacao continua fechando depois dele.
        current_app.logger.info(
            "evento=status_alterado pedido=%s de=%s para=%s "
            "unidades_devolvidas=%s gestor=%s",
            pedido.id,
            anterior,
            novo_status,
            devolvido,
            mascarar_email(getattr(cliente_atual(), "email", None)),
        )
        return resumo

    except Exception:
        db.session.rollback()
        raise


# =====================================================================
# Rotas
# =====================================================================

def registrar_rotas(app: Flask) -> None:
    app.jinja_env.filters["brl"] = formatar_brl

    # Disponivel em todo template como {{ token_csrf() }}
    app.jinja_env.globals["token_csrf"] = token_csrf

    @app.before_request
    def exigir_token_csrf():
        """Barra qualquer escrita sem token valido, antes de tocar no banco.

        Duas fontes para o token, nesta ordem:

          1. o campo escondido `_csrf` dos formularios da loja;
          2. o cabecalho `X-CSRF-Token`, para o PATCH da API.

        Aceitar o cabecalho NAO enfraquece os formularios: a exigencia
        continua sendo a mesma — provar que conhece um segredo que vive na
        sessao e que outro site nao consegue ler. O que muda e o envelope.
        O cabecalho e, se qualquer coisa, mais restritivo: um formulario
        HTML de outro site consegue fazer POST com campos arbitrarios,
        mas nao consegue definir cabecalho customizado sem passar pelo
        CORS — que, com a CSP e o SameSite=Lax desta aplicacao, nao
        libera.
        """
        if request.method not in METODOS_QUE_ESCREVEM:
            return

        enviado = (
            request.form.get("_csrf")
            or request.headers.get("X-CSRF-Token")
            or ""
        )
        esperado = session.get("_csrf", "")

        # compare_digest em vez de ==: comparacao de tempo constante, para
        # nao vazar o token caractere a caractere pelo tempo de resposta.
        if not esperado or not secrets.compare_digest(enviado, esperado):
            app.logger.warning(
                "evento=csrf_barrado metodo=%s rota=%s token_enviado=%s "
                "sessao_com_token=%s",
                request.method,
                request.path,
                # O tamanho, nunca o valor: serve para distinguir "nao
                # mandou nada" de "mandou um token errado".
                "nao" if not enviado else f"sim({len(enviado)}b)",
                "sim" if esperado else "nao",
            )

            if request.path == "/health" or request.path.startswith("/api/"):
                return (
                    jsonify(
                        {
                            "erro": "Token CSRF ausente ou inválido. "
                            "Envie o cabeçalho X-CSRF-Token."
                        }
                    ),
                    400,
                )

            abort(400, description="Sessão expirada. Recarregue a página e tente de novo.")

    @app.after_request
    def cabecalhos_de_seguranca(resposta):
        """Os cabecalhos que o OWASP ZAP cobra, com o porque de cada um."""

        # Impede o navegador de adivinhar o tipo do conteudo. Sem isto, um
        # arquivo enviado como texto pode acabar executado como script.
        resposta.headers["X-Content-Type-Options"] = "nosniff"

        # Ninguem coloca a loja dentro de um iframe — defesa contra
        # clickjacking, em que um botao invisivel e sobreposto ao real.
        resposta.headers["X-Frame-Options"] = "DENY"

        # Nao vaza a URL completa (com ids de pedido) para sites externos.
        resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # A politica de conteudo. script-src 'none' e possivel porque a loja
        # nao usa JavaScript nenhum — o que torna XSS praticamente inviavel.
        # As duas excecoes sao o Google Fonts: o CSS vem de googleapis e os
        # arquivos de fonte de gstatic.
        #
        # A UNICA rota com politica diferente e /projeto-final, o relatorio
        # tecnico navegavel. Os componentes interativos dele (diagrama ER
        # clicavel, simulacao do checkout, indicadores ao vivo) precisam de
        # JavaScript, e um relatorio estatico nao demonstraria nada.
        #
        # O que a excecao libera e o que ela NAO libera:
        #
        #   script-src 'self'   -> so arquivo .js servido por este dominio.
        #                          Sem 'unsafe-inline': nao existe <script>
        #                          escrito no HTML nem onclick= na pagina,
        #                          entao conteudo injetado no HTML continua
        #                          sem poder executar. Sem 'unsafe-eval'.
        #   connect-src 'self'  -> o fetch dos indicadores so alcanca a
        #                          propria aplicacao. Um script que
        #                          vazasse dado para fora seria bloqueado.
        #
        # O resto da loja — catalogo, carrinho, checkout, painel, as rotas
        # que tocam dinheiro e sessao — continua com script-src 'none'.
        # Esta separacao esta registrada em docs/decisoes.md (D09).
        if request.path == "/projeto-final":
            resposta.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "script-src 'self'; "
                "connect-src 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'none'"
            )
        else:
            resposta.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "script-src 'none'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'none'"
            )

        # HSTS so faz sentido sobre HTTPS. Atras do proxy do Railway o
        # request.is_secure e falso, entao olhamos o cabecalho encaminhado.
        encaminhado = request.headers.get("X-Forwarded-Proto", "")
        if request.is_secure or encaminhado == "https":
            resposta.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Pagina de cliente logado nao fica em cache: em computador
        # compartilhado, o botao voltar mostraria o pedido de quem saiu.
        if session.get("cliente_id"):
            resposta.headers["Cache-Control"] = "no-store"

        return resposta

    @app.context_processor
    def injetar_contexto():
        """Cliente logado, papel e contador do carrinho, em todo template."""
        cliente = cliente_atual()
        return {
            "cliente_logado": cliente,
            # O link "Painel" no menu so existe para o gestor. Esconder o
            # link nao e a protecao — a protecao e o decorador na rota;
            # isto e so para nao oferecer ao cliente uma porta fechada.
            "gestor_logado": eh_gestor(cliente),
            "itens_no_carrinho": sum(
                linha["quantidade"] for linha in ler_carrinho()
            ),
        }

    # -----------------------------------------------------------------
    # Paginas de erro
    # -----------------------------------------------------------------
    @app.errorhandler(403)
    def pagina_403(erro):
        """Cliente logado tentando abrir o painel."""
        return render_template("erro_403.html"), 403

    @app.errorhandler(500)
    def pagina_500(erro):
        """Erro inesperado.

        O log registra o caminho e o metodo; a pagina nao mostra traceback
        nenhum. Stack trace em pagina publica entrega estrutura de
        diretorio, versao de biblioteca e, as vezes, trecho de query.
        """
        # Duas sutilezas do Flask aqui, e as duas custam o traceback:
        #
        # 1. `logger.exception` nao serve: o handler de erro roda FORA do
        #    bloco except, e registraria "NoneType: None" no lugar da
        #    pilha. Por isso o exc_info explicito.
        # 2. O que chega neste handler e um InternalServerError, que
        #    apenas EMBRULHA a falha de verdade. Registrar `erro` diria
        #    so "500 Internal Server Error"; quem interessa e a excecao
        #    original, que o Flask guarda em `original_exception`.
        causa = getattr(erro, "original_exception", None) or erro

        app.logger.error(
            "evento=erro_500 metodo=%s rota=%s causa=%s",
            request.method,
            request.path,
            type(causa).__name__,
            exc_info=causa,
        )
        if request.path == "/health" or request.path.startswith("/api/"):
            return jsonify({"erro": "Erro interno."}), 500
        return render_template("erro_500.html"), 500

    # -----------------------------------------------------------------
    # RF01 — Catalogo
    # -----------------------------------------------------------------
    @app.route("/")
    def catalogo():
        categorias = db.session.scalars(
            db.select(Categoria).order_by(Categoria.nome)
        ).all()

        consulta = db.select(Produto).order_by(Produto.nome)

        # O filtro por regiao e a consulta que justifica o
        # idx_produtos_categoria: sem indice, seq scan em produtos inteiro.
        categoria_id = request.args.get("categoria", type=int)
        if categoria_id:
            consulta = consulta.where(Produto.categoria_id == categoria_id)

        produtos = db.session.scalars(consulta).all()

        return render_template(
            "catalogo.html",
            produtos=produtos,
            categorias=categorias,
            categoria_ativa=categoria_id,
        )

    # -----------------------------------------------------------------
    # RF02 — Detalhe do produto
    # -----------------------------------------------------------------
    @app.route("/produto/<int:produto_id>")
    def produto(produto_id: int):
        # get_or_404 devolve 404 limpo em vez de estourar AttributeError
        # numa pagina de erro 500 — criterio de aceite do RF02.
        item = db.get_or_404(
            Produto, produto_id, description="Café não encontrado."
        )
        return render_template("produto.html", produto=item)

    # -----------------------------------------------------------------
    # Apresentacao do trabalho
    #
    # Nao faz parte do e-commerce: e a apresentacao da disciplina servida
    # pela propria aplicacao, para ter um endereco facil de compartilhar.
    # Feita sem JavaScript, como o resto do site — a navegacao entre os
    # slides e o proprio scroll, com scroll-snap.
    # -----------------------------------------------------------------
    @app.route("/apresentacao")
    def apresentacao():
        return render_template("apresentacao.html")

    # -----------------------------------------------------------------
    # RF04 — Cadastro, login e sessao
    # -----------------------------------------------------------------
    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "GET":
            return render_template("cadastro.html")

        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""

        if not nome or not email or not senha:
            flash("Preencha nome, e-mail e senha.", "erro")
            return render_template("cadastro.html", nome=nome, email=email)

        if len(senha) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.", "erro")
            return render_template("cadastro.html", nome=nome, email=email)

        cliente = Cliente(
            nome=nome,
            email=email,
            # A senha em texto puro morre aqui: so o hash segue para o banco.
            senha_hash=generate_password_hash(senha),
        )

        try:
            db.session.add(cliente)
            db.session.commit()
        except IntegrityError:
            # O UNIQUE de clientes.email e quem decide, nao um SELECT previo.
            # Consultar antes de inserir abriria uma janela de corrida entre
            # a checagem e o INSERT; deixar o banco recusar elimina a janela.
            db.session.rollback()
            flash("Este e-mail já tem cadastro. Tente entrar.", "erro")
            return render_template("cadastro.html", nome=nome, email=email)

        session["cliente_id"] = cliente.id
        # Token novo apos autenticar: se alguem tivesse plantado uma
        # sessao no navegador da vitima, ela deixa de valer agora.
        renovar_token_csrf()
        flash(f"Bem-vindo, {cliente.nome}.", "sucesso")
        return redirect(url_for("catalogo"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html")

        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""

        cliente = db.session.scalar(
            db.select(Cliente).where(Cliente.email == email)
        )

        # Mensagem unica para e-mail inexistente e senha errada: dizer qual
        # dos dois falhou entregaria a um atacante a lista de quem tem conta.
        if not cliente or not check_password_hash(cliente.senha_hash, senha):
            # O log registra o e-mail MASCARADO e nunca a senha. O motivo
            # ("conta inexistente" ou "senha errada") fica so aqui, no log:
            # e a informacao que permite diferenciar um cliente que errou a
            # senha de alguem varrendo e-mails, e e exatamente a informacao
            # que a tela se recusa a dar.
            app.logger.warning(
                "evento=login_falho email=%s motivo=%s origem=%s",
                mascarar_email(email),
                "conta_inexistente" if not cliente else "senha_incorreta",
                request.remote_addr or "desconhecida",
            )
            flash("E-mail ou senha inválidos.", "erro")
            return render_template("login.html", email=email)

        session["cliente_id"] = cliente.id
        renovar_token_csrf()
        flash(f"Bem-vindo de volta, {cliente.nome}.", "sucesso")

        # Só aceita destino interno: `proximo` vem da URL e um atacante
        # poderia mandar para fora do site (open redirect).
        proximo = request.args.get("proximo", "")
        if proximo.startswith("/") and not proximo.startswith("//"):
            return redirect(proximo)
        return redirect(url_for("catalogo"))

    @app.route("/sair")
    def sair():
        session.clear()
        flash("Você saiu da sua conta.", "sucesso")
        return redirect(url_for("catalogo"))

    # -----------------------------------------------------------------
    # RF03 — Carrinho
    # -----------------------------------------------------------------
    @app.route("/carrinho")
    def carrinho():
        linhas, total = carrinho_detalhado()
        return render_template("carrinho.html", linhas=linhas, total=total)

    @app.route("/carrinho/adicionar/<int:produto_id>", methods=["POST"])
    def adicionar_ao_carrinho(produto_id: int):
        produto = db.session.get(Produto, produto_id)
        if produto is None:
            flash("Este café não está mais disponível.", "erro")
            return redirect(url_for("catalogo"))

        moagem = request.form.get("moagem", "")
        if moagem not in MOAGENS_VALIDAS:
            flash("Escolha uma moagem válida.", "erro")
            return redirect(url_for("produto", produto_id=produto_id))

        try:
            quantidade = int(request.form.get("quantidade", 1))
        except ValueError:
            quantidade = 0

        if quantidade < 1:
            flash("A quantidade precisa ser pelo menos 1.", "erro")
            return redirect(url_for("produto", produto_id=produto_id))

        linhas = ler_carrinho()

        # A chave e o par (produto, moagem), nao o produto sozinho: meio
        # quilo em grao e meio quilo moido fino sao duas linhas distintas
        # do mesmo cafe. E a mesma regra da constraint
        # uq_itens_pedido_produto_moagem no banco.
        for linha in linhas:
            if linha["produto_id"] == produto_id and linha["moagem"] == moagem:
                linha["quantidade"] += quantidade
                break
        else:
            linhas.append(
                {
                    "produto_id": produto_id,
                    "quantidade": quantidade,
                    "moagem": moagem,
                }
            )

        gravar_carrinho(linhas)
        flash(f"{produto.nome} adicionado ao carrinho.", "sucesso")
        return redirect(url_for("carrinho"))

    @app.route("/carrinho/remover", methods=["POST"])
    def remover_do_carrinho():
        produto_id = request.form.get("produto_id", type=int)
        moagem = request.form.get("moagem", "")

        linhas = [
            linha
            for linha in ler_carrinho()
            if not (
                linha["produto_id"] == produto_id and linha["moagem"] == moagem
            )
        ]

        gravar_carrinho(linhas)
        flash("Item removido do carrinho.", "sucesso")
        return redirect(url_for("carrinho"))

    @app.route("/carrinho/limpar", methods=["POST"])
    def limpar_carrinho():
        gravar_carrinho([])
        flash("Carrinho esvaziado.", "sucesso")
        return redirect(url_for("carrinho"))

    # -----------------------------------------------------------------
    # RF05 — Checkout transacional
    # -----------------------------------------------------------------
    @app.route("/checkout", methods=["GET", "POST"])
    @login_obrigatorio
    def checkout():
        linhas, total = carrinho_detalhado()

        if not linhas:
            flash("Seu carrinho está vazio.", "erro")
            return redirect(url_for("catalogo"))

        if request.method == "GET":
            return render_template(
                "checkout.html", linhas=linhas, total=total
            )

        try:
            pedido = finalizar_pedido(session["cliente_id"], ler_carrinho())
        except EstoqueInsuficiente as erro:
            # O evento mais importante do log da loja. Ele responde, no
            # fim do mes, "quanta venda a gente perdeu por falta de cafe,
            # e de qual cafe" — que e a pergunta que o indicador de
            # estoque critico do painel existe para evitar.
            app.logger.warning(
                "evento=checkout_recusado motivo=estoque_insuficiente "
                "cafe=%r disponivel=%s pedido=%s cliente=%s",
                erro.nome,
                erro.disponivel,
                erro.pedido,
                session["cliente_id"],
            )
            flash(str(erro), "erro")
            return redirect(url_for("carrinho"))
        except ErroCheckout as erro:
            # A transacao ja foi desfeita dentro de finalizar_pedido. O
            # carrinho continua intacto de proposito: o cliente corrige a
            # quantidade e tenta de novo sem remontar a compra.
            app.logger.warning(
                "evento=checkout_recusado motivo=%s cliente=%s",
                type(erro).__name__,
                session["cliente_id"],
            )
            flash(str(erro), "erro")
            return redirect(url_for("carrinho"))

        gravar_carrinho([])
        flash(f"Pedido #{pedido.id} confirmado.", "sucesso")
        return redirect(url_for("meus_pedidos"))

    # -----------------------------------------------------------------
    # RF06 — Meus pedidos
    # -----------------------------------------------------------------
    @app.route("/meus-pedidos")
    @login_obrigatorio
    def meus_pedidos():
        # O filtro por cliente_id e a consulta que justifica o
        # idx_pedidos_cliente. Nunca listar sem ele: sem o WHERE, um
        # cliente veria o historico de todos os outros.
        pedidos = db.session.scalars(
            db.select(Pedido)
            .where(Pedido.cliente_id == session["cliente_id"])
            .order_by(Pedido.criado_em.desc())
        ).all()

        return render_template("meus_pedidos.html", pedidos=pedidos)

    # -----------------------------------------------------------------
    # Projeto Final — RF07: painel de indicadores (so gestor)
    # -----------------------------------------------------------------
    @app.route("/painel")
    @gestor_obrigatorio
    def painel():
        dias = normalizar_dias(request.args.get("dias"))
        dados = indicadores(dias)

        return render_template(
            "painel.html",
            d=dados,
            pedidos=executar_consulta("pedidos_recentes"),
            transicoes=TRANSICOES_PERMITIDAS,
            periodos=(7, 30, 90),
        )

    # -----------------------------------------------------------------
    # Projeto Final — RF08: atualizacao de registro
    #
    # POST, nunca GET: muda estado. Com GET, o pre-carregamento de link
    # do navegador cancelaria pedidos sozinho.
    # -----------------------------------------------------------------
    @app.route("/painel/pedidos/<int:pedido_id>/status", methods=["POST"])
    @gestor_obrigatorio
    def mudar_status_pedido(pedido_id: int):
        novo = (request.form.get("status") or "").strip().upper()
        dias = normalizar_dias(request.form.get("dias"))

        try:
            resumo = alterar_status_pedido(pedido_id, novo)
        except ErroGestao as erro:
            flash(str(erro), "erro")
            return redirect(url_for("painel", dias=dias))

        mensagem = (
            f"Pedido #{resumo['pedido_id']}: "
            f"{resumo['de']} → {resumo['para']}."
        )
        if resumo["unidades_devolvidas"]:
            mensagem += (
                f" {resumo['unidades_devolvidas']} unidade(s) "
                f"devolvida(s) ao estoque."
            )

        flash(mensagem, "sucesso")
        return redirect(url_for("painel", dias=dias))

    # -----------------------------------------------------------------
    # Projeto Final — o relatorio tecnico navegavel
    #
    # Nao faz parte do e-commerce. E a unica rota da aplicacao que
    # executa JavaScript, e o cabecalho_de_seguranca trata dela a parte.
    # Todo o texto vem de static/projeto_final/conteudo.json.
    # -----------------------------------------------------------------
    @app.route("/projeto-final")
    def projeto_final():
        return render_template("projeto_final.html")


# =====================================================================
# API JSON — Projeto Final
#
# Blueprint separado das rotas de pagina de proposito: as rotas de pagina
# devolvem HTML, redirecionam e usam `flash`; estas devolvem JSON e nunca
# redirecionam. Misturar as duas coisas na mesma funcao produz rota que
# responde HTML para o cliente de API e JSON para o navegador, dependendo
# de um cabecalho — e dificil de testar e pior de documentar.
#
# Contrato de erro, uniforme em todos os endpoints:
#
#     {"erro": "mensagem em português"}
#
# com o codigo HTTP dizendo a natureza:
#
#     400  requisicao malformada (inclui CSRF ausente no PATCH)
#     401  nao autenticado — faca login
#     403  autenticado, mas sem permissao (nao e gestor)
#     404  recurso nao existe
#     409  conflito com o estado atual (transicao de status proibida)
#     503  dependencia fora do ar (banco inacessivel no /health)
#
# A distincao entre 401 e 403 e deliberada: 401 significa "identifique-se",
# 403 significa "eu sei quem voce e e a resposta e nao". Devolver 403 para
# quem nao fez login faria o cliente de API tentar de novo com a mesma
# credencial inexistente, para sempre.
#
# Documentacao: docs/api.md, docs/openapi.yaml e a colecao do Postman em
# docs/postman_projeto_final.json.
# =====================================================================

api = Blueprint("api", __name__)


def erro_json(mensagem: str, codigo: int):
    """Resposta de erro no formato unico da API."""
    return jsonify({"erro": mensagem}), codigo


def _exigir_cliente():
    """Devolve (cliente, None) ou (None, resposta_de_erro)."""
    cliente = cliente_atual()
    if cliente is None:
        return None, erro_json(
            "Faça login para acessar este recurso.", 401
        )
    return cliente, None


def _exigir_gestor():
    """Igual ao decorador gestor_obrigatorio, mas respondendo JSON.

    Nao reaproveita o decorador porque ele redireciona para a pagina de
    login e renderiza HTML no 403 — comportamento certo para o navegador,
    errado para um cliente de API, que precisa do codigo e do corpo JSON.
    A REGRA, no entanto, e a mesma funcao: `eh_gestor`.
    """
    cliente, falha = _exigir_cliente()
    if falha:
        return None, falha

    if not eh_gestor(cliente):
        current_app.logger.warning(
            "evento=acesso_negado_painel email=%s rota=%s",
            mascarar_email(cliente.email),
            request.path,
        )
        return None, erro_json(
            "Acesso restrito ao gestor da loja.", 403
        )

    return cliente, None


def produto_em_json(produto: Produto) -> dict:
    """Um cafe, como a API o entrega.

    `preco` sai como string decimal, nunca como numero JSON — ver
    `decimal_em_texto`. `pontuacao_sca` segue a mesma regra por ser
    NUMERIC(4,2) no banco.
    """
    return {
        "id": produto.id,
        "nome": produto.nome,
        "descricao": produto.descricao,
        "preco": decimal_em_texto(produto.preco),
        "estoque": produto.estoque,
        "categoria_id": produto.categoria_id,
        "regiao": produto.categoria.regiao if produto.categoria else None,
        "categoria": produto.categoria.nome if produto.categoria else None,
        "torra": produto.torra,
        "nota_sensorial": produto.nota_sensorial,
        "pontuacao_sca": (
            f"{produto.pontuacao_sca:.2f}"
            if produto.pontuacao_sca is not None
            else None
        ),
        "peso_g": produto.peso_g,
    }


# ---------------------------------------------------------------------
# GET /health — publico
# ---------------------------------------------------------------------
@api.route("/health")
def health():
    """Diz se a aplicacao esta no ar E se ela alcanca o banco.

    O `SELECT 1` existe porque um health check que so responde "o processo
    esta vivo" mente no caso mais comum de queda: a aplicacao de pe e o
    banco inacessivel. A loja inteira depende do banco — sem ele nao ha
    catalogo, nem login, nem pedido.

    Nenhum dado de configuracao sai daqui: nem a URL do banco, nem a
    versao do servidor, nem a mensagem de erro do driver. O detalhe vai
    para o log; a resposta publica diz apenas `banco: falha`.
    """
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        current_app.logger.exception(
            "evento=health_falhou banco=%s",
            mascarar_url(current_app.config.get("SQLALCHEMY_DATABASE_URI")),
        )
        return jsonify({"status": "degradado", "banco": "falha"}), 503

    return jsonify({"status": "ok", "banco": "ok"})


# ---------------------------------------------------------------------
# GET /api/categorias — publico
# ---------------------------------------------------------------------
@api.route("/api/categorias")
def api_categorias():
    """As regioes produtoras, com a contagem de cafes de cada uma."""
    categorias = db.session.scalars(
        db.select(Categoria).order_by(Categoria.nome)
    ).all()

    return jsonify(
        {
            "total": len(categorias),
            "categorias": [
                {
                    "id": c.id,
                    "nome": c.nome,
                    "regiao": c.regiao,
                    "descricao": c.descricao,
                    "cafes": len(c.produtos),
                }
                for c in categorias
            ],
        }
    )


# ---------------------------------------------------------------------
# GET /api/produtos?categoria=<id> — publico
# ---------------------------------------------------------------------
@api.route("/api/produtos")
def api_produtos():
    """O catalogo. Mesmo filtro por categoria da pagina inicial."""
    consulta = db.select(Produto).order_by(Produto.nome)

    categoria_id = request.args.get("categoria", type=int)
    if categoria_id:
        # Mesmo filtro da home, e o mesmo indice: idx_produtos_categoria.
        consulta = consulta.where(Produto.categoria_id == categoria_id)

    produtos = db.session.scalars(consulta).all()

    return jsonify(
        {
            "total": len(produtos),
            "categoria": categoria_id,
            "produtos": [produto_em_json(p) for p in produtos],
        }
    )


# ---------------------------------------------------------------------
# GET /api/produtos/<id> — publico
# ---------------------------------------------------------------------
@api.route("/api/produtos/<int:produto_id>")
def api_produto(produto_id: int):
    produto = db.session.get(Produto, produto_id)
    if produto is None:
        return erro_json(f"Café #{produto_id} não encontrado.", 404)
    return jsonify(produto_em_json(produto))


# ---------------------------------------------------------------------
# GET /api/pedidos — cliente logado
# ---------------------------------------------------------------------
@api.route("/api/pedidos")
def api_pedidos():
    """Os pedidos DO PROPRIO cliente. Nunca os de outro.

    O filtro vem da SESSAO, nunca da URL. Se o id do cliente fosse
    parametro (`/api/pedidos?cliente=7`), bastaria trocar o numero para
    ler o historico de compras de qualquer pessoa — a falha de controle de
    acesso mais comum que existe em API REST.

    E o mesmo cuidado, e o mesmo indice (idx_pedidos_cliente), da pagina
    "Meus pedidos".
    """
    cliente, falha = _exigir_cliente()
    if falha:
        return falha

    pedidos = db.session.scalars(
        db.select(Pedido)
        .where(Pedido.cliente_id == cliente.id)
        .order_by(Pedido.criado_em.desc())
    ).all()

    return jsonify(
        {
            "cliente_id": cliente.id,
            "total": len(pedidos),
            "pedidos": [
                {
                    "id": p.id,
                    "status": p.status,
                    "total": decimal_em_texto(p.total),
                    "criado_em": p.criado_em.isoformat(timespec="seconds"),
                    "itens": [
                        {
                            "produto_id": item.produto_id,
                            "nome": item.produto.nome,
                            "quantidade": item.quantidade,
                            # O preco da epoca, nao o de hoje.
                            "preco_unitario": decimal_em_texto(
                                item.preco_unitario
                            ),
                            "moagem": item.moagem,
                            "subtotal": decimal_em_texto(item.subtotal),
                        }
                        for item in p.itens
                    ],
                }
                for p in pedidos
            ],
        }
    )


# ---------------------------------------------------------------------
# GET /api/dashboard?dias=30 — gestor
# ---------------------------------------------------------------------
@api.route("/api/dashboard")
def api_dashboard():
    """Os mesmos sete indicadores da tela /painel, em JSON.

    Mesmas consultas, mesmo arquivo SQL/dashboard.sql. A tela e esta rota
    nao podem divergir porque leem a mesma funcao `indicadores`.
    """
    _, falha = _exigir_gestor()
    if falha:
        return falha

    dias = normalizar_dias(request.args.get("dias"))
    d = indicadores(dias)

    return jsonify(
        {
            "periodo_dias": d["dias"],
            "gerado_em": d["gerado_em"].isoformat(timespec="seconds"),
            "faturamento": {
                "pedidos": d["pedidos"],
                "valor": decimal_em_texto(d["faturamento"]),
                "observacao": "Pedidos com status CANCELADO não entram.",
            },
            "ticket_medio": decimal_em_texto(d["ticket_medio"]),
            "vendas_por_regiao": [
                {
                    "regiao": linha["regiao"],
                    "pedidos": linha["pedidos"],
                    "unidades": linha["unidades"],
                    "faturamento": decimal_em_texto(linha["faturamento"]),
                    "participacao_percentual": str(linha["participacao"]),
                }
                for linha in d["vendas_por_regiao"]
            ],
            "top_cafes": [
                {
                    "id": linha["id"],
                    "nome": linha["nome"],
                    "regiao": linha["regiao"],
                    "unidades": linha["unidades"],
                    "faturamento": decimal_em_texto(linha["faturamento"]),
                    "moagem_preferida": linha["moagem_preferida"],
                }
                for linha in d["top_cafes"]
            ],
            "estoque_critico": {
                "limite": d["limite_estoque"],
                "cafes": [
                    {
                        "id": linha["id"],
                        "nome": linha["nome"],
                        "regiao": linha["regiao"],
                        "estoque": linha["estoque"],
                    }
                    for linha in d["estoque_critico"]
                ],
            },
            "pedidos_por_status": [
                {
                    "status": linha["status"],
                    "pedidos": linha["pedidos"],
                    "valor": decimal_em_texto(linha["valor"]),
                }
                for linha in d["pedidos_por_status"]
            ],
            "conciliacao": {
                "pedidos": d["conciliacao"]["pedidos"],
                "conciliados": d["conciliacao"]["conciliados"],
                "divergentes": d["conciliacao"]["divergentes"],
                "observacao": (
                    "divergentes deve ser 0: é a prova de que o checkout "
                    "atômico mantém total igual à soma dos itens."
                ),
            },
        }
    )


# ---------------------------------------------------------------------
# PATCH /api/pedidos/<id>/status — gestor
# ---------------------------------------------------------------------
@api.route("/api/pedidos/<int:pedido_id>/status", methods=["PATCH"])
def api_mudar_status(pedido_id: int):
    """Muda o status de um pedido. Mesma regra da tela do painel.

    PATCH e nao PUT porque altera um campo do recurso, nao o substitui.

    O token CSRF vai no cabecalho `X-CSRF-Token` e e verificado antes
    desta funcao, no `before_request` da aplicacao — vale para a API
    exatamente como vale para os formularios.
    """
    _, falha = _exigir_gestor()
    if falha:
        return falha

    corpo = request.get_json(silent=True) or {}
    novo = str(corpo.get("status", "")).strip().upper()

    if not novo:
        return erro_json(
            "Informe o campo 'status' no corpo JSON. "
            f"Valores aceitos: {', '.join(STATUS_VALIDOS)}.",
            400,
        )

    try:
        resumo = alterar_status_pedido(pedido_id, novo)
    except PedidoInexistente as erro:
        return erro_json(str(erro), 404)
    except TransicaoInvalida as erro:
        # 409 e nao 400: a requisicao esta bem formada e o gestor tem
        # permissao. O que impede e o ESTADO atual do pedido — e isso e
        # conflito, nao erro de sintaxe.
        return erro_json(str(erro), 409)

    return jsonify(
        {
            "pedido_id": resumo["pedido_id"],
            "status_anterior": resumo["de"],
            "status_atual": resumo["para"],
            "unidades_devolvidas_ao_estoque": resumo["unidades_devolvidas"],
        }
    )


# ---------------------------------------------------------------------
# GET /api/resumo — publico
# ---------------------------------------------------------------------
@api.route("/api/resumo")
def api_resumo():
    """Agregados publicos, para os indicadores ao vivo do /projeto-final.

    Esta rota e aberta, e por isso o que ela devolve foi escolhido com
    cuidado. Sai: contagem de pedidos no periodo, unidades vendidas,
    numero de cafes no catalogo e participacao percentual por regiao.

    NAO sai, e nao pode sair: faturamento em reais, ticket medio, nome de
    cliente, e-mail, id de pedido, nem qualquer valor que permita deduzir
    o faturamento. Participacao em PORCENTAGEM existe justamente para a
    pagina conseguir desenhar o grafico de regioes sem que o valor
    absoluto vaze — 100% de um numero desconhecido nao revela o numero.

    A conciliacao entra porque e a prova tecnica do trabalho, e so diz
    "X de X pedidos conferem" — nao revela quanto cada um vale.
    """
    dias = normalizar_dias(request.args.get("dias"))

    cabecalho = executar_consulta("faturamento", dias=dias)[0]
    regioes = _participacao(
        executar_consulta("vendas_por_regiao", dias=dias), "faturamento"
    )
    conciliacao = executar_consulta("conciliacao", dias=dias)[0]

    unidades = sum(int(linha["unidades"] or 0) for linha in regioes)
    cafes = db.session.scalar(db.select(func.count(Produto.id))) or 0

    return jsonify(
        {
            "periodo_dias": dias,
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "pedidos_no_periodo": cabecalho["pedidos"],
            "cafes_vendidos": unidades,
            "cafes_no_catalogo": cafes,
            "participacao_por_regiao": [
                {
                    "regiao": linha["regiao"],
                    "percentual": float(linha["participacao"]),
                }
                for linha in regioes
            ],
            "conciliacao": {
                "pedidos": conciliacao["pedidos"],
                "conciliados": conciliacao["conciliados"],
            },
        }
    )


app = criar_app()


if __name__ == "__main__":
    app.run(debug=True)
