# Evidências

Entrega 4 do slide 41. Saídas reais, coladas do terminal.

**Ambiente:** PostgreSQL 17 gerenciado no Railway, projeto `worthy-serenity`,
ambiente `production`.
**URL:** https://projeto-nivaldo-production.up.railway.app
**Domínio próprio:** https://nivaldo.felipefurlan.com.br *(aguardando DNS)*
**Coletado em:** 26/08/2026

---

## 1. Estrutura do banco

### 1.1 Tabelas

```
categorias
clientes
itens_pedido
pedidos
produtos
```

### 1.2 Constraints, por tipo

```
CHECK        11
FOREIGN KEY   4
PRIMARY KEY   5
UNIQUE        3
```

As três `UNIQUE`: `categorias.nome`, `clientes.email` e a composta
`uq_itens_pedido_produto_moagem`.

### 1.3 Os onze CHECK, como o banco os guarda

```
ck_clientes_email_formato  (POSITION(('@'::text) IN (email)) > 1)
ck_itens_moagem            ((moagem)::text = ANY (ARRAY['GRAO','MEDIA','FINA']))
ck_itens_preco             (preco_unitario >= (0)::numeric)
ck_itens_quantidade        (quantidade > 0)
ck_pedidos_status          ((status)::text = ANY (ARRAY['CRIADO','PAGO','ENVIADO','CANCELADO']))
ck_pedidos_total           (total >= (0)::numeric)
ck_produtos_estoque        (estoque >= 0)
ck_produtos_peso           (peso_g > 0)
ck_produtos_preco          (preco >= (0)::numeric)
ck_produtos_sca            ((pontuacao_sca >= (80)::numeric) AND (pontuacao_sca <= (100)::numeric))
ck_produtos_torra          ((torra)::text = ANY (ARRAY['CLARA','MEDIA','ESCURA']))
```

Repare que o `BETWEEN 80 AND 100` que escrevemos virou duas comparações no
catálogo do sistema. É o mesmo predicado — o PostgreSQL normaliza.

### 1.4 Índices

```
idx_itens_pedido         itens_pedido
idx_pedidos_cliente      pedidos
idx_produtos_categoria   produtos
idx_produtos_nome        produtos
```

### 1.5 Carga inicial

```
Cerrado Mineiro       3 cafés  R$ 55,00–96,00   estoque 95
Chapada Diamantina    3 cafés  R$ 71,00–148,00  estoque 47
Mogiana Paulista      3 cafés  R$ 48,00–74,00   estoque 125
Sul de Minas          3 cafés  R$ 44,00–82,00   estoque 127
```

12 cafés, 4 regiões, 3 cafés cada.

---

## 2. Testes automatizados

```
platform win32 -- Python 3.11.9, pytest-8.3.4
collected 12 items

test_compra_normal_grava_pedido_itens_e_baixa_estoque PASSED   [  8%]
test_estoque_insuficiente_faz_rollback_completo PASSED          [ 16%]
test_produto_inexistente_nao_finaliza_o_pedido PASSED           [ 25%]
test_preco_negativo_e_recusado_pelo_banco PASSED                [ 33%]
test_estoque_negativo_e_recusado_pelo_banco PASSED              [ 41%]
test_pontuacao_sca_fora_da_faixa_e_recusada PASSED              [ 50%]
test_moagem_invalida_e_recusada_pelo_banco PASSED               [ 58%]
test_moagem_longa_demais_e_recusada_pelo_tamanho PASSED         [ 66%]
test_senha_nunca_e_gravada_em_texto_puro PASSED                 [ 75%]
test_mesmo_cafe_em_moagens_diferentes_vira_duas_linhas PASSED   [ 83%]
test_preco_unitario_fica_congelado_apos_reajuste PASSED         [ 91%]
test_carrinho_vazio_nao_gera_pedido PASSED                      [100%]

============================= 12 passed in 46.52s =============================
```

> **Um teste teve que ser corrigido durante a execução**, e vale contar na
> defesa. A primeira versão de `test_moagem_invalida` usava o valor
> `'EXTRAFINA'`. O banco recusou — mas por `StringDataRightTruncation`, não
> pelo `CHECK`: a coluna é `VARCHAR(6)` e a palavra tem 9 caracteres. O dado
> era barrado do mesmo jeito, só que pela regra errada, e o teste não provava
> o que se propunha. Trocamos para `'MOIDA'`, que cabe em 6 caracteres e não
> está no domínio, e separamos o caso do tamanho num teste próprio. A coluna
> tem duas defesas independentes e agora cada uma tem o seu teste.

