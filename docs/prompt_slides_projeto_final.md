# Prompt para gerar os slides do Projeto Final

Cole o texto abaixo da linha no chat que tem o Claude Slides. Ele é
autossuficiente: não depende de nada que esteja só neste repositório.

---

Você vai montar os **slides da apresentação do Projeto Final** da
disciplina Tratamento e Armazenamento da Informação (FACAMP, Prof. Me.
Nivaldo T. Marcusso). Grupo 3: Felipe Furlan, Henrique Biruel e Henrique
Palorca. Apresentação em **02/12**, **15 minutos**, **até 10 slides**.

Tudo se chama **Projeto Final**. Nada de "Atividade N".

## Antes de escrever qualquer slide

Abra estes endereços e use o que vir — não escreva de memória:

- **A loja:** https://nivaldo.felipefurlan.com.br
- **O relatório navegável:** https://nivaldo.felipefurlan.com.br/projeto-final
  (é a fonte mais completa: 12 seções, com os números e as decisões)
- **Os indicadores ao vivo:** https://nivaldo.felipefurlan.com.br/api/resumo
- **O health check:** https://nivaldo.felipefurlan.com.br/health
- **O repositório:** https://github.com/hick12/projeto-nivaldo

**Os números mudam.** Faturamento, contagem de pedidos e participação por
região vêm do banco de produção e mudam a cada venda de demonstração.
Leia `/api/resumo` no momento de montar o deck e use o que ele devolver.
O único número que **não** pode mudar é a conciliação: ela precisa dar
"X de X", sem divergência. Se vier divergente, me avise antes de montar
slide nenhum — isso seria um defeito, não um detalhe.

## Capturas de tela

Tire as suas, do site no ar — print atual vale mais que print guardado.
Se não conseguir navegar, use os que estão no repositório, em
`docs/evidencias/projeto_final/`, acessíveis pelo raw do GitHub:

`https://raw.githubusercontent.com/hick12/projeto-nivaldo/main/docs/evidencias/projeto_final/<arquivo>`

As capturas que valem a pena, e o que cada uma prova:

| Arquivo | Prova |
|---|---|
| `01_catalogo.png` | O catálogo vem do banco, com preço, região, torra e pontuação SCA |
| `02_produto.png` | A escolha de **moagem** acontece na compra, não no cadastro do café |
| `06_checkout_recusado_estoque.png` | A mensagem nomeando o café que faltou e o saldo real — e nada foi gravado |
| `09_painel.png` | Os quatro cartões, com a **conciliação fechando em verde** |
| `11_status_antes.png` / `12b_status_depois_na_lista.png` | O par antes/depois da mudança de status |
| `08_403_cliente_comum.png` | Cliente comum recebe 403 no painel |
| `17_componente_er.png` | O diagrama do modelo de dados, clicável |
| `18_componente_checkout.png` | A simulação das duas compras simultâneas |
| `19_componente_explain.png` | O plano de execução antes e depois do índice |

**Regra do manual, e ela é eliminatória:** nunca apresente mockup como
tela implementada. Toda imagem no deck tem que ser de tela que existe. A
simulação do componente `checkout` é ilustrativa e precisa ser rotulada
como tal se entrar.

## O que o projeto é, em uma frase

Uma loja de cafés especiais onde **a integridade da venda é garantida
pelo banco de dados, e isso é verificável** — o painel mostra que 100%
dos pedidos têm o total igual à soma dos itens.

## O problema, para o slide de abertura

Uma torrefação vende hoje por WhatsApp e planilha. Duas falhas se
repetem:

1. **O mesmo lote vendido duas vezes**, porque duas vendas aconteceram em
   paralelo e ninguém baixou o saldo a tempo.
2. **O pedido registrado pela metade** — o cabeçalho existe, os itens
   não, ou o total não bate com os itens.

Segmento 1 — Varejo. Contexto: carrinho, pedidos e pagamentos. Dor:
falhas de confirmação e de conciliação.

## Como a nota é distribuída na apresentação

Use isto para decidir quanto tempo cada slide ganha:

| Critério | Peso |
|---|---|
| Demonstração funcional do MVP | **12%** |
| Arquitetura e justificativa do banco | **10%** |
| Problema e proposta de valor | 6% |
| Comunicação e qualidade visual | 6% |
| Domínio técnico e respostas | 6% |

Ou seja: **a demo e a justificativa do banco valem mais que o resto
somado.** O deck existe para sustentar a demo, não para substituí-la.
Reserve pelo menos 4 dos 15 minutos para a demonstração ao vivo.

## Os três argumentos técnicos que precisam aparecer

**1. O checkout é uma transação, e dá para ver.**

```
BEGIN
 ├─ SELECT ... FOR UPDATE   trava o estoque de cada café,
 │                          sempre em ordem crescente de id
 ├─ valida existência e saldo de TODOS os itens
 ├─ INSERT do pedido · INSERT dos itens · UPDATE do estoque
 └─ COMMIT   ·   ROLLBACK em qualquer falha
```

Nada é inserido antes de todos os itens estarem travados e validados.
Travar sempre na mesma ordem elimina deadlock entre duas compras que
disputam os mesmos cafés.

**2. A moagem mora no item, não no produto.**

