-- =====================================================================
-- Torra & Terra — Projeto Final
-- Consultas do painel de indicadores
--
-- FACAMP · Tratamento e Armazenamento da Informacao
-- Professor: Nivaldo T. Marcusso
--
-- Este arquivo e a FONTE DA VERDADE dos indicadores. O app.py nao
-- reescreve estas consultas: ele le este arquivo, separa os blocos pelo
-- marcador `-- @consulta: nome` e executa cada bloco com text() e
-- parametros ligados. Mudar um indicador significa mudar aqui.
--
-- Por que SQL a mao e nao ORM: os indicadores sao o nucleo do criterio de
-- banco de dados do trabalho. Escritos como `db.select(...).group_by(...)`
-- eles existiriam, mas nao estariam VISIVEIS — e o que se avalia aqui e a
-- consulta, com o GROUP BY, os JOINs e o indice que ela usa.
--
-- Rodar no psql:
--     psql "$DATABASE_URL" -v dias=30 -v limite_estoque=5 -f SQL/dashboard.sql
--
-- Os dois parametros:
--     :dias             janela do periodo. Padrao da aplicacao: 30
--     :limite_estoque   limite do estoque critico. Padrao: 5
--
-- Valores padrao, para o arquivo rodar sem -v. O psql ignora o \set se a
-- variavel ja veio da linha de comando. O leitor do app.py descarta tudo
-- o que vem antes do primeiro marcador, entao estas duas linhas nunca
-- chegam ao banco pela aplicacao.
\if :{?dias}
\else
  \set dias 30
\endif
\if :{?limite_estoque}
\else
  \set limite_estoque 5
\endif


-- ---------------------------------------------------------------------
-- Sobre o filtro de periodo
--
-- `criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)`.
--
-- Usamos make_interval em vez de concatenar texto (`:dias || ' days'`)
-- porque ele recebe o parametro como INTEGER. Concatenar exigiria que o
-- banco adivinhasse o tipo de um parametro ligado dentro de um `||`, e
-- montar o intervalo com f-string em Python abriria a porta para SQL
-- injection no unico lugar da aplicacao que recebe numero da URL.
--
-- Sobre excluir CANCELADO: pedido cancelado nao e faturamento. Ele
-- continua no banco, continua contando em "pedidos por status" e continua
-- sendo conferido na conciliacao — mas somar o valor dele na receita
-- inflaria o resultado do mes.
-- ---------------------------------------------------------------------


-- @consulta: faturamento
--
-- PERGUNTA DE NEGOCIO: quanto a loja vendeu no periodo, e em quantos
-- pedidos? E o numero que abre o painel.
--
-- INDICE: idx_pedidos_criado_em, criado no Projeto Final exatamente para
-- este filtro. Sem ele, todo indicador do painel varre `pedidos` inteiro
-- — e `pedidos` e a tabela que cresce sem limite na loja.
--
-- COALESCE: periodo sem nenhuma venda devolveria SUM() = NULL, e o painel
-- mostraria vazio em vez de R$ 0,00.
SELECT
    COUNT(*)                   AS pedidos,
    COALESCE(SUM(total), 0)    AS faturamento
FROM pedidos
WHERE criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
  AND status <> 'CANCELADO';


-- @consulta: ticket_medio
--
-- PERGUNTA DE NEGOCIO: quanto vale, em media, um pedido fechado no
-- periodo? Serve para decidir frete gratis a partir de que valor.
--
-- INDICE: idx_pedidos_criado_em.
--
-- Por que AVG(total) e nao faturamento/pedidos calculado em Python: o
-- banco faz a divisao em NUMERIC, com a mesma aritmetica decimal exata do
-- resto do sistema. Dividir em float no Python reintroduziria no
-- indicador o erro de arredondamento que o NUMERIC(10,2) existe para
-- evitar. E AVG de conjunto vazio devolve NULL, nao erro de divisao por
-- zero — o COALESCE resolve o resto.
SELECT COALESCE(AVG(total), 0) AS ticket_medio
FROM pedidos
WHERE criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
  AND status <> 'CANCELADO';


