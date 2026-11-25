# Repasse para a sessão local — destravar o deploy

Este arquivo existe para ser **colado inteiro** no Claude Code que roda no
PC. Ele é autossuficiente: não depende do histórico da sessão da nuvem.

Cole daqui para baixo.

---

Você vai destravar o deploy da loja Torra & Terra. A sessão da nuvem fez
todo o código, mas não tem CLI nem credencial do Railway — é por isso que
você foi chamado.

## 1. Repositório, pasta e branch

- **Repositório:** `hick12/projeto-nivaldo`
- **Branch:** `main`. Está tudo publicado, HEAD = `b42286a`. Nada pendente.
- **Pasta:** confira com `git remote -v` se a sua pasta atual é esse
  repositório. Se for, `git pull origin main`. Se não for, clone.
- A branch `claude/confident-thompson-a6885s` aponta para o mesmo commit.
  Pode ignorar.

## 2. Objetivo

Pôr a loja de volta no ar em `https://nivaldo.felipefurlan.com.br`, com
`/painel` (só gestor), `/projeto-final` e a API JSON funcionando. A defesa
é 02/12, e o site no ar é pré-requisito para os prints e para a
demonstração ao vivo.

## 3. Passos, na ordem

### Passo 1 — Descobrir por que está 404

Hoje `https://nivaldo.felipefurlan.com.br/health` devolve, e a raiz `/`
também:

```
{"status":"error","code":404,"message":"Application not found"}
```

Isso é erro de **borda do Railway** — não há aplicação atendendo nesse
domínio. **Não é erro da aplicação:** se o app tivesse subido e quebrado,
seria 502 ou 503.

Hipóteses, em ordem de probabilidade:

1. Serviço parado ou sem deployment ativo
2. Último deploy falhou
3. Domínio desconectado do serviço

Comece pelo dashboard (`railway.app`, projeto `worthy-serenity`): ele
mostra as três de uma vez. Pela CLI, `railway status` e `railway logs`.

> **Isso mexe em produção.** Confirme com o Felipe antes de aplicar
> qualquer correção.

### Passo 2 — Variável do gestor

| | |
|---|---|
| Nome | `ADMIN_EMAILS` |
| Valor | `gestor.demo@exemplo.com` + o e-mail pessoal do Felipe, separados por vírgula |

Peça o e-mail pessoal a ele; não está escrito em lugar nenhum do
repositório, de propósito. Sem essa variável ninguém é gestor e o
`/painel` devolve 403 para todos — o resto da loja funciona normal.

### Passo 3 — O índice novo no banco

> ⚠️ **NUNCA rode `flask init-db` nem `flask reset-db` contra produção.**
> O `SQL/schema.sql` começa com `DROP TABLE` e apagaria clientes, pedidos
> e o histórico de vendas. Sem rollback.

A única mudança de estrutura do Projeto Final é um índice. A aplicação
conecta como `torra_app`, que **não pode criar índice** — isso é o
privilégio restrito funcionando, não defeito. Então precisa da credencial
administrativa:

```bash
railway ssh -s Postgres
```

```bash
psql -U postgres -d railway -c "CREATE INDEX IF NOT EXISTS idx_pedidos_criado_em ON pedidos(criado_em DESC); ANALYZE pedidos; ANALYZE itens_pedido;"
```

É idempotente — rodar duas vezes não causa erro. O equivalente completo
está em `SQL/migracao_projeto_final.sql`.

### Passo 4 — Dados de demonstração

```bash
railway run flask --app app seed-demo
```

Cria 8 clientes fictícios (`@exemplo.com`) e cerca de 40 pedidos
espalhados por 30 dias. **Não apaga nada** e pode rodar num banco que já
tem dados reais. Os pedidos passam pelo `finalizar_pedido` de verdade,
com a mesma transação do checkout.

Ele preserva de propósito o café `Chapada Geisha` com estoque 1 — é o que
deixa a demonstração do rollback pronta. Se esse estoque for consumido, a
evidência mais importante do trabalho vai embora.

### Passo 5 — Conta de gestor

Pelo `/cadastro` da própria loja, no navegador, com o e-mail que entrou em
`ADMIN_EMAILS`. **Não crie pelo seed:** conta administrativa com senha
publicada em README seria porta aberta em produção.

## 4. O que já está feito

Não refaça nada disto — está tudo na `main`:

- Segredos sem valor padrão em produção (503 nomeando a variável que
  falta, nunca o valor)
- Papel de gestor por `ADMIN_EMAILS`, sem mexer no schema
- `SQL/dashboard.sql` com os 7 indicadores em SQL à mão, lido pelo
  `app.py` — não há SQL de indicador duplicado em Python
- `/painel` com indicadores e mudança de status (cancelar devolve estoque
  na mesma transação)
- API JSON com 8 endpoints, `docs/api.md`, OpenAPI e coleção do Postman
- Logs estruturados, e-mail mascarado, senha do banco nunca registrada
- `flask seed-demo`
- `/projeto-final` com 6 componentes interativos
- 117 testes passando contra PostgreSQL de verdade
- 26 prints em `docs/evidencias/projeto_final/`

**Dois bugs graves já corrigidos**, para você não estranhar o commit:

1. O `SELECT ... FOR UPDATE` travava a linha no banco mas **não protegia
   a venda** — a rota de checkout já tinha carregado o produto na sessão
   do ORM, e o ORM devolvia o objeto em memória em vez da linha
   recém-travada. Reproduzido: duas unidades vendidas de um estoque de
   uma. Corrigido com `populate_existing=True`.
2. Validação por linha do carrinho em vez de por produto: mesmo café em
   duas moagens somando mais que o estoque dava página 500. Corrigido
   consolidando a demanda por produto.

**Descartado, não tente:** `style-src 'unsafe-inline'` na CSP — valeria
para a loja inteira e devolveria o vetor que a política fecha.

## 5. Como verificar no fim

```bash
curl.exe -s https://nivaldo.felipefurlan.com.br/health
```

```bash
curl.exe -s -o NUL -w "%{http_code}" https://nivaldo.felipefurlan.com.br/projeto-final
```

```bash
curl.exe -s -o NUL -w "%{http_code}" https://nivaldo.felipefurlan.com.br/api/resumo
```

```bash
curl.exe -s -o NUL -w "%{http_code}" https://nivaldo.felipefurlan.com.br/api/dashboard
```

| Rota | Esperado |
|---|---|
| `/health` | `{"banco":"ok","status":"ok"}` |
| `/projeto-final` | 200 |
| `/api/resumo` | 200, com a conciliação fechando |
| `/api/dashboard` **sem login** | **401** — é o controle de acesso funcionando, não erro |
| `/painel` sem login | 302 para o login |
| `/painel` como gestor | 200, com os sete indicadores |

**O sinal mais forte de sucesso:** em `/api/resumo`,
`conciliacao.conciliados` igual a `conciliacao.pedidos`. É o indicador
central do trabalho e precisa dar zero divergência.

## 6. O que devolver

Guarde e entregue ao Felipe:

1. A saída dos quatro `curl` acima
2. O JSON completo de `/api/resumo`
3. O que estava errado no Railway e o que foi feito para corrigir

Isso fecha a seção 9 do `docs/projeto_final_entrega.md`, hoje marcada
como pendente.
