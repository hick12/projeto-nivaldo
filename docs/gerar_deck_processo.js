/**
 * Deck do PROCESSO — Torra & Terra
 * Como o projeto foi construido, do requisito ao deploy.
 *
 * Sem capturas de tela: a loja e demonstrada ao vivo no final.
 * Espaco generoso de proposito — os slides sao apoio, quem conta e o aluno.
 */
const pptxgen = require("pptxgenjs");

const INK = "14120F", BG = "FAF9F7", SURF = "FFFFFF";
const ACC = "D4622A", ACC_SOFT = "FBF0E9", MUT = "6B6560", LINE = "E8E4DE";
const OK = "2F6B45", OK_SOFT = "EEF6F1", ERR = "A8321F", ERR_SOFT = "FDF0ED";
const SERIF = "Cambria", SANS = "Calibri", MONO = "Consolas";

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Felipe Furlan";
p.title = "Torra & Terra — do requisito ao deploy";

const W = 13.33, M = 0.7, CW = W - M * 2;

function fundo(s, c) { s.background = { color: c }; }
function titulo(s, t, sub) {
  s.addText(t, { x: M, y: 0.5, w: CW, h: 0.75, fontFace: SERIF, fontSize: 34,
    color: INK, isTextBox: true, margin: 0, valign: "middle" });
  if (sub) s.addText(sub, { x: M, y: 1.28, w: CW, h: 0.35, fontFace: SANS,
    fontSize: 14, color: MUT, isTextBox: true, margin: 0 });
}
function rotulo(s, t, x, y, w, cor) {
  s.addText(t.toUpperCase(), { x, y, w, h: 0.26, fontFace: SANS, fontSize: 10,
    color: cor || MUT, charSpacing: 1.4, bold: true, isTextBox: true, margin: 0, valign: "middle" });
}
function cartao(s, x, y, w, h, fill) {
  s.addShape(p.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.09,
    fill: { color: fill || SURF }, line: { color: LINE, width: 0.75 } });
}
function bolha(s, x, y, n, cor, fundoCor) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: 0.5, h: 0.5, fill: { color: fundoCor || ACC_SOFT } });
  s.addText(String(n), { x, y, w: 0.5, h: 0.5, fontFace: SANS, fontSize: 14, bold: true,
    color: cor || ACC, align: "center", valign: "middle", isTextBox: true, margin: 0 });
}

/* ============ 1 · CAPA ============ */
let s = p.addSlide(); fundo(s, INK);
s.addText([{ text: "Torra " }, { text: "&", options: { color: ACC } }, { text: " Terra" }],
  { x: M, y: 2.0, w: CW, h: 1.4, fontFace: SERIF, fontSize: 60, color: "FFFFFF",
    isTextBox: true, margin: 0 });
s.addText("Do requisito ao deploy", {
  x: M, y: 3.45, w: 9, h: 0.7, fontFace: SERIF, fontSize: 30, color: ACC,
  isTextBox: true, margin: 0 });
s.addText("Como construímos um e-commerce com integridade garantida pelo banco de dados.", {
  x: M, y: 4.35, w: 8.4, h: 0.5, fontFace: SANS, fontSize: 16, color: "C9C2BB",
  isTextBox: true, margin: 0 });
rotulo(s, "FACAMP · Tratamento e Armazenamento da Informação", M, 1.4, 9, "9B928A");
s.addText("Prof. Nivaldo T. Marcusso", { x: M, y: 5.85, w: 8, h: 0.35, fontFace: SANS,
  fontSize: 13, color: "9B928A", isTextBox: true, margin: 0 });
s.addNotes("Apresentar o grupo. Dizer em uma frase o que e o projeto: uma loja de cafe especial onde o que importa nao e a loja, e a integridade do dado. A demonstracao ao vivo fica para o final.");

