# Projeto Final — o que foi entregue

Torra & Terra · FACAMP · Tratamento e Armazenamento da Informação
Prof. Me. Nivaldo T. Marcusso · Grupo 3: Felipe Furlan, Henrique Biruel,
Henrique Palorca.

Este documento é o insumo do relatório técnico. Ele reúne o que mudou, as
saídas reais e o que ficou pendente.

**Coletado em:** 24/11/2026, no ambiente de desenvolvimento
(PostgreSQL 16, Python 3.13.18). As verificações em produção estão na
seção 9 e são preenchidas depois do deploy.

---

## 1. O que mudou, arquivo por arquivo

### Arquivos novos

| Arquivo | O que é, e por que existe |
|---|---|
| `SQL/dashboard.sql` | As oito consultas do painel, escritas à mão e comentadas com a pergunta de negócio e o índice de cada uma. **É a fonte da verdade:** a aplicação lê este arquivo e executa os blocos, então não há divergência possível entre o SQL documentado e o que roda. Também roda direto no `psql` |
| `SQL/migracao_projeto_final.sql` | A única mudança de estrutura do Projeto Final — o índice novo — num script idempotente, para aplicar em produção sem rodar o `schema.sql`, que começa com `DROP TABLE` |
| `templates/painel.html` | O painel do gestor. Gráficos em SVG gerado no servidor, sem JavaScript e sem estilo escrito no HTML |
| `templates/projeto_final.html` | A casca do relatório navegável. Nenhum texto aqui: tudo vem do `conteudo.json` |
| `templates/erro_403.html` | Página amigável para cliente logado que não é gestor. Não cita nome de variável de ambiente |
| `templates/erro_500.html` | Página de falha inesperada, sem traceback. O detalhe vai para o log |
| `templates/erro_configuracao.html` | A página 503 da aplicação sem segredo em produção. Mostra o **nome** da variável que falta, nunca o valor |
| `static/projeto_final/conteudo.json` | **Todo o texto do relatório navegável.** É o arquivo a substituir pelo conteúdo final |
| `static/projeto_final/app.js` | Só renderiza. JavaScript puro, sem framework e sem dependência |
| `static/projeto_final/estilo.css` | O visual editorial da página, com `@media print` |
| `static/projeto_final/LEIAME.md` | O contrato do `conteudo.json`: cada tipo de bloco, cada campo, e o que não pode entrar |
| `docs/api.md` | Cada endpoint com exemplo de requisição e de resposta, códigos de erro e regra de acesso |
| `docs/openapi.yaml` | Especificação OpenAPI 3.0.3 — 8 caminhos, 8 esquemas |
| `docs/postman_projeto_final.json` | Coleção do Postman, com os testes de cada requisição e o token CSRF obtido por script de pré-requisição |
| `tests/test_api.py` | Controle de acesso, contrato de erro, dinheiro como string e privacidade do `/api/resumo` |
| `tests/test_painel.py` | Acesso ao painel, indicadores, transições de status e devolução de estoque |
| `tests/test_producao.py` | O 503 sem segredo e o mascaramento de credencial em log |
| `docs/evidencias/projeto_final/` | Os prints, listados na seção 10 |

### Arquivos alterados

| Arquivo | O que mudou |
|---|---|
| `app.py` | Detecção de produção e os segredos sem valor padrão; papel de gestor e o decorador `gestor_obrigatorio`; leitura de `SQL/dashboard.sql` e a função `indicadores`; a máquina de estados do pedido e `alterar_status_pedido`; o blueprint `api` com oito endpoints; logs estruturados; o comando `seed-demo`; a CSP com a exceção de `/projeto-final`; CSRF aceitando o cabeçalho `X-CSRF-Token`; páginas de erro 403 e 500 |
| `SQL/schema.sql` | `CREATE INDEX idx_pedidos_criado_em ON pedidos(criado_em DESC)`, com o comentário justificando |
| `SQL/consultas.sql` | Seção 5 nova: o `EXPLAIN ANALYZE` de antes e depois do índice, com os números medidos e o preço em disco |
| `README.md` | Reescrito no formato do manual: objetivo, segmento e contexto, arquitetura em Mermaid, pré-requisitos com versões, configuração, carga de dados, testes, endpoints, credenciais fictícias e links |
| `docs/decisoes.md` | Cinco decisões novas: D09 (CSP só na rota do site), D10 (gestor sem mudar o schema), D11 (consultas em SQL à mão), D12 (conciliação como indicador), D13 (seed pelo checkout real) |
| `docs/evidencias.md` | Bloco "Projeto Final": seções 10 a 17 |
| `static/style.css` | O estilo do painel, no mesmo arquivo único da loja |
| `templates/base.html` | Link "Painel" no menu, só para o gestor; link "Projeto Final" no rodapé |
| `.env.example` | `ADMIN_EMAILS`, `AMBIENTE` e `TEST_DATABASE_URL`, com o comportamento de produção explicado |
| `tests/conftest.py` | Fixtures `navegador`, `entrar`, `token_da_sessao`, `gestor` e `outro_cliente` |
| `tests/test_seguranca.py` | Testes da exceção de CSP da rota `/projeto-final` |

