-- =====================================================================
-- Torra & Terra — consultas de validacao e evidencia
--
--     psql "$DATABASE_URL" -f SQL/consultas.sql
--
-- Divide-se em quatro partes:
--   1. Validacao do modelo
--   2. Evidencias de que o checkout persistiu
--   3. Evidencias de que o rollback segurou
--   4. EXPLAIN — por que cada indice existe
-- =====================================================================


-- =====================================================================
-- 1. VALIDACAO DO MODELO
-- =====================================================================

-- 1.1 As cinco tabelas existem?
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- 1.2 Todas as constraints, por tabela. E o que o professor avalia.
SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    cc.check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc
       ON cc.constraint_name = tc.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY','FOREIGN KEY','UNIQUE','CHECK')
  AND tc.constraint_name NOT LIKE '%not_null%'
ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;

-- 1.3 Os quatro indices criados a mao
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY indexname;

-- 1.4 Catalogo por regiao — o JOIN produtos x categorias
SELECT
    c.nome        AS regiao,
    COUNT(p.id)   AS cafes,
    MIN(p.preco)  AS menor_preco,
    MAX(p.preco)  AS maior_preco,
    SUM(p.estoque) AS estoque_total
FROM categorias c
JOIN produtos   p ON p.categoria_id = c.id
GROUP BY c.nome
ORDER BY c.nome;

-- 1.5 Nenhum cafe pode ter estoque negativo — a constraint garante,
--     esta consulta prova. Deve voltar ZERO linhas.
SELECT id, nome, estoque FROM produtos WHERE estoque < 0;

-- 1.6 Nenhum cafe fora da faixa SCA. Deve voltar ZERO linhas.
SELECT id, nome, pontuacao_sca
FROM produtos
WHERE pontuacao_sca IS NOT NULL
  AND pontuacao_sca NOT BETWEEN 80 AND 100;

-- 1.7 Nenhum item orfao. Deve voltar ZERO linhas — a FK garante.
SELECT i.id
FROM itens_pedido i
LEFT JOIN pedidos  p ON p.id = i.pedido_id
LEFT JOIN produtos pr ON pr.id = i.produto_id
WHERE p.id IS NULL OR pr.id IS NULL;

-- 1.8 O total do pedido bate com a soma dos itens?
--     Deve voltar ZERO linhas. Se voltar alguma, a transacao tem bug.
SELECT
    p.id,
    p.total                                       AS total_gravado,
    SUM(i.quantidade * i.preco_unitario)          AS soma_dos_itens
FROM pedidos p
JOIN itens_pedido i ON i.pedido_id = p.id
GROUP BY p.id, p.total
HAVING p.total <> SUM(i.quantidade * i.preco_unitario);


-- =====================================================================
-- 2. EVIDENCIAS DE QUE O CHECKOUT PERSISTIU
-- =====================================================================

-- 2.1 Os ultimos pedidos, com o cliente
SELECT
    p.id,
    c.nome    AS cliente,
    p.status,
    p.total,
    p.criado_em
FROM pedidos  p
JOIN clientes c ON c.id = p.cliente_id
ORDER BY p.criado_em DESC
LIMIT 5;

-- 2.2 Os itens guardaram a moagem e o preco congelado?
SELECT
    i.pedido_id,
    pr.nome,
    i.quantidade,
    i.moagem,
    i.preco_unitario,
    (i.quantidade * i.preco_unitario) AS subtotal
FROM itens_pedido i
JOIN produtos     pr ON pr.id = i.produto_id
ORDER BY i.pedido_id DESC, pr.nome
LIMIT 10;

-- 2.3 A PROVA do congelamento: onde o preco do item difere do preco atual
--     do produto, o historico esta preservado.
SELECT
    i.pedido_id,
    pr.nome,
    i.preco_unitario      AS preco_na_compra,
    pr.preco              AS preco_hoje,
    (pr.preco - i.preco_unitario) AS diferenca
FROM itens_pedido i
JOIN produtos     pr ON pr.id = i.produto_id
WHERE i.preco_unitario <> pr.preco
ORDER BY i.pedido_id DESC;

-- 2.4 O mesmo cafe em duas moagens no mesmo pedido — a prova de que
--     itens_pedido e entidade e nao tabela de ligacao.
SELECT
    i.pedido_id,
    pr.nome,
    COUNT(*)                    AS linhas,
    STRING_AGG(i.moagem, ', ')  AS moagens
FROM itens_pedido i
JOIN produtos     pr ON pr.id = i.produto_id
GROUP BY i.pedido_id, pr.nome
HAVING COUNT(*) > 1;

-- 2.5 Historico completo de um cliente
SELECT
    c.nome     AS cliente,
    p.id       AS pedido,
    p.criado_em,
    pr.nome    AS cafe,
    i.quantidade,
    i.moagem,
    i.preco_unitario
