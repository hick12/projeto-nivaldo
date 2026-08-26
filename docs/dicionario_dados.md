# Dicionário de dados — Torra & Terra

Campo a campo: tipo, obrigatoriedade, regra de negócio e exemplo.

Convenções: **PK** chave primária · **FK** chave estrangeira · **UK** único ·
"Obrig." = `NOT NULL`.

---

## `categorias` — regiões produtoras

| Campo | Tipo | Obrig. | Regra de negócio | Exemplo |
|---|---|:---:|---|---|
| `id` | `SERIAL` | PK | Gerado pelo banco | `2` |
| `nome` | `VARCHAR(80)` | sim, UK | Nome da região; não se repete | `Cerrado Mineiro` |
| `regiao` | `VARCHAR(80)` | sim | Estado ou macrorregião | `Minas Gerais` |
| `descricao` | `TEXT` | não | Altitude, solo, perfil de xícara | `Primeira denominação de origem...` |

> Existe como tabela separada para respeitar a 3FN: a descrição depende da
> região, não do café.

---

## `clientes`

| Campo | Tipo | Obrig. | Regra de negócio | Exemplo |
|---|---|:---:|---|---|
| `id` | `SERIAL` | PK | Gerado pelo banco | `7` |
| `nome` | `VARCHAR(120)` | sim | Nome de exibição | `Ana Souza` |
| `email` | `VARCHAR(160)` | sim, UK | Único no sistema; precisa conter `@` | `ana@exemplo.com` |
| `senha_hash` | `VARCHAR(255)` | sim | Hash scrypt do werkzeug. **A senha em texto puro nunca chega ao banco** | `scrypt:32768:8:1$...` |
| `criado_em` | `TIMESTAMP` | sim | `DEFAULT CURRENT_TIMESTAMP` | `2026-08-26 19:40:11` |

> 255 caracteres em `senha_hash` porque o scrypt gera 162 hoje — dimensionado
> com folga para o caso de o algoritmo padrão do werkzeug mudar.

---

## `produtos` — os cafés

| Campo | Tipo | Obrig. | Regra de negócio | Exemplo |
|---|---|:---:|---|---|
| `id` | `SERIAL` | PK | Gerado pelo banco | `11` |
| `nome` | `VARCHAR(140)` | sim | Nome comercial do lote | `Chapada Geisha` |
| `descricao` | `TEXT` | não | Origem, processo, produtor | `Variedade Geisha adaptada à Bahia...` |
| `preco` | `NUMERIC(10,2)` | sim | **`>= 0`**. Nunca `FLOAT`: ponto flutuante não representa `0,10` exatamente e o erro se acumula ao somar itens | `148.00` |
| `estoque` | `INTEGER` | sim | **`>= 0`**, `DEFAULT 0`. Última linha de defesa contra venda a descoberto | `1` |
| `categoria_id` | `INTEGER` | sim, FK | Aponta para `categorias.id`. Café sem origem não existe neste domínio | `4` |
| `torra` | `VARCHAR(10)` | sim | **`CLARA`, `MEDIA` ou `ESCURA`** | `CLARA` |
| `nota_sensorial` | `VARCHAR(200)` | não | Descritores de xícara | `Bergamota, jasmim, pêssego branco` |
| `pontuacao_sca` | `NUMERIC(4,2)` | não | **`BETWEEN 80 AND 100`**. Café especial, pela definição da SCA, pontua 80+ | `91.00` |
| `peso_g` | `INTEGER` | sim | **`> 0`**, `DEFAULT 250`. Peso do pacote em gramas | `250` |

> `pontuacao_sca` é o exemplo canônico de regra que **precisa** estar no banco:
> é regra do negócio, não do formulário. Se o dado entrar por um `INSERT`
> manual ou por uma futura API, a regra continua valendo.

---

## `pedidos` — cabeçalho