---

## 3. O cenário de erro — em produção, na URL pública

### Passo 1 — o estado antes

```
pedidos = 0      itens_pedido = 0
Chapada Geisha: estoque = 1
```

O estoque 1 vem do `seed.sql`, de propósito.

### Passo 2 — a tentativa que falha

Logado como `demo.tai@exemplo.com`, adicionou **2 unidades** do Chapada
Geisha ao carrinho e finalizou. O `POST /checkout` redirecionou para
`/carrinho`, e a mensagem exibida ao cliente foi:

```
Estoque insuficiente de Chapada Geisha: voce pediu 2 e temos 1 em estoque.
```

A mensagem **nomeia o café** e informa o saldo real — critério de aceite do RF05.

### Passo 3 — a prova de que nada foi gravado

```
pedidos = 0      itens_pedido = 0     <- idênticos ao passo 1
Chapada Geisha: estoque = 1           <- intacto
pedidos órfãos (sem item) = 0
```

Rollback completo. Nem o cabeçalho do pedido sobrou.

---

## 4. A compra que dá certo

Mesmo cliente, agora comprando **o mesmo café em duas moagens**:
2 unidades em grão e 1 moída fina.

### 4.1 Pedido persistido

```
#1 | Demonstracao TAI | CRIADO | R$ 267.00 | 26/08/2026 23:34
```

### 4.2 Itens, com moagem e preço congelado

```
pedido #1 | Piata Altitude | 2x | moagem GRAO | R$ 89.00 | subtotal R$ 178.00
pedido #1 | Piata Altitude | 1x | moagem FINA | R$ 89.00 | subtotal R$  89.00
```

### 4.3 Duas linhas do mesmo café — `itens_pedido` é entidade

```
pedido #1 | Piata Altitude | 2 linhas | GRAO, FINA
```

Esta é a prova concreta do argumento central da modelagem. O mesmo produto,
no mesmo pedido, em duas linhas, porque a **moagem** difere. Se `moagem`
fosse coluna de `produtos`, isso seria impossível sem duplicar o cadastro do
café — e o controle de estoque, que é do café e não da moagem, quebraria.

### 4.4 O total bate com a soma dos itens

```
divergências: 0
```

R$ 178,00 + R$ 89,00 = R$ 267,00, exatamente o `total` gravado no pedido.

### 4.5 Estoque reduzido

```
Piata Altitude:  15    <- era 18, comprou 3
Chapada Geisha:   1    <- intacto, preservado para a demonstração
```

---

## 5. Índices e `EXPLAIN`

Colhido na base real de produção, com 12 cafés e 1 pedido.

### 5.1 `idx_produtos_categoria` — filtro por região · **Index Scan** ✅

```
Sort  (cost=8.17..8.18 rows=1 width=830) (actual time=0.044..0.045 rows=3.00)
  Sort Key: nome
  ->  Index Scan using idx_produtos_categoria on produtos
        (cost=0.14..8.16 rows=1) (actual time=0.027..0.030 rows=3.00)
        Index Cond: (categoria_id = 4)
Execution Time: 0.067 ms
```

### 5.2 `idx_pedidos_cliente` — histórico · **Bitmap Index Scan** ✅

```
Sort  (cost=12.68..12.69 rows=4 width=74) (actual time=0.065..0.066 rows=1.00)
  Sort Key: criado_em DESC
  ->  Bitmap Heap Scan on pedidos  (cost=4.18..12.64 rows=4)
        Recheck Cond: (cliente_id = 2)
        ->  Bitmap Index Scan on idx_pedidos_cliente
              (cost=0.00..4.18 rows=4) (actual time=0.010..0.010)
              Index Cond: (cliente_id = 2)
Execution Time: 0.087 ms
```

### 5.3 `idx_produtos_nome` — catálogo completo · **Seq Scan**

```
Sort  (cost=13.82..14.05 rows=90 width=830) (actual time=0.042..0.043 rows=12.00)
  Sort Key: nome
  Sort Method: quicksort  Memory: 27kB
  ->  Seq Scan on produtos  (cost=0.00..10.90 rows=90) (actual time=0.011..0.013)
Execution Time: 0.063 ms
```

**Este é o resultado mais interessante para a defesa, e não é um problema.**

