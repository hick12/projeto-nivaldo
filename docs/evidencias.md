# Evidências

Entrega 4 do slide 41. Saídas reais, coladas do terminal.

**Ambiente:** PostgreSQL 17 gerenciado no Railway, projeto `worthy-serenity`,
ambiente `production`.
**URL:** https://projeto-nivaldo-production.up.railway.app
**Domínio próprio:** https://nivaldo.felipefurlan.com.br — no ar, HTTPS válido
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
Estoque insuficiente de Chapada Geisha: você pediu 2 e temos 1 em estoque.
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

## 7. Backup e restauração ✅

Procedimento no `README.md`. Executado contra o banco de **produção**.

### 7.1 O obstáculo do cliente desatualizado

A primeira tentativa falhou, e vale registrar porque é um erro comum:

```
servidor Railway : PostgreSQL 18.6
pg_dump local    : PostgreSQL 17.5
```

O `pg_dump` **se recusa a dumpar um servidor mais novo que ele**. Não é
capricho: formatos internos mudam entre versões maiores e um dump feito por
cliente antigo poderia sair incompleto.

Solução: rodar o `pg_dump` **de dentro do container do Postgres**, via
`railway ssh -s Postgres`, onde as ferramentas são exatamente da versão do
servidor.

### 7.2 Backup

```
$ pg_dump -U postgres -d railway -F c -f /tmp/torra_terra.dump
-rw-r--r-- 1 root root 23K /tmp/torra_terra.dump
```

Formato *custom* (`-F c`): comprimido e restaurável seletivamente.

### 7.3 Contagens na origem

```
 produtos | categorias | clientes | pedidos | itens
----------+------------+----------+---------+-------
       12 |          4 |        2 |       2 |     3
```

### 7.4 Restauração num banco novo

```
$ psql -U postgres -c 'CREATE DATABASE torra_restaurado;'
$ pg_restore -U postgres -d torra_restaurado /tmp/torra_terra.dump
```

Restaurado num banco **separado**, de propósito: restaurar por cima do
original destruiria justamente o que se quer proteger, e não provaria nada.

### 7.5 Contagens no destino — idênticas

```
 produtos | categorias | clientes | pedidos | itens
----------+------------+----------+---------+-------
       12 |          4 |        2 |       2 |     3
```

### 7.6 As constraints sobreviveram?

Restaurar dados sem as regras não é restaurar nada. Contagem por tipo no
banco restaurado (`contype` do `pg_constraint`):

```
 contype | count
---------+-------
 c       |    11     <- CHECK
 f       |     4     <- FOREIGN KEY
 n       |    26     <- NOT NULL
 p       |     5     <- PRIMARY KEY
 u       |     3     <- UNIQUE
```

Idêntico à produção. E os 4 índices também vieram:

```
 indices_idx
-------------
           4
```

### 7.7 A prova final: a constraint ainda **funciona**

Tentativa de inserir preço negativo no banco restaurado:

```
ERROR:  new row for relation "produtos" violates check constraint "ck_produtos_preco"
DETAIL:  Failing row contains (13, Cafe invalido, null, -1.00, 0, 1, MEDIA, null, null, 250).
```

Não é só a estrutura que voltou — a **regra de negócio** voltou junto e está
ativa. É isso que o slide 24 quer dizer com *"backup só é confiável quando a
restauração também é testada"*.

O banco `torra_restaurado` e o arquivo de dump foram removidos depois do
teste, para não consumir espaço em produção.

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
- [ ] **`git push` na `main` NÃO está disparando deploy automático** — ver 8.4
- [x] **`https://nivaldo.felipefurlan.com.br` no ar, com HTTPS válido**

### 8.1 Domínio próprio

A zona de `felipefurlan.com.br` é gerenciada pelo **Netlify DNS** — os
nameservers são `dns1.p02.nsone.net` a `dns4`, infraestrutura NS1. Os dois
registros foram criados lá:

