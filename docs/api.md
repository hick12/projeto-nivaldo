# API JSON — Projeto Final

Torra & Terra · FACAMP · Tratamento e Armazenamento da Informação
Professor: Nivaldo T. Marcusso · Grupo 3

Base em produção: `https://nivaldo.felipefurlan.com.br`
Base local: `http://localhost:5000`

Especificação formal: [`openapi.yaml`](openapi.yaml) ·
Coleção do Postman: [`postman_projeto_final.json`](postman_projeto_final.json)

---

## Por que existe uma API aqui

A loja é renderizada no servidor e não precisaria de API para funcionar. Ela
existe por três razões concretas:

1. O site do Projeto Final (`/projeto-final`) lê `GET /api/resumo` e mostra
   indicadores **ao vivo**, do banco de produção. Sem isso o relatório
   navegável seria uma página estática afirmando números — e o manual é
   explícito em não aceitar mockup apresentado como tela implementada.
2. `GET /health` é o que um monitor externo consulta para saber se a loja
   está no ar **e alcançando o banco**.
3. Os mesmos indicadores do painel ficam disponíveis em JSON para quem
   quiser levá-los a uma planilha, sem precisar raspar HTML.

---

## Convenções

**Formato.** Todas as respostas são JSON com `Content-Type:
application/json`. Erros têm sempre a mesma forma:

```json
{"erro": "mensagem em português"}
```

**Dinheiro é string, nunca número.** `"preco": "148.00"`, não
`"preco": 148.0`. Um número JSON é um float IEEE 754 — exatamente o tipo
que o projeto rejeitou no banco por não representar 0,10 de forma exata.
Quem consome recebe o valor íntegro e decide como somar. A mesma regra vale
para `pontuacao_sca`, que é `NUMERIC(4,2)` no banco.

**Datas em ISO 8601**, com segundos: `"2026-11-24T23:12:16"`.

**Códigos de status**

| Código | Quando |
|:---:|---|
| `200` | Deu certo |
| `400` | Requisição malformada — inclui token CSRF ausente no `PATCH` |
| `401` | Não autenticado. Faça login |
| `403` | Autenticado, mas sem permissão (não é gestor) |
| `404` | O recurso não existe |
| `409` | Conflito com o estado atual — transição de status proibida |
| `500` | Erro interno. O detalhe vai para o log, não para a resposta |
| `503` | Dependência fora do ar, ou aplicação sem configuração |

A diferença entre **401 e 403** é deliberada. `401` significa
"identifique-se"; `403` significa "eu sei quem você é, e a resposta é não".
Devolver 403 para quem não fez login faria o cliente tentar de novo com a
mesma credencial inexistente, para sempre.

**Autenticação.** Por cookie de sessão, o mesmo da loja — não há token de
API. Faça `POST /login` com o formulário e o navegador (ou o Postman, que
guarda cookies) mantém a sessão. É coerente com o escopo: a API serve a
própria aplicação e o gestor, não integrações de terceiros.

---

## Resumo dos endpoints

| Método e rota | Acesso | O que devolve |
|---|---|---|
| `GET /health` | público | Estado da aplicação e do banco |
| `GET /api/categorias` | público | As regiões produtoras |
| `GET /api/produtos` | público | O catálogo, com filtro opcional por categoria |
| `GET /api/produtos/<id>` | público | Um café |
| `GET /api/pedidos` | cliente logado | **Só os pedidos do próprio cliente** |
| `GET /api/dashboard` | gestor | Os sete indicadores do painel |
| `PATCH /api/pedidos/<id>/status` | gestor | Muda o status de um pedido |
| `GET /api/resumo` | público | Agregados que não expõem ninguém |

---

## `GET /health`

Público. Diz se a aplicação está de pé **e se ela alcança o banco**.

O `SELECT 1` não é enfeite: um health check que só responde "o processo está
vivo" mente no caso mais comum de queda — aplicação de pé e banco
inacessível. A loja inteira depende do banco; sem ele não há catálogo, nem
login, nem pedido.

