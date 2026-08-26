# Perguntas para a defesa

As seis perguntas de discussão do material (slide 47), respondidas com o
recorte deste projeto. Não são respostas para decorar — são o roteiro do que
precisa estar claro na cabeça de quem apresenta.

---

## 1. Que requisitos são realmente indispensáveis para o MVP?

Os que o **fluxo de compra não fecha sem eles**. Aplicando esse corte:

**Indispensáveis:** RF01 catálogo lendo do banco, RF03 carrinho, RF04
identificação do cliente e RF05 checkout transacional. Sem qualquer um dos
quatro não existe venda registrada.

**Importante mas não bloqueante:** RF02 detalhe do produto (o catálogo já
mostra preço e nome) e RF06 histórico (o pedido existe no banco mesmo sem
tela para vê-lo).

**Ficaram fora conscientemente:** pagamento, frete, área administrativa e
relatórios. Todos estão listados em `requisitos.md` como evolução, com o
motivo.

O critério que usamos: *o requisito é indispensável se a sua ausência quebra
a integridade do dado ou impede a transação principal.* Tela bonita não entra
nesse teste; transação atômica entra.

---

## 2. Quais campos merecem constraint no banco, além da validação da aplicação?

Os que carregam **regra de negócio**, não regra de formulário. A distinção:
a validação do formulário protege a experiência; a constraint protege o dado.

O exemplo mais forte é **`pontuacao_sca BETWEEN 80 AND 100`**. Café especial,
pela definição da SCA, pontua 80 ou mais. Isso não é preferência de interface
— é o que define o produto. Se amanhã alguém inserir um café por um `INSERT`
manual, por um script de importação ou por uma futura API, a regra precisa
continuar valendo.

Os demais, pela mesma lógica:

| Constraint | Por que no banco |
|---|---|
| `preco NUMERIC(10,2) CHECK (preco >= 0)` | Dinheiro negativo não existe. E `NUMERIC` em vez de `FLOAT` porque ponto flutuante binário não representa `0,10` exatamente |
| `estoque >= 0` | Última linha de defesa contra venda a descoberto, mesmo se o `FOR UPDATE` falhar |
| `quantidade > 0` | Item com quantidade zero não é item |
| `torra`, `moagem`, `status` em `CHECK ... IN (...)` | Domínio fechado. Um status inventado quebraria toda a lógica de negócio a jusante |
| `email UNIQUE` | Identidade do cliente. Um `SELECT` prévio na aplicação abriria janela de corrida entre a checagem e o `INSERT` |
| `UNIQUE (pedido_id, produto_id, moagem)` | Impede falha de consolidação do carrinho sem impedir o mesmo café em moagens diferentes |

**O que NÃO merece constraint no banco:** formato de telefone, tamanho mínimo
de senha, campo obrigatório de interface. Regras que mudam com a interface
devem morar na interface.

---

## 3. Quais consultas justificam a criação dos primeiros índices?

Cada um dos quatro índices existe por causa de **uma consulta real e
identificável** da aplicação:

| Consulta | Onde roda | Índice |
|---|---|---|
| `SELECT ... FROM produtos ORDER BY nome` | Home — a consulta mais executada da aplicação inteira | `idx_produtos_nome` |
| `WHERE categoria_id = ?` | Filtro por região | `idx_produtos_categoria` |
| `WHERE cliente_id = ? ORDER BY criado_em DESC` | Meus pedidos | `idx_pedidos_cliente` |
| `JOIN itens_pedido ON pedido_id = ?` | Detalhe de cada pedido | `idx_itens_pedido` |

Dois pontos que valem mencionar sem ser perguntado:

**O PostgreSQL não cria índice automático em coluna de FK** — só em PK e
`UNIQUE`. Por isso `idx_produtos_categoria` e `idx_pedidos_cliente` precisam
ser criados à mão.

**O que o `EXPLAIN` mostrou de verdade** (medido em produção, ver
`docs/evidencias.md` seção 5) — e o resultado é melhor do que se esperaria:

| Consulta | Plano escolhido |
|---|---|
| `WHERE categoria_id = 4` | **Index Scan** usando `idx_produtos_categoria` |
| `WHERE cliente_id = 2` | **Bitmap Index Scan** usando `idx_pedidos_cliente` |
| `ORDER BY nome`, sem filtro | **Seq Scan** + Sort |

A explicação está na **seletividade**, e é o que o professor vai querer ouvir:

- As duas primeiras têm `WHERE` seletivo — pegam 3 linhas de 12, e 1 pedido
  de 1. Compensa consultar o índice e buscar só as linhas necessárias.
- A terceira não tem `WHERE`: precisa de **todas** as linhas. Usar o índice
  significaria ler o índice inteiro *e depois* a tabela inteira — mais
  trabalho, não menos. O planejador varre e ordena em memória (`quicksort`,
  27 kB), e essa é a decisão correta.

