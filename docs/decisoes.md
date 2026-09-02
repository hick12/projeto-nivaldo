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
