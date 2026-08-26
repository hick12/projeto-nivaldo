-- =====================================================================
-- Torra & Terra — estrutura fisica do banco
-- FACAMP · Tratamento e Armazenamento da Informacao
--
-- DDL escrito a mao, executavel direto no psql:
--     psql -U torra_app -d torra_terra -f SQL/schema.sql
--
-- Este arquivo NAO e gerado por db.create_all(). As regras de negocio
-- precisam estar visiveis em SQL, nao escondidas no ORM: e o banco que
-- garante a integridade, mesmo quando o dado entra por fora da aplicacao.
-- Os modelos SQLAlchemy em app.py espelham este schema.
-- =====================================================================

-- Ordem inversa a das dependencias: quem tem FK cai primeiro.
DROP TABLE IF EXISTS itens_pedido CASCADE;
DROP TABLE IF EXISTS pedidos      CASCADE;
DROP TABLE IF EXISTS produtos     CASCADE;
DROP TABLE IF EXISTS categorias   CASCADE;
DROP TABLE IF EXISTS clientes     CASCADE;


-- ---------------------------------------------------------------------
-- categorias — as regioes produtoras
-- ---------------------------------------------------------------------
CREATE TABLE categorias (
    id        SERIAL       PRIMARY KEY,
    nome      VARCHAR(80)  NOT NULL UNIQUE,
    regiao    VARCHAR(80)  NOT NULL,
    descricao TEXT
);

-- Categoria separada de produto e a 3FN na pratica: a descricao da regiao
-- depende da regiao, nao do cafe. Repetir "Cerrado Mineiro, altitude 900m"
-- em cada um dos cafes da regiao seria redundancia por dependencia transitiva.
COMMENT ON TABLE categorias IS
    'Regioes produtoras. Separada de produtos para evitar dependencia transitiva (3FN).';


-- ---------------------------------------------------------------------
-- clientes
-- ---------------------------------------------------------------------
CREATE TABLE clientes (
    id         SERIAL        PRIMARY KEY,
    nome       VARCHAR(120)  NOT NULL,
    email      VARCHAR(160)  NOT NULL UNIQUE,
    senha_hash VARCHAR(255)  NOT NULL,
    criado_em  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- O UNIQUE acima ja impede duplicidade; este CHECK impede o dado sem
    -- sentido. Nao e validacao de e-mail completa de proposito: regex de
    -- RFC 5322 no banco custa caro e rejeita endereco valido.
    CONSTRAINT ck_clientes_email_formato
        CHECK (POSITION('@' IN email) > 1)
);

-- 255 caracteres porque o werkzeug gera hash scrypt longo (~162 chars hoje).
-- Dimensionado com folga para nao quebrar se o algoritmo padrao mudar.
COMMENT ON COLUMN clientes.senha_hash IS
    'Hash werkzeug (scrypt). A senha em texto puro nunca chega ao banco.';


-- ---------------------------------------------------------------------
-- produtos — os cafes
-- ---------------------------------------------------------------------
CREATE TABLE produtos (
    id             SERIAL         PRIMARY KEY,
    nome           VARCHAR(140)   NOT NULL,
    descricao      TEXT,
    preco          NUMERIC(10,2)  NOT NULL,
    estoque        INTEGER        NOT NULL DEFAULT 0,
    categoria_id   INTEGER        NOT NULL,
    torra          VARCHAR(10)    NOT NULL,
    nota_sensorial VARCHAR(200),
    pontuacao_sca  NUMERIC(4,2),
    peso_g         INTEGER        NOT NULL DEFAULT 250,

    CONSTRAINT fk_produtos_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id),

    -- NUMERIC e nao FLOAT: ponto flutuante binario nao representa 0,10
    -- exatamente, e o erro se acumula ao somar itens do pedido. Dinheiro
    -- exige aritmetica decimal exata.
    CONSTRAINT ck_produtos_preco       CHECK (preco >= 0),

    -- Estoque negativo nao existe no mundo fisico. Esta constraint e a
    -- ultima linha de defesa do checkout: mesmo que o SELECT ... FOR UPDATE
    -- falhe, o banco recusa a venda a descoberto.
    CONSTRAINT ck_produtos_estoque     CHECK (estoque >= 0),

    -- Regra de negocio pura: cafe especial, pela definicao da SCA, pontua
    -- 80 ou mais. Nao pode depender do formulario — se o dado entrar por
    -- um INSERT manual ou por uma futura API, a regra continua valendo.
    CONSTRAINT ck_produtos_sca         CHECK (pontuacao_sca BETWEEN 80 AND 100),

    CONSTRAINT ck_produtos_torra       CHECK (torra IN ('CLARA','MEDIA','ESCURA')),
    CONSTRAINT ck_produtos_peso        CHECK (peso_g > 0)
);


