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
-- Aviso honesto para a defesa: com 12 cafes o planejador vai preferir
-- Seq Scan mesmo COM indice — ler a tabela inteira e mais barato do que
-- consultar o indice quando a tabela cabe em uma pagina. Isso nao invalida
-- o indice: e a resposta certa para o volume atual. Para ver o Index Scan
-- aparecer, use o gerador de carga da secao 4.5.
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
