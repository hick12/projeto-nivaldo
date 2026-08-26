# Deploy no Railway — passo a passo

## Projeto de e-commerce · FACAMP · TAI

Objetivo final: a aplicação Flask no ar em [**https://nivaldo.felipefurlan.com.br**](https://nivaldo.felipefurlan.com.br), com PostgreSQL gerenciado, HTTPS automático e deploy a cada `git push`.

Você já tem o plano **Hobby (US$ 5/mês)**, então é só criar um projeto novo — sem custo adicional de assinatura.

> **Fique de olho no consumo.** O Hobby inclui US$ 5 de uso por mês, e o preço é por recurso: **US$ 10/GB de RAM/mês** e **US$ 20/vCPU/mês**. App pequeno \+ Postgres pequeno consomem em torno de US$ 4–5/mês. Se você já tem outros serviços rodando na conta, esse projeto novo pode estourar o crédito e virar cobrança extra. Confira em **Usage** antes e depois de subir.

---

## Antes de começar — checklist

- [ ] Código no GitHub, num repositório (pode ser privado)  
- [ ] `requirements.txt` incluindo `gunicorn` e `psycopg[binary]`  
- [ ] `Procfile` na raiz  
- [ ] `.env` no `.gitignore` (confira de novo — segredo vazado no GitHub é ponto perdido)  
- [ ] `SQL/schema.sql` e `SQL/seed.sql` prontos  
- [ ] Acesso ao painel de DNS de `felipefurlan.com.br`

**Procfile** — exatamente isto:

web: gunicorn app:app \--bind 0.0.0.0:$PORT

**A pegadinha do psycopg 3\.** O Railway entrega a `DATABASE_URL` começando com `postgresql://`, mas o SQLAlchemy com psycopg 3 espera `postgresql+psycopg://`. Sem tratar isso, o deploy sobe e quebra na primeira query. No `app.py`:

import os

url \= os.getenv("DATABASE\_URL", "postgresql://postgres:postgres@localhost:5432/ecommerce")

if url.startswith("postgres://"):          \# formato legado

    url \= url.replace("postgres://", "postgresql://", 1\)

if url.startswith("postgresql://"):

    url \= url.replace("postgresql://", "postgresql+psycopg://", 1\)

app.config\["SQLALCHEMY\_DATABASE\_URI"\] \= url

---

## Parte 1 — Criar o projeto e o banco

### 1\. Novo projeto a partir do GitHub

1. Em [railway.com](https://railway.com), clique em **New Project**  
2. Escolha **Deploy from GitHub repo**  
3. Autorize o Railway no repositório (se for a primeira vez, use **Configure GitHub App** e libere só este repo)  
4. Selecione o repositório do projeto

O Railway detecta Python pelo `requirements.txt` e começa a buildar sozinho. **O primeiro build vai falhar ou o app vai crashar** — é esperado, ainda não existe banco. Siga em frente.

### 2\. Adicionar o PostgreSQL

1. Dentro do projeto, clique em **\+ New** (ou tecle `Cmd/Ctrl + K`)  
2. **Database → Add PostgreSQL**

Aparece um segundo card no canvas. Ele já vem com `DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD` e afins.

### 3\. Ligar o app ao banco

Aqui está o pulo do gato — **não copie e cole a URL do banco**. Use uma *reference variable*, que o Railway resolve sozinho e atualiza se o banco mudar:

1. Clique no card **do app** (não no do Postgres)  
2. Aba **Variables → \+ New Variable**  
3. Nome: `DATABASE_URL` · Valor: `${{Postgres.DATABASE_URL}}`

>   
> Se o serviço de banco tiver outro nome no seu projeto, troque `Postgres` pelo nome que aparece no card.

Aproveite e adicione, na mesma tela:

| Variável | Valor |
| :---- | :---- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `SECRET_KEY` | uma string longa e aleatória — gere com o comando abaixo |
| `FLASK_ENV` | `production` |

python \-c "import secrets; print(secrets.token\_hex(32))"

Clique em **Deploy** para aplicar. O app reconstrói com as variáveis.

---

## Parte 2 — Criar as tabelas no banco de produção

O banco sobe vazio. Você precisa rodar o `schema.sql` e o `seed.sql` lá dentro. Três caminhos — o primeiro é o mais limpo.

### Opção A — Railway CLI (recomendado)

npm i \-g @railway/cli

railway login

railway link                      \# escolha o projeto e o serviço do app

railway run flask \--app app init-db

railway run flask \--app app seed-db

O `railway run` executa o comando **na sua máquina**, mas com as variáveis de ambiente do Railway injetadas — inclusive a `DATABASE_URL` de produção. É a forma mais direta de rodar migração pontual.

### Opção B — psql direto

1. Clique no card do Postgres → aba **Variables** → copie a `DATABASE_PUBLIC_URL`  
2. No seu terminal:

psql "\<cole\_a\_DATABASE\_PUBLIC\_URL\_aqui\>" \-f SQL/schema.sql

psql "\<cole\_a\_DATABASE\_PUBLIC\_URL\_aqui\>" \-f SQL/seed.sql

> Use a `DATABASE_PUBLIC_URL` (não a `DATABASE_URL`) para conectar de fora do Railway. A interna só funciona entre serviços do mesmo projeto.

### Opção C — pela interface

Card do Postgres → aba **Data** → você consegue navegar nas tabelas e rodar queries. Bom para conferir o resultado; ruim para rodar um script grande.

### Confira que funcionou

SELECT tablename FROM pg\_tables WHERE schemaname \= 'public';

SELECT COUNT(\*) FROM produtos;

---

## Parte 3 — Gerar a URL pública

1. Card do app → **Settings → Networking → Public Networking**  
2. Clique em **Generate Domain**  
3. Se ele perguntar a porta, informe a que o app escuta (o gunicorn com `$PORT` costuma ser detectado sozinho)

Você recebe algo como `ecommerce-facamp-production.up.railway.app`. **Abra e teste antes de mexer no domínio próprio** — se estiver quebrado aqui, o problema não é DNS.

Se der erro, vá em **Deployments → View Logs**. Os suspeitos de sempre:

| Sintoma no log | Causa |
| :---- | :---- |
| `ModuleNotFoundError` | falta a dependência no `requirements.txt` |
| `could not translate host name` | `DATABASE_URL` não foi setada ou a reference está com nome errado |
| `Can't load plugin: sqlalchemy.dialects:postgres` | esqueceu a normalização do `postgresql+psycopg://` |
| `relation "produtos" does not exist` | faltou rodar o `init-db` |
| app sobe e cai em loop | gunicorn não está usando `$PORT`, ou o `Procfile` está errado |

---

## Parte 4 — Apontar nivaldo.felipefurlan.com.br

### 1\. Registrar o domínio no Railway

1. Card do app → **Settings → Networking → \+ Custom Domain**  
2. Digite `nivaldo.felipefurlan.com.br`  
3. O Railway devolve **dois registros**: um `CNAME` e um `TXT`

>   
> **Os dois são obrigatórios.** Este é o erro mais comum: com o CNAME resolvendo mas o TXT faltando, o domínio responde **404**. O TXT é a verificação de propriedade.

### 2\. Criar os registros no seu DNS

Os valores exatos vêm da tela do Railway. O formato é este:

| Tipo | Nome / Host | Valor | TTL |
| :---- | :---- | :---- | :---- |
| CNAME | `nivaldo` | `xxxxxx.up.railway.app` | automático |
| TXT | (o que o Railway indicar) | (o token que o Railway indicar) | automático |

Como `nivaldo` é **subdomínio**, um CNAME comum resolve — você não esbarra na limitação de CNAME em domínio raiz.

**Se o DNS estiver no Cloudflare:** crie os registros com a nuvem **cinza (DNS only)** primeiro. A nuvem laranja durante a emissão do certificado costuma travar o processo. Depois que o site estiver no ar com HTTPS, se quiser ativar o proxy, mude o SSL/TLS para **Full (strict)** antes.

**Se estiver no Registro.br:** painel do domínio → **Editar Zona** → adicione as entradas. O campo "Nome" recebe só `nivaldo`, sem o domínio completo.

**Se estiver em outro provedor:** procure "Zona DNS" ou "Gerenciar registros". A regra é a mesma.

### 3\. Esperar

- Propagação do DNS: minutos a algumas horas  
- Certificado SSL (Let's Encrypt, renovado sozinho a cada 90 dias): **até 1 hora** depois do DNS resolver

Para acompanhar:

dig nivaldo.felipefurlan.com.br CNAME \+short

dig nivaldo.felipefurlan.com.br TXT \+short

Na tela do Railway o domínio fica com um aviso amarelo até tudo bater, e então vira verde.

---

## Parte 5 — Validação final

Antes de considerar entregue, teste tudo pela URL definitiva:

- [ ] `https://nivaldo.felipefurlan.com.br` abre com cadeado de HTTPS  
- [ ] O catálogo carrega os cafés vindos do banco  
- [ ] Dá para cadastrar e logar  
- [ ] Dá para adicionar ao carrinho escolhendo a moagem  
- [ ] O checkout grava o pedido e reduz o estoque  
- [ ] **O cenário de erro funciona:** zere o estoque de um café pelo painel e tente comprar → mensagem clara, e um `SELECT` mostra que nada foi gravado  
- [ ] "Meus pedidos" mostra o histórico com os itens  
- [ ] `git push` na main dispara um deploy novo automaticamente

Evidências para anexar na entrega:

\-- prova de que o pedido foi persistido

SELECT p.id, c.nome, p.status, p.total, p.criado\_em

FROM pedidos p JOIN clientes c ON c.id \= p.cliente\_id

ORDER BY p.criado\_em DESC LIMIT 5;

\-- prova de que os itens guardaram a moagem e o preço congelado

SELECT i.pedido\_id, pr.nome, i.quantidade, i.moagem, i.preco\_unitario

FROM itens\_pedido i JOIN produtos pr ON pr.id \= i.produto\_id

ORDER BY i.pedido\_id DESC LIMIT 10;

\-- prova de que a constraint de estoque segurou

SELECT nome, estoque FROM produtos WHERE estoque \< 5;

---

## Dicas para o dia da apresentação

**Abra a URL uns minutos antes.** No Railway o app não dorme como no Render, mas o primeiro acesso depois de um deploy novo ainda leva alguns segundos.

**Deixe um café com estoque baixo de propósito.** Ter um produto com 1 unidade em estoque te dá a demonstração do rollback pronta, sem precisar mexer no banco na frente da turma.

**Tenha o painel do Postgres aberto numa aba.** Mostrar o registro aparecendo na tabela no instante seguinte ao checkout vale mais do que qualquer slide.

**Leve um plano B.** Grave um vídeo curto de 30 segundos do fluxo funcionando. Se o Wi-Fi da sala falhar, você ainda apresenta.

---

## Depois da entrega

O projeto continua consumindo crédito enquanto estiver rodando. Quando a disciplina acabar, ou você **deleta o projeto**, ou deixa só o banco de pé e remove o serviço do app. Um app parado ainda ocupa recurso se estiver deployado.  
