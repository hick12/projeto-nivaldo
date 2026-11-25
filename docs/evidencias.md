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

---

# Projeto Final

Bloco acrescentado na entrega do **Projeto Final**. As saídas abaixo são
reais, coladas do terminal.

**Ambiente de coleta:** PostgreSQL 16, Python 3.13.18, pytest 8.3.4.
**Coletado em:** 24/11/2026.

> As evidências das seções 1 a 9 deste documento continuam válidas e foram
> colhidas no banco de produção do Railway. As deste bloco foram colhidas
> no ambiente de desenvolvimento, com o catálogo do `seed.sql` e os
> pedidos do `seed-demo`. As de produção entram depois do deploy.

---

## 10. Suíte de testes completa

```
============================= test session starts ==============================
platform linux -- Python 3.13.18, pytest-8.3.4, pluggy-1.7.0
rootdir: /home/user/projeto-nivaldo
collected 113 items

tests/test_api.py ...........................                            [ 23%]
tests/test_checkout.py ............                                      [ 34%]
tests/test_painel.py ..........................                          [ 57%]
tests/test_producao.py ...........................                       [ 81%]
tests/test_seguranca.py .....................                            [100%]

============================= 113 passed in 8.16s ==============================
```

Os três arquivos novos cobrem o que o manual cobra nesta entrega.

### 10.1 Dashboard — o indicador muda depois de inserir dados

`test_indicador_se_move_depois_de_um_checkout` lê os indicadores, faz uma
compra de 3 × R$ 89,00 e lê de novo:

| Indicador | Antes | Depois |
|---|---|---|
| Pedidos no período | 0 | 1 |
| Faturamento | R$ 0,00 | R$ 267,00 |
| Ticket médio | R$ 0,00 | R$ 267,00 |
| Vendas por região | nenhuma linha | Bahia, 3 unidades, 100% |

O teste não aceita "mais ou menos": compara o valor exato.

### 10.2 Conciliação em zero depois de vários checkouts

`test_conciliacao_fica_em_zero_depois_de_varios_checkouts` cria oito
pedidos, de dois clientes, com moagens misturadas:

```
pedidos = 8     conciliados = 8     divergentes = 0
```

E refaz a conferência **à mão**, sem passar pela consulta do painel: se as
duas contas discordassem, uma das duas estaria errada.

### 10.3 Atualização de registro — antes e depois

`test_transicao_valida_criado_para_pago` e os parametrizados de transição
inválida:

```
CRIADO  -> PAGO       ok        (de=CRIADO para=PAGO unidades_devolvidas=0)
PAGO    -> ENVIADO    ok
CRIADO  -> ENVIADO    recusado  "Não é possível ir de CRIADO para ENVIADO.
                                 De CRIADO só dá para ir para PAGO ou CANCELADO."
ENVIADO -> PAGO       recusado  estado final
ENVIADO -> CANCELADO  recusado  estado final
CANCELADO -> PAGO     recusado  estado final
```

Em todos os casos recusados, o teste confere que **o status não mudou**.

### 10.4 Cancelamento devolve o estoque, e um cancelamento recusado não

`test_cancelamento_devolve_o_estoque`: pedido de 2 unidades, estoque em 8
depois da compra, volta para 10 no cancelamento. O `total` e os itens do
pedido continuam gravados — é por isso que a conciliação continua
fechando.

`test_cancelamento_recusado_nao_altera_nada`: cancelar de novo um pedido
já cancelado é recusado, e o estoque **não** é devolvido uma segunda vez.
Clique repetido não pode criar estoque do nada.

### 10.5 Produção sem segredo

`test_producao_sem_secret_key_responde_503` sobe a aplicação com
`AMBIENTE=producao`, `DATABASE_URL` definida e `SECRET_KEY` ausente:

```
GET /              -> 503
GET /carrinho      -> 503
GET /checkout      -> 503
GET /painel        -> 503
GET /rota/inventada-> 503
POST /checkout     -> 503   (não 405)
```

A página nomeia `SECRET_KEY` e o teste confere que **nada do valor** sai:
nem a senha do banco, nem `torra_app:senha`, nem `postgresql://`, nem
`banco:5432`.

---

## 11. O índice novo: `idx_pedidos_criado_em`

Medição completa em `SQL/consultas.sql`, seção 5. Resumo:

### 11.1 Na base de demonstração — 40 pedidos

**Seq Scan, com e sem o índice**, e é a decisão certa do planejador: a
tabela inteira ocupa uma página de disco.