| Tipo | Nome | Valor |
|---|---|---|
| CNAME | `nivaldo` | `gmcessmo.up.railway.app` |
| TXT | `_railway-verify.nivaldo` | `railway-verify=2cc89b4f…12db42` |

**Os dois são obrigatórios.** O TXT é a verificação de propriedade; sem ele o
Railway não emite o certificado.

Status final no Railway:

```
Verified: yes
Certificate status: CERTIFICATE_STATUS_TYPE_VALID
```

### 8.2 Certificado

```
subject = CN=nivaldo.felipefurlan.com.br
issuer  = C=US, O=Let's Encrypt, CN=YR2
válido  = 26/08/2026 até 24/11/2026
```

Renovação automática a cada 90 dias, pelo Railway.

### 8.3 Rotas na URL definitiva

```
/                HTTP 200
/produto/11      HTTP 200
/?categoria=4    HTTP 200
/carrinho        HTTP 200
/login           HTTP 200
/cadastro        HTTP 200
/meus-pedidos    HTTP 302   <- protegida, redireciona sem sessão
```

E o `http://` redireciona para `https://` com **HTTP 301**.

> **Nota para quem testar durante a propagação:** entre "o DNS já aponta para
> o Railway" e "o Let's Encrypt já emitiu o certificado" existe uma janela em
> que o navegador mostra `ERR_CERT_COMMON_NAME_INVALID`. Não é erro de
> configuração — é o Railway servindo o certificado curinga `*.up.railway.app`
> enquanto o específico não sai. Levou cerca de 20 minutos neste caso.


### 8.4 Deploy automático — pendência aberta

**Esta era uma afirmação errada deste documento e foi corrigida.**

O item estava marcado como verificado. Ele não estava. O que aconteceu: um
`git push` e um `railway deployment redeploy` foram executados com poucos
segundos de diferença, e o deploy que apareceu foi atribuído ao push. Era do
redeploy.

Testado de novo depois, de forma isolada: dois pushes para a `main` não
geraram deployment nenhum. O deploy só saiu com
`railway deployment redeploy --from-source`, que puxa o último commit à força.

**Hipótese mais provável:** o repositório pertence a outra conta
(`hick12`) e o serviço do Railway está numa conta diferente
(`lipefurlan`). A conexão inicial funcionou — o primeiro build veio do
GitHub — mas o *webhook* de push, que exige a Railway GitHub App instalada
no repositório com permissão de eventos, aparentemente não está entregando.

**Onde verificar:** no Railway, card do serviço → **Settings → Source**.
Conferir a branch configurada e se existe alguma opção de auto-deploy
desligada. No GitHub, em **Settings → GitHub Apps** do repositório, conferir
se a Railway está instalada com acesso a `projeto-nivaldo` — isso depende do
Henrique, que é dono do repositório.

**Impacto na avaliação:** é um item do checklist do Bloco 6. Enquanto não
for resolvido, o deploy continua funcionando, mas manualmente:

```
railway deployment redeploy --from-source
```

**Alternativa se não for resolvível:** trocar a fonte para `railway up`, que
sobe a pasta local direto — funciona sempre, mas também não tem gatilho
automático; ou o Felipe fazer um fork do repositório para a conta dele e
apontar o Railway para o fork, que aí ele controla as permissões.

---

## 9. Varredura de segurança — OWASP ZAP

O ZAP foi rodado contra a aplicação publicada e apontou **11 alertas**. Oito
eram acionáveis e foram corrigidos; três são informativos.

### 9.1 Antes

| Alerta | Gravidade | Situação |
|---|---|---|
| Ausência de tokens Anti-CSRF | Alta | corrigido |
| Cookie sem atributo SameSite | Alta | corrigido |
| Cookie sem flag Secure | Alta | corrigido |
| Content Security Policy não definido | Média | corrigido |
| Missing Anti-clickjacking Header | Média | corrigido |
| Strict-Transport-Security não definido | Média | corrigido |
| X-Content-Type-Options ausente | Baixa | corrigido |
| Sub Resource Integrity ausente | Baixa | **não corrigido — ver 9.4** |
| Re-examine Cache-control Directives | Informativo | mitigado |
| Session Management Response Identified | Informativo | é só a detecção da sessão |
| User Controllable HTML Element Attribute | Informativo | falso positivo |

