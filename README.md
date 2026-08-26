# Torra &amp; Terra

E-commerce de café especial em Flask + PostgreSQL.

Projeto integrador da disciplina **Tratamento e Armazenamento da Informação** —
FACAMP, Prof. Nivaldo T. Marcusso.

A loja é o pretexto. O que o projeto demonstra é **modelagem relacional,
constraints no banco, transação atômica e deploy em cloud**.

![Print do projeto](2026-08-26-195256.jpg)

---

## O que ele faz

Catálogo de 12 cafés de origem única em 4 regiões produtoras brasileiras. O
cliente filtra por região, escolhe **quantidade e moagem**, monta o carrinho,
se cadastra e finaliza a compra. O checkout grava o pedido, grava os itens e
baixa o estoque — os três dentro de uma transação única.

**Por que café especial:** cada item do pedido carrega a moagem escolhida na
compra — grão, média ou fina. É um atributo que existe só no item, nunca no
produto. É o que faz `itens_pedido` ser uma entidade de verdade, e não uma
tabela de ligação.

---

## Stack

PostgreSQL 17 · Python 3.11 · Flask · SQLAlchemy · Jinja · psycopg 3 ·
gunicorn · pytest · python-dotenv

CSS puro, sem framework. Deploy no Railway.

---

## Rodar localmente, do zero

### 1. Pré-requisitos

PostgreSQL rodando e Python 3.11+.

No Windows o `psql` costuma não estar no `PATH`. Ele fica em
`C:\Program Files\PostgreSQL\17\bin`.

### 2. Clonar e instalar

```bash
git clone https://github.com/hick12/projeto-nivaldo.git
```

```bash
cd projeto-nivaldo && python -m venv .venv
```

Ative o ambiente — `.venv\Scripts\activate` no Windows,
`source .venv/bin/activate` no Linux e no macOS. Depois:

```bash
pip install -r requirements.txt
```

### 3. Criar o banco e o usuário da aplicação

```bash
psql -U postgres -f SQL/usuario_app.sql
```

Isso cria o papel `torra_app` e o banco `torra_terra`. **Troque a senha
dentro do arquivo antes de rodar.**

> A aplicação usa usuário próprio, nunca o superusuário `postgres`. O
> superusuário pode dropar qualquer coisa no cluster inteiro; um bug rodando
> com ele é catastrófico e irreversível.

Crie também o banco de testes:

```bash
psql -U postgres -c "CREATE DATABASE torra_terra_teste OWNER torra_app"
```

### 4. Configurar as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com a senha que você escolheu. Gere a `SECRET_KEY` com:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

O `.env` está no `.gitignore` e **nunca** vai para o repositório.

### 5. Criar as tabelas e carregar o catálogo

```bash
flask --app app reset-db
```

Ou em dois passos: `flask --app app init-db` (roda o `schema.sql`) e
`flask --app app seed-db` (roda o `seed.sql`).

### 6. Subir

```bash
flask --app app run --debug
```

A loja abre em `http://localhost:5000`.

---

## Variáveis de ambiente

| Variável | Obrigatória | Para que serve |
|---|:---:|---|
| `DATABASE_URL` | sim | Conexão com o PostgreSQL. Aceita `postgres://`, `postgresql://` ou `postgresql+psycopg://` — o `app.py` normaliza |
| `SECRET_KEY` | sim | Assina o cookie de sessão. Sem uma chave forte, a sessão é forjável |
| `TEST_DATABASE_URL` | não | Banco dos testes. Sem ela, usa a `DATABASE_URL` com sufixo `_teste` |
| `FLASK_ENV` | não | `development` ou `production` |

---

## Testes

```bash
pytest -v
```

Os testes rodam contra um **PostgreSQL de verdade**, não SQLite: o
`SELECT ... FOR UPDATE` e as constraints `CHECK` do schema são justamente o
que precisa ser testado, e o SQLite trata os dois de forma diferente.

O que está coberto:

| Caso | O que prova |
|---|---|
| Compra normal | Pedido gravado, itens gravados, estoque reduzido |
| Estoque insuficiente | Rollback completo, nada gravado, estoque intacto, mensagem nomeando o café |
| Produto inexistente | Pedido não é finalizado |
| Preço negativo | A constraint do **banco** recusa, não só a aplicação |
| Estoque negativo | Idem |
| Pontuação SCA fora de 80–100 | Idem |
| Moagem inválida | Idem |
| Senha | Nunca gravada em texto puro |
| Mesmo café, duas moagens | Vira duas linhas — `itens_pedido` é entidade |
| Preço congelado | Reajuste do produto não altera pedido antigo |

