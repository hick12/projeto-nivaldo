/**
 * Deck de defesa oral — Torra & Terra
 * FACAMP · Tratamento e Armazenamento da Informacao
 *
 * A paleta e a identidade do proprio projeto: laranja torra sobre off-white
 * quente. Serif nos titulos (ecoa o Instrument Serif da loja), sans no corpo.
 */
const pptxgen = require("pptxgenjs");

const INK = "14120F", BG = "FAF9F7", SURF = "FFFFFF";
const ACC = "D4622A", ACC_SOFT = "FBF0E9", MUT = "6B6560", LINE = "E8E4DE";
const OK = "2F6B45", OK_SOFT = "EEF6F1", ERR = "A8321F", ERR_SOFT = "FDF0ED";

const SERIF = "Cambria", SANS = "Calibri", MONO = "Consolas";
const CAP = "C:/projetos/Nivaldo/docs/capturas/";

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";                 // 13.3 x 7.5
p.author = "Felipe Furlan";
p.title = "Torra & Terra — defesa";

const W = 13.33, M = 0.62;                // margem
const CW = W - M * 2;                     // largura util = 12.09

/* ---------- helpers ---------- */
function fundo(s, cor) { s.background = { color: cor }; }

function titulo(s, texto, opts = {}) {
  s.addText(texto, {
    x: M, y: opts.y || 0.45, w: CW, h: 0.8,
    fontFace: SERIF, fontSize: opts.size || 34, color: opts.cor || INK,
    bold: false, isTextBox: true, margin: 0, valign: "middle",
  });
}

function rotulo(s, texto, x, y, w, cor) {
  s.addText(texto.toUpperCase(), {
    x, y, w, h: 0.26, fontFace: SANS, fontSize: 10, color: cor || MUT,
    charSpacing: 1.4, bold: true, isTextBox: true, margin: 0, valign: "middle",
  });
}

function cartao(s, x, y, w, h, fill) {
  s.addShape(p.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.09,
    fill: { color: fill || SURF }, line: { color: LINE, width: 0.75 },
  });
}

function imagem(s, arq, x, y, w, h) {
  s.addImage({ path: CAP + arq, x, y, w, h, sizing: { type: "contain", w, h } });
}

function nota(s, txt) { s.addNotes(txt); }

/* =================================================================
   1 · CAPA
   ================================================================= */
let s = p.addSlide(); fundo(s, INK);
s.addText(
  [{ text: "Torra ", options: {} },
   { text: "&", options: { color: ACC } },
   { text: " Terra", options: {} }],
  { x: M, y: 2.15, w: CW, h: 1.5, fontFace: SERIF, fontSize: 66,
    color: "FFFFFF", isTextBox: true, margin: 0 });