```
Aggregate  (cost=1.97..1.98 rows=1) (actual time=0.018..0.018 rows=1)
  ->  Seq Scan on pedidos  (cost=0.00..1.80 rows=34)
                           (actual time=0.005..0.010 rows=34)
        Filter: ((status <> 'CANCELADO') AND (criado_em >= ...))
        Rows Removed by Filter: 6
Execution Time: 0.053 ms
```

### 11.2 Com 60.000 pedidos — a virada

Carga sintética de 60 mil pedidos em 24 meses, num banco descartável.

**Card de faturamento do painel:**

| | Plano | Tempo |
|---|---|---|
| Antes | Seq Scan · `Rows Removed by Filter: 58162` | **6,713 ms** |
| Depois | Bitmap Index Scan · `Rows Removed by Filter: 640` | **0,900 ms** |

7,5× mais rápido. O custo estimado caiu de 1667 para 562 — é por isso que
o planejador troca de plano sozinho, sem dica nenhuma no código.

**Lista de pedidos recentes (`ORDER BY criado_em DESC LIMIT 20`):**

| | Plano | Tempo |
|---|---|---|
| Antes | Seq Scan de 60.000 linhas + `top-N heapsort` | **10,401 ms** |
| Depois | Index Scan, **sem Sort no plano** | **0,031 ms** |

335× mais rápido. É a razão de o índice ser `criado_em DESC` e não apenas
`criado_em`: o índice já está na ordem pedida, o banco lê 20 entradas e
para.

**O preço:**

```
tabela pedidos ...... 6736 kB
idx_pedidos_criado_em  1328 kB   (~20% do tamanho da tabela)
```

Índice não é de graça: todo INSERT de pedido passa a escrever em dois
lugares. O checkout fica marginalmente mais lento para o painel ficar 335×
mais rápido.

---

## 12. Migração aplicada sem apagar nada

`SQL/migracao_projeto_final.sql` rodado **duas vezes** seguidas, para
provar a idempotência. Na segunda:

```
NOTICE:  relation "idx_pedidos_criado_em" already exists, skipping
```

Conferência depois de aplicar:

```
       indexname        |  tablename   
------------------------+--------------
 idx_itens_pedido       | itens_pedido
 idx_pedidos_cliente    | pedidos
 idx_pedidos_criado_em  | pedidos      <- o novo
 idx_produtos_categoria | produtos
 idx_produtos_nome      | produtos
(5 rows)

 tabelas | checks | foreign_keys 
---------+--------+--------------
       5 |     11 |            4

 categorias | produtos | clientes | pedidos | itens 
------------+----------+----------+---------+-------
          4 |       12 |        0 |       0 |     0
```

A estrutura não mudou — as mesmas 5 tabelas, 11 CHECK e 4 FK — e nenhum
dado foi tocado.

---

## 13. Indicadores do painel, com os dados de demonstração

Saída do `psql "$DATABASE_URL" -f SQL/dashboard.sql`:

```
 pedidos | faturamento 
---------+-------------
      34 |     7571.00

     ticket_medio     
----------------------
 222.6764705882352941

    regiao    | pedidos | unidades | faturamento 
--------------+---------+----------+-------------
 Minas Gerais |      28 |       66 |     4513.00
 Bahia        |      12 |       20 |     1618.00
 Sao Paulo    |      12 |       23 |     1440.00

 id |          nome           |    regiao    | unidades | faturamento | moagem_preferida 
----+-------------------------+--------------+----------+-------------+------------------
  4 | Alta Mogiana do Cerrado | Minas Gerais |       17 |     1156.00 | MEDIA
  6 | Cerrado Reserva         | Minas Gerais |       13 |      715.00 | GRAO
  7 | Serra da Mantiqueira    | Minas Gerais |       12 |      984.00 | MEDIA
  1 | Fazenda Serra Negra     | Sao Paulo    |       11 |      682.00 | FINA
 10 | Piata Altitude          | Bahia        |       11 |      979.00 | MEDIA

 id |       nome        |    regiao    | estoque | preco  
----+-------------------+--------------+---------+--------
 11 | Chapada Geisha    | Bahia        |       1 | 148.00
  5 | Vereda do Cerrado | Minas Gerais |       5 |  96.00

  status   | pedidos |  valor  
-----------+---------+---------
 CRIADO    |       4 |  741.00
 PAGO      |       6 | 1113.00
 ENVIADO   |      24 | 5717.00
 CANCELADO |       6 |  818.00

 pedidos | divergentes | conciliados 
---------+-------------+-------------
      40 |           0 |          40
```

**Zero divergências em 40 pedidos.** É o indicador central do trabalho, e
ele vale mais por ser uma consulta sobre 100% dos registros do que por
qualquer afirmação sobre o código.

> O `Chapada Geisha` aparece no estoque crítico com 1 unidade. Isso é
> proposital e o `seed-demo` o preserva: é o café que deixa a
> demonstração do rollback sempre pronta.

