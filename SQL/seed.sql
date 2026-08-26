-- =====================================================================
-- Torra & Terra — carga inicial
-- 12 cafes de origem unica em 4 regioes produtoras brasileiras.
--
--     psql -U torra_app -d torra_terra -f SQL/seed.sql
--
-- Dados de exemplo ficam separados da estrutura de proposito: schema.sql
-- pode ser aplicado em producao sem arrastar cafe ficticio junto.
-- =====================================================================

-- Idempotente: rodar duas vezes nao duplica o catalogo.
-- clientes fica de fora — recarregar o catalogo nao pode apagar quem se
-- cadastrou. pedidos cai junto porque referencia produtos.
TRUNCATE TABLE itens_pedido, pedidos, produtos, categorias
    RESTART IDENTITY CASCADE;


-- ---------------------------------------------------------------------
-- Regioes produtoras
-- ---------------------------------------------------------------------
INSERT INTO categorias (nome, regiao, descricao) VALUES
('Mogiana Paulista',  'Sao Paulo',    'Serra da Mogiana, entre 900 e 1.200 m. Solo de basalto decomposto e clima de inverno seco. Xicara encorpada, doce, com acidez media e retrogosto de castanhas.'),
('Cerrado Mineiro',   'Minas Gerais', 'Primeira denominacao de origem do cafe brasileiro. Estacoes bem definidas e colheita uniforme. Corpo aveludado, doce de caramelo e acidez baixa.'),
('Sul de Minas',      'Minas Gerais', 'Maior regiao produtora do pais, entre 800 e 1.300 m. Relevo montanhoso e colheita manual. Perfil equilibrado, achocolatado, muito estavel na torra.'),
('Chapada Diamantina','Bahia',        'Altitudes acima de 1.000 m no semiarido baiano. Amplitude termica alta e maturacao lenta. Acidez citrica marcante e aroma floral.');


-- ---------------------------------------------------------------------
-- Cafes
--
-- Todos com pontuacao_sca >= 80: e o que define cafe especial pela SCA, e
-- a constraint ck_produtos_sca recusa qualquer coisa fora da faixa 80-100.
-- ---------------------------------------------------------------------
INSERT INTO produtos
    (nome, descricao, preco, estoque, categoria_id, torra, nota_sensorial, pontuacao_sca, peso_g)
VALUES

-- Mogiana Paulista (categoria 1)
('Fazenda Serra Negra',
 'Bourbon amarelo cultivado a 1.100 m, colhido em derriça seletiva e secado em terreiro suspenso. Um cafe de corpo redondo para quem gosta de espresso doce.',
 62.00, 40, 1, 'MEDIA', 'Castanha-do-para, chocolate ao leite, caramelo', 84.50, 250),

('Sitio Boa Vista',
 'Catuai vermelho de lote pequeno, fermentacao natural de 36 horas. Doçura alta e final prolongado.',
 74.00, 25, 1, 'MEDIA', 'Melado de cana, amendoa torrada, laranja madura', 86.25, 250),

('Mogiana Classica',
 'Blend de talhao unico da mesma fazenda, torra mais escura para coador e prensa francesa. O cafe de todo dia da casa.',
 48.00, 60, 1, 'ESCURA', 'Cacau, nozes, tabaco doce', 82.00, 500),

-- Cerrado Mineiro (categoria 2)
('Alta Mogiana do Cerrado',
 'Acaia despolpado, secagem lenta em estufa. Corpo aveludado e acidez baixa — perfeito para quem acha cafe especial acido demais.',
 68.00, 35, 2, 'MEDIA', 'Caramelo, avela, baunilha', 85.00, 250),

('Vereda do Cerrado',
 'Microlote de Mundo Novo com fermentacao anaerobica. Producao limitada de 40 sacas por safra.',
 96.00, 12, 2, 'CLARA', 'Frutas amarelas, mel silvestre, jasmim', 88.75, 250),

('Cerrado Reserva',
 'Lote de fazenda familiar em Patrocinio, terceira geracao. Torra media escura pensada para leite.',
 55.00, 48, 2, 'ESCURA', 'Chocolate meio amargo, castanha de caju, especiarias', 83.25, 500),

-- Sul de Minas (categoria 3)
('Serra da Mantiqueira',
 'Cultivado a 1.250 m na divisa com Sao Paulo. Maturacao lenta e acidez malica bem definida.',
 82.00, 22, 3, 'CLARA', 'Maça verde, ameixa, chocolate branco', 87.50, 250),

('Carmo de Minas Natural',
 'Referencia do Sul de Minas em cafe natural. Secagem em terreiro por 18 dias, revolvido a mao.',
 78.00, 30, 3, 'MEDIA', 'Morango, chocolate ao leite, panela', 86.00, 250),

('Varginha Tradicional',
 'Catuai amarelo de safra plena. O equilibrio classico mineiro: nada dominante, tudo no lugar.',
 44.00, 75, 3, 'MEDIA', 'Achocolatado, amendoim, cana-de-acucar', 82.75, 500),

-- Chapada Diamantina (categoria 4)
('Piata Altitude',
 'Cultivado a 1.150 m no semiarido baiano. A amplitude termica de 20 graus entre dia e noite concentra os açucares no grao.',
 89.00, 18, 4, 'CLARA', 'Limao siciliano, flor de laranjeira, mel', 89.25, 250),

('Chapada Geisha',
 'Variedade Geisha adaptada a Bahia. Sete anos de lavoura para chegar a este perfil. O cafe mais premiado da casa.',
 148.00, 1, 4, 'CLARA', 'Bergamota, jasmim, pessego branco, cha preto', 91.00, 250),

('Morro do Chapeu',
 'Producao agroecologica de cooperativa local, sombreamento natural. Corpo medio e acidez citrica.',
 71.00, 28, 4, 'MEDIA', 'Tangerina, castanha, cacau', 85.75, 250);


-- ---------------------------------------------------------------------
-- Nota para a apresentacao
--
-- O 'Chapada Geisha' tem estoque = 1 de proposito. Isso deixa a demonstracao
-- do rollback pronta: basta tentar comprar 2 unidades para o checkout falhar,
-- exibir a mensagem dizendo qual cafe faltou, e um SELECT provar que nada foi
-- gravado em pedidos nem em itens_pedido.
-- ---------------------------------------------------------------------

SELECT
    c.nome                AS regiao,
    COUNT(p.id)           AS cafes,
    MIN(p.preco)          AS menor_preco,
    MAX(p.preco)          AS maior_preco,
    SUM(p.estoque)        AS estoque_total
FROM categorias c
JOIN produtos   p ON p.categoria_id = c.id
GROUP BY c.nome
ORDER BY c.nome;