---

## Comandos disponíveis

| Comando | O que faz |
|---|---|
| `flask --app app init-db` | Cria a estrutura a partir do `SQL/schema.sql` |
| `flask --app app seed-db` | Carrega os 12 cafés do `SQL/seed.sql` |
| `flask --app app reset-db` | Dropa, recria e recarrega. Só para desenvolvimento |

---

## Backup e restauração

Backup só é confiável quando a restauração também é testada.

### Backup lógico

```bash
pg_dump -U torra_app -d torra_terra -F c -f backup_torra_terra.dump
```

O `-F c` gera formato *custom*, comprimido e restaurável seletivamente. Para
um `.sql` legível, use `-F p` — útil para inspecionar o DDL gerado.

Só a estrutura, sem dados:

```bash
pg_dump -U torra_app -d torra_terra --schema-only -f estrutura.sql
```

Só os dados, sem estrutura:

```bash
pg_dump -U torra_app -d torra_terra --data-only -f dados.sql
```

### Restauração

Em um banco novo, para não sobrescrever o original enquanto testa:

```bash
psql -U postgres -c "CREATE DATABASE torra_terra_restaurado OWNER torra_app"
```

```bash
pg_restore -U torra_app -d torra_terra_restaurado backup_torra_terra.dump
```

### Verificar que a restauração funcionou

Compare as contagens entre origem e destino. Os números precisam bater:

```bash
psql -U torra_app -d torra_terra_restaurado -c "SELECT (SELECT COUNT(*) FROM produtos) AS produtos, (SELECT COUNT(*) FROM pedidos) AS pedidos, (SELECT COUNT(*) FROM itens_pedido) AS itens;"
```

### Backup do banco de produção

O Railway expõe uma `DATABASE_PUBLIC_URL` para conexão externa:

```bash
pg_dump "<DATABASE_PUBLIC_URL>" -F c -f backup_producao.dump
```

> Use a `DATABASE_PUBLIC_URL`, não a `DATABASE_URL`. A interna só funciona
> entre serviços do mesmo projeto Railway.

---

## Estrutura

```
├── app.py                  configuração, modelos, rotas e CLI
├── requirements.txt · Procfile · .env.example · .gitignore
├── CLAUDE.md               briefing do projeto
├── SQL/
│   ├── schema.sql          DDL à mão, com todas as constraints
│   ├── seed.sql            12 cafés em 4 regiões
│   ├── usuario_app.sql     papel dedicado da aplicação
│   └── consultas.sql       validação, evidências e EXPLAIN
├── templates/              base, catálogo, produto, cadastro, login,
│                           carrinho, checkout, meus_pedidos
├── static/style.css
├── tests/                  conftest.py e test_checkout.py
└── docs/
    ├── requisitos.md       RF, RNF, critérios de aceite, backlog, fluxo
    ├── modelo_er.md        DER em Mermaid + normalização 1FN/2FN/3FN
    ├── dicionario_dados.md campo · tipo · regra · exemplo
    ├── evidencias.md       saídas reais dos testes e das consultas
    ├── decisoes.md         escolhas de projeto justificadas
    ├── perguntas_defesa.md as 6 perguntas do slide 47
    ├── prompt_ia.md        prompt usado com a IA (anexo da entrega)
    └── deploy_railway.md   passo a passo do deploy
```

---

## Segurança

- Senhas apenas como **hash scrypt** (`werkzeug.security`). A senha em texto
  puro nunca chega ao banco
- `DATABASE_URL` e `SECRET_KEY` vêm de variável de ambiente. Nenhum segredo
  no código-fonte
- `.env` no `.gitignore`, `.env.example` versionado
- A aplicação conecta com **usuário próprio** do PostgreSQL, não o superusuário
- Validação no formulário **e** no banco — a constraint é a que vale
- Login com credencial errada devolve mensagem única, sem revelar se o erro
  foi no e-mail ou na senha
- O redirecionamento pós-login só aceita destino interno, para não virar um
  *open redirect*

---

## Limitações conhecidas do MVP

Sem pagamento real, sem frete, sem controle de lote e data de torra, sem área
administrativa e sem relatórios. O carrinho vive na sessão e não sobrevive à
troca de dispositivo.

Todas documentadas com o motivo em [`docs/requisitos.md`](docs/requisitos.md),
seção 8.

---

## Deploy

O guia completo está em [`docs/deploy_railway.md`](docs/deploy_railway.md).

A escolha do Railway em vez do Render + Neon sugeridos no material está
justificada em [`docs/decisoes.md`](docs/decisoes.md), decisão D01.