-- ---------------------------------------------------------------------
-- pedidos — o cabecalho
-- ---------------------------------------------------------------------
CREATE TABLE pedidos (
    id         SERIAL         PRIMARY KEY,
    cliente_id INTEGER        NOT NULL,
    status     VARCHAR(12)    NOT NULL DEFAULT 'CRIADO',
    total      NUMERIC(10,2)  NOT NULL DEFAULT 0,
    criado_em  TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_pedidos_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),

    CONSTRAINT ck_pedidos_status
        CHECK (status IN ('CRIADO','PAGO','ENVIADO','CANCELADO')),

    CONSTRAINT ck_pedidos_total CHECK (total >= 0)
);

-- Sem ON DELETE CASCADE de proposito: pedido e registro contabil. Apagar um
-- cliente nao pode apagar o historico de vendas — o banco recusa o DELETE
-- enquanto houver pedido, e a decisao volta para a Operacao.
COMMENT ON CONSTRAINT fk_pedidos_cliente ON pedidos IS
    'RESTRICT implicito: preserva o historico de vendas ao tentar excluir cliente.';


-- ---------------------------------------------------------------------
-- itens_pedido — entidade, nao tabela de ligacao
-- ---------------------------------------------------------------------
CREATE TABLE itens_pedido (
    id             SERIAL         PRIMARY KEY,
    pedido_id      INTEGER        NOT NULL,
    produto_id     INTEGER        NOT NULL,
    quantidade     INTEGER        NOT NULL,
    preco_unitario NUMERIC(10,2)  NOT NULL,
    moagem         VARCHAR(6)     NOT NULL,

    CONSTRAINT fk_itens_pedido
        FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,

    CONSTRAINT fk_itens_produto
        FOREIGN KEY (produto_id) REFERENCES produtos(id),

    CONSTRAINT ck_itens_quantidade CHECK (quantidade > 0),
    CONSTRAINT ck_itens_preco      CHECK (preco_unitario >= 0),
    CONSTRAINT ck_itens_moagem     CHECK (moagem IN ('GRAO','MEDIA','FINA')),

    -- O mesmo cafe pode aparecer duas vezes no pedido desde que em moagens
    -- diferentes — meio quilo em grao para o cliente moer, meio quilo fina
    -- para a prensa. O que nao pode e a mesma combinacao duplicada: isso
    -- seria falha de consolidacao do carrinho.
    CONSTRAINT uq_itens_pedido_produto_moagem
        UNIQUE (pedido_id, produto_id, moagem)
);

-- Aqui o CASCADE faz sentido: item sem pedido e orfao, nao tem significado
-- proprio. E o inverso da regra de pedidos/clientes acima.
COMMENT ON TABLE itens_pedido IS
    'Entidade de verdade, nao tabela de ligacao: carrega moagem e preco_unitario proprios.';

COMMENT ON COLUMN itens_pedido.moagem IS
    'Escolhida na compra, nao no cadastro do cafe. E o atributo que torna esta tabela uma entidade.';

-- Desnormalizacao deliberada. O preco do cafe muda (safra, cambio, reajuste);
-- o pedido antigo precisa manter o valor da epoca. Se o item lesse
-- produtos.preco, o historico se reescreveria sozinho e o total do pedido
-- deixaria de bater com a soma dos itens.
COMMENT ON COLUMN itens_pedido.preco_unitario IS
    'Congelado no momento da compra. Preserva o historico quando o preco do produto muda.';


-- =====================================================================
-- Indices
--
-- Sao apenas quatro, e cada um existe por causa de uma consulta real da
-- aplicacao. Indice acelera leitura mas encarece escrita e ocupa disco —
-- criar "por precaucao" e custo sem beneficio.
-- As evidencias de EXPLAIN antes/depois estao em SQL/consultas.sql.
-- =====================================================================

-- Catalogo: SELECT ... FROM produtos ORDER BY nome — a consulta da home,
-- a mais executada da aplicacao inteira. Sem indice, sort completo a cada visita.
CREATE INDEX idx_produtos_nome ON produtos(nome);

-- Filtro por regiao: SELECT ... FROM produtos WHERE categoria_id = ?
-- O PostgreSQL nao cria indice automatico em coluna de FK — so em PK e UNIQUE.
CREATE INDEX idx_produtos_categoria ON produtos(categoria_id);

-- Meus pedidos: SELECT ... FROM pedidos WHERE cliente_id = ? ORDER BY criado_em DESC
-- Cresce sem limite ao longo do tempo; e o indice que mais se paga no longo prazo.
CREATE INDEX idx_pedidos_cliente ON pedidos(cliente_id);

-- Detalhe do pedido: o JOIN que monta os itens de cada pedido do historico.
CREATE INDEX idx_itens_pedido ON itens_pedido(pedido_id);