```bash
curl -s https://nivaldo.felipefurlan.com.br/health
```

```json
{
  "banco": "ok",
  "status": "ok"
}
```

Com o banco inacessível, **503**:

```json
{
  "banco": "falha",
  "status": "degradado"
}
```

Nenhum detalhe de configuração sai daqui: nem a URL do banco, nem a versão
do servidor, nem a mensagem do driver. Isso vai para o log.

Se a aplicação subir **sem** `SECRET_KEY` ou `DATABASE_URL` em produção, a
resposta também é 503, e nomeia o que falta — só o **nome** da variável:

```json
{
  "erro": "Aplicação sem configuração completa.",
  "variaveis_ausentes": ["SECRET_KEY"]
}
```

---

## `GET /api/categorias`

Público. As quatro regiões produtoras, com a contagem de cafés de cada uma.

```bash
curl -s https://nivaldo.felipefurlan.com.br/api/categorias
```

```json
{
  "total": 4,
  "categorias": [
    {
      "id": 2,
      "nome": "Cerrado Mineiro",
      "regiao": "Minas Gerais",
      "descricao": "Primeira denominacao de origem do cafe brasileiro. Estacoes bem definidas e colheita uniforme. Corpo aveludado, doce de caramelo e acidez baixa.",
      "cafes": 3
    },
    {
      "id": 4,
      "nome": "Chapada Diamantina",
      "regiao": "Bahia",
      "descricao": "Altitudes acima de 1.000 m no semiarido baiano. Amplitude termica alta e maturacao lenta. Acidez citrica marcante e aroma floral.",
      "cafes": 3
    }
  ]
}
```

> `nome` é a denominação de origem e `regiao` é o estado. Duas categorias
> ficam em Minas Gerais — Cerrado Mineiro e Sul de Minas. Os indicadores que
> agrupam por `regiao` somam as duas.

---

## `GET /api/produtos`

Público. O catálogo inteiro, ordenado por nome.

**Parâmetro de consulta**

| Nome | Tipo | Padrão | Para que serve |
|---|---|---|---|
| `categoria` | inteiro | — | Filtra por `categoria_id`. Mesmo filtro da home, e o mesmo índice `idx_produtos_categoria` |

```bash
curl -s "https://nivaldo.felipefurlan.com.br/api/produtos?categoria=4"
```

```json
{
  "total": 3,
  "categoria": 4,
  "produtos": [
    {
      "id": 11,
      "nome": "Chapada Geisha",
      "descricao": "Variedade Geisha adaptada a Bahia. Sete anos de lavoura para chegar a este perfil. O cafe mais premiado da casa.",
      "preco": "148.00",
      "estoque": 1,
      "categoria_id": 4,
      "categoria": "Chapada Diamantina",
      "regiao": "Bahia",
      "torra": "CLARA",
      "nota_sensorial": "Bergamota, jasmim, pessego branco, cha preto",
      "pontuacao_sca": "91.00",
      "peso_g": 250
    }
  ]
}
```

Uma `categoria` inexistente devolve `200` com lista vazia, não 404: a
consulta é válida e o resultado é "nenhum café". 404 aqui diria que a *rota*
não existe.

---

## `GET /api/produtos/<id>`

Público. Um café. O mesmo objeto do catálogo, sem o envelope.

```bash
curl -s https://nivaldo.felipefurlan.com.br/api/produtos/11
```

```json
{
  "id": 11,
  "nome": "Chapada Geisha",
  "descricao": "Variedade Geisha adaptada a Bahia. Sete anos de lavoura para chegar a este perfil. O cafe mais premiado da casa.",
  "preco": "148.00",
  "estoque": 1,
  "categoria_id": 4,
  "categoria": "Chapada Diamantina",
  "regiao": "Bahia",
  "torra": "CLARA",
  "nota_sensorial": "Bergamota, jasmim, pessego branco, cha preto",
  "pontuacao_sca": "91.00",
  "peso_g": 250
}
```