```
 11 arquivos alterados · 12.152 linhas acrescentadas · 117 removidas
 18 arquivos e pastas novos
```

---

## 2. A lista final de endpoints

| Método e rota | Acesso | Resposta |
|---|---|---|
| `GET /health` | público | `{"status":"ok","banco":"ok"}` · 503 se o banco não responder |
| `GET /api/categorias` | público | As 4 regiões produtoras, com a contagem de cafés |
| `GET /api/produtos` | público | O catálogo. `?categoria=<id>` filtra |
| `GET /api/produtos/<id>` | público | Um café · 404 JSON se não existir |
| `GET /api/pedidos` | cliente logado | Só os pedidos do próprio cliente · 401 sem sessão |
| `GET /api/dashboard` | gestor | Os sete indicadores · 401 sem sessão · 403 sem ser gestor |
| `PATCH /api/pedidos/<id>/status` | gestor | Muda o status · 400 sem CSRF · 404 · 409 em transição proibida |
| `GET /api/resumo` | público | Só agregados que não expõem ninguém |

Rotas de página acrescentadas:

| Rota | Acesso |
|---|---|
| `GET /painel` | gestor — 302 para visitante, 403 para cliente comum |
| `POST /painel/pedidos/<id>/status` | gestor, com CSRF |
| `GET /projeto-final` | público |

Documentação: `docs/api.md` · `docs/openapi.yaml` ·
`docs/postman_projeto_final.json`.

---

## 3. A saída real dos testes

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

A lista nominal completa está em `docs/evidencias.md`, seção 10. Os casos
que o manual cobra explicitamente:

| O que o manual pede | Teste |
|---|---|
| Dashboard: indicador após inserir dados | `test_indicador_se_move_depois_de_um_checkout` |
| Atualização: alterar status, antes e depois | `test_transicao_valida_criado_para_pago` |
| Erro tratado | `test_transicoes_invalidas_sao_recusadas`, `test_patch_transicao_invalida_devolve_409` |
| Consulta com filtro | `test_filtro_de_periodo_limita_o_valor_vindo_da_url` |
| Integridade referencial | `test_produto_inexistente_nao_finaliza_o_pedido` |

---

## 4. O `EXPLAIN ANALYZE` de antes e depois do índice novo

`CREATE INDEX idx_pedidos_criado_em ON pedidos(criado_em DESC);`

Medido no PostgreSQL 16, com carga sintética de 60.000 pedidos em 24
meses. Os planos completos estão em `SQL/consultas.sql`, seção 5.

### 4.1 O card de faturamento do painel

```sql
SELECT COUNT(*), COALESCE(SUM(total), 0)
FROM pedidos
WHERE criado_em >= CURRENT_TIMESTAMP - make_interval(days => 30)
  AND status <> 'CANCELADO';
```

**ANTES**

```
Aggregate  (cost=1667.30..1667.31 rows=1) (actual time=6.692..6.692)
  Buffers: shared hit=458
  ->  Seq Scan on pedidos  (cost=0.00..1658.00 rows=1860)
                           (actual time=0.011..6.553 rows=1838)
        Filter: ((status <> 'CANCELADO') AND (criado_em >= ...))
        Rows Removed by Filter: 58162
        Buffers: shared hit=458
Execution Time: 6.713 ms
```

**DEPOIS**

