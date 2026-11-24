# Como trocar o conteúdo do site do Projeto Final

Esta pasta é a página `/projeto-final` da loja — o relatório técnico
navegável. Ela **complementa** o relatório entregue em documento; não o
substitui.

```
static/projeto_final/
├── conteudo.json   ← TODO o texto do relatório. É o único que você precisa trocar
├── app.js          só renderiza. Não contém texto nenhum
├── estilo.css      o visual
└── LEIAME.md       este arquivo
```

**Para publicar uma versão nova do relatório, troque apenas o
`conteudo.json` e faça o commit.** O deploy é automático a cada push na
`main`, e a página passa a servir o texto novo. Nada mais precisa ser
tocado — nem o `app.js`, nem o `estilo.css`, nem o `app.py`.

Antes do commit, vale um minuto de conferência:

```bash
python -c "import json; json.load(open('static/projeto_final/conteudo.json')); print('JSON válido')"
```

Depois, abra a página e role até o fim. Um bloco com problema aparece
como uma **tarja vermelha dizendo o que está errado**, no lugar onde ele
deveria estar — a página não quebra inteira e não fica em branco.

---

## O formato

```json
{
  "meta":   { ... },
  "secoes": [ { "id": "...", "titulo": "...", "numero": 1, "blocos": [ ... ] } ],
  "dados":  { ... }
}
```

Três chaves no topo. `meta` é a capa, `secoes` é o relatório e `dados`
alimenta os componentes interativos.

---

## `meta` — a capa

```json
{
  "meta": {
    "titulo": "Projeto Final — Torra & Terra",
    "subtitulo": "Relatório técnico navegável",
    "segmento": "Segmento 1 — Varejo",
    "contexto": "Carrinho, pedidos e pagamentos",
    "disciplina": "Tratamento e Armazenamento da Informação",
    "instituicao": "FACAMP",
    "professor": "Prof. Me. Nivaldo T. Marcusso",
    "grupo": ["Felipe Furlan", "Henrique Biruel", "Henrique Palorca"],
    "grupo_numero": "Grupo 3",
    "banco": "PostgreSQL 17",
    "data": "Dezembro de 2026",
    "aviso": "Esta página complementa o relatório técnico entregue em documento. Não o substitui.",
    "links": {
      "loja": "https://nivaldo.felipefurlan.com.br",
      "repositorio": "https://github.com/hick12/projeto-nivaldo",
      "relatorio_pdf": "",
      "health": "https://nivaldo.felipefurlan.com.br/health"
    }
  }
}
```

Todos os campos são opcionais: o que estiver vazio ou ausente
simplesmente não aparece. **Um link com valor `""` não é renderizado** —
é assim que o `relatorio_pdf` fica fora até o PDF existir. Para
publicá-lo, basta preencher a URL.

`titulo` também vira o `<title>` da aba do navegador.

---

## `secoes` — o relatório

Uma entrada por seção, na ordem em que devem aparecer. O índice lateral é
montado a partir desta lista.

```json
{
  "id": "banco",
  "numero": 7,
  "titulo": "Banco de dados",
  "blocos": [ ... ]
}
```

| Campo | Para que serve |
|---|---|
| `id` | Vira a âncora da URL (`/projeto-final#sec-banco`) e o alvo do índice. Use letras minúsculas sem acento, espaço nem barra |
| `numero` | O número mostrado no título e no índice. Só visual — a ordem quem define é a posição na lista |
| `titulo` | O título da seção |
| `blocos` | O conteúdo, na ordem |

**A primeira seção da lista é a capa.** Ela recebe tratamento visual
próprio: a ficha com grupo, professor e data, os links e o aviso saem de
`meta`, e os `blocos` dela aparecem logo abaixo. As demais seções são
renderizadas normalmente.

> As doze seções seguem o template do manual da disciplina: 1 Capa,
> 2 Resumo executivo, 3 Contexto e problema, 4 Requisitos, 5 Processo de
> negócio, 6 Arquitetura, 7 Banco de dados, 8 Implementação, 9 Testes e
> evidências, 10 Deploy e repositório, 11 Conclusão, 12 Bibliografia.
> Dá para acrescentar ou renomear seções — a página não depende de serem
> exatamente doze.

---

## Os seis tipos de bloco

### `texto`