/* ============ 2 · O MÉTODO ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Como trabalhamos", "Oito etapas, uma revisão entre cada uma, um commit por etapa.");

const etapas = [
  ["0", "Requisitos", "RF, RNF e aceite"],
  ["1", "Schema SQL", "DDL à mão, com constraints"],
  ["2", "Modelos ORM", "espelhando o schema"],
  ["3", "Catálogo", "e detalhe do produto"],
  ["4", "Login", "cadastro e sessão"],
  ["5", "Carrinho", "com escolha de moagem"],
  ["6", "Checkout", "a transação"],
  ["7", "Testes", "e documentação"],
];
etapas.forEach(([n, t, d], i) => {
  const col = i % 4, lin = Math.floor(i / 4);
  const x = M + col * 3.06, y = 2.0 + lin * 1.85;
  cartao(s, x, y, 2.8, 1.55, n === "6" ? ACC_SOFT : SURF);
  bolha(s, x + 0.28, y + 0.24, n);
  s.addText(t, { x: x + 0.28, y: y + 0.82, w: 2.3, h: 0.3, fontFace: SANS, fontSize: 14,
    bold: true, color: INK, isTextBox: true, margin: 0 });
  s.addText(d, { x: x + 0.28, y: y + 1.12, w: 2.3, h: 0.3, fontFace: SANS, fontSize: 11,
    color: MUT, isTextBox: true, margin: 0 });
});

s.addText("Nenhuma etapa começou antes da anterior ser revisada. O histórico do Git conta essa ordem — são commits que contam a construção, não um único “projeto pronto”.", {
  x: M, y: 5.85, w: CW, h: 0.6, fontFace: SANS, fontSize: 14, italic: true, color: MUT,
  isTextBox: true, margin: 0 });
s.addNotes("Ponto importante: a ordem nao foi acidental. Requisito gera entidade, entidade gera tabela, tabela alimenta o ORM, o ORM sustenta as rotas, as rotas precisam de transacao e teste, e tudo culmina no deploy.");

/* ============ 3 · REQUISITOS ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Etapa 0 — Requisitos antes de qualquer código",
  "A tentação é começar pelo schema. Começamos pelo problema.");

cartao(s, M, 2.0, 5.9, 2.0, ACC_SOFT);
rotulo(s, "A pergunta que orientou tudo", M + 0.35, 2.25, 5, ACC);
s.addText("Como concluir um pedido com integridade garantida pelo banco, e não pela boa vontade da aplicação?", {
  x: M + 0.35, y: 2.6, w: 5.2, h: 1.2, fontFace: SERIF, fontSize: 19, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });

const artefatos = [
  ["6 requisitos funcionais", "cada um com critério de aceite"],
  ["8 requisitos não funcionais", "integridade, segurança, desempenho, recuperação"],
  ["Backlog priorizado", "o que entra no MVP e o que fica como evolução"],
  ["Fluxo do processo", "com os pontos de validação marcados"],
];
artefatos.forEach(([t, d], i) => {
  const y = 2.0 + i * 1.12;
  s.addText(t, { x: 7.1, y, w: 5.5, h: 0.32, fontFace: SANS, fontSize: 14, bold: true,
    color: INK, isTextBox: true, margin: 0 });
  s.addText(d, { x: 7.1, y: y + 0.32, w: 5.5, h: 0.32, fontFace: SANS, fontSize: 12,
    color: MUT, isTextBox: true, margin: 0 });
});

s.addText("Decidimos aqui que o carrinho seria sessão, e não tabela: ele é processo, não entidade — existe só enquanto a compra não fecha.", {
  x: M, y: 4.45, w: 5.9, h: 1.0, fontFace: SANS, fontSize: 13, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
s.addNotes("Se perguntarem por que gastar tempo com requisito: porque requisito mal definido gera tabela errada. A decisao do carrinho em sessao veio daqui, e ela nos poupou uma tabela inteira.");

/* ============ 4 · MODELO E CONSTRAINTS ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Etapas 1 e 2 — O modelo e as constraints",
  "Escrevemos o DDL à mão. db.create_all() não é chamado em lugar nenhum.");

cartao(s, M, 2.0, 5.9, 2.3, ACC_SOFT);
rotulo(s, "A decisão de modelagem central", M + 0.35, 2.25, 5, ACC);
s.addText("A moagem mora no item, não no produto.", {
  x: M + 0.35, y: 2.6, w: 5.2, h: 0.4, fontFace: SANS, fontSize: 16, bold: true,
  color: INK, isTextBox: true, margin: 0 });
s.addText("O cliente escolhe na compra. É esse atributo que faz itens_pedido ser entidade de verdade, e não tabela de ligação.", {
  x: M + 0.35, y: 3.05, w: 5.2, h: 1.0, fontFace: SANS, fontSize: 13, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

const n = [["11", "CHECK"], ["4", "FK"], ["5", "PK"], ["3", "UNIQUE"]];
n.forEach(([v, r], i) => {
  const x = 7.1 + (i % 2) * 2.85, y = 2.0 + Math.floor(i / 2) * 1.2;
  s.addText(v, { x, y, w: 1.0, h: 0.7, fontFace: SERIF, fontSize: 34, color: ACC,
    isTextBox: true, margin: 0, valign: "middle" });
  s.addText(r, { x: x + 1.0, y: y + 0.15, w: 1.7, h: 0.4, fontFace: SANS, fontSize: 12,
    color: MUT, isTextBox: true, margin: 0, valign: "middle" });
});

s.addText("Por que no banco e não só na aplicação: a validação do formulário protege a experiência; a constraint protege o dado. Se amanhã alguém inserir por script ou por API, a regra continua valendo.", {
  x: M, y: 4.6, w: CW, h: 0.8, fontFace: SANS, fontSize: 14, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

s.addText("pontuacao_sca BETWEEN 80 AND 100  —  café especial, por definição da SCA, pontua 80 ou mais.", {
  x: M, y: 5.65, w: CW, h: 0.4, fontFace: MONO, fontSize: 13, color: INK,
  isTextBox: true, margin: 0 });
s.addNotes("Espaco para falar: escolher duas ou tres constraints e explicar o que aconteceria sem cada uma. A da SCA e a mais didatica porque e regra de negocio pura.");

/* ============ 5 · O CHECKOUT ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Etapa 6 — O checkout transacional", "O coração do trabalho. Tudo, ou absolutamente nada.");

const fases = [
  ["FASE 1", "travar e validar", "SELECT … FOR UPDATE em cada café,\nem ordem crescente de id.\nNada é gravado ainda.", ACC],
  ["FASE 2", "gravar", "INSERT do pedido e dos itens,\ncom preço congelado.\nUPDATE do estoque.", INK],
];
fases.forEach(([f, t, d, cor], i) => {
  const x = M + i * 4.4;
  cartao(s, x, 2.0, 4.1, 2.5, i === 0 ? ACC_SOFT : SURF);
  rotulo(s, f, x + 0.32, 2.25, 2, cor);
  s.addText(t, { x: x + 0.32, y: 2.55, w: 3.4, h: 0.35, fontFace: SANS, fontSize: 15,
    bold: true, color: INK, isTextBox: true, margin: 0 });
  s.addText(d, { x: x + 0.32, y: 2.95, w: 3.5, h: 1.3, fontFace: SANS, fontSize: 12.5,
    color: MUT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
});

cartao(s, M + 8.8, 2.0, 3.13, 2.5, OK_SOFT);
rotulo(s, "Fim", M + 9.12, 2.25, 2, OK);
s.addText("COMMIT", { x: M + 9.12, y: 2.55, w: 2.5, h: 0.35, fontFace: MONO, fontSize: 15,
  bold: true, color: OK, isTextBox: true, margin: 0 });
s.addText("ou ROLLBACK em qualquer falha, desfazendo a transação inteira.", {
  x: M + 9.12, y: 2.95, w: 2.5, h: 1.3, fontFace: SANS, fontSize: 12.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

cartao(s, M, 4.75, CW, 1.55, SURF);
rotulo(s, "Duas decisões que valem explicar", M + 0.35, 4.98, 6, ACC);
s.addText([
  { text: "Travamos em ordem crescente de id. ", options: { bold: true, color: INK } },
  { text: "Duas compras simultâneas travando os mesmos cafés em ordens opostas entrariam em deadlock.\n", options: { color: MUT } },
  { text: "Nada é inserido antes da validação terminar. ", options: { bold: true, color: INK } },
  { text: "O caso de erro nem chega a criar o cabeçalho do pedido.", options: { color: MUT } },
], { x: M + 0.35, y: 5.32, w: CW - 0.7, h: 0.85, fontFace: SANS, fontSize: 13,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });
s.addNotes("Aqui vale abrir o app.py e mostrar o caminho do rollback linha por linha, se houver tempo. O SELECT FOR UPDATE e o que impede vender o mesmo lote duas vezes.");

/* ============ 6 · OS TESTES ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Etapa 7 — Os testes, e o que eles pegaram",
  "24 testes contra um PostgreSQL real. Não SQLite.");

cartao(s, M, 2.0, 5.9, 1.75, SURF);
rotulo(s, "Por que não SQLite", M + 0.35, 2.22, 5, ACC);
s.addText("O SELECT … FOR UPDATE e as constraints CHECK são justamente o que precisa ser testado — e o SQLite trata os dois de forma diferente. Testar contra outro banco daria confiança falsa.", {
  x: M + 0.35, y: 2.55, w: 5.2, h: 1.05, fontFace: SANS, fontSize: 13, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

cartao(s, M, 3.95, 5.9, 2.35, ERR_SOFT);
rotulo(s, "Um teste nosso estava errado", M + 0.35, 4.18, 5, ERR);
s.addText([
  { text: "Escrevemos um teste que inseria a moagem ", options: { color: MUT } },
  { text: "'EXTRAFINA'", options: { fontFace: MONO, color: INK } },
  { text: " esperando que o CHECK recusasse. O banco recusou — mas ", options: { color: MUT } },
  { text: "por tamanho", options: { bold: true, color: INK } },
  { text: ": a coluna é VARCHAR(6) e a palavra tem 9 caracteres.\n\nO dado era barrado, mas pela regra errada. O teste não provava o que dizia provar.", options: { color: MUT } },
], { x: M + 0.35, y: 4.52, w: 5.2, h: 1.65, fontFace: SANS, fontSize: 12.5,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.25 });

const casos = [
  "Compra normal grava pedido, itens e baixa estoque",
  "Estoque insuficiente faz rollback completo",
  "Produto inexistente não finaliza o pedido",
  "Preço, estoque, SCA e moagem inválidos são recusados pelo banco",
  "Senha nunca é gravada em texto puro",
  "Mesmo café em duas moagens vira duas linhas",
  "Preço congelado sobrevive a um reajuste",
];
rotulo(s, "O que está coberto", 7.1, 2.05, 5, ACC);
casos.forEach((c, i) => {
  const y = 2.42 + i * 0.55;
  s.addShape(p.ShapeType.ellipse, { x: 7.1, y: y + 0.09, w: 0.16, h: 0.16, fill: { color: ACC } });
  s.addText(c, { x: 7.45, y, w: 5.2, h: 0.45, fontFace: SANS, fontSize: 12.5, color: MUT,
    isTextBox: true, margin: 0, valign: "middle" });
});
s.addNotes("Contar o caso do EXTRAFINA como historia: e o tipo de erro que so aparece quando voce roda o teste de verdade e le a mensagem, em vez de confiar que passou.");

/* ============ 7 · O DEPLOY ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Três problemas que só apareceram em produção",
  "O deploy é uma etapa do trabalho, não um detalhe do final. Funcionar na máquina do desenvolvedor não é funcionar.");

const probs = [
  ["A aplicação estava usando superusuário",
   "O provedor entrega a conexão como postgres, que é superusuário do container. Isso violava um requisito do próprio material.",
   "Criamos o papel torra_app, sem SUPERUSER. Verificado: DROP TABLE é negado.", ERR],
  ["O pg_dump local era velho demais",
   "Cliente 17.5 contra servidor 18.6 — o pg_dump se recusa a dumpar um servidor mais novo que ele.",
   "Rodamos o backup de dentro do container do banco, onde as ferramentas são da versão exata.", ERR],
  ["O deploy automático não dispara",
   "O repositório pertence a outra conta do GitHub, e o Railway respondeu: “no one in the project has access to it”.",
   "Depende do dono do repositório autorizar. Enquanto isso, o deploy é manual e funciona.", MUT],
];
probs.forEach(([t, d, sol, cor], i) => {
  const x = M + i * 4.05;
  cartao(s, x, 2.0, 3.75, 3.9, SURF);
  bolha(s, x + 0.3, 2.22, i + 1, cor === MUT ? MUT : ERR, cor === MUT ? "EFECE9" : ERR_SOFT);
  s.addText(t, { x: x + 0.3, y: 2.85, w: 3.15, h: 0.6, fontFace: SANS, fontSize: 13.5,
    bold: true, color: INK, isTextBox: true, margin: 0, lineSpacingMultiple: 1.1 });
  s.addText(d, { x: x + 0.3, y: 3.5, w: 3.15, h: 1.25, fontFace: SANS, fontSize: 11.5,
    color: MUT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
  s.addText(sol, { x: x + 0.3, y: 4.8, w: 3.15, h: 0.95, fontFace: SANS, fontSize: 11.5,
    color: OK, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
});
s.addText("Nenhum dos três aparece em ambiente local — todos foram encontrados conferindo o que estava no ar, em vez de assumir que estava certo.", {
  x: M, y: 6.05, w: CW, h: 0.5, fontFace: SANS, fontSize: 14, italic: true, color: MUT,
  isTextBox: true, margin: 0 });
s.addNotes("Esta e a parte mais honesta da apresentacao e provavelmente a que mais rende conversa. Mostrar que a gente conferiu em producao em vez de assumir que estava certo.");

/* ============ 8 · SEGURANÇA ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "Segurança — rodamos o OWASP ZAP",
  "Onze alertas. Oito eram reais e foram corrigidos.");

cartao(s, M, 2.0, 6.4, 2.6, ERR_SOFT);
rotulo(s, "O achado que importava", M + 0.35, 2.25, 5, ERR);
s.addText("Sem token CSRF e sem SameSite no cookie, um site malicioso visitado por um cliente logado poderia disparar um POST para /checkout usando o cookie dele — o navegador anexa o cookie sozinho e não sabe distinguir o formulário. O pedido sairia de verdade.", {
  x: M + 0.35, y: 2.6, w: 5.7, h: 1.85, fontFace: SANS, fontSize: 13, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.28 });

cartao(s, M, 4.8, 6.4, 1.5, OK_SOFT);
rotulo(s, "As duas defesas", M + 0.35, 5.0, 5, OK);
s.addText("SameSite=Lax barra o cookie em POST de outro site. O token CSRF é um segredo que só o nosso HTML conhece — e o atacante não consegue ler a sessão para forjá-lo.", {
  x: M + 0.35, y: 5.32, w: 5.7, h: 0.85, fontFace: SANS, fontSize: 12.5, color: MUT,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.22 });

rotulo(s, "Também corrigidos", 7.6, 2.05, 5, ACC);
const itens = ["Cookie sem flag Secure", "Content Security Policy ausente",
  "Cabeçalho anti-clickjacking", "HSTS não definido",
  "X-Content-Type-Options ausente", "Cache em página de cliente logado"];
itens.forEach((t, i) => {
  const y = 2.45 + i * 0.5;
  s.addShape(p.ShapeType.ellipse, { x: 7.6, y: y + 0.08, w: 0.15, h: 0.15, fill: { color: OK } });
  s.addText(t, { x: 7.95, y, w: 4.7, h: 0.4, fontFace: SANS, fontSize: 12.5, color: MUT,
    isTextBox: true, margin: 0, valign: "middle" });
});

cartao(s, 7.6, 5.5, 5.05, 0.85, ACC_SOFT);
s.addText("A loja não tem uma linha de JavaScript — o que permitiu a política mais restritiva possível e torna XSS inviável.", {
  x: 7.9, y: 5.68, w: 4.5, h: 0.55, fontFace: SANS, fontSize: 12, color: INK,
  isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
s.addNotes("Um alerta nao foi corrigido, e vale dizer por que: SRI no Google Fonts nao e aplicavel porque o CSS varia por navegador e o hash mudaria por visitante. A mitigacao e o proprio CSP.");

/* ============ 9 · NÚMEROS ============ */
s = p.addSlide(); fundo(s, BG);
titulo(s, "O projeto em números");

