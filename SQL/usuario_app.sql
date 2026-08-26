-- =====================================================================
-- Torra & Terra — banco e usuario da aplicacao
--
-- Roda UMA VEZ, conectado como superusuario:
--     psql -U postgres -f SQL/usuario_app.sql
--
-- Depois disso, tudo o mais roda como torra_app.
--
-- Por que um usuario proprio (slides 20 e 35 do material):
-- o postgres pode dropar qualquer coisa no cluster inteiro. Um bug de SQL
-- injection ou um script errado rodando como superusuario e catastrofico e
-- irreversivel. O torra_app so manipula dados das tabelas da aplicacao —
-- nao altera o schema, nao cria extensao, nao enxerga outros bancos.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. O papel da aplicacao
-- ---------------------------------------------------------------------
-- Troque a senha antes de rodar. Ela vai para o .env, nunca para o Git.
CREATE ROLE torra_app WITH LOGIN PASSWORD 'troque_esta_senha';

-- Sem CREATEDB, sem CREATEROLE, sem SUPERUSER: apenas login.
ALTER ROLE torra_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;


-- ---------------------------------------------------------------------
-- 2. O banco
-- ---------------------------------------------------------------------
CREATE DATABASE torra_terra WITH OWNER torra_app ENCODING 'UTF8';

-- Do ponto daqui para baixo, conecte-se ao banco novo:
--     \c torra_terra
--
-- (o psql nao troca de banco no meio de um arquivo — rode os GRANTs abaixo
--  em uma segunda chamada, ou use o comando pronto no README)


-- ---------------------------------------------------------------------
-- 3. Privilegios — rodar JA CONECTADO em torra_terra
-- ---------------------------------------------------------------------
-- Ninguem alem do dono mexe no schema public. Desde o PostgreSQL 15 este
-- ja e o padrao, mas deixamos explicito porque e exatamente o ponto que o
-- material levanta.
-- REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- GRANT USAGE ON SCHEMA public TO torra_app;

-- A aplicacao le e escreve dados. Nao cria nem altera tabela: isso e papel
-- do schema.sql, aplicado deliberadamente por quem administra o banco.
-- GRANT SELECT, INSERT, UPDATE, DELETE
--     ON ALL TABLES IN SCHEMA public TO torra_app;

-- As sequences dos SERIAL precisam de USAGE, senao todo INSERT falha.
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO torra_app;

-- Vale tambem para as tabelas que o schema.sql criar no futuro.
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public
--     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO torra_app;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public
--     GRANT USAGE, SELECT ON SEQUENCES TO torra_app;


-- ---------------------------------------------------------------------
-- Nota sobre os GRANTs comentados
--
-- Como torra_app e OWNER do banco torra_terra, ele ja tem todos esses
-- privilegios sobre os objetos que ele mesmo cria — os GRANTs acima sao
-- redundantes neste arranjo e ficam comentados.
--
-- Eles existem aqui porque sao necessarios no cenario mais restritivo, em
-- que o schema e criado por um administrador e a aplicacao recebe apenas
-- permissao de dados. E o arranjo correto em producao de verdade; para o
-- escopo do trabalho, OWNER do proprio banco ja atende ao requisito de nao
-- usar o superusuario.
--
-- No Railway isso e resolvido pelo provedor: o banco gerenciado ja entrega
-- um usuario dedicado na DATABASE_URL, nunca o superusuario do cluster.
-- ---------------------------------------------------------------------

-- Conferencia:
--     SELECT rolname, rolsuper, rolcreatedb, rolcreaterole
--     FROM pg_roles WHERE rolname = 'torra_app';