```
Aggregate  (cost=562.69..562.70 rows=1) (actual time=0.882..0.882)
  Buffers: shared hit=454 read=8
  ->  Bitmap Heap Scan on pedidos  (cost=46.98..553.58)
                                   (actual time=0.191..0.743 rows=1838)
        Recheck Cond: (criado_em >= ...)
        Filter: (status <> 'CANCELADO')
        Rows Removed by Filter: 640
        Heap Blocks: exact=454
        ->  Bitmap Index Scan on idx_pedidos_criado_em
              (cost=0.00..46.52) (actual time=0.154..0.155 rows=2478)
              Index Cond: (criado_em >= ...)
Execution Time: 0.900 ms
```

**6,713 ms → 0,900 ms · 7,5× mais rápido.**

O número que explica o ganho é `Rows Removed by Filter`: 58.162 antes,
640 depois. O Seq Scan lê as 60 mil linhas e joga 97% fora.

### 4.2 A lista de pedidos recentes

```sql
SELECT p.id, p.status, p.total, p.criado_em
FROM pedidos p ORDER BY p.criado_em DESC LIMIT 20;
```

**ANTES**

```
Limit  (cost=2654.58..2654.63 rows=20) (actual time=10.387..10.390 rows=20)
  ->  Sort  (cost=2654.58..2804.58 rows=60000)
            (actual time=10.385..10.387 rows=20)
        Sort Key: criado_em DESC
        Sort Method: top-N heapsort  Memory: 27kB
        ->  Seq Scan on pedidos p  (cost=0.00..1058.00 rows=60000)
                                   (actual time=0.004..4.043 rows=60000)
Execution Time: 10.401 ms
```

**DEPOIS**

```
Limit  (cost=0.29..1.42 rows=20) (actual time=0.011..0.022 rows=20)
  ->  Index Scan using idx_pedidos_criado_em on pedidos p
        (cost=0.29..3396.26 rows=60000) (actual time=0.010..0.020 rows=20)
Execution Time: 0.031 ms
```

**10,401 ms → 0,031 ms · 335× mais rápido.**

O passo de `Sort` **desapareceu do plano**: o índice já está na ordem
pedida. É a razão de ele ser `criado_em DESC` e não apenas `criado_em`.

### 4.3 O preço

```
tabela pedidos ...... 6736 kB
idx_pedidos_criado_em  1328 kB   (~20% do tamanho da tabela)
linhas .............. 60.000
```

Todo INSERT de pedido passa a escrever em dois lugares. A troca vale
porque pedido se insere um por venda e o painel é lido a cada visita do
gestor — mas é uma troca, e é por isso que o projeto tem cinco índices e
não quinze.

### 4.4 Na base de demonstração, com 40 pedidos

Seq Scan, com e sem o índice — e é a decisão **certa** do planejador: a
tabela inteira ocupa uma página de disco.

```
Aggregate  (cost=1.97..1.98 rows=1) (actual time=0.018..0.018 rows=1)
  ->  Seq Scan on pedidos  (cost=0.00..1.80 rows=34)
        Rows Removed by Filter: 6
Execution Time: 0.053 ms
```

Vale contar na defesa: o índice não está inútil, está esperando o volume.
O planejador decide por custo estimado, e com 40 registros a decisão dele
está certa.

---

## 5. Os valores dos indicadores depois do `seed-demo`

Ambiente de desenvolvimento, período de 30 dias:

| Indicador | Valor |
|---|---|
| Faturamento | R$ 7.571,00 |
| Pedidos fechados | 34 |
| Ticket médio | R$ 222,68 |
| Vendas por região | Minas Gerais R$ 4.513,00 (59,6%) · Bahia R$ 1.618,00 (21,4%) · São Paulo R$ 1.440,00 (19,0%) |
| Top café | Alta Mogiana do Cerrado — 17 unidades, moagem MEDIA |
| Estoque crítico | Chapada Geisha (1) · Vereda do Cerrado (5) |
| Pedidos por status | CRIADO 4 · PAGO 6 · ENVIADO 24 · CANCELADO 6 |
| **Conciliação** | **40 de 40 · zero divergências** |

Depois dos pedidos feitos à mão durante a captura dos prints, o painel
mostrava **42 de 42 conciliados**.

Os números de produção entram na seção 9 depois do `seed-demo` lá.

---

## 6. Os logs, com exemplos reais

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

O sexto evento, `erro_500`, só aparece quando há falha inesperada, e
registra método e rota com o traceback — sem expor nada na página.