```json
{ "tipo": "texto", "md": "Primeiro parágrafo.\n\nSegundo parágrafo, com **negrito** e `código`." }
```

Linha em branco dupla (`\n\n`) separa parágrafos. Uma linha que comece
com `### ` vira subtítulo.

**Formatação aceita**, e só ela:

| Escreva | Sai como |
|---|---|
| `**negrito**` | **negrito** |
| `*itálico*` | *itálico* |
| `` `código` `` | `código` |
| `[texto](https://exemplo.com)` | link, que abre em nova aba |
| `[texto](#sec-banco)` | link para outra seção desta página |
| `### Subtítulo` | subtítulo, quando é a primeira coisa do parágrafo |

Não há suporte a imagem, lista ou tabela dentro de `texto` — para isso
existem os tipos próprios abaixo. Tudo o mais é escrito como texto
literal: um `<select>` no meio de uma frase aparece como `<select>`
escrito, não como um campo de formulário.

Só `http`, `https` e âncora interna (`#`) são aceitos em link. Qualquer
outro esquema é mostrado como texto, sem virar link.

### `lista`

```json
{ "tipo": "lista", "itens": ["Primeiro item", "Segundo, com **negrito**"] }
```

Cada item aceita a mesma formatação do `texto`.

### `tabela`

```json
{
  "tipo": "tabela",
  "legenda": "Opcional, aparece acima da tabela",
  "colunas": ["Antes", "Depois"],
  "linhas": [
    ["Estoque conferido à mão", "Estoque travado na transação"],
    ["Total que não bate", "Conciliação sobre 100% dos pedidos"]
  ]
}
```

A **primeira célula de cada linha** vira cabeçalho daquela linha — é o
que permite a um leitor de tela dizer de que linha é cada valor. Então
coloque na primeira coluna o que identifica a linha.

Todas as células aceitam a formatação do `texto`. Tabela larga rola na
horizontal no celular, em vez de estourar a tela.

### `codigo`

```json
{
  "tipo": "codigo",
  "linguagem": "sql",
  "codigo": "SELECT COUNT(*) FROM pedidos;",
  "legenda": "Opcional. Aparece abaixo, em corpo menor"
}
```

O conteúdo de `codigo` é mostrado **exatamente como está**, sem nenhuma
interpretação. `linguagem` é só a etiqueta no canto — não há colorização
de sintaxe, de propósito: ela exigiria uma biblioteca de terceiro para
uma página de doze seções.

Em JSON, a quebra de linha se escreve `\n` e a barra invertida se escreve
`\\`.

### `figura`

```json
{
  "tipo": "figura",
  "src": "/static/evidencias/projeto_final/painel.png",
  "legenda": "O painel do gestor, com os sete indicadores",
  "comprova": "Que os indicadores vêm do banco, e não de valor fixo na página"
}
```

O campo `comprova` é o que o manual cobra de cada figura: **o que aquele
print prova**. A imagem sozinha não é evidência. Ele aparece em verde,
abaixo da legenda.

O `src` precisa ser um caminho que a aplicação sirva. As imagens
versionadas em `docs/evidencias/` **não** são servidas pela web — para
publicar um print, copie-o para dentro de `static/` e aponte para lá.

### `interativo`

```json
{ "tipo": "interativo", "componente": "er" }
```

Insere um dos seis componentes. O nome tem que ser exatamente um destes:

| `componente` | O que faz |
|---|---|
| `as_is_to_be` | Um botão alterna entre o fluxo atual (WhatsApp e planilha) e o proposto, mostrando as falhas de um lado e os pontos de validação do outro |
| `er` | O diagrama das cinco tabelas em SVG. Clicar numa tabela abre colunas, tipos, constraints e índices — é o dicionário de dados navegável |
| `checkout` | A simulação de duas compras disputando o último pacote: uma passa pelo `FOR UPDATE` e faz COMMIT, a outra espera e recebe ROLLBACK. Rotulada como **simulação ilustrativa**, com link para o teste que prova o comportamento |
| `explain` | O plano de execução antes e depois do índice, lado a lado, com os números reais de `SQL/consultas.sql` |
| `indicadores` | Lê `GET /api/resumo` ao vivo e mostra quando foi atualizado. Se a loja não responder, mostra o motivo e um botão para tentar de novo |
| `testes` | A tabela de casos de teste, com filtro por tipo |