const met = [
  ["5", "tabelas", "23 constraints e 4 índices"],
  ["24", "testes", "todos passando"],
  ["12", "cafés", "em 4 regiões produtoras"],
  ["25", "commits", "um por etapa da construção"],
];
met.forEach(([v, t, d], i) => {
  const x = M + i * 3.06;
  cartao(s, x, 2.0, 2.8, 2.0);
  s.addText(v, { x: x + 0.3, y: 2.22, w: 2.2, h: 0.85, fontFace: SERIF, fontSize: 44,
    color: ACC, isTextBox: true, margin: 0, valign: "middle" });
  s.addText(t, { x: x + 0.3, y: 3.1, w: 2.2, h: 0.32, fontFace: SANS, fontSize: 14,
    bold: true, color: INK, isTextBox: true, margin: 0 });
  s.addText(d, { x: x + 0.3, y: 3.42, w: 2.3, h: 0.45, fontFace: SANS, fontSize: 11.5,
    color: MUT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });
});

cartao(s, M, 4.3, CW, 2.0, ACC_SOFT);
rotulo(s, "O que ficou de fora, de propósito", M + 0.4, 4.55, 6, ACC);
s.addText([
  { text: "Pagamento real e frete    ·    Área administrativa    ·    Relatórios de venda\n", options: { color: MUT } },
  { text: "Controle de lote e data de torra", options: { color: INK, bold: true } },
  { text: " — a evolução mais natural do domínio, e a que mais mexeria no modelo\n", options: { color: MUT } },
  { text: "Carrinho entre dispositivos", options: { color: INK, bold: true } },
  { text: " — é exatamente onde um Redis passaria a fazer sentido", options: { color: MUT } },
], { x: M + 0.4, y: 4.95, w: CW - 0.8, h: 1.2, fontFace: SANS, fontSize: 13.5,
     isTextBox: true, margin: 0, lineSpacingMultiple: 1.35 });