s.addText("E-commerce de café especial em Flask e PostgreSQL.\nDo levantamento de requisitos ao deploy em cloud.", {
  x: M, y: 3.7, w: 7.6, h: 0.9, fontFace: SANS, fontSize: 16,
  color: "C9C2BB", isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

rotulo(s, "FACAMP · Tratamento e Armazenamento da Informação", M, 1.55, 8.5, "9B928A");

s.addText("nivaldo.felipefurlan.com.br", {
  x: M, y: 5.35, w: 7, h: 0.4, fontFace: SANS, fontSize: 15, bold: true,
  color: ACC, isTextBox: true, margin: 0 });
s.addText("Prof. Nivaldo T. Marcusso", {
  x: M, y: 5.8, w: 7, h: 0.35, fontFace: SANS, fontSize: 13,
  color: "9B928A", isTextBox: true, margin: 0 });

imagem(s, "10_mobile_catalogo.png", 9.55, 1.15, 2.55, 5.3);
nota(s, "Abrir a URL alguns minutos antes. O primeiro acesso depois de um deploy leva alguns segundos.");

/* =================================================================
   2 · O PROBLEMA
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "O problema");

const dores = [
  ["Estoque fora de controle", "Duas vendas em paralelo, e o mesmo lote sai duas vezes."],
  ["Pedido pela metade", "Cabeçalho gravado sem itens, ou total que não bate com a soma."],
];
dores.forEach(([t, d], i) => {
  const y = 1.7 + i * 1.55;
  cartao(s, M, y, 6.1, 1.3);
  s.addShape(p.ShapeType.ellipse, { x: M + 0.32, y: y + 0.4, w: 0.5, h: 0.5, fill: { color: ACC_SOFT } });
  s.addText(String(i + 1), { x: M + 0.32, y: y + 0.4, w: 0.5, h: 0.5, fontFace: SERIF,
    fontSize: 18, color: ACC, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(t, { x: M + 1.02, y: y + 0.24, w: 4.8, h: 0.35, fontFace: SANS, fontSize: 15,
    bold: true, color: INK, isTextBox: true, margin: 0 });
  s.addText(d, { x: M + 1.02, y: y + 0.6, w: 4.9, h: 0.55, fontFace: SANS, fontSize: 13,
    color: MUT, isTextBox: true, margin: 0 });
});

cartao(s, 7.15, 1.7, CW - 6.53, 3.15, ACC_SOFT);
rotulo(s, "A pergunta central", 7.6, 2.05, 5, ACC);
s.addText("Como estruturar uma loja que liste os cafés, monte um carrinho e conclua o pedido com integridade garantida pelo banco de dados?", {
  x: 7.6, y: 2.45, w: 4.9, h: 2.1, fontFace: SERIF, fontSize: 23, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });

s.addText("A loja é o pretexto. O que está sendo demonstrado é modelagem, constraints, transação e deploy.", {
  x: M, y: 5.25, w: CW, h: 0.4, fontFace: SANS, fontSize: 14, italic: true,
  color: MUT, isTextBox: true, margin: 0 });
nota(s, "30 segundos. Nao se alongar aqui — o peso da apresentacao esta no modelo e na transacao.");

/* =================================================================
   3 · POR QUE CAFÉ ESPECIAL
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Por que café especial, e não um e-commerce genérico");

s.addText("A moagem é escolhida na compra — não no cadastro do produto.", {
  x: M, y: 1.45, w: 6.4, h: 0.5, fontFace: SANS, fontSize: 16, bold: true,
  color: INK, isTextBox: true, margin: 0 });

s.addText([
  { text: "O mesmo café pode sair em grão para um cliente e moído fino para outro, no mesmo dia.\n\n", options: { color: MUT } },
  { text: "Se ", options: { color: MUT } },
  { text: "moagem", options: { fontFace: MONO, color: ACC } },
  { text: " fosse coluna de ", options: { color: MUT } },
  { text: "produtos", options: { fontFace: MONO, color: ACC } },
  { text: ", o mesmo café viraria três cadastros — e o controle de estoque, que é do café e não da moagem, quebraria.\n\n", options: { color: MUT } },
  { text: "É esse atributo que faz ", options: { color: MUT } },
  { text: "itens_pedido", options: { fontFace: MONO, color: ACC } },
  { text: " ser uma entidade de verdade, e não uma tabela de ligação.", options: { color: INK, bold: true } },
], { x: M, y: 2.05, w: 6.4, h: 3.2, fontFace: SANS, fontSize: 14,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });

imagem(s, "03_produto_detalhe.png", 7.35, 1.45, 5.35, 4.9);
nota(s, "Este e o argumento central do trabalho. Se so uma coisa for lembrada, que seja esta.");

/* =================================================================
   4 · MODELO DE DADOS
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "O modelo de dados");

const tabelas = [
  ["clientes", "id · nome · email UK\nsenha_hash · criado_em"],
  ["categorias", "id · nome UK\nregiao · descricao"],
  ["produtos", "id · nome · preco · estoque\ncategoria_id FK · torra · sca"],
  ["pedidos", "id · cliente_id FK\nstatus · total · criado_em"],
  ["itens_pedido", "id · pedido_id FK · produto_id FK\nquantidade · preco_unitario · moagem"],
];
tabelas.forEach(([nome, campos], i) => {
  const col = i % 3, lin = Math.floor(i / 3);
  const x = M + col * 4.07, y = 1.55 + lin * 1.75;
  const destaque = nome === "itens_pedido";
  cartao(s, x, y, 3.82, 1.5, destaque ? ACC_SOFT : SURF);
  s.addText(nome, { x: x + 0.28, y: y + 0.2, w: 3.3, h: 0.35, fontFace: MONO,
    fontSize: 14, bold: true, color: destaque ? ACC : INK, isTextBox: true, margin: 0 });
  s.addText(campos, { x: x + 0.28, y: y + 0.58, w: 3.3, h: 0.75, fontFace: SANS,
    fontSize: 10.5, color: MUT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });
});

cartao(s, M + 2 * 4.07, 3.3, 3.82, 1.5);
s.addText("Cardinalidades", { x: M + 2 * 4.07 + 0.28, y: 3.5, w: 3.3, h: 0.3,
  fontFace: SANS, fontSize: 12, bold: true, color: INK, isTextBox: true, margin: 0 });
s.addText("1 cliente → N pedidos\n1 pedido → N itens\n1 categoria → N produtos", {
  x: M + 2 * 4.07 + 0.28, y: 3.85, w: 3.3, h: 0.85, fontFace: SANS, fontSize: 11,
  color: MUT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });

cartao(s, M, 5.15, CW, 1.3, SURF);
rotulo(s, "Normalização", M + 0.35, 5.35, 3, ACC);
s.addText([
  { text: "1FN ", options: { bold: true, color: INK } },
  { text: "campos atômicos    ", options: { color: MUT } },
  { text: "2FN ", options: { bold: true, color: INK } },
  { text: "nada depende de parte da chave    ", options: { color: MUT } },
  { text: "3FN ", options: { bold: true, color: INK } },
  { text: "categorias separada evita dependência transitiva", options: { color: MUT } },
], { x: M + 0.35, y: 5.7, w: CW - 0.7, h: 0.5, fontFace: SANS, fontSize: 13,
     isTextBox: true, margin: 0 });
nota(s, "Se perguntarem sobre desnormalizacao: preco_unitario duplica produtos.preco de proposito, porque sao fatos diferentes — 'quanto custa hoje' e 'quanto custou naquela compra'.");

/* =================================================================
   5 · CONSTRAINTS
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "As constraints vivem no banco");

const nums = [["11", "CHECK"], ["4", "FOREIGN KEY"], ["5", "PRIMARY KEY"], ["3", "UNIQUE"]];
nums.forEach(([n, r], i) => {
  const x = M + i * 3.06;
  cartao(s, x, 1.55, 2.8, 1.5);
  s.addText(n, { x: x + 0.28, y: 1.72, w: 2.2, h: 0.8, fontFace: SERIF, fontSize: 44,
    color: ACC, isTextBox: true, margin: 0, valign: "middle" });
  rotulo(s, r, x + 0.3, 2.6, 2.3);
});

s.addText([
  { text: "O SQL/schema.sql é DDL escrito à mão. ", options: { bold: true, color: INK } },
  { text: "db.create_all() não é chamado em lugar nenhum do projeto — as constraints precisam estar visíveis em SQL, não escondidas no ORM.", options: { color: MUT } },
], { x: M, y: 3.3, w: 6.3, h: 1, fontFace: SANS, fontSize: 14, isTextBox: true,
     margin: 0, lineSpacingMultiple: 1.3 });

s.addText([
  { text: "A validação do formulário protege a experiência.\n", options: { color: MUT } },
  { text: "A constraint protege o dado.", options: { color: INK, bold: true } },
], { x: M, y: 4.45, w: 6.3, h: 0.9, fontFace: SANS, fontSize: 15, isTextBox: true,
     margin: 0, lineSpacingMultiple: 1.3 });

cartao(s, 7.15, 3.3, CW - 6.53, 2.6, ACC_SOFT);
rotulo(s, "A mais didática", 7.6, 3.6, 5, ACC);
s.addText("pontuacao_sca BETWEEN 80 AND 100", { x: 7.6, y: 3.95, w: 5, h: 0.4,
  fontFace: MONO, fontSize: 13, bold: true, color: INK, isTextBox: true, margin: 0 });
s.addText("Café especial, pela definição da SCA, pontua 80 ou mais. Não é preferência de interface — é o que define o produto. Regra de negócio pura, e por isso mora no banco.", {
  x: 7.6, y: 4.45, w: 4.9, h: 1.3, fontFace: SANS, fontSize: 13, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

s.addText("Dinheiro é NUMERIC(10,2), nunca FLOAT — ponto flutuante binário não representa 0,10 exatamente, e o erro se acumula ao somar os itens.", {
  x: M, y: 6.1, w: CW, h: 0.4, fontFace: SANS, fontSize: 13, italic: true,
  color: MUT, isTextBox: true, margin: 0 });
nota(s, "Se pedirem para explicar cada constraint: preco>=0, estoque>=0, quantidade>0, os tres dominios fechados (torra, moagem, status), o email UNIQUE e a UNIQUE composta de pedido+produto+moagem.");

/* =================================================================
   6 · A TRANSAÇÃO
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "A transação de checkout");
s.addText("Tudo-ou-nada, em duas fases dentro de uma única transação.", {
  x: M, y: 1.3, w: CW, h: 0.35, fontFace: SANS, fontSize: 14, color: MUT,
  isTextBox: true, margin: 0 });

const passos = [
  ["BEGIN", "abre a transação", INK],
  ["SELECT … FOR UPDATE", "trava cada café, em ordem crescente de id", ACC],
  ["valida TODOS os itens", "existe? tem estoque? nada foi gravado ainda", ACC],
  ["INSERT pedido + itens", "com preco_unitario congelado", INK],
  ["UPDATE estoque", "baixa o saldo de cada café", INK],
  ["COMMIT · ROLLBACK", "tudo, ou absolutamente nada", OK],
];
passos.forEach(([t, d, cor], i) => {
  const y = 1.85 + i * 0.78;
  s.addShape(p.ShapeType.ellipse, { x: M, y: y + 0.06, w: 0.44, h: 0.44,
    fill: { color: cor === OK ? OK_SOFT : ACC_SOFT } });
  s.addText(String(i + 1), { x: M, y: y + 0.06, w: 0.44, h: 0.44, fontFace: SANS,
    fontSize: 13, bold: true, color: cor === OK ? OK : ACC, align: "center",
    valign: "middle", isTextBox: true, margin: 0 });
  s.addText(t, { x: M + 0.65, y: y, w: 3.5, h: 0.32, fontFace: MONO, fontSize: 13,
    bold: true, color: cor, isTextBox: true, margin: 0 });
  s.addText(d, { x: M + 0.65, y: y + 0.31, w: 5.4, h: 0.3, fontFace: SANS,
    fontSize: 12, color: MUT, isTextBox: true, margin: 0 });
});

cartao(s, 7.15, 1.85, CW - 6.53, 2.15, SURF);
rotulo(s, "Por que travar em ordem de id", 7.6, 2.1, 5, ACC);
s.addText("Duas compras simultâneas que travassem os mesmos cafés em ordens opostas ficariam em deadlock, cada uma esperando a outra. Ordenar elimina o ciclo antes que ele exista.", {
  x: 7.6, y: 2.45, w: 4.9, h: 1.35, fontFace: SANS, fontSize: 13, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

cartao(s, 7.15, 4.25, CW - 6.53, 2.2, ACC_SOFT);
rotulo(s, "Três camadas de defesa", 7.6, 4.5, 5, ACC);
s.addText([
  { text: "1  ", options: { bold: true, color: ACC } },
  { text: "o navegador barra pelo atributo max\n", options: { color: MUT } },
  { text: "2  ", options: { bold: true, color: ACC } },
  { text: "a aplicação valida com a linha travada\n", options: { color: MUT } },
  { text: "3  ", options: { bold: true, color: ACC } },
  { text: "a constraint estoque >= 0 é a última", options: { color: MUT } },
], { x: 7.6, y: 4.85, w: 4.9, h: 1.3, fontFace: SANS, fontSize: 13,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.35 });
nota(s, "Ponto de parada sugerido pelo briefing: mostrar o caminho do rollback linha por linha no app.py.");

/* =================================================================
   7 · A LOJA
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "A loja no ar");
s.addText("nivaldo.felipefurlan.com.br  ·  HTTPS válido  ·  12 cafés lidos do banco de produção", {
  x: M, y: 1.28, w: CW, h: 0.35, fontFace: SANS, fontSize: 14, color: MUT,
  isTextBox: true, margin: 0 });
imagem(s, "01_catalogo.png", M, 1.75, 8.3, 4.7);
cartao(s, 9.2, 1.75, 3.5, 2.2);
rotulo(s, "RF01 · Catálogo", 9.5, 1.98, 3);
s.addText("Filtro por região, torra, pontuação SCA e nota sensorial. Preço sempre em R$ 0,00.", {
  x: 9.5, y: 2.32, w: 2.95, h: 1.4, fontFace: SANS, fontSize: 12, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
cartao(s, 9.2, 4.15, 3.5, 2.3, ACC_SOFT);
rotulo(s, "Design", 9.5, 4.38, 3, ACC);
s.addText("CSS puro, sem framework. Mobile-first: uma coluna no celular, três no desktop. Sem gradiente, sem sombra.", {
  x: 9.5, y: 4.72, w: 2.95, h: 1.5, fontFace: SANS, fontSize: 12, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
nota(s, "Abrir a loja de verdade aqui, nao ficar no slide. Filtrar por regiao ao vivo.");

/* =================================================================
   8 · O CENÁRIO DE ERRO  (slide principal)
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "O cenário de erro");
s.addText("Tentativa de comprar 2 unidades de um café com estoque 1.", {
  x: M, y: 1.28, w: CW, h: 0.35, fontFace: SANS, fontSize: 14, color: MUT,
  isTextBox: true, margin: 0 });
imagem(s, "08_rollback_estoque_insuficiente.png", M, 1.75, 8.3, 4.7);

cartao(s, 9.2, 1.75, 3.5, 2.35, ERR_SOFT);
rotulo(s, "A mensagem", 9.5, 1.98, 3, ERR);
s.addText("Nomeia o café que faltou e informa o saldo real. O carrinho é preservado, para o cliente corrigir sem remontar a compra.", {
  x: 9.5, y: 2.32, w: 2.95, h: 1.6, fontFace: SANS, fontSize: 12, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

cartao(s, 9.2, 4.3, 3.5, 2.15, OK_SOFT);
rotulo(s, "E no banco", 9.5, 4.52, 3, OK);
s.addText("pedidos = 0\nitens_pedido = 0\nestoque = 1  intacto", {
  x: 9.5, y: 4.87, w: 2.95, h: 1.1, fontFace: MONO, fontSize: 12.5, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });
nota(s, "O momento mais importante da apresentacao. Fazer ao vivo: tentar comprar 2 do Chapada Geisha, mostrar a mensagem, e rodar o SELECT no painel do banco provando que nada foi gravado.");

/* =================================================================
   9 · A PROVA NO BANCO
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "A compra que dá certo");

imagem(s, "09_meus_pedidos.png", M, 1.5, 6.4, 4.9);

cartao(s, 7.35, 1.5, CW - 6.73, 2.5, ACC_SOFT);
rotulo(s, "Duas linhas do mesmo café", 7.75, 1.75, 5, ACC);
s.addText("pedido #5 | Piata Altitude | 2x | GRAO | R$ 89,00\npedido #5 | Piata Altitude | 1x | FINA | R$ 89,00", {
  x: 7.75, y: 2.12, w: 4.7, h: 0.8, fontFace: MONO, fontSize: 10.5, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });
s.addText("A prova concreta de que itens_pedido é entidade: mesmo produto, mesmo pedido, duas linhas — porque a moagem difere.", {
  x: 7.75, y: 3.0, w: 4.7, h: 0.85, fontFace: SANS, fontSize: 12.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

cartao(s, 7.35, 4.15, CW - 6.73, 2.25);
rotulo(s, "Integridade verificada", 7.75, 4.4, 5, OK);
s.addText([
  { text: "R$ 178,00 + R$ 89,00 = R$ 267,00\n", options: { fontFace: MONO, color: INK } },
  { text: "o total gravado bate com a soma dos itens\n\n", options: { color: MUT } },
  { text: "Piata Altitude: 18 → 15\n", options: { fontFace: MONO, color: INK } },
  { text: "o estoque desceu exatamente 3", options: { color: MUT } },
], { x: 7.75, y: 4.75, w: 4.7, h: 1.5, fontFace: SANS, fontSize: 12,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
nota(s, "Mostrar no painel do Postgres o registro aparecendo no instante seguinte ao checkout.");

/* =================================================================
   10 · QUALIDADE
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Qualidade");

cartao(s, M, 1.55, 3.82, 2.5);
s.addText("24", { x: M + 0.32, y: 1.75, w: 2, h: 0.85, fontFace: SERIF, fontSize: 46,
  color: ACC, isTextBox: true, margin: 0, valign: "middle" });
rotulo(s, "Testes passando", M + 0.34, 2.62, 3.2);
s.addText("Contra um PostgreSQL real, não SQLite — o FOR UPDATE e as constraints CHECK são justamente o que precisa ser testado.", {
  x: M + 0.32, y: 2.95, w: 3.2, h: 0.95, fontFace: SANS, fontSize: 11.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });

cartao(s, M + 4.07, 1.55, 3.82, 2.5);
s.addText("8", { x: M + 4.39, y: 1.75, w: 2, h: 0.85, fontFace: SERIF, fontSize: 46,
  color: ACC, isTextBox: true, margin: 0, valign: "middle" });
rotulo(s, "Achados do OWASP ZAP corrigidos", M + 4.41, 2.62, 3.3);
s.addText("CSRF, flags do cookie e os cabeçalhos. O CSP usa script-src 'none' — a loja não tem JavaScript, o que torna XSS inviável.", {
  x: M + 4.39, y: 2.95, w: 3.2, h: 0.95, fontFace: SANS, fontSize: 11.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });

cartao(s, M + 8.14, 1.55, 3.82, 2.5);
s.addText("4", { x: M + 8.46, y: 1.75, w: 2, h: 0.85, fontFace: SERIF, fontSize: 46,
  color: ACC, isTextBox: true, margin: 0, valign: "middle" });
rotulo(s, "Índices, cada um justificado", M + 8.48, 2.62, 3.3);
s.addText("Índice acelera leitura mas encarece escrita. Criar por precaução é custo sem benefício.", {
  x: M + 8.46, y: 2.95, w: 3.2, h: 0.95, fontFace: SANS, fontSize: 11.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });

cartao(s, M, 4.3, CW, 2.15, SURF);
rotulo(s, "O que o EXPLAIN mostrou", M + 0.35, 4.55, 5, ACC);
s.addText([
  { text: "WHERE categoria_id = 4", options: { fontFace: MONO, color: INK } },
  { text: "   →  Index Scan          ", options: { color: OK, bold: true } },
  { text: "WHERE cliente_id = 2", options: { fontFace: MONO, color: INK } },
  { text: "   →  Bitmap Index Scan          ", options: { color: OK, bold: true } },
  { text: "ORDER BY nome", options: { fontFace: MONO, color: INK } },
  { text: "   →  Seq Scan", options: { color: MUT, bold: true } },
], { x: M + 0.35, y: 4.92, w: CW - 0.7, h: 0.5, fontSize: 12.5, fontFace: SANS,
     isTextBox: true, margin: 0 });
s.addText("A diferença é a seletividade. As duas primeiras filtram poucas linhas de muitas — compensa consultar o índice. A terceira precisa de todas as linhas: usar o índice seria ler o índice inteiro e depois a tabela inteira. O planejador está certo nos três casos.", {
  x: M + 0.35, y: 5.45, w: CW - 0.7, h: 0.85, fontFace: SANS, fontSize: 12.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
nota(s, "Se perguntarem por que um indice nao foi usado: e a resposta acima. Saber explicar isso vale mais do que ter os tres planos usando indice.");

/* =================================================================
   11 · DEPLOY
   ================================================================= */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Deploy e operação");

const infra = [
  ["Aplicação", "Railway · gunicorn"],
  ["Banco", "PostgreSQL 18.6 gerenciado"],
  ["Domínio", "HTTPS · Let's Encrypt"],
  ["Código", "GitHub · 23 commits"],
];
infra.forEach(([t, d], i) => {
  const x = M + i * 3.06;
  cartao(s, x, 1.55, 2.8, 1.25);
  rotulo(s, t, x + 0.3, 1.78, 2.3, ACC);
  s.addText(d, { x: x + 0.28, y: 2.1, w: 2.35, h: 0.55, fontFace: SANS, fontSize: 12.5,
    color: INK, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });
});

cartao(s, M, 3.05, 6.1, 3.4);
rotulo(s, "Backup e restauração — testados", M + 0.35, 3.3, 5, OK);
s.addText([
  { text: "Backup só é confiável quando a restauração também é testada.\n\n", options: { color: MUT } },
  { text: "origem      12 · 4 · 2 · 2 · 3\nrestaurado  12 · 4 · 2 · 2 · 3\n", options: { fontFace: MONO, color: INK } },
  { text: "constraints e índices, todos presentes\n\n", options: { color: MUT } },
  { text: "E a regra ainda funciona no destino:\n", options: { color: MUT } },
  { text: "violates check constraint \"ck_produtos_preco\"", options: { fontFace: MONO, color: ERR } },
], { x: M + 0.35, y: 3.65, w: 5.4, h: 2.5, fontFace: SANS, fontSize: 12,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

cartao(s, 7.15, 3.05, CW - 6.53, 3.4, ACC_SOFT);
rotulo(s, "Limitações do MVP, documentadas", 7.6, 3.3, 5, ACC);
s.addText([
  { text: "Sem pagamento real e sem frete\n", options: { bullet: true, breakLine: true } },
  { text: "Sem controle de lote e data de torra — a evolução mais natural do domínio\n", options: { bullet: true, breakLine: true } },
  { text: "Sem área administrativa nem relatórios\n", options: { bullet: true, breakLine: true } },
  { text: "Carrinho na sessão: não sobrevive à troca de dispositivo. É exatamente onde um Redis passaria a fazer sentido", options: { bullet: true } },
], { x: 7.6, y: 3.68, w: 4.85, h: 2.5, fontFace: SANS, fontSize: 12.5, color: MUT,
     isTextBox: true, margin: 0, paraSpaceAfter: 6 });
nota(s, "Pendencia honesta, se perguntarem: o deploy automatico a cada push nao esta ativo porque o repositorio e de outra conta do GitHub e a Railway GitHub App precisa da autorizacao do dono.");

/* =================================================================
   12 · ENCERRAMENTO
   ================================================================= */
s = p.addSlide(); fundo(s, INK);
s.addText("A lógica do projeto é cumulativa", {
  x: M, y: 2.1, w: 9.0, h: 1.0, fontFace: SERIF, fontSize: 36, color: "FFFFFF",
  isTextBox: true, margin: 0 });

s.addText([
  { text: "boa análise  →  boa modelagem  →  bom banco\n", options: { color: "C9C2BB" } },
  { text: "→  boa aplicação  →  boa qualidade  →  bom deploy", options: { color: "C9C2BB" } },
], { x: M, y: 3.2, w: 8.5, h: 1, fontFace: SANS, fontSize: 17, isTextBox: true,
     margin: 0, lineSpacingMultiple: 1.35 });

s.addText("Se o requisito for fraco, o modelo fica confuso. Se o modelo for fraco, o banco fica inconsistente. Se o banco for fraco, a aplicação falha.", {
  x: M, y: 4.5, w: 8.2, h: 1, fontFace: SANS, fontSize: 14, italic: true,
  color: "9B928A", isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });

s.addText("nivaldo.felipefurlan.com.br", {
  x: M, y: 5.85, w: 8, h: 0.4, fontFace: SANS, fontSize: 16, bold: true,
  color: ACC, isTextBox: true, margin: 0 });

imagem(s, "10_mobile_catalogo.png", 9.9, 1.3, 2.4, 4.95);
nota(s, "Deixar a loja aberta numa aba e o painel do Postgres em outra, para as perguntas.");

p.writeFile({ fileName: "C:/projetos/Nivaldo/docs/Defesa_Torra_e_Terra.pptx" })
 .then(f => console.log("deck gerado:", f));
