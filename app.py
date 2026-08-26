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
from decimal import Decimal
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
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

    @app.context_processor
    def injetar_contexto():
        """Deixa o cliente logado disponivel em todos os templates."""
        return {"cliente_logado": cliente_atual()}

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
            Produto, produto_id, description="Cafe nao encontrado."
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
            flash("Este e-mail ja tem cadastro. Tente entrar.", "erro")
            return render_template("cadastro.html", nome=nome, email=email)

        session["cliente_id"] = cliente.id
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
            flash("E-mail ou senha invalidos.", "erro")
            return render_template("login.html", email=email)

        session["cliente_id"] = cliente.id
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
        flash("Voce saiu da sua conta.", "sucesso")
        return redirect(url_for("catalogo"))


app = criar_app()


if __name__ == "__main__":
    app.run(debug=True)