FROM clientes     c
JOIN pedidos      p  ON p.cliente_id = c.id
JOIN itens_pedido i  ON i.pedido_id  = p.id
JOIN produtos     pr ON pr.id        = i.produto_id
ORDER BY p.criado_em DESC, pr.nome;


-- =====================================================================
-- 3. EVIDENCIAS DE QUE O ROLLBACK SEGUROU
--
-- Roteiro da demonstracao ao vivo:
--   a) rode 3.1 e anote o estoque do Chapada Geisha (vem com 1)
--   b) tente comprar 2 unidades pela loja
--   c) a loja mostra a mensagem dizendo qual cafe faltou
--   d) rode 3.1 e 3.2 de novo: nada mudou, nada foi gravado
-- =====================================================================

-- 3.1 Cafes com estoque baixo — o candidato a demonstracao
SELECT id, nome, estoque, preco
FROM produtos
WHERE estoque < 5
ORDER BY estoque, nome;

-- 3.2 Contagem antes e depois da tentativa que falha.
--     Os dois numeros precisam ser IDENTICOS antes e depois.
SELECT
    (SELECT COUNT(*) FROM pedidos)      AS total_pedidos,
    (SELECT COUNT(*) FROM itens_pedido) AS total_itens;

-- 3.3 Nenhum pedido pode existir sem item. Um pedido orfao aqui seria
--     prova de transacao quebrada pela metade. Deve voltar ZERO linhas.
SELECT p.id, p.total, p.criado_em
FROM pedidos p
LEFT JOIN itens_pedido i ON i.pedido_id = p.id
WHERE i.id IS NULL;


-- =====================================================================
-- 4. EXPLAIN — POR QUE CADA INDICE EXISTE
--
-- Como tirar a evidencia comparativa:
--
--   1. rode os EXPLAIN abaixo com os indices no lugar     -> Index Scan
--   2. derrube os indices:
--        DROP INDEX idx_produtos_nome, idx_produtos_categoria,
--                   idx_pedidos_cliente, idx_itens_pedido;
--   3. rode os mesmos EXPLAIN                             -> Seq Scan
--   4. recrie: psql -f SQL/schema.sql  (ou so os CREATE INDEX)
--
-- O que foi medido em producao com 12 cafes (docs/evidencias.md secao 5):
--
--   WHERE categoria_id = 4    -> Index Scan        (usa idx_produtos_categoria)
--   WHERE cliente_id = 2      -> Bitmap Index Scan (usa idx_pedidos_cliente)
--   ORDER BY nome, sem WHERE  -> Seq Scan + Sort
--
-- A diferenca e a SELETIVIDADE. As duas primeiras filtram poucas linhas de
-- muitas: compensa consultar o indice. A terceira precisa de TODAS as linhas
-- — usar o indice seria ler o indice inteiro e depois a tabela inteira, mais
-- trabalho e nao menos. O planejador esta certo nos tres casos.
--
-- O idx_produtos_nome passa a compensar quando o Sort nao couber mais em
-- memoria. Use o gerador da secao 4.5 para demonstrar a virada.
-- =====================================================================

-- 4.1 idx_produtos_nome — a ordenacao do catalogo, a consulta mais
--     executada da aplicacao inteira.
EXPLAIN ANALYZE
SELECT * FROM produtos ORDER BY nome;

-- 4.2 idx_produtos_categoria — o filtro por regiao.
--     O PostgreSQL NAO cria indice automatico em coluna de FK, so em PK e
--     UNIQUE. Sem este CREATE INDEX, todo filtro varre produtos inteiro.
EXPLAIN ANALYZE
SELECT * FROM produtos WHERE categoria_id = 1 ORDER BY nome;

-- 4.3 idx_pedidos_cliente — o historico do cliente. Cresce sem limite ao
--     longo do tempo: e o indice que mais se paga no longo prazo.
EXPLAIN ANALYZE
SELECT * FROM pedidos WHERE cliente_id = 1 ORDER BY criado_em DESC;

-- 4.4 idx_itens_pedido — o JOIN que monta o detalhe de cada pedido.
EXPLAIN ANALYZE
SELECT i.*, pr.nome
FROM itens_pedido i
JOIN produtos     pr ON pr.id = i.produto_id
WHERE i.pedido_id = 1;