Os dois primeiros planos usam índice porque têm `WHERE` **seletivo**: pegam 3
linhas de 12, e 1 pedido de 1. Vale a pena consultar o índice e depois buscar
só as linhas necessárias.

O terceiro não tem `WHERE` nenhum — precisa de **todas** as 12 linhas. Usar o
índice significaria ler o índice inteiro *e depois* a tabela inteira: mais
trabalho, não menos. O planejador varre a tabela e ordena em memória, com
`quicksort` em 27 kB. É a decisão certa.

Ou seja: o `idx_produtos_nome` não é inútil — ele passa a compensar quando a
tabela crescer o suficiente para o `Sort` não caber em memória. A seção 4.5
de `SQL/consultas.sql` traz um gerador de 200 mil linhas para demonstrar a
virada.

**A lição:** o índice existir não obriga o planejador a usá-lo. Ele decide por
custo estimado, e com 12 registros a decisão dele está certa.

---

## 6. Segurança

### 6.1 Senha nunca em texto puro

```
#2 Demonstracao TAI <demo.tai@exemplo.com> -> scrypt:32768:8:1$iGRVY...
```

Hash scrypt, com fator de custo 32768. A senha digitada não aparece.

### 6.2 E-mail único

```
clientes = 1     emails distintos = 1     -> UNIQUE OK
```

> O `id` do único cliente é 2, não 1. O 1 foi consumido por um `INSERT`
> desfeito: **sequences não voltam atrás no PostgreSQL**, nem em rollback. É
> comportamento esperado e garante que dois pedidos simultâneos nunca recebam
> o mesmo id.

### 6.3 A aplicação não usa o superusuário

```
usuário conectado: torra_app
superuser  = False
createdb   = False
createrole = False
```

Teste de privilégio real, pelo túnel:

```
conectou como torra_app | superuser=False
SELECT ok -> 12 cafés
INSERT e UPDATE ok (sequence acessível)
DROP TABLE negado, como esperado: InsufficientPrivilege
```

> **Este item exigiu correção durante o deploy e vale contar.** O Railway
> entrega a `DATABASE_URL` com o usuário `postgres`, que é **superusuário**
> dentro daquele container. A conferência mostrou `superuser=True`, o que
> contradizia o RNF04. Criamos o papel `torra_app` no banco de produção, com
> `SELECT/INSERT/UPDATE/DELETE` nas tabelas e `USAGE` nas sequences, e
> trocamos a `DATABASE_URL` do serviço. A aplicação continuou funcionando e
> agora não consegue mais alterar o schema.

### 6.4 Nenhum segredo no repositório

```
$ git log --all --oneline -- .env
(vazio)
```

O `.env` nunca foi versionado. O `.env.example` está no repositório com
valores de exemplo.

---

## 7. Backup e restauração

```
PENDENTE — rodar o pg_dump e colar a comparação de contagens
```

Procedimento no `README.md`, seção "Backup e restauração".

---

## 8. Deploy

- [x] Build no Railway concluído com sucesso
- [x] `Procfile` funcionando — gunicorn escutando em `0.0.0.0:8080`
- [x] Variáveis de ambiente no provedor, nenhum segredo no código
- [x] `https://projeto-nivaldo-production.up.railway.app` responde **HTTP 200** com HTTPS
- [x] O catálogo carrega os 12 cafés vindos do banco de produção
- [x] Filtro por região responde **HTTP 200**
- [x] Detalhe do produto responde **HTTP 200**
- [x] Rota protegida `/meus-pedidos` redireciona (**HTTP 302**) sem sessão
- [x] Cadastro e login funcionam em produção
- [x] Carrinho aceita a escolha de moagem
- [x] O checkout gravou o pedido #1 e reduziu o estoque
- [x] **O cenário de erro funciona em produção**
- [x] "Meus pedidos" mostra o histórico
- [x] `git push` na `main` dispara deploy automático
- [ ] `https://nivaldo.felipefurlan.com.br` — aguardando os registros de DNS

### DNS pendente

Os dois registros precisam ser criados na zona de `felipefurlan.com.br`:

| Tipo | Nome | Valor |
|---|---|---|
| CNAME | `nivaldo` | `gmcessmo.up.railway.app` |
| TXT | `_railway-verify.nivaldo` | `railway-verify=2cc89b4fecd8af80de6108950cc6dc8ef34379f7d35b8a189837e0f52912db42` |

**Os dois são obrigatórios.** Com o CNAME resolvendo e o TXT faltando, o
domínio responde 404 — o TXT é a verificação de propriedade.