---

## 14. O controle de acesso, verificado

Sem sessão:

```
/health          -> 200
/api/categorias  -> 200
/api/produtos    -> 200
/api/resumo      -> 200
/api/dashboard   -> 401   <- restrito ao gestor
/api/pedidos     -> 401   <- exige login
```

Com sessão de **cliente comum**:

```
GET  /painel                        -> 403, com página amigável
POST /painel/pedidos/<id>/status    -> 403, e o status não muda
GET  /api/dashboard                 -> 403 {"erro": "Acesso restrito ao gestor da loja."}
```

Com sessão de **gestor** (e-mail em `ADMIN_EMAILS`):

```
GET /painel        -> 200
GET /api/dashboard -> 200
```

O `POST` barrado para o cliente comum é o caso que importa: ele foi
enviado **com token CSRF válido da própria sessão**. O que barra é o
papel, não o token.

---

## 15. Logs estruturados

Linhas reais do `stdout` da aplicação, uma por evento:

```
INFO    evento=aplicacao_iniciada producao=False
        banco=postgresql+psycopg://torra_app:***@127.0.0.1:5432/torra_terra gestores=1

WARNING evento=login_falho email=an***@exemplo.com motivo=senha_incorreta origem=127.0.0.1
WARNING evento=login_falho email=ni***@exemplo.com motivo=conta_inexistente origem=127.0.0.1

WARNING evento=csrf_barrado metodo=POST rota=/login token_enviado=nao sessao_com_token=nao

WARNING evento=acesso_negado_painel email=an***@exemplo.com rota=/painel

WARNING evento=checkout_recusado motivo=estoque_insuficiente
        cafe='Chapada Geisha' disponivel=1 pedido=2 cliente=1

INFO    evento=status_alterado pedido=42 de=CRIADO para=PAGO
        unidades_devolvidas=0 gestor=ge***@exemplo.com
```

Três coisas a observar:

1. **A senha do banco nunca aparece.** A `DATABASE_URL` sai mascarada em
   toda linha de log, e a query inteira é descartada porque `?password=`
   também é credencial.
2. **E-mail entra mascarado.** `an***@exemplo.com` permite investigar
   força bruta — mesmo domínio? mesma conta repetida? — sem o painel de
   logs virar uma lista de e-mails de clientes.
3. **O motivo do login falho fica só no log.** A tela diz "E-mail ou senha
   inválidos" para os dois casos; o log distingue `senha_incorreta` de
   `conta_inexistente`. É exatamente a informação que a tela se recusa a
   dar, no único lugar em que ela é útil e não é explorável.

No `csrf_barrado`, o log registra se havia token e **o tamanho** dele,
nunca o valor — serve para distinguir "não mandou nada" de "mandou um
token errado".

---

## 16. O site do Projeto Final

Verificado no Chromium, em `/projeto-final`:

```
12 seções no índice lateral · 12 seções renderizadas
7 instâncias de 6 componentes distintos (o as_is_to_be aparece duas vezes)
11 tabelas · 15 blocos de código
0 erros no console · 0 violações de CSP
0 blocos com dado faltando
```

Cada componente, exercitado:

| Componente | Verificação |
|---|---|
| `as_is_to_be` | O botão alterna entre os dois fluxos; o AS IS mostra as falhas em vermelho, o TO BE os pontos de validação em verde |
| `er` | Clicar em `itens_pedido` abre as 6 colunas com tipo e constraint, mais a constraint composta e o índice que a tabela usa |
| `checkout` | No passo 9 de 10, a faixa do Bruno está em estado de falha e a narração diz *"Rollback completo: nem o cabeçalho do pedido sobrou"* |
| `explain` | Os dois planos lado a lado, com 6,713 ms → 0,900 ms e 10,401 ms → 0,031 ms |
| `indicadores` | Leu `/api/resumo` ao vivo e mostrou **42 de 42 pedidos conciliados** |
| `testes` | O filtro por tipo funciona: *"Mostrando os casos do tipo Transação"* |

### 16.1 A política de conteúdo, verificada

```
GET /projeto-final
content-security-policy: default-src 'self'; style-src 'self' https://fonts.googleapis.com;
                         font-src https://fonts.gstatic.com; img-src 'self' data:;
                         script-src 'self'; connect-src 'self'; form-action 'self';
                         frame-ancestors 'none'; base-uri 'none'

GET /  (e todas as outras rotas da loja)
content-security-policy: ... script-src 'none'; ...
```

E no HTML servido da rota `/projeto-final`:

```
style="        -> 0 ocorrências
<script>       -> 0 ocorrências
<script src=>  -> 1 ocorrência   (o app.js, sem corpo)
```

