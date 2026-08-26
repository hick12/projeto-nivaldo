# Prompt para o Claude Code — Projeto de E-commerce (FACAMP · TAI)

> **Como usar:** abra um terminal numa pasta vazia, rode `claude`, e cole o bloco inteiro abaixo (da linha `## Contexto` até o fim).  
>   
> **Guarde este arquivo.** O Prof. Nivaldo pede que o prompt usado com a IA seja entregue junto com a atividade — este `.md` já serve como esse anexo.

---

## O bloco para colar

\#\# Contexto

Sou aluno de Engenharia de Computação da FACAMP, na disciplina "Tratamento e

Armazenamento da Informação" (Prof. Nivaldo T. Marcusso). O projeto integrador

da disciplina é construir uma aplicação de e-commerce com banco de dados

relacional, do levantamento de requisitos até o deploy em cloud.

O tema escolhido pelo meu grupo é uma TORREFAÇÃO DE CAFÉ ESPECIAL — loja

online chamada "Torra & Terra", que vende cafés de origem única das regiões

produtoras brasileiras (Mogiana, Cerrado Mineiro, Sul de Minas, Chapada

Diamantina).

Esse tema foi escolhido de propósito: cada item do pedido carrega a MOAGEM

escolhida pelo cliente (grão, média, fina), que é um atributo que existe só no