**404** quando não existe:

```json
{"erro": "Café #9999 não encontrado."}
```

---

## `GET /api/pedidos`

**Exige cliente logado.** Devolve os pedidos **do próprio cliente**, com os
itens de cada um.

O filtro vem da **sessão**, nunca da URL. Se o id do cliente fosse
parâmetro — `/api/pedidos?cliente=7` — bastaria trocar o número para ler o
histórico de compras de qualquer pessoa. É a falha de controle de acesso
mais comum em API REST, e o teste
`test_pedidos_nunca_devolve_pedido_de_outro_cliente` existe para travá-la.

```bash
curl -s -b cookies.txt https://nivaldo.felipefurlan.com.br/api/pedidos
```

```json
{
  "cliente_id": 3,
  "total": 1,
  "pedidos": [
    {
      "id": 17,
      "status": "ENVIADO",
      "total": "267.00",
      "criado_em": "2026-11-18T14:31:00",
      "itens": [
        {
          "produto_id": 10,
          "nome": "Piata Altitude",
          "quantidade": 2,
          "preco_unitario": "89.00",
          "moagem": "GRAO",
          "subtotal": "178.00"
        },
        {
          "produto_id": 10,
          "nome": "Piata Altitude",
          "quantidade": 1,
          "preco_unitario": "89.00",
          "moagem": "FINA",
          "subtotal": "89.00"
        }
      ]
    }
  ]
}
```

> Repare nas duas linhas do **mesmo** café no mesmo pedido, separadas pela
> `moagem`. É o que faz `itens_pedido` ser uma entidade e não uma tabela de
> ligação. E `preco_unitario` é o preço **da época da compra**, não o de
> hoje.

**401** sem sessão:

```json
{"erro": "Faça login para acessar este recurso."}
```

---

## `GET /api/dashboard`

**Exige gestor** — cliente logado cujo e-mail está em `ADMIN_EMAILS`.

Os mesmos sete indicadores da tela `/painel`, pelas mesmas consultas de
`SQL/dashboard.sql`. A tela e esta rota não podem divergir porque chamam a
mesma função.

**Parâmetro de consulta**

| Nome | Tipo | Padrão | Para que serve |
|---|---|---|---|
| `dias` | inteiro | `30` | Janela do período. Limitado a 1–365; valor inválido cai no padrão |

> O teto de 365 não é capricho: `?dias=99999999` faria o planejador
> desprezar o índice e varrer `pedidos` inteiro — um jeito barato de
> derrubar o painel pela URL.

```bash
curl -s -b cookies.txt \
  "https://nivaldo.felipefurlan.com.br/api/dashboard?dias=30"
```

```json
{
  "periodo_dias": 30,
  "gerado_em": "2026-11-24T23:12:16",
  "faturamento": {
    "pedidos": 34,
    "valor": "7571.00",
    "observacao": "Pedidos com status CANCELADO não entram."
  },
  "ticket_medio": "222.68",
  "vendas_por_regiao": [
    {
      "regiao": "Minas Gerais",
      "pedidos": 28,
      "unidades": 66,
      "faturamento": "4513.00",
      "participacao_percentual": "59.6"
    },
    {
      "regiao": "Bahia",
      "pedidos": 12,
      "unidades": 20,
      "faturamento": "1618.00",
      "participacao_percentual": "21.4"
    },
    {
      "regiao": "Sao Paulo",
      "pedidos": 12,
      "unidades": 23,
      "faturamento": "1440.00",
      "participacao_percentual": "19.0"
    }
  ],
  "top_cafes": [
    {
      "id": 4,
      "nome": "Alta Mogiana do Cerrado",
      "regiao": "Minas Gerais",
      "unidades": 17,
      "faturamento": "1156.00",
      "moagem_preferida": "MEDIA"
    }
  ],
  "estoque_critico": {
    "limite": 5,
    "cafes": [
      {"id": 11, "nome": "Chapada Geisha", "regiao": "Bahia", "estoque": 1},
      {"id": 5, "nome": "Vereda do Cerrado", "regiao": "Minas Gerais", "estoque": 5}
    ]
  },
  "pedidos_por_status": [
    {"status": "CRIADO",    "pedidos": 4,  "valor": "741.00"},
    {"status": "PAGO",      "pedidos": 6,  "valor": "1113.00"},
    {"status": "ENVIADO",   "pedidos": 24, "valor": "5717.00"},
    {"status": "CANCELADO", "pedidos": 6,  "valor": "818.00"}
  ],
  "conciliacao": {
    "pedidos": 40,
    "conciliados": 40,
    "divergentes": 0,
    "observacao": "divergentes deve ser 0: é a prova de que o checkout atômico mantém total igual à soma dos itens."
  }
}
```