-- 4.5 Carga sintetica para ver o indice trabalhar de verdade.
--     Descomente, rode, refaca os EXPLAIN acima e compare os planos.
--
-- INSERT INTO produtos (nome, preco, estoque, categoria_id, torra, pontuacao_sca, peso_g)
-- SELECT
--     'Cafe de carga ' || g,
--     (random() * 100 + 30)::numeric(10,2),
--     (random() * 50)::int,
--     (g % 4) + 1,
--     (ARRAY['CLARA','MEDIA','ESCURA'])[(g % 3) + 1],
--     (random() * 20 + 80)::numeric(4,2),
--     250
-- FROM generate_series(1, 200000) g;
--
-- ANALYZE produtos;   -- sem isto o planejador decide com estatistica velha
--
-- EXPLAIN ANALYZE SELECT * FROM produtos WHERE categoria_id = 1 ORDER BY nome;
--
-- Limpeza:
-- DELETE FROM produtos WHERE nome LIKE 'Cafe de carga %';
-- ANALYZE produtos;


-- =====================================================================
-- 5. PROJETO FINAL — o indice novo: idx_pedidos_criado_em
--
-- O painel de indicadores (SQL/dashboard.sql) tem sete consultas e TODAS
-- comecam filtrando o periodo:
--
--     WHERE criado_em >= CURRENT_TIMESTAMP - make_interval(days => :dias)
--
-- A lista de pedidos recentes, logo abaixo dos cards, ordena pelo mesmo
-- campo: ORDER BY criado_em DESC LIMIT 20.
--
-- Este e o indice que o Projeto Final acrescentou:
--
--     CREATE INDEX idx_pedidos_criado_em ON pedidos(criado_em DESC);
--
-- Em producao ele e aplicado por SQL/migracao_projeto_final.sql, NUNCA
-- rodando o schema.sql — que comeca com DROP TABLE.
--
-- ---------------------------------------------------------------------
-- 5.1 Como refazer a medicao
--
-- As duas consultas de referencia:
-- ---------------------------------------------------------------------

-- (a) o card de faturamento do painel
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS pedidos, COALESCE(SUM(total), 0) AS faturamento
FROM pedidos
WHERE criado_em >= CURRENT_TIMESTAMP - make_interval(days => 30)
  AND status <> 'CANCELADO';

-- (b) a lista de pedidos recentes
EXPLAIN ANALYZE
SELECT p.id, p.status, p.total, p.criado_em
FROM pedidos p
ORDER BY p.criado_em DESC
LIMIT 20;

-- Para comparar antes e depois:
--
--     DROP INDEX idx_pedidos_criado_em;  ANALYZE pedidos;   -- antes
--     (rode (a) e (b))
--     CREATE INDEX idx_pedidos_criado_em ON pedidos(criado_em DESC);
--     ANALYZE pedidos;                                      -- depois
--     (rode (a) e (b) de novo)
--
-- O ANALYZE nao e opcional: sem atualizar as estatisticas, o planejador
-- decide com o retrato antigo da tabela e pode ignorar o indice novo.

-- Carga sintetica usada na medicao 5.3 — 60 mil pedidos em 24 meses, a
-- ordem de grandeza de uma torrefacao pequena depois de alguns anos.
-- Rode num banco DESCARTAVEL (torra_terra_teste), nunca em producao.
--
-- INSERT INTO pedidos (cliente_id, status, total, criado_em)
-- SELECT 1,
--        (ARRAY['CRIADO','PAGO','ENVIADO','CANCELADO'])[(g % 4) + 1],
--        (random() * 300 + 40)::numeric(10,2),
--        CURRENT_TIMESTAMP - (random() * 730 || ' days')::interval
-- FROM generate_series(1, 60000) g;
--
-- ANALYZE pedidos;
--
-- Limpeza: TRUNCATE TABLE itens_pedido, pedidos RESTART IDENTITY CASCADE;


-- ---------------------------------------------------------------------
-- 5.2 MEDIDO na base de demonstracao — 40 pedidos
--
-- Seq Scan, com e sem o indice. E a decisao CERTA do planejador, e vale
-- explicar na defesa em vez de esconder: a tabela inteira ocupa uma
-- pagina de disco. Ler o indice e depois buscar as linhas na tabela seria
-- dois acessos onde um resolve.
--
--   Aggregate  (cost=1.97..1.98 rows=1) (actual time=0.018..0.018 rows=1)
--     ->  Seq Scan on pedidos  (cost=0.00..1.80 rows=34)
--                              (actual time=0.005..0.010 rows=34)
--           Filter: ((status <> 'CANCELADO') AND (criado_em >= ...))
--           Rows Removed by Filter: 6
--   Planning Time: 0.384 ms
--   Execution Time: 0.053 ms
--
-- O indice nao esta inutil: ele esta esperando o volume. A proxima secao
-- mostra o ponto de virada.
-- ---------------------------------------------------------------------