| Campo | Tipo | Obrig. | Regra de negócio | Exemplo |
|---|---|:---:|---|---|
| `id` | `SERIAL` | PK | Gerado pelo banco | `3` |
| `cliente_id` | `INTEGER` | sim, FK | Aponta para `clientes.id`. Pedido sem cliente não faz sentido | `7` |
| `status` | `VARCHAR(12)` | sim | **`CRIADO`, `PAGO`, `ENVIADO` ou `CANCELADO`**. Nasce como `CRIADO` | `CRIADO` |
| `total` | `NUMERIC(10,2)` | sim | **`>= 0`**. Soma dos itens, calculada dentro da transação | `326.00` |
| `criado_em` | `TIMESTAMP` | sim | `DEFAULT CURRENT_TIMESTAMP` | `2026-08-26 20:15:03` |

> A FK **não** tem `ON DELETE CASCADE`: pedido é registro contábil. O banco
> recusa excluir um cliente enquanto houver histórico de venda.

---

## `itens_pedido` — entidade, não tabela de ligação

| Campo | Tipo | Obrig. | Regra de negócio | Exemplo |
|---|---|:---:|---|---|
| `id` | `SERIAL` | PK | Gerado pelo banco | `9` |
| `pedido_id` | `INTEGER` | sim, FK | Aponta para `pedidos.id`, **`ON DELETE CASCADE`** — item sem pedido é órfão | `3` |
| `produto_id` | `INTEGER` | sim, FK | Aponta para `produtos.id`. Sem cascade: o histórico precisa continuar legível | `11` |
| `quantidade` | `INTEGER` | sim | **`> 0`**. Item com quantidade zero não é item | `2` |
| `preco_unitario` | `NUMERIC(10,2)` | sim | **`>= 0`**. **Congelado no momento da compra** — se o preço mudar amanhã, o pedido antigo mantém o valor da época | `148.00` |
| `moagem` | `VARCHAR(6)` | sim | **`GRAO`, `MEDIA` ou `FINA`**. Escolhida na compra, não no cadastro do café | `FINA` |

**Restrição composta:** `UNIQUE (pedido_id, produto_id, moagem)`.

O mesmo café pode aparecer duas vezes no pedido desde que em moagens
diferentes — meio quilo em grão para o cliente moer, meio quilo fina para a
prensa. O que não pode é a mesma combinação duplicada: seria falha de
consolidação do carrinho.

---

## Índices

| Índice | Coluna(s) | Consulta que o justifica |
|---|---|---|
| `idx_produtos_nome` | `produtos(nome)` | `SELECT ... FROM produtos ORDER BY nome` — a home, a consulta mais executada da aplicação |
| `idx_produtos_categoria` | `produtos(categoria_id)` | `WHERE categoria_id = ?` — o filtro por região. O PostgreSQL **não** indexa coluna de FK automaticamente |
| `idx_pedidos_cliente` | `pedidos(cliente_id)` | `WHERE cliente_id = ? ORDER BY criado_em DESC` — "meus pedidos". Cresce sem limite ao longo do tempo |
| `idx_itens_pedido` | `itens_pedido(pedido_id)` | O `JOIN` que monta o detalhe de cada pedido do histórico |

> Só estes quatro. Índice acelera leitura mas encarece escrita e ocupa disco —
> criar "por precaução" é custo sem benefício. As evidências de `EXPLAIN`
> antes/depois estão em `SQL/consultas.sql`, seção 4.

---

## Domínios enumerados

Valores fechados por `CHECK`, não por tabela de domínio. Para três conjuntos
pequenos e estáveis, uma tabela extra e um `JOIN` a mais custariam mais do que
entregam.

| Campo | Valores aceitos |
|---|---|
| `produtos.torra` | `CLARA` · `MEDIA` · `ESCURA` |
| `itens_pedido.moagem` | `GRAO` · `MEDIA` · `FINA` |
| `pedidos.status` | `CRIADO` · `PAGO` · `ENVIADO` · `CANCELADO` |

Se os valores passassem a ter atributos próprios — descrição, ordem de
exibição, ativo/inativo — aí a tabela de domínio se justificaria.