### 9.2 O achado que importava: CSRF

Era o único explorável de verdade, e só porque vinha acompanhado da ausência
de `SameSite`.

**O ataque:** um cliente logado na loja visita uma página maliciosa. Essa
página tem um formulário escondido que dispara `POST` para
`/checkout`. O navegador **anexa o cookie de sessão automaticamente** — ele
não sabe distinguir um formulário nosso de um de outro site. O pedido sai de
verdade, em nome do cliente.

**As duas defesas implementadas:**

1. `SameSite=Lax` no cookie — o navegador se recusa a enviar o cookie num
   `POST` originado de outro site. Barra o ataque antes de chegar à aplicação.
2. Token CSRF — um segredo que vive na sessão e é reenviado num campo
   escondido. O site atacante não consegue ler a sessão, logo não consegue
   forjar o campo.

A validação acontece em `before_request`, **antes de qualquer acesso ao
banco**, e usa `secrets.compare_digest` em vez de `==` — comparação de tempo
constante, para não vazar o token caractere a caractere pelo tempo de resposta.

### 9.3 Depois — verificado na URL definitiva

```
content-security-policy: default-src 'self'; style-src 'self' https://fonts.googleapis.com;
                         font-src https://fonts.gstatic.com; img-src 'self' data:;
                         script-src 'none'; form-action 'self'; frame-ancestors 'none';
                         base-uri 'none'
referrer-policy:         strict-origin-when-cross-origin
strict-transport-security: max-age=31536000; includeSubDomains
x-content-type-options:  nosniff
x-frame-options:         DENY

Set-Cookie: session=...; Secure; HttpOnly; Path=/; SameSite=Lax
```

Teste do bloqueio:

```
POST /login sem o campo _csrf  ->  HTTP 400
```

E o fluxo completo continua funcionando com o token:

```
login          -> HTTP 302
add carrinho   -> HTTP 302
checkout       -> HTTP 302
mensagem: Estoque insuficiente de Chapada Geisha: você pediu 2 e temos 1 em estoque.
```

> **Sobre o `script-src 'none'`:** a loja não usa JavaScript nenhum. Isso
> permite a política mais restritiva possível e torna XSS praticamente
> inviável — não há onde um script injetado executar. É um benefício
> acidental da decisão de fazer CSS puro sem framework.

### 9.4 O alerta que NÃO foi corrigido, e por quê

**Sub Resource Integrity ausente** — refere-se ao `<link>` do Google Fonts.

SRI funciona colocando o hash do arquivo no HTML: o navegador baixa, calcula
o hash e recusa se não bater. **Não é aplicável ao Google Fonts**: a
resposta do `fonts.googleapis.com` **varia conforme o navegador** — o Google
serve `woff2` moderno para uns e formatos antigos para outros. O hash mudaria
por visitante, e a página quebraria para parte deles.

**A mitigação adotada** é o CSP, que restringe `style-src` e `font-src` a
exatamente esses dois domínios. Se alguém injetasse um `<link>` para outro
lugar, o navegador bloquearia.

**A correção definitiva** seria hospedar as fontes junto com a aplicação —
elimina a dependência externa, o alerta e ainda deixa a página mais rápida.
Ficou como evolução, registrada aqui.

### 9.5 Testes

Doze testes em `tests/test_seguranca.py` cobrem cada item corrigido — POST
sem token, com token errado, com token válido, presença de cada cabeçalho,
o CSP, o HSTS condicional ao `X-Forwarded-Proto`, e as flags do cookie.

```
24 passed in 71.25s
```

Sem esses testes, uma refatoração futura removeria um cabeçalho e ninguém
perceberia até o próximo scan.