**`conciliacao.divergentes` é o indicador central do trabalho.** Ele conta
os pedidos cujo `total` difere da soma de `quantidade × preco_unitario` dos
itens. Precisa dar zero, sempre — e é a medida direta da dor do contexto
escolhido, "falhas de confirmação e de conciliação".

**401** sem sessão · **403** logado mas sem ser gestor:

```json
{"erro": "Acesso restrito ao gestor da loja."}
```

---

## `PATCH /api/pedidos/<id>/status`

**Exige gestor.** Muda o status de um pedido. Mesma regra da tela do painel,
porque é a mesma função.

`PATCH` e não `PUT` porque altera **um campo** do recurso, não o substitui.

**Transições permitidas**

```
CRIADO ──> PAGO ──> ENVIADO
   │         │
   └──> CANCELADO <┘
```

`ENVIADO` e `CANCELADO` são terminais. Não existe "des-enviar" um pedido que
já saiu, e não existe ressuscitar um cancelado: o cancelamento devolveu o
estoque, e reabrir o pedido venderia de novo um café que pode já ter sido
vendido a outra pessoa.

**Cancelar devolve o estoque** dos itens, na mesma transação que muda o
status, com `SELECT ... FOR UPDATE` nos produtos — igual ao checkout. Ou as
duas coisas acontecem, ou nenhuma.

**Cabeçalhos obrigatórios**

| Cabeçalho | Valor |
|---|---|
| `Content-Type` | `application/json` |
| `X-CSRF-Token` | O token da sessão |

> O token CSRF é o mesmo dos formulários da loja, só muda o envelope.
> Aceitar o cabeçalho **não** enfraquece os formulários: a exigência
> continua sendo provar que você conhece um segredo que vive na sessão e que
> outro site não consegue ler. Se qualquer coisa, o cabeçalho é mais
> restritivo — um formulário HTML de outro site consegue fazer POST com
> campos arbitrários, mas não consegue definir cabeçalho customizado sem
> passar pelo CORS.
>
> Para obter o token: faça `GET /login` e leia o `value` do campo
> `name="_csrf"` no HTML. A coleção do Postman já faz isso num script de
> pré-requisição.

**Corpo**

```json
{"status": "PAGO"}
```

```bash
curl -s -X PATCH \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"status":"PAGO"}' \
  https://nivaldo.felipefurlan.com.br/api/pedidos/17/status
```

**200**

```json
{
  "pedido_id": 17,
  "status_anterior": "CRIADO",
  "status_atual": "PAGO",
  "unidades_devolvidas_ao_estoque": 0
}
```

Num cancelamento, `unidades_devolvidas_ao_estoque` traz quantas unidades
voltaram ao saldo:

```json
{
  "pedido_id": 23,
  "status_anterior": "PAGO",
  "status_atual": "CANCELADO",
  "unidades_devolvidas_ao_estoque": 3
}
```

**Erros**

