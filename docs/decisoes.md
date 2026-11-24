# Decisões de projeto

Registro das escolhas que fogem do óbvio ou do material da disciplina, com a
justificativa. Serve para a defesa oral: toda decisão aqui tem um "por quê".

---

## D01 — Deploy no Railway em vez de Render + Neon

**O material recomenda** (Bloco 6, slides 38, 39 e 45): GitHub para
versionamento, **Render** para a aplicação e **Neon/Supabase** para o PostgreSQL.

**Escolhemos o Railway.** Motivos:

1. O critério de avaliação do slide 42 é agnóstico de ferramenta — diz apenas
   *"se a solução está publicada e utilizável"*. O que é avaliado é o resultado.
2. Já existe plano Hobby ativo na conta, então não há custo adicional.
3. O Railway hospeda **aplicação e banco no mesmo projeto**, com
   *reference variable* (`${{Postgres.DATABASE_URL}}`) ligando os dois. No
   Render + Neon a string de conexão é copiada à mão entre dois provedores — mais
   passos e mais chance de erro.
4. Domínio próprio já disponível: `nivaldo.felipefurlan.com.br`.

**O que não muda:** GitHub como versionamento, `Procfile` com gunicorn,
`DATABASE_URL` e `SECRET_KEY` por variável de ambiente, deploy automático a cada
push. A arquitetura de deploy é a mesma que o material descreve; só o provedor é
outro.

**Plano B.** Se for exigida a ferramenta do material, a migração é barata: o
Render lê o mesmo `Procfile`, e o Neon entrega uma `DATABASE_URL` no mesmo
formato `postgresql://` — que o `app.py` já normaliza para
`postgresql+psycopg://`. Nenhuma linha de código muda.

---

## D02 — `moagem` mora em `itens_pedido`, não em `produtos`

O cliente escolhe a moagem **na hora da compra**. O mesmo café pode ser vendido
em grão para um cliente e moído fino para outro, no mesmo dia.

Se `moagem` fosse coluna de `produtos`, o mesmo café precisaria virar três
registros diferentes — triplicando o cadastro e quebrando o controle de estoque,
que é do café e não da moagem.

É esse atributo que faz `itens_pedido` ser **entidade** e não tabela de ligação:
ela tem dados próprios que não pertencem nem ao pedido nem ao produto.

---

## D03 — `preco_unitario` é congelado no item

O preço do café muda: safra nova, câmbio, reajuste. Se o pedido antigo lesse o
preço de `produtos`, o histórico se reescreveria sozinho e o total do pedido
deixaria de bater com a soma dos itens.

Gravar o preço no item é **desnormalização deliberada**: aceita-se a redundância
porque o dado tem significado temporal — é "o preço naquele momento", não "o
preço do produto". Responde diretamente ao teste mental do slide 16:
*"o que acontece se o produto mudar de preço? Onde o histórico deve ficar?"*

---

## D04 — Carrinho na sessão, não no banco

Recomendação explícita do material (slide 17): *"diferencie entidade de processo:
carrinho pode ser sessão no MVP, não necessariamente tabela"*.

O carrinho é **processo**, não entidade: existe só enquanto a compra não fecha e
não tem valor histórico. Vira entidade (`pedidos` + `itens_pedido`) no instante
do checkout.

**Limitação aceita:** o carrinho não sobrevive à troca de dispositivo. É
exatamente o cenário em que um Redis passaria a fazer sentido — resposta pronta
para a pergunta 4 do slide 47.

---

## D05 — Constraints no banco, não só na aplicação

O material insiste nisso em três lugares (slides 21, 24 e 48). A validação do
formulário protege a experiência do usuário; a constraint protege o **dado**.

O exemplo mais claro é `pontuacao_sca BETWEEN 80 AND 100`: café especial, pela
definição da SCA, pontua 80 ou mais. É regra do negócio, não do formulário. Se
amanhã alguém inserir um produto por um script, por um `INSERT` manual ou por
uma futura API, a regra continua valendo.

Por isso o `SQL/schema.sql` é **DDL escrito à mão**, nunca gerado por
`db.create_all()`: as constraints precisam estar visíveis em SQL, não escondidas
no ORM.

---

## D06 — Usuário próprio do PostgreSQL para a aplicação

Slides 20 e 35: *"a aplicação usa usuário próprio no PostgreSQL, não
superusuário"*.