Então o `idx_produtos_nome` não está sendo desperdiçado: ele passa a compensar
quando a tabela crescer a ponto de o `Sort` não caber em memória. A seção 4.5
de `SQL/consultas.sql` traz um gerador de 200 mil linhas para demonstrar a
virada.

**A lição para a defesa:** o índice existir não obriga o planejador a usá-lo.
Ele decide por custo estimado. Saber explicar *por que* ele escolheu Seq Scan
num caso e Index Scan no outro vale mais do que ter os três planos usando
índice.

---

## 4. Quando um Redis ou outro banco complementar faria sentido?

Não no MVP. O ponto em que passaria a fazer:

**Carrinho persistente entre dispositivos.** Hoje o carrinho vive na sessão
do Flask — some ao trocar de aparelho. Colocá-lo no PostgreSQL seria caro:
seriam escritas constantes de dado descartável, com o custo de índice e WAL
de um dado que não tem valor histórico. Redis, com TTL, é exatamente a
ferramenta para estado efêmero compartilhado.

**Cache do catálogo.** Se a home passasse a receber muito acesso, o resultado
da listagem poderia ser cacheado por alguns minutos. Só depois de medir — sem
`EXPLAIN` e sem métrica, cache é otimização por superstição.

**Fila de processamento.** Quando entrar pagamento real, a confirmação vira
operação assíncrona: o cliente não pode esperar o gateway responder dentro da
transação do pedido.

O que **não** justificaria: substituir o PostgreSQL. O domínio é relacional e
transacional — é o caso de uso onde o banco relacional é insubstituível.

---

## 5. Quais evidências demonstram que o deploy está consistente?

Consistente não é "abriu a página". É **o dado circulando de ponta a ponta**:

1. A URL pública responde com **HTTPS válido**, cadeado no navegador
2. O catálogo carrega **cafés vindos do banco de produção**, não fixos no código
3. Um cadastro novo persiste — e o `SELECT` na tabela `clientes` mostra o hash,
   nunca a senha
4. Um checkout completo grava o pedido, grava os itens **e baixa o estoque** —
   os três na mesma transação
5. **O cenário de erro funciona:** tentar comprar mais do que existe devolve a
   mensagem nomeando o café, e um `SELECT` prova que `pedidos` e
   `itens_pedido` continuam com a mesma contagem de antes
6. As variáveis de ambiente estão no provedor, e **nenhum segredo está no
   repositório** — `.env` no `.gitignore`, `.env.example` versionado
7. `git push` na `main` dispara deploy novo automaticamente
8. O backup com `pg_dump` roda e a **restauração foi testada** — backup que
   nunca foi restaurado não é backup

As consultas prontas para tirar essas evidências estão em
`SQL/consultas.sql`, seções 2 e 3.

---

## 6. Quais extensões evoluiriam melhor este MVP?

Em ordem de valor pelo custo:

**1. Lote e data de torra.** A evolução mais natural do domínio, e a que mais
mexe no modelo. Café tem validade curta e a data de torra é informação de
venda — cliente de café especial compara. Viraria uma tabela `lotes` com
`data_torra`, e o estoque migraria de `produtos` para `lotes`, com o item do
pedido apontando para o lote. É também o que permitiria FIFO de verdade.

**2. Área administrativa.** Hoje o catálogo entra por `seed.sql`. A Operação
precisa cadastrar café, ajustar estoque e mudar o status do pedido —
`CRIADO → PAGO → ENVIADO` está no `CHECK` mas nada faz a transição ainda.

**3. Pagamento real.** Traz a necessidade de fila e de estado intermediário
no pedido; é onde a modelagem de status ganha uso de verdade.

**4. Busca por nota sensorial.** Hoje `nota_sensorial` é texto descritivo.
Vira tabela `notas_sensoriais` com N:N para produtos — e aí a 1FN passa a
exigir a separação, que hoje não exige.

**5. Relatórios para a Gestão.** Vendas por região, por período, cafés mais
vendidos. É onde os índices atuais começariam a não bastar e apareceria a
discussão de índice composto.

---

## Roteiro sugerido da apresentação

1. **O problema** e por que café especial justifica a modelagem (30 s)
2. **O DER**, explicando por que `itens_pedido` é entidade (2 min)
3. **O `schema.sql`**, mostrando as constraints em SQL, não no ORM (2 min)
4. **A loja funcionando** — catálogo, moagem, carrinho, checkout (2 min)
5. **O cenário de erro ao vivo** — o que mais impressiona (2 min)
6. **O `SELECT` provando** que nada foi gravado (1 min)
7. **`pytest -v`** com a saída na tela (1 min)

> Dica do material: deixe o **Chapada Geisha com estoque 1** — o `seed.sql`
> já faz isso. A demonstração do rollback fica pronta sem mexer no banco na
> frente da turma.
