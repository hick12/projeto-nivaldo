-- =====================================================================
-- Torra & Terra — Projeto Final
-- Migracao para o banco EM PRODUCAO
--
-- FACAMP · Tratamento e Armazenamento da Informacao
--
-- ---------------------------------------------------------------------
-- POR QUE ESTE ARQUIVO EXISTE
--
-- O `SQL/schema.sql` comeca com DROP TABLE. Ele e o DDL completo, pensado
-- para criar o banco do zero, e e isso que o `flask init-db` executa.
--
-- Rodar `flask init-db` contra o banco do Railway APAGARIA a loja: os
-- clientes cadastrados, os pedidos e o historico de vendas. Nao existe
-- rollback para isso, e o backup mais recente seria a unica saida.
--
--     NUNCA rode `flask init-db` nem `flask reset-db` em producao.
--
-- A unica mudanca de estrutura que o Projeto Final traz e um indice novo.
-- Este arquivo aplica so isso, de forma idempotente: rodar duas vezes nao
-- causa erro e nao muda nada na segunda vez.
-- ---------------------------------------------------------------------
--
-- COMO APLICAR
--
-- A aplicacao conecta como `torra_app`, que por decisao de projeto (RNF04
-- e docs/decisoes.md D06) NAO pode alterar o schema. CREATE INDEX e DDL,
-- entao esta migracao roda com a credencial administrativa do banco, nao
-- com a da loja.
--
-- No Railway, de dentro do container do Postgres:
--
--     railway ssh -s Postgres
--     psql -U postgres -d railway -f /tmp/migracao_projeto_final.sql
--
-- ou, pelo tunel da CLI, com a DATABASE_PUBLIC_URL administrativa:
--
--     psql "<URL_ADMIN>" -v ON_ERROR_STOP=1 -f SQL/migracao_projeto_final.sql
--
-- Depois de aplicar, confira com a secao 3 deste arquivo.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. O indice do periodo do painel
--
-- Mesma definicao que esta no SQL/schema.sql. Os dois arquivos precisam
-- continuar iguais nesta linha: o schema para quem cria o banco do zero,
-- a migracao para o banco que ja existe.
--
-- IF NOT EXISTS: sem isso, aplicar de novo levanta
-- `ERROR: relation "idx_pedidos_criado_em" already exists` e, com
-- ON_ERROR_STOP, interrompe o resto do script.
--
-- Nota operacional: CREATE INDEX trava escrita na tabela enquanto
-- constroi. Com o volume desta loja isso e instantaneo. Numa tabela
-- grande em producao a forma correta seria CREATE INDEX CONCURRENTLY, que
-- nao bloqueia INSERT — ele exige rodar fora de bloco de transacao e por
-- isso nao entra aqui, mas fica registrado como o caminho certo em escala.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pedidos_criado_em ON pedidos(criado_em DESC);


-- ---------------------------------------------------------------------
-- 2. Estatisticas
--
-- O planejador decide usar ou nao o indice a partir das estatisticas da
-- tabela. Depois de criar um indice novo — e depois de carregar os
-- pedidos de demonstracao — o ANALYZE evita que ele decida com dado
-- velho e escolha Seq Scan por engano.
-- ---------------------------------------------------------------------
ANALYZE pedidos;
ANALYZE itens_pedido;


-- ---------------------------------------------------------------------
-- 3. Conferencia — o que deve aparecer depois de aplicar
-- ---------------------------------------------------------------------

-- 3.1 Os cinco indices criados a mao. `idx_pedidos_criado_em` e o novo.
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY indexname;

-- 3.2 A estrutura NAO mudou: as 5 tabelas continuam lá, com as mesmas
--     contagens de constraint. Nenhum dado foi tocado por esta migracao.
SELECT
    (SELECT COUNT(*) FROM pg_tables
      WHERE schemaname = 'public')                      AS tabelas,
    (SELECT COUNT(*) FROM pg_constraint
      WHERE contype = 'c'
        AND connamespace = 'public'::regnamespace)       AS checks,
    (SELECT COUNT(*) FROM pg_constraint
      WHERE contype = 'f'
        AND connamespace = 'public'::regnamespace)       AS foreign_keys;

-- 3.3 Os dados continuam no lugar.
SELECT
    (SELECT COUNT(*) FROM categorias)   AS categorias,
    (SELECT COUNT(*) FROM produtos)     AS produtos,
    (SELECT COUNT(*) FROM clientes)     AS clientes,
    (SELECT COUNT(*) FROM pedidos)      AS pedidos,
    (SELECT COUNT(*) FROM itens_pedido) AS itens;

-- 3.4 O indice novo esta sendo usado pelo filtro de periodo?
--     Espera-se Index Scan ou Bitmap Index Scan sobre
--     idx_pedidos_criado_em — nunca Seq Scan, depois do seed-demo.
EXPLAIN ANALYZE
SELECT COUNT(*), COALESCE(SUM(total), 0)
FROM pedidos
WHERE criado_em >= CURRENT_TIMESTAMP - make_interval(days => 30)
  AND status <> 'CANCELADO';