O `postgres` pode dropar qualquer coisa no cluster inteiro. Uma falha de SQL
injection ou um bug num script rodando como superusuário é catastrófico. O
`torra_app` tem apenas `SELECT`, `INSERT`, `UPDATE` e `DELETE` nas tabelas da
aplicação — não pode alterar o schema nem tocar em outros bancos.

Ver `SQL/usuario_app.sql`.

**Correção feita durante o deploy.** Este documento afirmava antes que "no
Railway isso é resolvido pelo provedor". **Estava errado.** A conferência em
produção mostrou:

```
usuario=postgres  superuser=True  banco=railway
```

O Railway entrega na `DATABASE_URL` o usuário `postgres`, que é superusuário
dentro daquele container. O isolamento do provedor é no nível do **container**,
não no nível do **papel** — e o RNF04 fala de papel.

Criamos então o `torra_app` também no banco de produção, com os mesmos
privilégios restritos, e apontamos a `DATABASE_URL` do serviço para ele. A
verificação depois da troca:

```
conectou como torra_app | superuser=False
SELECT ok -> 12 cafés
INSERT e UPDATE ok (sequence acessível)
DROP TABLE negado, como esperado: InsufficientPrivilege
```

**Efeito colateral aceito:** a `DATABASE_URL` deixou de ser a *reference
variable* `${{Postgres.DATABASE_URL}}` e virou uma URL explícita. Se o Railway
trocar o hostname interno do Postgres, a referência se atualizaria sozinha e a
URL explícita não. A senha do `torra_app` é nossa e não rotaciona, e
`postgres.railway.internal` é estável — mas é um ponto de manutenção que antes
não existia.

---

## D07 — SERIAL em vez de IDENTITY

`GENERATED BY DEFAULT AS IDENTITY` é o padrão SQL moderno e o preferido no
PostgreSQL 10+. Usamos `SERIAL` porque é a forma que aparece no material do
professor (slide 21) e a que o grupo consegue explicar sem ressalvas na defesa.

A diferença prática neste projeto é nula: ambos criam uma sequence.

---

## D08 — Flask-SQLAlchemy no `requirements.txt`

**Aqui houve um descumprimento de regra, e ele precisa estar registrado.**

A regra 2 do `CLAUDE.md` fecha a stack em PostgreSQL, Python, Flask,
SQLAlchemy, Jinja, psycopg 3, gunicorn, pytest e python-dotenv, e diz:
*"Nada além disso sem me perguntar antes."*

O `requirements.txt` tem **Flask-SQLAlchemy**, que não está nessa lista. Ele
foi adicionado sem a pergunta prévia que a regra exige.

**A justificativa técnica existe** — o material do professor usa essa
biblioteca. O slide 29 mostra exatamente esta API:

```python
db = SQLAlchemy(app)

class Produto(db.Model):
    __tablename__ = "produtos"
```

`SQLAlchemy(app)` e `db.Model` são do Flask-SQLAlchemy, não do SQLAlchemy
puro. Seguir o slide à risca implica usá-la. Ela é uma camada fina sobre o
SQLAlchemy: cuida do ciclo de vida da sessão dentro do contexto do Flask e
do `db.Model` declarativo.

**O que mudaria sem ela:** o projeto usaria `sessionmaker` e
`scoped_session` montados à mão, e o código se afastaria do exemplo do
material — ficaria mais difícil de defender na apresentação, não mais fácil.

**Como reverter, se for exigido:** trocar `db = SQLAlchemy()` por um
`registry()` do SQLAlchemy 2.0, criar a sessão por requisição num
`teardown_appcontext`, e ajustar os cinco modelos para herdar de uma
`DeclarativeBase`. É trabalho de uma tarde e não muda o schema, o
`checkout` nem os testes.

**Atualização.** A regra foi relaxada depois: a orientação passou a ser
*"pode ser qualquer linguagem desde que seja SQL"*. O Flask-SQLAlchemy deixa
de ser um desvio — mas o registro fica, porque a decisão foi tomada antes da
autorização, e é isso que este documento existe para rastrear.

---

## D09 — CSP relaxada só na rota `/projeto-final`

**O contexto.** A loja serve `script-src 'none'`. Isso foi possível
porque nenhuma página dela usa JavaScript, e é a política mais restritiva
que existe: não há onde um script injetado executar.

