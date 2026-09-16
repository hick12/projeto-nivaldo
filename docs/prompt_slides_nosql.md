# Prompt — Slides do projeto NoSQL (CouchDB)

Prompt para gerar a apresentação do segundo projeto seguindo o mesmo padrão da
apresentação do projeto PostgreSQL. Cole o bloco abaixo inteiro no outro chat.

---

```
## Contexto

Sou aluno de Engenharia de Computação da FACAMP, disciplina "Tratamento e
Armazenamento da Informação" (Prof. Nivaldo T. Marcusso). Preciso da
apresentação do projeto prático NoSQL: um e-commerce de café especial,
"Torra & Terra", feito em Python/Flask sobre Apache CouchDB.

Esse é o SEGUNDO projeto da disciplina. O primeiro foi o mesmo e-commerce sobre
PostgreSQL, e a apresentação dele já existe. Quero esta no mesmo padrão. O
objetivo declarado da atividade é comparar na prática o ciclo de uma aplicação
NoSQL com o projeto relacional — então a comparação com o PostgreSQL não é um
slide de enfeite, é o fio condutor.

Referência, se você tiver acesso ao repositório (C:\projetos\Nivaldo ou
github.com/hick12/projeto-nivaldo):
  - docs/gerar_deck_processo.js  → o gerador do deck PowerPoint
  - templates/apresentacao.html  → a versão web
  - static/apresentacao.css      → o CSS dos slides, incluindo o de impressão

## A regra mais importante: linguagem simples

Quem apresenta não é especialista em infraestrutura. Na versão anterior, a
primeira tentativa usou jargão ("servidor WSGI", "driver", "ORM", "deadlock",
"CSRF") e não serviu: não dá para apresentar o que não se consegue explicar.

Então:
  - Todo termo técnico vem acompanhado de UMA frase simples que dê para falar em
    voz alta. De preferência uma analogia.
  - Em vez de "o _bulk_docs não é ACID", diga o que acontece: "o pedido pode
    ficar gravado sem o estoque ter sido descontado".
  - Em vez de nomear o ataque, descreva a cena.
  - O jargão pode aparecer, mas nunca sozinho.

Analogias que já funcionaram no projeto anterior e devem ser mantidas:
  - gunicorn  → o PORTEIRO: escuta a internet e entrega cada acesso ao Python
  - Flask     → o CÉREBRO: decide o que responder; é onde moram as regras
  - Jinja     → o MOLDE da página: encaixa o dado no HTML

Analogias novas para o NoSQL (use estas ou melhores):
  - requests  → o CARTEIRO: leva cada pedido ao CouchDB por HTTP, como se o
                banco fosse um site
  - CouchDB   → o ARQUIVO DE FICHAS: cada produto, cliente e pedido é uma ficha
                JSON completa, guardada inteira
  - Mango     → a BUSCA no arquivo: "me traga as fichas de pedido deste cliente"
  - _rev      → o NÚMERO DA VERSÃO da ficha: se alguém mexeu antes de você, o
                banco recusa a sua alteração (é o erro 409)
  - Fauxton   → o PAINEL: onde se vê as fichas e as versões de cada uma
  - PostgreSQL, na comparação → o COFRE COM REGRAS: ele próprio recusa dado
    errado. O CouchDB guarda o que você mandar; as regras são da aplicação.

## Estrutura — cerca de 12 slides

 1. Capa
 2. Como trabalhamos — as etapas, uma revisão entre cada uma
 3. Por que NoSQL aqui — justificar pelo padrão de acesso (o material exige:
    "justifique NoSQL pelo padrão de acesso"; "liste consultas antes de modelar")
 4. Como o site funciona por dentro — o caminho de um clique:
    Navegador › gunicorn › Flask › requests › CouchDB, e uma tabela
    "o que é cada peça, em uma frase" com as analogias acima
 5. Ferramentas — agrupadas por etapa (modelagem e banco / desenvolvimento /
    qualidade e operação), cada uma com o "para quê"
 6. Modelagem documental — os três documentos (produto, cliente, pedido) e as
    três decisões: EMBUTIR (itens dentro do pedido: lidos e alterados juntos),
    REFERENCIAR (cliente_id: o cliente tem vida própria), FOTOGRAFAR (nome e
    preço copiados no item: preservam o histórico). Mostrar que a moagem
    continua no item do pedido — é o argumento central herdado do projeto
    relacional
 7. O que mudou em relação ao PostgreSQL — tabela lado a lado: estrutura,
    identidade (_id), relacionamento, consulta, índice, regras de negócio,
    concorrência, unidade de consistência
 8. O checkout — O CORAÇÃO DO TRABALHO. Explicar em linguagem simples que o
    CouchDB não tem "tudo ou nada" entre fichas diferentes: se o pedido grava e
    a baixa de estoque falha, sobra pedido sem baixa. Mostrar a estratégia que
    o projeto usou para resolver (reserva, nova tentativa, compensação)
 9. O teste de conflito — duas pessoas alterando a mesma ficha ao mesmo tempo,
    o 409, e como a aplicação reagiu
10. Problemas encontrados e como resolvemos
11. O projeto em números + o que ficou de fora, de propósito
12. Demonstração — slide escuro, roteiro de 5 passos numerados, sem imagem

## NÃO invente resultado

O projeto NoSQL ainda está sendo construído. Só entra no slide o que
realmente aconteceu. Para tudo que ainda não existe — número de testes,
problemas encontrados, resultado do teste de conflito, URL do deploy — use um
marcador visível no próprio slide: [PREENCHER: descrição do que falta].
Prefiro um slide com lacuna honesta a um slide com número inventado.

## O que já está decidido e pode entrar

  - Tema: o mesmo café especial, 12 cafés de 4 regiões produtoras
  - A moagem continua sendo escolhida na compra e mora no item do pedido
  - Critérios de avaliação do material: requisitos/justificativa 15%,
    modelagem documental 25%, CouchDB/índices 20%, aplicação Python 20%,
    testes/segurança 10%, documentação/deploy 10%
  - Achado sobre o projeto-base do professor: o checkout dele envia tudo num
    _bulk_docs e, se algum documento der conflito, apenas avisa o usuário —
    não desfaz o que já foi gravado. É exatamente o problema que o slide 8
    precisa mostrar resolvido.

## Regras de conteúdo

  - Slides com pouco texto: o texto é gancho para falar, não roteiro para ler.
  - O que dizer vai na NOTA DO APRESENTADOR de cada slide (slide.addNotes).
  - Sem capturas de tela do site — a loja é mostrada ao vivo no último slide.
  - Todo slide tem um elemento visual: cartões, números grandes, bolhas
    numeradas, fluxo com setas ou tabela. Nunca só título e marcadores.
  - Varie o layout entre slides.
  - Tudo em português, com acentuação correta.

## Identidade visual (a mesma do site)

Paleta — use exatamente estes valores:
  fundo              #FAF9F7   (off-white quente)
  cartões            #FFFFFF
  texto principal    #14120F   (quase-preto)
  texto secundário   #6B6560
  bordas             #E8E4DE   (sempre 1px)
  destaque           #D4622A   (laranja torra)
  destaque suave     #FBF0E9
  sucesso            #2F6B45   · fundo #EEF6F1
  erro               #A8321F   · fundo #FDF0ED

  - Capa e slide de demonstração com fundo #14120F; os demais claros.
  - Títulos em fonte serifada, corpo em sem serifa.
  - Cartões com borda de 1px e cantos arredondados. Sem sombra, sem gradiente.
  - Proibido: faixa colorida decorativa, linha de destaque embaixo de título,
    barra lateral, logotipo com órbita/elipse/esfera. A marca é só o nome
    "Torra & Terra" em serifada, com o "&" em #D4622A.

## Entregáveis

1) POWERPOINT (.pptx), gerado com pptxgenjs:
   - pres.layout = "LAYOUT_WIDE" (13,33 × 7,5 polegadas), antes de criar slides
   - Títulos em Cambria, corpo em Calibri, código em Consolas
   - Cor em hex SEM "#" (ex.: "D4622A")
   - isTextBox: true em todo addText; margin: 0 quando alinhar com forma
   - Nota do apresentador em todos os slides
   - Depois de gerar: o pptxgenjs grava o ZIP sem compressão. Recompacte com
     deflate — no projeto anterior o arquivo caiu de 302 KB para 54 KB
   - Verifique se algum texto estoura a caixa antes de entregar

2) VERSÃO WEB, uma página servida pelo próprio Flask em /apresentacao:
   - HTML e CSS puros, SEM JAVASCRIPT. O site usa a política de segurança
     script-src 'none', que bloqueia qualquer script
   - Navegação pelo próprio scroll: scroll-snap-type: y mandatory, um slide por
     tela
   - Reaproveitar as variáveis de cor do CSS do site
   - Botões para baixar o .pptx e o .pdf

3) PDF, gerado imprimindo a versão web:
   - CSS de impressão com @page { size: 338mm 190mm; margin: 0 }
   - Cada slide com height: 190mm e quebra de página depois
   - ATENÇÃO: fontes definidas com clamp() e unidades de viewport saem
     erradas na impressão. No bloco @media print, fixe os tamanhos em pt —
     no projeto anterior o conteúdo vazava entre as páginas até isso ser feito
   - Gerar com Chrome headless:
       chrome --headless --no-pdf-header-footer --print-to-pdf=saida.pdf URL
   - Conferir que cada página do PDF é exatamente um slide

## Como trabalhar

1. Antes de gerar qualquer arquivo, me mostre o roteiro: o título de cada
   slide, o que vai nele e a analogia de cada termo técnico. Espere meu OK.
2. Aponte o que do roteiro depende de algo que ainda não foi feito no
   projeto — isso vira [PREENCHER].
3. Depois do OK, gere os três formatos.
```

---

## Por que o prompt é assim

Cada exigência vem de algo que aconteceu na apresentação do projeto
PostgreSQL:

| No prompt | O que aconteceu antes |
|---|---|
| Linguagem simples com analogia | A primeira versão tinha "servidor WSGI" e "psycopg" sem explicação. Não dava para apresentar |
| Não inventar resultado | O projeto NoSQL não existe ainda — um deck com "24 testes passando" seria falso |
| Sem capturas de tela | A loja é mostrada ao vivo; a captura só duplicaria |
| Sem JavaScript na web | O site bloqueia script por segurança; a página de slides precisa respeitar |
| Recompactar o .pptx | O arquivo ia 6× maior do que precisava |
| Fontes fixas no print | O PDF vazava conteúdo de um slide para o outro |
| Roteiro antes de gerar | Evita refazer 12 slides por um desencontro de expectativa |