item — não no produto. Isso justifica a tabela \`itens\_pedido\` como entidade de

verdade, e não como mera tabela de ligação. Preserve essa característica.

A stack é obrigatória e não pode ser trocada: PostgreSQL, Python, Flask,

SQLAlchemy, Jinja. Deploy no Railway.

\#\# O que eu quero que você construa

Um MVP funcional e completo, com o fluxo catálogo → carrinho → checkout

persistindo no PostgreSQL, pronto para rodar localmente e para subir no Railway.

\#\#\# Modelo de dados (implemente exatamente assim)

clientes(id, nome, email UNIQUE, senha\_hash, criado\_em)

categorias(id, nome UNIQUE, regiao, descricao)

produtos(id, nome, descricao, preco, estoque, categoria\_id FK,

         torra, nota\_sensorial, pontuacao\_sca, peso\_g)

pedidos(id, cliente\_id FK, status, total, criado\_em)

itens\_pedido(id, pedido\_id FK, produto\_id FK, quantidade,

             preco\_unitario, moagem)

Constraints obrigatórias — quero que elas vivam NO BANCO, não só na aplicação:

\- PRIMARY KEY em todas as tabelas; FOREIGN KEY em todo relacionamento

\- preco NUMERIC(10,2) NOT NULL CHECK (preco \>= 0\)   ← nunca FLOAT para dinheiro

\- estoque INTEGER NOT NULL DEFAULT 0 CHECK (estoque \>= 0\)

\- pontuacao\_sca NUMERIC(4,2) CHECK (pontuacao\_sca BETWEEN 80 AND 100\)

\- torra CHECK (torra IN ('CLARA','MEDIA','ESCURA'))

\- moagem CHECK (moagem IN ('GRAO','MEDIA','FINA'))

\- status CHECK (status IN ('CRIADO','PAGO','ENVIADO','CANCELADO'))

\- quantidade CHECK (quantidade \> 0\)

\- NOT NULL em todos os campos obrigatórios

Índices (só estes, e comente no código por que cada um existe):

\- idx\_produtos\_nome        → ordenação do catálogo

\- idx\_produtos\_categoria   → filtro por região

\- idx\_pedidos\_cliente      → histórico de pedidos do cliente

\- idx\_itens\_pedido         → montagem do detalhe do pedido

\#\#\# Requisitos funcionais

RF01 — Catálogo: listar produtos lendo do banco, com filtro por categoria/região

RF02 — Detalhe do produto: página com nota sensorial, torra, pontuação SCA

RF03 — Carrinho: adicionar item escolhendo quantidade E moagem; guardar na sessão

RF04 — Cadastro e login do cliente (senha com hash)

RF05 — Checkout: transformar o carrinho em pedido persistido \+ baixar o estoque

RF06 — Meus pedidos: histórico do cliente logado com os itens de cada pedido

\#\#\# O requisito mais importante: a transação de checkout

O checkout PRECISA ser uma transação real, tudo-ou-nada:

  BEGIN

   ├─ INSERT do pedido (cabeçalho)

   ├─ INSERT de cada item (gravando preco\_unitario congelado no momento da compra)

   ├─ UPDATE do estoque de cada produto

   └─ COMMIT se tudo deu certo · ROLLBACK em qualquer falha

Regras:

\- Se qualquer produto não tiver estoque suficiente, NADA é gravado — rollback

  completo e mensagem clara ao usuário dizendo qual produto faltou.

\- Se um produto do carrinho não existir mais, o pedido não é finalizado.

\- O preco\_unitario é congelado no item. Se o preço do produto mudar amanhã, o

  pedido antigo mantém o valor da época. Quero um comentário no código

  explicando essa decisão de modelagem.

\- Use SELECT ... FOR UPDATE ao ler o estoque, para evitar que duas compras

  simultâneas vendam o mesmo grão duas vezes.

\#\#\# Testes (pytest)

Escreva testes que cubram, no mínimo:

1\. Compra normal → pedido gravado, itens gravados, estoque reduzido

2\. Estoque insuficiente → rollback, nada gravado, estoque intacto

3\. Produto inexistente → pedido não finalizado

4\. Constraint do banco → tentar inserir preço negativo levanta erro

5\. Senha nunca é gravada em texto puro

\#\#\# Segurança mínima

\- Senhas só como hash (werkzeug.security)

\- DATABASE\_URL e SECRET\_KEY vindos de variável de ambiente, com .env.example

  versionado e .env no .gitignore

\- Nenhum segredo hardcoded, nenhum print de credencial em log

\- Validação tanto no formulário quanto no banco

\#\#\# Estrutura de arquivos

ecommerce\_facamp/

├── app.py                  \# config, modelos, rotas, comandos CLI

├── requirements.txt

├── Procfile                \# web: gunicorn app:app \--bind 0.0.0.0:$PORT

├── .env.example

├── .gitignore

├── README.md

├── SQL/

│   ├── schema.sql          \# DDL puro, com todas as constraints

│   ├── seed.sql            \# \~12 cafés em 4 categorias/regiões

│   └── consultas.sql       \# queries de validação e evidência

├── templates/

│   ├── base.html

│   ├── catalogo.html

│   ├── produto.html

│   ├── carrinho.html

│   ├── checkout.html

│   └── meus\_pedidos.html

├── static/style.css

├── tests/test\_checkout.py

└── docs/

    ├── requisitos.md       \# RF, RNF e critérios de aceite

    ├── dicionario\_dados.md \# campo · tipo · obrigatoriedade · regra · exemplo

    └── modelo\_er.md        \# DER em Mermaid (erDiagram)

Importante sobre o SQL/schema.sql: ele deve ser DDL escrito à mão, completo e

executável no psql — não gerado pelo \`db.create\_all()\`. O professor avalia as

constraints, então elas precisam estar visíveis em SQL, não escondidas no ORM.

Os modelos SQLAlchemy devem espelhar esse schema.

\#\#\# Comandos CLI que eu quero ter

flask \--app app init-db     \# roda schema.sql

flask \--app app seed-db     \# roda seed.sql

flask \--app app reset-db    \# dropa e recria (só para desenvolvimento)

\#\#\# Compatibilidade com o Railway

O Railway entrega a DATABASE\_URL no formato \`postgresql://...\`, mas o psycopg 3

precisa de \`postgresql+psycopg://...\`. Trate isso no app.py, normalizando a

string de conexão na inicialização. O app também precisa escutar em

0.0.0.0 na porta vinda de $PORT.

\#\# Como eu quero que você trabalhe

1\. Antes de escrever código, me mostre o plano: modelo de dados, rotas e ordem

   de implementação. Espere meu OK.

2\. Depois construa em etapas, nesta ordem, parando para eu revisar entre elas:

   schema.sql \+ seed.sql → modelos ORM → catálogo → carrinho →

   checkout transacional → testes → documentação.

3\. Rode os testes e me mostre o resultado real, não uma suposição.

4\. Comente no código as DECISÕES DE MODELAGEM, não o óbvio. Prefiro um

   comentário explicando por que preco\_unitario é congelado do que um

   comentário dizendo "\# insere o pedido".

5\. Escreva tudo em português: nomes de tabelas, colunas, rotas, mensagens e

   comentários. É um trabalho acadêmico em português.

6\. Não use bibliotecas além do necessário. Flask, SQLAlchemy, psycopg,

   gunicorn, python-dotenv, pytest. Só isso.

7\. O README precisa ter: o que é o projeto, como rodar localmente do zero,

   as variáveis de ambiente, e como rodar os testes.

Comece pelo plano.

---

## Depois que o Claude Code terminar

Coisas que **você** precisa fazer (e que valem nota), porque não dá para terceirizar:

1. **Entender o DER antes de apresentar.** Abra o `docs/modelo_er.md` e saiba explicar por que cada relacionamento é 1:N.  
2. **Rodar o cenário de erro na frente do professor.** Zere o estoque de um café e tente comprar — mostre a mensagem e mostre com um `SELECT` que nada foi gravado. É o que mais impressiona.  
3. **Tirar as evidências**: prints do catálogo, do carrinho, do checkout, e as consultas SQL de `SQL/consultas.sql` mostrando os dados no banco.  
4. **Anexar este prompt** na entrega, conforme o professor pede.

## Perguntas do slide 47 — prepare as respostas

O material lista perguntas de discussão. Com o tema café, elas ficam assim:

- **Quais campos merecem constraint no banco além da validação da aplicação?** → `pontuacao_sca BETWEEN 80 AND 100` é o exemplo perfeito: é uma regra do negócio (café especial, por definição SCA, pontua 80+) que não pode depender do formulário.  
- **Quais consultas justificam os primeiros índices?** → ordenação do catálogo por nome e o histórico de pedidos por cliente. Rode `EXPLAIN` antes e depois e leve o print.  
- **Quando um Redis faria sentido?** → carrinho persistente entre dispositivos, ou cache do catálogo. Não no MVP.  
- **Limitações do MVP?** → sem pagamento real, sem frete, sem controle de lote/validade do café (que seria a evolução natural: café tem data de torra).