O site do Projeto Final precisa de JavaScript. Os seis componentes
interativos — o diagrama do modelo de dados clicável, a simulação de duas
compras simultâneas, os indicadores lidos ao vivo da API — são o motivo
de a página existir. Um relatório sobre transação concorrente que não
deixa o leitor **ver** a concorrência acontecer explica menos.

**A decisão.** Apenas a rota `/projeto-final` serve
`script-src 'self'; connect-src 'self'`. O `app.py` decide pelo
`request.path`, num `if` de uma linha.

**O que a exceção libera, e o que não libera:**

| | |
|---|---|
| `script-src 'self'` | Só arquivo `.js` servido por este domínio. **Sem `unsafe-inline`**: não existe `<script>` escrito no HTML nem `onclick=` na página, então conteúdo injetado no HTML continua sem poder executar. **Sem `unsafe-eval`** |
| `connect-src 'self'` | O `fetch` dos indicadores só alcança a própria aplicação. Um script que tentasse vazar dado para fora seria bloqueado pelo navegador |

**O que não muda.** Catálogo, produto, carrinho, checkout, meus pedidos e
painel — as rotas que tocam dinheiro, sessão e estoque — continuam com
`script-src 'none'`.

**Um efeito colateral que mudou o design do painel.** A política traz
também `style-src 'self'` sem `unsafe-inline`, o que faz o navegador
**descartar todo `style="..."` escrito no HTML**. Isso elimina o truque
comum de barra de gráfico em CSS (`style="width: 62%"`), que simplesmente
não renderiza na loja.

A saída foi gerar as barras em **SVG no servidor**, com a largura no
atributo `width` do `<rect>` — atributo de apresentação do SVG, não CSS, e
portanto fora do alcance da CSP. E cada gráfico virou uma tabela de
verdade com a barra dentro da célula. O resultado ficou melhor que a
solução original: o número continua legível no projetor, no celular, no
leitor de tela e na impressão.

> Falha silenciosa que vale conhecer: a rota `/apresentacao`, feita antes
> desta análise, tem estilo escrito no HTML. Na loja publicada esses
> estilos são descartados pelo navegador, sem erro nenhum no servidor.
> Está registrado em `docs/projeto_final_entrega.md`, entre as pendências.

---

## D10 — Papel de gestor por variável de ambiente, sem mudar o schema

**A alternativa seria** uma coluna `clientes.papel`, ou uma tabela de
papéis com relacionamento N:N.

**A decisão.** Quem pode abrir o painel vem de `ADMIN_EMAILS`, uma
variável de ambiente com e-mails separados por vírgula. Um cliente logado
cujo e-mail esteja na lista é gestor.

**Por quê.** O `SQL/schema.sql` é a entrega avaliada do trabalho e já está
aplicado no banco de produção. Acrescentar uma coluna obrigaria a uma
migração num banco no ar para atender um requisito de **operação**, não de
modelagem. Quem administra a loja é decisão de configuração do deploy —
da mesma natureza da `SECRET_KEY`, e por isso mora no mesmo lugar que ela.

**A limitação, aceita e declarada.** Trocar o gestor exige editar a
variável e reiniciar o serviço; não dá para fazer pela interface. Com mais
de um punhado de gestores, ou com papéis diferentes entre si — um que só
lê indicadores, outro que muda status —, isso viraria tabela. No escopo
do MVP, com um gestor, não vira.

**O que não foi relaxado.** Esconder o link "Painel" no menu não é a
proteção; a proteção é o decorador `gestor_obrigatorio` na rota. Existe
teste para o caso de um cliente comum montar o `POST` à mão, com token
CSRF válido da própria sessão: ele recebe 403 e o status do pedido não
muda.

---

## D11 — As consultas do painel em SQL à mão, lidas de um arquivo

**A alternativa seria** escrever os indicadores com o ORM:
`db.select(...).join(...).group_by(...)`.

**A decisão.** Os sete indicadores estão em `SQL/dashboard.sql`, escritos
à mão e comentados com a pergunta de negócio e o índice de cada um. O
`app.py` **lê esse arquivo**, separa os blocos pelo marcador
`-- @consulta: nome` e executa cada bloco com `text()` e parâmetros
ligados.

**Por quê, em três razões:**