Senha, token, `SECRET_KEY` e URL com credencial **nunca** entram. O
`csrf_barrado` registra o **tamanho** do token enviado, nunca o valor.

---

## 7. Como aplicar em produção

Na ordem, e **sem rodar `init-db` nem `reset-db`**:

1. Variáveis no Railway:
   - `ADMIN_EMAILS=<e-mail da conta de gestor>`
   - `AMBIENTE=producao` (opcional — o Railway já define
     `RAILWAY_ENVIRONMENT`, que tem o mesmo efeito)
2. Aplicar a migração com a credencial **administrativa**:

```bash
railway ssh -s Postgres
```

```bash
psql -U postgres -d railway -f /tmp/migracao_projeto_final.sql
```

3. Carregar os dados de demonstração:

```bash
railway run flask --app app seed-demo
```

4. Criar a conta de gestor pelo `/cadastro` da loja, com o e-mail que
   estiver em `ADMIN_EMAILS`.
5. Validar com os `curl` da seção 9.

> A aplicação conecta como `torra_app`, que não pode criar índice. Isso é
> o privilégio restrito funcionando, não um defeito — por isso a migração
> roda com a credencial administrativa.

---

## 8. Limitações que ficaram

### Do produto

| Limitação | Por quê | O que seria preciso |
|---|---|---|
| Sem pagamento real | O escopo é a integridade do pedido | Gateway e um status de autorização entre CRIADO e PAGO |
| Sem frete | O total é a soma dos itens | Integração com transportadora e endereço |
| Sem lote e data de torra | Evolução mais natural do domínio | Tabela de lotes, com o item referenciando o lote |
| Sem cadastro de produto pela interface | Produtos entram pelo `seed.sql` | CRUD para a Operação, com as mesmas constraints |
| Carrinho na sessão | Decisão consciente: carrinho é processo | Redis, para sobreviver à troca de dispositivo |

### Da implementação do Projeto Final

| Limitação | Detalhe |
|---|---|
| **Gestor por variável de ambiente** | Trocar o gestor exige editar `ADMIN_EMAILS` e reiniciar o serviço. Com papéis diferentes entre si, viraria tabela |
| **API sem paginação** | `GET /api/produtos` devolve o catálogo inteiro. Com centenas de itens, `?pagina=` passaria a ser necessário |
| **API sem versionamento nem limite de taxa** | Não há `/api/v1/`, e `/api/resumo` é público sem *rate limit*. Num serviço de verdade, ambos seriam exigidos antes de abrir a rota |
| **`SQL/dashboard.sql` em cache por processo** | Editar o `.sql` exige reiniciar a aplicação. Mesmo comportamento do `schema.sql` |
| **O `seed-demo` simula a data** | O pedido nasce agora e o `criado_em` é reescrito. Está declarado no código e no README |
| **O site do Projeto Final exige JavaScript** | É a única rota da loja que exige. O `<noscript>` explica e lembra que a loja em si funciona sem |

### Pendências herdadas, que continuam abertas

| Pendência | Situação |
|---|---|
| **Deploy automático a cada push** | Documentado em `docs/evidencias.md`, seção 8.4. O webhook do GitHub para o Railway não estava entregando; o deploy saía com `railway deployment redeploy --from-source`. **Confirmar se ainda é o caso antes de contar com o push automático** |
| **Sub Resource Integrity no Google Fonts** | Não aplicável ao Google Fonts, que serve formatos diferentes por navegador. Mitigado pela CSP. A correção definitiva é hospedar as fontes junto com a aplicação |

### Dois defeitos graves encontrados por revisão, e corrigidos

Com a entrega pronta e a suíte verde, o código novo passou por revisão
independente. Ela achou dois defeitos no `finalizar_pedido` — anteriores
a esta entrega, e invisíveis para todos os testes que existiam.

1. **O `SELECT ... FOR UPDATE` protegia o banco e não a aplicação.** A
   rota de checkout carrega o produto na sessão antes da transação, e o
   ORM devolve o objeto já carregado em vez da linha recém-travada. O
   lock era tomado, a concorrente esperava, e a validação decidia com o
   saldo de antes. Reproduzido: **duas unidades vendidas de um estoque de
   uma, sem erro nenhum.** Corrigido com `populate_existing=True`.