-- ---------------------------------------------------------------------
-- 5.3 MEDIDO com 60.000 pedidos — a virada
--
-- Mesmo PostgreSQL 16, mesmo schema, banco torra_terra_teste.
-- ---------------------------------------------------------------------
--
-- (a) CARD DE FATURAMENTO
--
-- ANTES — sem idx_pedidos_criado_em:
--
--   Aggregate  (cost=1667.30..1667.31 rows=1) (actual time=6.692..6.692)
--     Buffers: shared hit=458
--     ->  Seq Scan on pedidos  (cost=0.00..1658.00 rows=1860)
--                              (actual time=0.011..6.553 rows=1838)
--           Filter: ((status <> 'CANCELADO') AND (criado_em >= ...))
--           Rows Removed by Filter: 58162
--           Buffers: shared hit=458
--   Execution Time: 6.713 ms
--
-- DEPOIS — com idx_pedidos_criado_em:
--
--   Aggregate  (cost=562.69..562.70 rows=1) (actual time=0.882..0.882)
--     Buffers: shared hit=454 read=8
--     ->  Bitmap Heap Scan on pedidos  (cost=46.98..553.58 rows=1823)
--                                      (actual time=0.191..0.743 rows=1838)
--           Recheck Cond: (criado_em >= ...)
--           Filter: (status <> 'CANCELADO')
--           Rows Removed by Filter: 640
--           Heap Blocks: exact=454
--           ->  Bitmap Index Scan on idx_pedidos_criado_em
--                 (cost=0.00..46.52 rows=2430)
--                 (actual time=0.154..0.155 rows=2478)
--                 Index Cond: (criado_em >= ...)
--                 Buffers: shared read=8
--   Execution Time: 0.900 ms
--
--   6,713 ms -> 0,900 ms   (7,5x mais rapido)
--
-- O numero que explica o ganho e `Rows Removed by Filter`: 58.162 antes,
-- 640 depois. O Seq Scan le as 60 mil linhas e joga 97% fora. O indice
-- devolve 2.478 candidatas e o filtro de status descarta 640.
--
-- Repare que o custo estimado tambem caiu (1667 -> 562). E por isso que o
-- planejador troca de plano sozinho: ele compara os dois custos. Nao ha
-- dica nem hint no codigo da aplicacao.
--
--
-- (b) LISTA DE PEDIDOS RECENTES — o caso em que o DESC se paga
--
-- ANTES:
--
--   Limit  (cost=2654.58..2654.63 rows=20) (actual time=10.387..10.390)
--     ->  Sort  (cost=2654.58..2804.58 rows=60000)
--               (actual time=10.385..10.387 rows=20)
--           Sort Key: criado_em DESC
--           Sort Method: top-N heapsort  Memory: 27kB
--           ->  Seq Scan on pedidos p  (cost=0.00..1058.00 rows=60000)
--                                      (actual time=0.004..4.043 rows=60000)
--   Execution Time: 10.401 ms
--
-- DEPOIS:
--
--   Limit  (cost=0.29..1.42 rows=20) (actual time=0.011..0.022 rows=20)
--     ->  Index Scan using idx_pedidos_criado_em on pedidos p
--           (cost=0.29..3396.26 rows=60000)
--           (actual time=0.010..0.020 rows=20)
--   Execution Time: 0.031 ms
--
--   10,401 ms -> 0,031 ms   (335x mais rapido)
--
-- Este e o resultado mais eloquente da medicao, e a razao de o indice ser
-- `criado_em DESC` e nao so `criado_em`.
--
-- ANTES o banco le TODAS as 60 mil linhas e ordena para entregar 20. Ele
-- usa top-N heapsort, que e o algoritmo certo para "as N maiores", mas
-- ainda assim precisa olhar cada linha uma vez.
--
-- DEPOIS ele caminha pelo indice, que JA ESTA na ordem pedida, le as 20
-- primeiras entradas e para. Nao ha Sort no plano: ele desapareceu.
--
-- O `cost=0.29..3396.26` do Index Scan parece alto, mas o Limit acima
-- cobra so `0.29..1.42`: o custo total seria percorrer o indice inteiro,
-- e o plano para na vigesima linha.
--
--
-- (c) O PRECO DO INDICE
--
--   tabela pedidos ...... 6736 kB
--   idx_pedidos_criado_em  1328 kB   (~20% do tamanho da tabela)
--   linhas .............. 60000
--
-- Indice nao e de graca: ocupa disco e todo INSERT de pedido passa a
-- escrever em dois lugares. O checkout fica marginalmente mais lento para
-- o painel ficar 335x mais rapido. A troca vale porque pedido se insere
-- um por venda e o painel e consultado a cada visita do gestor — mas e
-- uma TROCA, e e por isso que este projeto tem cinco indices e nao
-- quinze: cada um existe por causa de uma consulta real, demonstrada.
-- ---------------------------------------------------------------------