1. Os indicadores são o núcleo do critério de banco de dados do trabalho.
   Escritos no ORM eles existiriam, mas não estariam **visíveis** — e o
   que se avalia aqui é a consulta, com o `GROUP BY`, os `JOIN` e o índice
   que ela usa.
2. O arquivo roda direto no `psql`, do jeito que está, com `-v dias=30`.
   O professor executa e vê o mesmo SQL que a tela executa.
3. Não existe divergência possível entre "o SQL documentado" e "o SQL que
   roda". São o mesmo texto.

**O custo.** O arquivo é lido uma vez por processo e fica em cache; editar
o `.sql` exige reiniciar a aplicação. É o mesmo comportamento do
`schema.sql`, e preferível a ler o disco a cada carregamento do painel.

**O que não foi relaxado.** O `?dias=` chega pela URL e **nunca** entra no
SQL por concatenação. Vai ligado como parâmetro, o intervalo é montado
pelo próprio PostgreSQL com `make_interval(days => :dias)`, e o valor é
limitado a 1–365 antes de chegar ao banco — `?dias=99999999` faria o
planejador desprezar o índice e varrer a tabela inteira.

---

## D12 — Conciliação como indicador, e não como relatório de auditoria

**A decisão.** Um dos sete indicadores do painel conta quantos pedidos têm
`total` igual à soma de `quantidade × preco_unitario` dos itens, e mostra
o resultado como **"Pedidos conciliados: X de X"**.

**Por quê.** O contexto escolhido no Segmento 1 é *carrinho, pedidos e
pagamentos*, e a dor descrita é *falhas de confirmação e de conciliação*.
Esse número é a **medida direta** dessa dor.

Ele também muda a natureza do que o trabalho afirma. Dizer "o checkout é
atômico" é uma afirmação sobre o código, que o avaliador precisa aceitar
lendo o `app.py`. Mostrar "42 de 42 pedidos conferem" é uma consulta que
confere 100% dos registros e devolve zero divergências — verificável por
quem nunca vai ler o código.

**Decisões de desenho da consulta:**

- **`LEFT JOIN`, não `JOIN`.** Um pedido sem nenhum item seria a prova de
  uma transação partida pela metade. Com `JOIN` ele desapareceria da
  conferência justamente no caso em que mais importa aparecer.
- **Todos os status entram, cancelado incluído.** Cancelar muda o status e
  devolve o estoque, mas **não reescreve o histórico financeiro**: os
  itens e o total continuam gravados, e continuam tendo que bater entre
  si.
- **O indicador é um semáforo.** Quando fecha, o cartão fica verde; quando
  não fecha, vermelho, e diz quantos divergiram. Tem que ser legível de
  longe, no projetor, sem comparar dois números.

---

## D13 — O `seed-demo` passa pelo checkout real

**A alternativa seria** um script de `INSERT` gerando pedidos
diretamente — mais rápido de escrever e de rodar.

**A decisão.** Cada pedido de demonstração nasce de `finalizar_pedido`, a
mesma função do checkout da loja, com o mesmo `SELECT ... FOR UPDATE`, a
mesma validação de estoque e o mesmo congelamento de preço. Os
cancelamentos passam por `alterar_status_pedido`, que devolve o estoque na
mesma transação.

**Por quê.** Dado de demonstração inserido por `INSERT` direto produziria
um painel bonito e **mentiroso**. O indicador de conciliação fecharia
porque o `INSERT` caprichou no total, não porque a transação funciona — e
o indicador existe exatamente para provar a transação. Um painel que prova
o cuidado de quem escreveu o seed não prova nada.

Vale para o estoque também: marcar `status = 'CANCELADO'` com `UPDATE`
deixaria o saldo errado, e o painel contaria uma história impossível.

**O que é simulado, e está declarado como tal:** a **data**. O pedido
nasce agora e o `criado_em` é reescrito para dentro dos últimos trinta
dias. Não há como fazer de outro jeito sem viajar no tempo, e sem espalhar
as datas o filtro de período do painel não teria o que filtrar.

**Duas garantias operacionais.** O comando não apaga nada — nenhum
`TRUNCATE`, nenhum `DELETE` — e pode rodar num banco que já tem clientes
reais. E ele preserva o `Chapada Geisha`, que o `seed.sql` deixa com
estoque 1 de propósito: se a demo o consumisse, a evidência mais
importante do trabalho iria embora.