2. **A validação era por linha do carrinho, não por produto.** Mesmo café
   em duas moagens somando mais que o estoque gravava `-1`, e o cliente
   recebia página 500 em vez da mensagem de negócio. Corrigido
   consolidando a demanda por produto antes de validar.

Quatro testes de regressão na fronteira, os dois principais conferidos
desfazendo cada correção. O relato completo está em `docs/evidencias.md`,
seção 18 — e vale levar para a defesa: é a melhor evidência de
maturidade técnica que o projeto tem.

### Um defeito encontrado nesta rodada, e não corrigido

**A rota `/apresentacao` usa estilo escrito no HTML.** Ela foi feita antes
da análise da CSP e tem dezenas de `style="..."` nos templates. Como a
política da loja traz `style-src 'self'` **sem** `unsafe-inline`, o
navegador **descarta esses estilos** na loja publicada.

A falha é silenciosa: a página carrega, o servidor não registra erro
nenhum, e só o navegador mostra o resultado sem a formatação pretendida.

Não foi corrigido porque está fora do escopo desta tarefa e porque a
correção é mecânica — mover cada `style=` para classe no `static/style.css`
— mas longa. **Vale conferir no navegador antes da apresentação**, já que
`/apresentacao` é uma das páginas que podem ser mostradas ao professor.

---

## 9. Verificação em produção

> **Pendente.** Esta seção se preenche depois do push e do deploy. O
> container em que este trabalho foi feito não tem a CLI do Railway, e a
> aplicação em produção ainda não recebeu as variáveis novas.

Comandos a rodar, e o que cada um deve devolver:

```bash
curl -s https://nivaldo.felipefurlan.com.br/health
```

```bash
curl -s https://nivaldo.felipefurlan.com.br/api/produtos | head -c 400
```

```bash
curl -s https://nivaldo.felipefurlan.com.br/api/resumo
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nivaldo.felipefurlan.com.br/api/dashboard
```

| Verificação | Esperado |
|---|---|
| `/health` | `{"status":"ok","banco":"ok"}` |
| `/api/produtos` | 200, com os 12 cafés e `preco` como string |
| `/api/resumo` | 200, com a conciliação fechando |
| `/api/dashboard` **sem login** | **401** — é o controle de acesso funcionando |
| `/api/pedidos` sem login | **401** |
| `/painel` sem login | **302** para o login |
| `/painel` como cliente comum | **403** |
| `/painel` como gestor | **200**, com os sete indicadores |
| `/projeto-final` | **200**, com os indicadores ao vivo lendo de produção |

Resultado local equivalente, já verificado:

```
/health              -> 200
/api/categorias      -> 200
/api/produtos        -> 200
/api/resumo          -> 200
/api/dashboard       -> 401
/api/pedidos         -> 401
```

---

## 10. Os prints

Em `docs/evidencias/projeto_final/`. Capturados no Chromium, a 1440×1000,
em escala 2×.

### A loja e o fluxo de compra

| Arquivo | URL | O que comprova |
|---|---|---|
| `01_catalogo.png` | `/` | O catálogo vem do banco, com preço formatado em R$, região, torra e pontuação SCA em cada card |
| `02_produto.png` | `/produto/11` | O detalhe do café, com a escolha de **moagem** na compra e o aviso de última unidade |
| `03_carrinho.png` | `/carrinho` | O carrinho na sessão, com a moagem escolhida e o total recalculado |
| `04_checkout.png` | `/checkout` | A conferência antes de fechar: itens, moagem e total |
| `05_checkout_sucesso.png` | `/meus-pedidos` | O pedido confirmado, com número |
| `06a_checkout_com_estoque_1.png` | `/checkout` | O carrinho com 2 unidades de um café que tem estoque 1 — o cenário de erro, montado |
| `06_checkout_recusado_estoque.png` | `/carrinho` | **A evidência central do RF05.** A mensagem *"Estoque insuficiente de Chapada Geisha: você pediu 2 e temos 1 em estoque"* nomeia o café e informa o saldo real. Nada foi gravado |
| `07_meus_pedidos.png` | `/meus-pedidos` | O histórico do cliente, com a moagem e o preço congelado de cada item |

### O controle de acesso