O mesmo componente pode aparecer em mais de uma seção. O `as_is_to_be`,
por exemplo, está no contexto e no processo de negócio.

---

## `dados` — o que alimenta os componentes

Os textos dos componentes interativos moram em `dados`, uma chave por
componente:

```json
{
  "dados": {
    "as_is_to_be": { ... },
    "er": { ... },
    "checkout": { ... },
    "explain": { ... },
    "testes": { ... }
  }
}
```

O `indicadores` não aparece aqui: ele lê os números da API, não do
arquivo.

Se preferir, os dados podem ir **dentro do bloco**, o que é útil para ter
dois diagramas diferentes na mesma página:

```json
{ "tipo": "interativo", "componente": "er", "dados": { ... } }
```

O bloco tem prioridade sobre o `dados` global.

Um componente sem dados aparece como uma tarja dizendo exatamente qual
chave está faltando — não como uma área vazia.

A forma de cada um está no `conteudo.json` atual, que serve de modelo.
Em resumo:

| Componente | Chaves que ele lê |
|---|---|
| `as_is_to_be` | `legenda`, `as_is` e `to_be`, cada um com `titulo`, `resumo` e `passos[]`. Cada passo tem `ator`, `acao` e — conforme o lado — `problema` ou `validacao` |
| `er` | `legenda`, `tabelas[]` e `ligacoes[]`. Cada tabela tem `nome`, `x`, `y`, `w`, `h` (a posição no diagrama), `papel`, `nota`, `colunas[]` (`nome`, `tipo`, `regra`) e `indices[]` (`nome`, `porque`). Cada ligação tem `de`, `para` e `rotulo` |
| `checkout` | `aviso`, `explicacao`, `cafe`, `mensagem_real`, `nome_do_teste` e `passos[]`, com `ana`, `bruno`, `banco` e `nota` por passo |
| `explain` | `legenda`, `nota_volume`, `casos[]` (com `nome`, `consulta`, `antes`/`depois` — cada um com `titulo`, `plano`, `tempo` —, `ganho` e `licao`) e `preco` |
| `testes` | `legenda`, `nota` e `casos[]`, com `tipo`, `caso`, `entrada`, `esperado`, `obtido` e `evidencia`. Os filtros são gerados a partir dos valores de `tipo` que aparecerem |

No diagrama `er`, `x` e `y` são coordenadas do sistema do SVG, cuja
largura útil é 540. Mexer nelas reposiciona as caixas, e o `app.js`
desenha as linhas de ligação automaticamente, do centro de uma caixa ao
centro da outra.

O `h` é apenas um **mínimo**: a altura de cada caixa é calculada pelo
número de colunas, e a moldura do diagrama cresce junto. Acrescentar uma
coluna a uma tabela não exige ajustar pixel nenhum. A caixa mostra as
sete primeiras colunas e, havendo mais, um `+ N colunas` — a lista
completa aparece ao clicar.

---

## Três coisas que vale saber antes de mexer

**1. Esta é a única rota da loja que executa JavaScript.**
A política de conteúdo de `/projeto-final` é `script-src 'self'` — sem
`unsafe-inline` e sem `unsafe-eval`. Só um arquivo `.js` servido por este
domínio executa, e conteúdo colocado no HTML continua sem poder rodar. O
`connect-src 'self'` limita o `fetch` à própria aplicação. O resto da
loja — catálogo, carrinho, checkout, painel — continua com
`script-src 'none'`.

Consequência prática: **não adicione `<script>` nem `style="..."` ao
`conteudo.json`**. Os dois são bloqueados pelo navegador e apareceriam
como texto escrito na página.

**2. A página é lida em três lugares.**
Celular, projetor e papel. O `estilo.css` tem um `@media print` que
esconde a navegação, abre cada seção numa página nova e imprime os
endereços dos links — vale conferir no `Ctrl+P` antes de entregar.

**3. O aviso da capa não é decoração.**
O manual da disciplina proíbe apresentar mockup como tela implementada.
Daí duas coisas: o campo `aviso` de `meta`, que diz que esta página
complementa o relatório em documento, e o selo **simulação ilustrativa**
do componente `checkout`, que não deve ser removido — a animação
reproduz o comportamento, ela não executa o banco. Quem prova o
comportamento é o teste automatizado, e o componente diz o nome dele.