-- @consulta: vendas_por_regiao
--
-- PERGUNTA DE NEGOCIO: qual regiao produtora sustenta a receita? Diz onde
-- vale negociar mais volume com o produtor na proxima safra.
--
-- E o JOIN de quatro tabelas do trabalho: pedidos -> itens_pedido ->
-- produtos -> categorias. Repare que o faturamento sai de
-- `i.quantidade * i.preco_unitario`, o preco CONGELADO no item, e nao de
-- `produtos.preco`. Usar o preco atual faria o historico de vendas mudar
-- a cada reajuste de tabela.
--
-- INDICES: idx_pedidos_criado_em no filtro, idx_itens_pedido no JOIN com
-- os itens, e a PK de produtos e categorias nos dois ultimos JOINs.
--
-- COUNT(DISTINCT p.id): sem o DISTINCT, um pedido com tres cafes da mesma
-- regiao seria contado tres vezes.
--
-- Agrupamos por `categorias.regiao` (o estado), como pede o indicador.
-- Consequencia que vale conhecer na defesa: Cerrado Mineiro e Sul de
-- Minas sao duas categorias e somam juntas em "Minas Gerais". Para ver
-- por denominacao de origem, o GROUP BY seria por `categorias.nome`.
SELECT
    cat.regiao,
    COUNT(DISTINCT p.id)                        AS pedidos,
    SUM(i.quantidade)                           AS unidades,
    SUM(i.quantidade * i.preco_unitario)        AS faturamento
FROM pedidos      p
JOIN itens_pedido i   ON i.pedido_id    = p.id
JOIN produtos     pr  ON pr.id          = i.produto_id
JOIN categorias   cat ON cat.id         = pr.categoria_id
WHERE p.criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
  AND p.status <> 'CANCELADO'
GROUP BY cat.regiao
ORDER BY faturamento DESC, cat.regiao;


-- @consulta: top_cafes
--
-- PERGUNTA DE NEGOCIO: quais cinco cafes puxam o volume, e em que moagem
-- o cliente costuma pedir cada um? A moagem muda a operacao da
-- torrefacao: cafe que sai moido fino precisa do moinho na hora do
-- empacotamento, cafe em grao nao.
--
-- Esta e a consulta que mais se beneficia de `moagem` morar no ITEM e nao
-- no produto. Se a moagem fosse coluna de `produtos`, a pergunta "em que
-- moagem este cafe e mais pedido?" nao teria resposta possivel: cada
-- moagem seria um produto diferente, com estoque separado.
--
-- INDICES: idx_pedidos_criado_em e idx_itens_pedido.
--
-- DISTINCT ON e extensao do PostgreSQL: devolve a primeira linha de cada
-- grupo na ordem do ORDER BY. Aqui, a moagem de maior volume por produto.
-- O desempate por nome da moagem existe para o resultado ser estavel —
-- sem ele, dois empates devolveriam ora um, ora outro, e a evidencia do
-- relatorio nao seria reproduzivel.
WITH vendas AS (
    SELECT
        i.produto_id,
        SUM(i.quantidade)                    AS unidades,
        SUM(i.quantidade * i.preco_unitario) AS faturamento
    FROM itens_pedido i
    JOIN pedidos      p ON p.id = i.pedido_id
    WHERE p.criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
      AND p.status <> 'CANCELADO'
    GROUP BY i.produto_id
),
moagem_preferida AS (
    SELECT DISTINCT ON (i.produto_id)
        i.produto_id,
        i.moagem,
        SUM(i.quantidade) AS unidades_na_moagem
    FROM itens_pedido i
    JOIN pedidos      p ON p.id = i.pedido_id
    WHERE p.criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
      AND p.status <> 'CANCELADO'
    GROUP BY i.produto_id, i.moagem
    ORDER BY i.produto_id, SUM(i.quantidade) DESC, i.moagem
)
SELECT
    pr.id,
    pr.nome,
    cat.regiao,
    v.unidades,
    v.faturamento,
    m.moagem                AS moagem_preferida,
    m.unidades_na_moagem
FROM vendas     v
JOIN produtos   pr  ON pr.id  = v.produto_id
JOIN categorias cat ON cat.id = pr.categoria_id
LEFT JOIN moagem_preferida m ON m.produto_id = v.produto_id
ORDER BY v.unidades DESC, pr.nome
LIMIT 5;


-- @consulta: estoque_critico
--
-- PERGUNTA DE NEGOCIO: o que precisa ser torrado nesta semana para a loja
-- nao recusar venda? E o indicador que liga o painel a dor do contexto:
-- quem descobre o estoque zerado pela mensagem de erro do cliente
-- descobriu tarde.
--
-- SEM FILTRO DE PERIODO, de proposito: estoque e um saldo de AGORA, nao
-- um acumulado de janela. "Estoque dos ultimos 30 dias" nao significa
-- nada.
--
-- INDICE: nenhum. `produtos` tem 12 linhas e o planejador escolhe Seq
-- Scan, corretamente — criar indice em `estoque` seria custo de escrita
-- (toda venda altera a coluna) sem beneficio de leitura. Se o catalogo
-- crescesse para milhares de itens, o indice certo seria parcial:
-- CREATE INDEX ... ON produtos(estoque) WHERE estoque <= 5.
SELECT
    pr.id,
    pr.nome,
    cat.regiao,
    pr.estoque,
    pr.preco