| Arquivo | URL | O que comprova |
|---|---|---|
| `08_403_cliente_comum.png` | `/painel` | Cliente logado que não é gestor recebe 403 com página amigável, **sem citar nome de variável de ambiente** |
| `13_health.png` | `/health` | O health check respondendo `{"status":"ok","banco":"ok"}` |

### O painel do gestor

| Arquivo | URL | O que comprova |
|---|---|---|
| `09_painel.png` | `/painel` | Os quatro cartões — faturamento, ticket médio, estoque crítico e **conciliação em verde, 42 de 42** — e o gráfico de vendas por região |
| `10_painel_pedidos.png` | `/painel#pedidos` | A lista de pedidos recentes, com cliente, data, itens, total, status e as ações disponíveis para cada status |
| `11_status_antes.png` | `/painel` | **Antes:** o pedido #41 em `CRIADO`, com os botões "Marcar como pago" e "Cancelar" |
| `12_status_depois.png` | `/painel` | **Depois:** a mensagem *"Pedido #42: CRIADO → PAGO."* no topo da página |
| `12b_status_depois_na_lista.png` | `/painel` | A mesma linha do pedido #42, agora em `PAGO`, com as ações mudadas para "Marcar como enviado" e "Cancelar" |
| `24_painel_mobile.png` | `/painel` (390×844) | O painel no celular: as tabelas rolam na horizontal em vez de estourar a tela |

> `11_status_antes.png` e `12b_status_depois_na_lista.png` são o par
> "antes e depois" que o manual pede para a atualização de registro.

### O site do Projeto Final

| Arquivo | URL | O que comprova |
|---|---|---|
| `14_projeto_final_capa.png` | `/projeto-final` | A capa, o índice lateral com as 12 seções e o aviso de que a página complementa o relatório em documento |
| `15_componente_as_is.png` | `/projeto-final#sec-contexto` | O fluxo **AS IS**, com as falhas de cada passo em vermelho |
| `16_componente_to_be.png` | `/projeto-final#sec-contexto` | O fluxo **TO BE** depois do clique, com os pontos de validação em verde |
| `17_componente_er.png` | `/projeto-final#sec-banco` | O diagrama das 5 tabelas, com `itens_pedido` selecionada |
| `18_componente_checkout.png` | `/projeto-final#sec-processo` | A simulação no passo 9 de 10: o Bruno em `ROLLBACK`, o selo **simulação ilustrativa** e o nome do teste que prova o comportamento |
| `19_componente_explain.png` | `/projeto-final#sec-banco` | Os dois planos de execução lado a lado, com os tempos reais |
| `20_componente_indicadores.png` | `/projeto-final#sec-resumo` | Os indicadores lidos **ao vivo** de `/api/resumo`, com a hora da leitura |
| `21_componente_testes.png` | `/projeto-final#sec-testes` | A tabela de casos de teste com o filtro por tipo aplicado |
| `22_projeto_final_mobile.png` | `/projeto-final` (390×844) | A página no celular |
| `23_projeto_final_mobile_indice.png` | `/projeto-final` (390×844) | O índice lateral aberto no celular |

### Prints a refazer em produção

Os acima foram capturados no ambiente de desenvolvimento. Depois do
deploy, vale refazer pelo menos estes quatro na URL pública, para o
relatório mostrar a loja no ar:

- `/painel` como gestor, com os dados de produção
- `/projeto-final`, com os indicadores ao vivo de produção
- `/health`
- `/api/dashboard` sem login, mostrando o **401**

Os prints das atividades anteriores continuam em `docs/capturas/`.

---

## 11. O que o Claude Code **não** fez, e por quê

| Não feito | Motivo |
|---|---|
| **O push** | O prompt manda parar antes do primeiro push e esperar o OK |
| **Deploy no Railway** | A CLI do Railway não existe neste container, e não há credencial do Railway aqui |
| **Aplicar a migração em produção** | Depende do acesso administrativo ao banco do Railway |
| **Criar a conta de gestor em produção** | Depende do deploy e da variável `ADMIN_EMAILS` |
| **Os `curl` em produção** | Dependem do deploy |
| **Slides e relatório em documento** | Ficam no Claude Slides, fora do escopo desta tarefa |
| **O `conteudo.json` final** | O arquivo entregue é uma **primeira versão**, montada a partir do que já existia em `docs/`. O texto final substitui esse arquivo — o formato está documentado em `static/projeto_final/LEIAME.md` |
