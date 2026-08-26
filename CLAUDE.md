# Torra & Terra — E-commerce de café especial

Projeto acadêmico da disciplina **Tratamento e Armazenamento da Informação** (FACAMP, Prof. Nivaldo T. Marcusso). É um trabalho de **banco de dados aplicado**: a loja é o pretexto para demonstrar modelagem, constraints, transações e deploy.

## Regras que valem para o projeto inteiro

1. **Tudo em português** — tabelas, colunas, rotas, variáveis, mensagens, comentários, commits.  
2. **Stack fechada.** PostgreSQL, Python, Flask, SQLAlchemy, Jinja, psycopg 3, gunicorn, pytest, python-dotenv. Nada além disso sem me perguntar antes.  
3. **As constraints vivem no banco.** O `SQL/schema.sql` é DDL escrito à mão, completo e executável no `psql` — nunca gerado por `db.create_all()`. Os modelos SQLAlchemy espelham esse schema. O professor avalia as constraints; elas precisam estar visíveis em SQL.  
4. **Comente decisões, não o óbvio.** Um comentário explicando por que `preco_unitario` é congelado no item vale mais que dez dizendo `# insere o pedido`.  
5. **Nenhum segredo no código.** `DATABASE_URL` e `SECRET_KEY` sempre de variável de ambiente. `.env` no `.gitignore`, `.env.example` versionado.  
6. **Rode os testes e me mostre a saída real.** Nunca afirme que passou sem ter rodado.  
7. **Pare entre as etapas.** Construa na ordem definida abaixo e espere meu OK antes de seguir.

## Modelo de dados

clientes(id, nome, email UNIQUE, senha_hash, criado_em)

categorias(id, nome UNIQUE, regiao, descricao)

produtos(id, nome, descricao, preco, estoque, categoria_id FK,

         torra, nota_sensorial, pontuacao_sca, peso_g)

pedidos(id, cliente_id FK, status, total, criado_em)

itens_pedido(id, pedido_id FK, produto_id FK, quantidade,

             preco_unitario, moagem)

Constraints obrigatórias:

- PK em todas as tabelas, FK em todo relacionamento  
- `preco NUMERIC(10,2) NOT NULL CHECK (preco >= 0)` — nunca FLOAT para dinheiro  
- `estoque INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0)`  
- `pontuacao_sca NUMERIC(4,2) CHECK (pontuacao_sca BETWEEN 80 AND 100)`  
- `torra CHECK (torra IN ('CLARA','MEDIA','ESCURA'))`  
- `moagem CHECK (moagem IN ('GRAO','MEDIA','FINA'))`  
- `status CHECK (status IN ('CRIADO','PAGO','ENVIADO','CANCELADO'))`  
- `quantidade CHECK (quantidade > 0)`

Índices — só estes, cada um com comentário justificando: `idx_produtos_nome`, `idx_produtos_categoria`, `idx_pedidos_cliente`, `idx_itens_pedido`

**Por que `moagem` mora no item e não no produto:** o cliente escolhe a moagem na hora da compra. É o que faz `itens_pedido` ser uma entidade de verdade, não uma tabela de ligação. Preserve isso.

**Por que `preco_unitario` é congelado:** se o preço do café mudar amanhã, o pedido antigo mantém o valor da época.

## A transação de checkout

O coração do trabalho. Tudo-ou-nada:

BEGIN

 ├─ INSERT do pedido

 ├─ INSERT de cada item (com preco_unitario congelado)

 ├─ UPDATE do estoque

 └─ COMMIT  ·  ROLLBACK em qualquer falha

- Estoque insuficiente em qualquer item → rollback completo, nada gravado, mensagem dizendo **qual** café faltou  
- Produto inexistente → pedido não finaliza  
- `SELECT ... FOR UPDATE` ao ler o estoque, para duas compras simultâneas não venderem o mesmo lote

## Design — linguagem visual

Minimalismo quente e editorial. Muito espaço em branco, blocos modulares, hierarquia por peso de fonte e não por caixa colorida. Nada de cinza corporativo, nada de gradiente, nada de sombra pesada.

:root {

  --bg:      #faf9f7;   /* off-white quente, fundo de tudo */

  --surface: #ffffff;   /* cards */

  --ink:     #14120f;   /* quase-preto, texto principal */

  --muted:   #6b6560;   /* texto secundário */

  --line:    #e8e4de;   /* bordas — 1px, nunca mais */

  --accent:  #d4622a;   /* laranja torra: CTA, preço, destaque */

  --accent-soft: #fbf0e9;

  --r-sm: 6px;  --r-md: 10px;  --r-lg: 16px;

  --space: 8px; /* escala 8 / 16 / 24 / 40 / 64 / 96 */

}

- **Tipografia:** `Inter` (Google Fonts) para interface e corpo. `Instrument Serif` só para o nome da loja e os títulos de produto — é o toque editorial que combina com café especial. Fallback: `system-ui, sans-serif` / `Georgia, serif`.  
- **Botões:** primário sólido `--accent` com texto branco, raio `--r-md`, sem sombra. Secundário com borda `1px solid var(--line)` e fundo transparente.  
- **Cards de produto:** fundo `--surface`, borda 1px, raio `--r-lg`, padding 24px. No hover, só a borda escurece — sem levantar, sem escalar.  
- **Preço:** peso 600, cor `--accent`, sempre formatado `R$ 0,00`.  
- **Labels pequenas** (torra, região, pontuação SCA): caixa alta, 11px, letter-spacing 0.08em, cor `--muted`.  
- **Layout:** container de 1120px, grade de 3 colunas no catálogo, 1 coluna no mobile. Mobile-first de verdade — o professor pode abrir no celular.  
- CSS puro num único `static/style.css`. Sem Tailwind, sem Bootstrap, sem framework de componente.  
- Acessibilidade: contraste mínimo AA, `<label>` em todo input, foco visível.

**Não** invente logo com órbita, elipse ou esfera — essa é a identidade de outro projeto meu e não entra aqui. A marca do Torra & Terra é só o nome em `Instrument Serif`, com o "&" em `--accent`.

## Ordem de construção

1. `SQL/schema.sql` + `SQL/seed.sql` (12 cafés, 4 regiões)  
2. Modelos SQLAlchemy espelhando o schema  
3. Catálogo + detalhe do produto  
4. Cadastro, login, sessão  
5. Carrinho (com escolha de moagem)  
6. **Checkout transacional**  
7. Testes + documentação (`docs/requisitos.md`, `docs/dicionario_dados.md`, `docs/modelo_er.md` em Mermaid)

## Estrutura

├── app.py · requirements.txt · Procfile · .env.example · README.md

├── SQL/{schema,seed,consultas}.sql

├── templates/{base,catalogo,produto,carrinho,checkout,meus_pedidos}.html

├── static/style.css

├── tests/test_checkout.py

└── docs/{requisitos,dicionario_dados,modelo_er}.md

## Ambiente

`Procfile`: `web: gunicorn app:app --bind 0.0.0.0:$PORT`

O Railway entrega `DATABASE_URL` como `postgresql://`, mas o psycopg 3 precisa de `postgresql+psycopg://`. Normalize a string na inicialização do `app.py`.

Comandos: `flask --app app init-db` · `seed-db` · `reset-db`

> O guia de deploy está em `docs/deploy_railway.md`. **Ignore esse arquivo até a etapa 7 estar concluída** — ele é para o final.  
