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

import os
import secrets
from decimal import Decimal
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint, func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

RAIZ = Path(__file__).resolve().parent


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


def criar_app(config_teste: dict | None = None) -> Flask:
    """Fabrica da aplicacao.

    Recebe `config_teste` para que o pytest monte a app apontando para um
    banco separado, sem tocar no banco de desenvolvimento.
    """
    app = Flask(__name__)

    url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/torra_terra",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = normalizar_url(url)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Sem valor padrao em producao: sessao assinada com chave conhecida e
    # sessao forjavel. O fallback so existe para desenvolvimento local.
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-inseguro-trocar")

    # --- Cookie de sessao ------------------------------------------------
    # HttpOnly: JavaScript nao le o cookie, entao um XSS nao rouba a sessao.
    app.config["SESSION_COOKIE_HTTPONLY"] = True

    # SameSite=Lax: o navegador nao envia o cookie em POST vindo de outro
    # site. E a primeira barreira contra CSRF, antes mesmo do token.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Secure so em producao: em desenvolvimento local o Flask roda em http
    # e um cookie Secure simplesmente nao seria enviado, quebrando o login.
    app.config["SESSION_COOKIE_SECURE"] = (
        os.getenv("FLASK_ENV", "development") == "production"
    )

    if config_teste:
        app.config.update(config_teste)

    db.init_app(app)
    registrar_comandos(app)
    registrar_rotas(app)
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
    cliente_id = session.get("cliente_id")
    if not cliente_id:
        return None
    return db.session.get(Cliente, cliente_id)


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
        # Trava sempre na mesma ordem crescente de id. Duas compras
        # simultaneas que travassem os mesmos cafes em ordens opostas
        # ficariam em deadlock, uma esperando o lock da outra; ordenar
        # elimina o ciclo antes que ele exista.
        ordenadas = sorted(linhas_carrinho, key=lambda l: l["produto_id"])

        # --- Fase 1: travar e validar TODOS os itens -------------------
        #
        # Nada e inserido antes desta fase terminar. Assim o caso de erro
        # nao chega sequer a criar o cabecalho do pedido — o rollback
        # continua sendo obrigatorio, mas o banco trabalha menos.
        travados = []
        for linha in ordenadas:
            # with_for_update() gera o SELECT ... FOR UPDATE: segura a linha
            # do produto ate o fim da transacao. Sem isso, duas compras
            # simultaneas leem o mesmo estoque 1, ambas aprovam, e o mesmo
            # lote e vendido duas vezes.
            produto = db.session.scalar(
                db.select(Produto)
                .where(Produto.id == linha["produto_id"])
                .with_for_update()
            )

            if produto is None:
                raise ProdutoInexistente(
                    "Um dos cafés do seu carrinho não está mais disponível. "
                    "Revise o carrinho e tente de novo."
                )

            if produto.estoque < linha["quantidade"]:
                raise EstoqueInsuficiente(
                    produto.nome, produto.estoque, linha["quantidade"]
                )

            travados.append((produto, linha))

        # --- Fase 2: gravar -------------------------------------------
        pedido = Pedido(
            cliente_id=cliente_id, status="CRIADO", total=Decimal("0")
        )
        db.session.add(pedido)

        # flush envia o INSERT e recebe o id gerado pela sequence, sem
        # encerrar a transacao. O commit continua sendo o unico ponto em
        # que algo se torna definitivo.
        db.session.flush()

        total = Decimal("0")
        for produto, linha in travados:
            db.session.add(
                ItemPedido(
                    pedido_id=pedido.id,
                    produto_id=produto.id,
                    quantidade=linha["quantidade"],
                    # Congelado aqui, e so aqui. Se o preco deste cafe mudar
                    # amanha, este pedido mantem o valor de hoje.
                    preco_unitario=produto.preco,
                    moagem=linha["moagem"],
                )
            )
            produto.estoque -= linha["quantidade"]
            total += produto.preco * linha["quantidade"]

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


# =====================================================================
# Rotas
# =====================================================================

def registrar_rotas(app: Flask) -> None:
    app.jinja_env.filters["brl"] = formatar_brl

    # Disponivel em todo template como {{ token_csrf() }}
    app.jinja_env.globals["token_csrf"] = token_csrf

    @app.before_request
    def exigir_token_csrf():
        """Barra qualquer escrita sem token valido, antes de tocar no banco."""
        if request.method not in METODOS_QUE_ESCREVEM:
            return

        enviado = request.form.get("_csrf", "")
        esperado = session.get("_csrf", "")

        # compare_digest em vez de ==: comparacao de tempo constante, para
        # nao vazar o token caractere a caractere pelo tempo de resposta.
        if not esperado or not secrets.compare_digest(enviado, esperado):
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
        """Cliente logado e contador do carrinho, disponiveis em todo template."""
        return {
            "cliente_logado": cliente_atual(),
            "itens_no_carrinho": sum(
                linha["quantidade"] for linha in ler_carrinho()
            ),
        }

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
        except ErroCheckout as erro:
            # A transacao ja foi desfeita dentro de finalizar_pedido. O
            # carrinho continua intacto de proposito: o cliente corrige a
            # quantidade e tenta de novo sem remontar a compra.
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


app = criar_app()


if __name__ == "__main__":
    app.run(debug=True)