FROM produtos   pr
JOIN categorias cat ON cat.id = pr.categoria_id
WHERE pr.estoque <= :limite_estoque
ORDER BY pr.estoque, pr.nome;


-- @consulta: pedidos_por_status
--
-- PERGUNTA DE NEGOCIO: onde estao os pedidos do periodo? Muitos em
-- CRIADO significa pagamento que nao fecha; muitos em PAGO sem ENVIADO
-- significa expedicao atrasada.
--
-- Aqui CANCELADO ENTRA: a pergunta e sobre a fila de trabalho, e pedido
-- cancelado faz parte do retrato.
--
-- A lista VALUES no CTE espelha a constraint ck_pedidos_status. Ela serve
-- para o status com zero pedido ainda aparecer no painel: sem o LEFT
-- JOIN, uma coluna some do grafico quando chega a zero, e grafico com
-- numero de barras variavel engana quem olha.
--
-- INDICE: idx_pedidos_criado_em.
WITH dominio(status, ordem) AS (
    VALUES ('CRIADO', 1), ('PAGO', 2), ('ENVIADO', 3), ('CANCELADO', 4)
)
SELECT
    d.status,
    COUNT(p.id)                  AS pedidos,
    COALESCE(SUM(p.total), 0)    AS valor
FROM dominio d
LEFT JOIN pedidos p
       ON p.status = d.status
      AND p.criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
GROUP BY d.status, d.ordem
ORDER BY d.ordem;


-- @consulta: conciliacao
--
-- PERGUNTA DE NEGOCIO: o total gravado em cada pedido bate com a soma dos
-- itens dele?
--
-- ESTE E O INDICADOR CENTRAL DO TRABALHO. O contexto escolhido no
-- Segmento 1 (Varejo) foi "carrinho, pedidos e pagamentos", e a dor
-- descrita e "falhas de confirmacao e de conciliacao". Este numero e a
-- medida direta dessa dor: ele precisa dar ZERO divergencia, sempre.
--
-- Se o checkout gravasse o pedido fora de transacao, uma falha no meio
-- deixaria cabecalho sem item, ou item sem a baixa de estoque, e o total
-- deixaria de bater. Como o checkout e atomico — BEGIN, trava,
-- INSERT/INSERT/UPDATE, COMMIT ou ROLLBACK inteiro — nao existe estado
-- intermediario para divergir. O painel mostra "Pedidos conciliados: X de
-- X" e a prova fica visivel para quem nunca vai ler o codigo.
--
-- Todos os status entram, CANCELADO incluido: cancelar um pedido muda o
-- status e devolve o estoque, mas NAO reescreve o historico financeiro
-- dele. Os itens e o total continuam gravados, e continuam tendo que
-- bater entre si.
--
-- LEFT JOIN em vez de JOIN: um pedido sem nenhum item seria a prova de
-- uma transacao partida pela metade. Com JOIN ele desapareceria da
-- conferencia justamente no caso em que mais importa aparecer.
SELECT
    COUNT(*)                                             AS pedidos,
    COUNT(*) FILTER (WHERE total <> soma_itens)          AS divergentes,
    COUNT(*) FILTER (WHERE total  = soma_itens)          AS conciliados
FROM (
    SELECT
        p.id,
        p.total,
        COALESCE(SUM(i.quantidade * i.preco_unitario), 0) AS soma_itens
    FROM pedidos      p
    LEFT JOIN itens_pedido i ON i.pedido_id = p.id
    WHERE p.criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
    GROUP BY p.id, p.total
) AS conferencia;


-- @consulta: pedidos_recentes
--
-- Nao e indicador: e a lista de trabalho do gestor, logo abaixo dos
-- cards. Cliente, total, status e data dos ultimos pedidos, com a
-- quantidade de itens de cada um.
--
-- O JOIN com `clientes` existe porque a lista e operacional — o gestor
-- precisa saber de quem e o pedido para atender. Nenhuma rota publica
-- expoe esta consulta: ela vive atras de gestor_obrigatorio.
--
-- INDICE: idx_pedidos_criado_em no ORDER BY, idx_itens_pedido na contagem.
SELECT
    p.id,
    c.nome          AS cliente,
    p.status,
    p.total,
    p.criado_em,
    COUNT(i.id)     AS itens
FROM pedidos      p
JOIN clientes     c ON c.id = p.cliente_id
LEFT JOIN itens_pedido i ON i.pedido_id = p.id
GROUP BY p.id, c.nome, p.status, p.total, p.criado_em
ORDER BY p.criado_em DESC, p.id DESC
LIMIT 20;