s.addNotes("Saber o que NAO foi feito, e por que, vale tanto quanto o que foi. Cada limitacao aqui esta documentada no repositorio com a justificativa.");

/* ============ 10 · DEMONSTRAÇÃO ============ */
s = p.addSlide(); fundo(s, INK);
s.addText("Demonstração", { x: M, y: 1.9, w: 8, h: 0.95, fontFace: SERIF, fontSize: 46,
  color: "FFFFFF", isTextBox: true, margin: 0 });
s.addText("nivaldo.felipefurlan.com.br", { x: M, y: 2.95, w: 8, h: 0.5, fontFace: SANS,
  fontSize: 20, bold: true, color: ACC, isTextBox: true, margin: 0 });

const roteiro = [
  "Catálogo e filtro por região",
  "Escolha da moagem — a decisão de modelagem, na tela",
  "Checkout: o pedido gravado e o estoque baixando",
  "O cenário de erro: comprar 2 de um café com estoque 1",
  "O SELECT provando que nada foi gravado",
];
roteiro.forEach((t, i) => {
  const y = 4.0 + i * 0.56;
  s.addShape(p.ShapeType.ellipse, { x: M, y: y + 0.06, w: 0.38, h: 0.38,
    fill: { color: i === 3 ? ACC : "2A2622" } });
  s.addText(String(i + 1), { x: M, y: y + 0.06, w: 0.38, h: 0.38, fontFace: SANS,
    fontSize: 12, bold: true, color: i === 3 ? "FFFFFF" : "9B928A", align: "center",
    valign: "middle", isTextBox: true, margin: 0 });
  s.addText(t, { x: M + 0.6, y, w: 7.5, h: 0.5, fontFace: SANS, fontSize: 14.5,
    color: i === 3 ? "FFFFFF" : "C9C2BB", bold: i === 3, isTextBox: true, margin: 0,
    valign: "middle" });
});

s.addText("O Chapada Geisha está com estoque 1, de propósito.", {
  x: 9.1, y: 4.05, w: 3.5, h: 1.2, fontFace: SANS, fontSize: 13, italic: true,
  color: "9B928A", isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 });
s.addNotes("Abrir a loja alguns minutos antes. Deixar o painel do Postgres numa segunda aba. O passo 4 e o que mais impressiona: a mensagem nomeia o cafe que faltou, e o SELECT depois mostra que a contagem de pedidos nao mudou.");

p.writeFile({ fileName: "C:/projetos/Nivaldo/docs/Processo_Torra_e_Terra.pptx" })
 .then(f => console.log("deck do processo gerado:", f));