O cliente escolhe a moagem na hora da compra. Se fosse coluna de
`produtos`, o mesmo café viraria três cadastros e o controle de estoque
— que é do café, não da moagem — quebraria. É esse atributo que faz
`itens_pedido` ser uma entidade de verdade, e não tabela de ligação. E é
o que torna possível a pergunta *"em que moagem este café é mais
pedido?"*, que é um dos indicadores do painel.

**3. O índice novo se paga, e foi medido.**

Com 60 mil pedidos, o filtro de período do painel: **6,713 ms → 0,900
ms**. A lista de pedidos recentes: **10,401 ms → 0,031 ms**, e o passo
de `Sort` desaparece do plano — é por isso que o índice é
`criado_em DESC` e não apenas `criado_em`.

Vale contar o contrário também: com os poucos pedidos da base de
demonstração o planejador escolhe `Seq Scan`, e **está certo**, porque a
tabela inteira cabe numa página de disco. Admitir isso vale mais que
escondê-lo — mostra que o grupo entende o planejador, não só o comando.

## Roteiro da demonstração ao vivo — 4 minutos

Ensaiem isto até sair sem travar:

1. **Catálogo** — filtra por região. Os dados vêm do banco.
2. **Produto** — escolhe a moagem. *"Repare: a moagem é escolhida aqui,
   na compra."*
3. **Checkout que dá certo** — pedido confirmado.
4. **Checkout que falha** — tenta levar 2 unidades do Chapada Geisha, que
   tem estoque 1. A loja recusa, **nomeia o café** e diz o saldo real.
   *"E agora o importante: nada foi gravado."*
5. **Meus pedidos** — o preço do item é o da época, não o de hoje.
6. **Painel, como gestor** — os indicadores, e a conciliação fechando.
7. **Mudar o status de um pedido** — mostra o antes e o depois. Cancelar
   devolve o estoque na mesma transação.
8. **403** — sair, entrar como cliente comum, tentar abrir o painel.

Deixem o **Chapada Geisha com estoque 1** antes de começar: é ele que faz
o passo 4 funcionar.

## Credenciais, para o slide final e para a demo

- **Cliente de demonstração:** `ana.braganca@exemplo.com` ·
  senha `demo-torra-e-terra-2026`
- **Gestor de demonstração:** `gestor.demo@exemplo.com` · a senha o grupo
  informa na hora

São contas fictícias, em `@exemplo.com` — domínio que a RFC 2606 reserva
para documentação. Nenhum dado de pessoa real está no banco.

## Perguntas prováveis, com a resposta curta

Prepare um slide de apoio (fora da conta dos 10, para usar só se
perguntarem) com estas:

- **"E se duas pessoas comprarem o último pacote ao mesmo tempo?"** A
  segunda não lê estoque errado — ela **espera** o lock. Quando lê, já vê
  o saldo atualizado, e o pedido dela é recusado com rollback completo.
- **"Por que não NoSQL?"** O checkout precisa de transação entre
  documentos diferentes, e banco de documento dá atomicidade por
  documento. O grupo construiu a mesma loja em CouchDB para comparar: lá
  o pedido vira um documento único e a concorrência passa a depender do
  `_rev` com nova tentativa. A escolha do banco é a escolha de **onde a
  integridade vai morar**: no SGBD ou na aplicação.
- **"Por que o preço fica gravado no item?"** Porque o preço do café
  muda. Se o item lesse `produtos.preco`, o pedido do mês passado se
  reescreveria sozinho — que é exatamente a falha de conciliação que o
  contexto pede para resolver.
- **"Por que o carrinho não está no banco?"** Carrinho é processo, não
  entidade: existe só enquanto a compra não fecha e não tem valor
  histórico. Vira entidade no instante do checkout.
- **"O que ficou de fora?"** Pagamento real, frete, lote e data de torra,
  cadastro de produto pela interface. A lista completa, com o motivo de
  cada um, está na seção 11 do relatório navegável.

## Linguagem visual

Editorial e quente, a mesma da loja: fundo creme `#f7f4ef`, texto
`#1a1814`, destaque terracota `#c8502a`, verde `#2d5a3d` só para sucesso.
Títulos em DM Serif Display, corpo em Outfit.

Muito espaço em branco. Hierarquia por peso de fonte, não por caixa
colorida. Nada de gradiente, nada de sombra pesada, nada de ícone
genérico de banco de dados.

**Legibilidade no projetor é requisito, não estética:** corpo de texto
grande, no máximo seis linhas por slide, e todo print com legenda
dizendo o que ele comprova.

A marca é só o nome **Torra & Terra**, com o "&" em terracota. **Não
invente logo com órbita, elipse ou esfera** — essa é a identidade de
outro projeto e não entra aqui.

## Duas regras de texto

- **Não use quantidade de testes nem linhas de código como métrica.**
  Descreva o que o teste prova, não quantos existem.
- Fale do efeito para quem usa a loja, não do esforço de quem a
  construiu.

## Entregáveis

1. O deck, até 10 slides, editável.
2. Um slide de apoio com as perguntas prováveis, fora da contagem.
3. O roteiro de 15 minutos, com o tempo de cada bloco e quem fala o quê —
   são três apresentadores, e o manual avalia se todos dominam a solução.
4. Exportáveis em PDF e PowerPoint.

E um **plano B**: um roteiro de vídeo curto da demo, para gravar antes,
caso a internet da sala falhe no dia.