| Código | Situação | Corpo |
|:---:|---|---|
| `400` | Sem `X-CSRF-Token` | `{"erro": "Token CSRF ausente ou inválido. Envie o cabeçalho X-CSRF-Token."}` |
| `400` | Sem o campo `status` | `{"erro": "Informe o campo 'status' no corpo JSON. Valores aceitos: CRIADO, PAGO, ENVIADO, CANCELADO."}` |
| `401` | Sem sessão | `{"erro": "Faça login para acessar este recurso."}` |
| `403` | Logado, não gestor | `{"erro": "Acesso restrito ao gestor da loja."}` |
| `404` | Pedido não existe | `{"erro": "Pedido #9999 não encontrado."}` |
| `409` | Transição proibida | `{"erro": "Não é possível ir de CRIADO para ENVIADO. De CRIADO só dá para ir para PAGO ou CANCELADO."}` |
| `409` | Estado final | `{"erro": "O pedido #1 está em ENVIADO, que é um estado final. Não há mudança possível a partir dele."}` |

**Por que 409 e não 400** na transição proibida: a requisição está bem
formada e o gestor tem permissão. O que impede é o **estado atual** do
pedido — isso é conflito, não erro de sintaxe. Um cliente que receba 400
tende a corrigir o corpo; um que receba 409 sabe que precisa reler o estado.

---

## `GET /api/resumo`

Público. Só agregados — é o endpoint que alimenta os indicadores ao vivo do
site do Projeto Final.

**Esta rota é aberta, e o que ela devolve foi escolhido com cuidado.**

| Sai | Não sai, e não pode sair |
|---|---|
| Contagem de pedidos no período | Faturamento em reais |
| Unidades vendidas | Ticket médio |
| Cafés no catálogo | Nome ou e-mail de cliente |
| Participação por região, em **%** | Id de pedido |
| Conciliação, como "X de X" | Qualquer valor que permita deduzir o faturamento |

A participação sai em **porcentagem** justamente para a página conseguir
desenhar o gráfico de regiões sem vazar valor absoluto: 100% de um número
desconhecido não revela o número. A conciliação entra porque é a prova
técnica do trabalho, e só diz quantos pedidos conferem — não quanto cada um
vale.

```bash
curl -s https://nivaldo.felipefurlan.com.br/api/resumo
```

```json
{
  "periodo_dias": 30,
  "gerado_em": "2026-11-24T23:12:16",
  "pedidos_no_periodo": 34,
  "cafes_vendidos": 109,
  "cafes_no_catalogo": 12,
  "participacao_por_regiao": [
    {"regiao": "Minas Gerais", "percentual": 59.6},
    {"regiao": "Bahia",        "percentual": 21.4},
    {"regiao": "Sao Paulo",    "percentual": 19.0}
  ],
  "conciliacao": {"pedidos": 40, "conciliados": 40}
}
```

Aceita o mesmo parâmetro `dias` do dashboard, com os mesmos limites.

---

## Verificação rápida de ponta a ponta

O que deve acontecer em produção, sem login:

```bash
curl -s -o /dev/null -w "%{http_code} %{url_effective}\n" \
  https://nivaldo.felipefurlan.com.br/health \
  https://nivaldo.felipefurlan.com.br/api/categorias \
  https://nivaldo.felipefurlan.com.br/api/produtos \
  https://nivaldo.felipefurlan.com.br/api/resumo \
  https://nivaldo.felipefurlan.com.br/api/dashboard
```

Os quatro primeiros devem dar `200`. O último, **`401`** — é o controle de
acesso funcionando.

---

## Limitações, declaradas

- **Sem paginação.** `GET /api/produtos` devolve o catálogo inteiro, que tem
  12 itens. Com algumas centenas, `?pagina=` e `?por_pagina=` passariam a
  ser necessários.
- **Sem versionamento na URL.** Não há `/api/v1/`. A API serve a própria
  aplicação; não há cliente externo a quem prometer estabilidade.
- **Sem token de API.** A autenticação é por cookie de sessão. Integração de
  terceiros exigiria chave por cliente e escopo por chave.
- **Sem limite de taxa.** `GET /api/resumo` é público e não tem *rate
  limit*. Num serviço de verdade isso seria exigido antes de abrir a rota.