Sem `unsafe-inline` e sem `unsafe-eval`. Conteúdo injetado no HTML
continua sem poder executar.

---

## 17. Prints

Em `docs/evidencias/projeto_final/`. A lista, com o que cada um comprova,
está em `docs/projeto_final_entrega.md`.

---

## 18. O defeito que a suíte inteira não via

Vale contar na defesa, e vale mais que qualquer teste que passou de
primeira.

Depois de a entrega estar pronta e com a suíte verde, o código novo
passou por **revisão independente**. Ela encontrou dois defeitos no
`finalizar_pedido` — a função que é o argumento central do trabalho. Os
dois são anteriores a esta entrega e os dois eram invisíveis para a suíte
que existia.

### 18.1 O `SELECT ... FOR UPDATE` protegia o banco e não protegia a aplicação

A rota `/checkout` chama `carrinho_detalhado()` **antes** de
`finalizar_pedido()`, para desenhar a tela. Aquilo já carrega o `Produto`
na sessão do ORM. Quando o `SELECT ... FOR UPDATE` roda em seguida, o
SQLAlchemy encontra o objeto no *identity map* e, por padrão, **devolve o
objeto em memória e descarta a linha recém-lida do banco**.

Resultado: o lock era tomado corretamente no PostgreSQL, a transação
concorrente de fato esperava — e a validação decidia com o saldo de
**antes** do lock.

Reproduzido contra o PostgreSQL, com o `Chapada Geisha` de estoque 1:

```
A: carrinho_detalhado leu estoque = 1
B: outra compra commitou. No banco agora estoque = 0
A: VENDA APROVADA -> pedido #41
A: estoque final no banco = 0

>>> FALHA: duas unidades vendidas de um estoque de uma.
```

A baixa é gravada como valor absoluto (`SET estoque = 0`), não como
decremento, então nem o `ck_produtos_estoque` pegava. **Nenhum erro em
lugar nenhum.**

Era exatamente a venda em duplicidade que a função existe para impedir, e
acontecia **só pelo navegador** — o caminho que o cliente usa, e o que o
professor vai abrir.

A correção tem uma linha:

```python
db.select(Produto)
  .where(Produto.id == produto_id)
  .with_for_update()
  .execution_options(populate_existing=True)   # <- esta
```

### 18.2 A validação era por linha do carrinho, não por produto

O estoque é do **café**, não da moagem. Com estoque 1, uma linha em
`GRAO` de 1 unidade e outra em `FINA` de 1 passavam as duas, porque cada
uma era comparada isoladamente com o saldo cheio.

A fase 2 gravava `estoque = -1`, o `CHECK` do banco barrava com
`IntegrityError` — que **não** é `ErroCheckout` — e o cliente recebia uma
página 500 em vez da mensagem dizendo qual café faltou.

```
estoque = 1; carrinho: 1 GRAO + 1 FINA do mesmo café
>>> FALHA: IntegrityError em vez de ErroCheckout
    (o cliente recebe página 500, sem saber qual café faltou)
```

Repare no detalhe: **a constraint do banco funcionou**. Ela foi a última
linha de defesa e impediu o estoque negativo, exatamente como o RNF01
promete. O que falhou foi a aplicação, que não traduziu aquilo em
mensagem de negócio.

A correção consolida a demanda por produto antes de validar, e faz uma
baixa por produto com a quantidade somada. As linhas do item continuam
separadas por moagem.

### 18.3 Por que a suíte não via

Porque ela não testava a **fronteira**.

| Teste que existia | Por que não pegava |
|---|---|
| `test_estoque_insuficiente_faz_rollback_completo` | Pedia 5 de um estoque de 1 — folgado demais. O defeito mora em pedir exatamente o saldo, ou o saldo + 1 |
| `test_mesmo_cafe_em_moagens_diferentes_vira_duas_linhas` | 2 + 1 unidades de um estoque de 10 — a soma nunca cruzava o limite |
| Nenhum | Não havia teste com uma transação concorrente commitando no meio |

Quatro testes de regressão foram acrescentados, todos na fronteira. Os
dois principais foram conferidos **desfazendo cada correção e rodando**:
falham contra o código antigo, passam contra o novo.

### 18.4 A lição

Suíte verde não é prova de correção — é prova de que o que foi testado
passou. Os dois defeitos sobreviveram a uma suíte que cobria compra
normal, estoque insuficiente, produto inexistente, rollback, preço
congelado e as constraints do banco.

O que os encontrou foi **revisão por quem não escreveu o código**. Quem
escreve revisa o que quis dizer; quem lê de fora revisa o que está
escrito.
