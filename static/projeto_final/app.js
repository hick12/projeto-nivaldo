/* =====================================================================
   Projeto Final — Torra & Terra
   Relatório técnico navegável

   FACAMP · Tratamento e Armazenamento da Informação

   ---------------------------------------------------------------------
   O QUE ESTE ARQUIVO FAZ, E O QUE NÃO FAZ

   Ele só RENDERIZA. Nenhum texto do relatório está escrito aqui: tudo
   vem de conteudo.json. Trocar o conteúdo é trocar aquele arquivo, sem
   abrir este. O formato está documentado em LEIAME.md.

   JavaScript puro, sem framework e sem dependência nenhuma. Duas razões:
   a política de segurança desta rota é `script-src 'self'` — sem
   'unsafe-inline' e sem 'unsafe-eval', então não há script escrito no
   HTML nem `eval` em lugar nenhum — e um relatório acadêmico que
   dependesse de CDN de terceiro envelheceria antes da defesa.

   Nota sobre estilo: a política também traz `style-src 'self'` sem
   'unsafe-inline', o que bloqueia `style="..."` escrito no HTML. Estilo
   definido por script (`elemento.style.setProperty`) NÃO é bloqueado —
   a CSP não se aplica ao CSSOM — e é assim que as barras dos gráficos
   recebem largura aqui. No painel do gestor, que não executa script, a
   mesma barra é um SVG gerado pelo servidor.
   ===================================================================== */

'use strict';

(function () {
  /* -------------------------------------------------------------------
     Utilidades
     ------------------------------------------------------------------- */

  /** Cria um elemento com classe e texto, de uma vez. */
  function elemento(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) { el.className = classe; }
    if (texto !== undefined && texto !== null) { el.textContent = String(texto); }
    return el;
  }

  /**
   * Escapa HTML. Roda ANTES de qualquer formatação de markdown.
   *
   * O conteudo.json é nosso, mas ele é feito para ser substituído por
   * quem escreve o relatório — e texto de relatório tem `<`, `>` e `&`
   * dentro de trecho técnico. Sem escapar, um `<select>` no meio de uma
   * frase viraria um campo de formulário na página.
   */
  function escapar(texto) {
    return String(texto === undefined || texto === null ? '' : texto)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * Mini-markdown. Suporta o que o texto de um relatório realmente usa:
   * negrito, itálico, código, link e cabeçalho de nível 3.
   *
   * Deliberadamente pequeno. Uma biblioteca de markdown resolveria mais
   * casos e traria uma dependência de terceiro para uma página que tem
   * doze seções de texto — a conta não fecha.
   *
   * A ordem importa: `código` é extraído primeiro e devolvido ao final,
   * para que **asteriscos** dentro de um trecho de código não virem
   * negrito.
   */
  function markdown(texto) {
    var guardados = [];

    var html = escapar(texto)
      // `código` sai de cena primeiro, guardado por um marcador.
      .replace(/`([^`]+)`/g, function (_, dentro) {
        guardados.push(dentro);
        return '\u0000' + (guardados.length - 1) + '\u0000';
      })
      // [texto](url) — só http, https e âncora interna. Um `javascript:`
      // aqui seria execução de script vinda do conteúdo.
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|#[^)\s]*)\)/g,
        function (_, rotulo, url) {
          var externo = url.indexOf('#') !== 0;
          return '<a href="' + url + '"' +
            (externo ? ' rel="noopener" target="_blank"' : '') +
            '>' + rotulo + '</a>';
        })
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');

    // Devolve o código guardado, agora como <code>.
    html = html.replace(/\u0000(\d+)\u0000/g, function (_, indice) {
      return '<code>' + escapar(guardados[Number(indice)]) + '</code>';
    });

    return html;
  }

  /** Transforma um bloco de markdown em parágrafos e subtítulos. */
  function paragrafos(texto) {
    var caixa = document.createDocumentFragment();

    String(texto || '').split(/\n{2,}/).forEach(function (pedaco) {
      var limpo = pedaco.trim();
      if (!limpo) { return; }

      if (limpo.indexOf('### ') === 0) {
        var titulo = elemento('h3', 'sub');
        titulo.innerHTML = markdown(limpo.slice(4));
        caixa.appendChild(titulo);
        return;
      }

      var p = elemento('p');
      p.innerHTML = markdown(limpo).replace(/\n/g, '<br>');
      caixa.appendChild(p);
    });

    return caixa;
  }

  /** Um aviso visível na página, para falha de dado em vez de tela branca. */
  function aviso(mensagem) {
    var caixa = elemento('p', 'aviso-dado');
    caixa.textContent = mensagem;
    return caixa;
  }

  /* -------------------------------------------------------------------
     Movimento

     Regra que vale para tudo aqui: quem pediu menos animação no sistema
     operacional não recebe nenhuma. `prefers-reduced-motion` não é
     preferência estética — para parte das pessoas, movimento na tela
     causa enjoo de verdade. A página precisa continuar INTEIRA sem as
     animações: os números aparecem no valor final, as seções aparecem
     visíveis, o brilho do cursor não existe.
     ------------------------------------------------------------------- */

  var MOVIMENTO_OK = !(
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  /** Lê um tempo em milissegundos de um texto tipo "6,713 ms". */
  function msDoTexto(texto) {
    var achado = String(texto || '').replace(',', '.').match(/[\d.]+/);
    return achado ? parseFloat(achado[0]) : null;
  }

  /**
   * Conta de zero até o valor, com desaceleração.
   *
   * O número do indicador é o que o olho procura primeiro. Vê-lo subir
   * diz, sem texto nenhum, que aquilo foi LIDO agora — e não escrito na
   * página.
   */
  function animarNumero(elemento, valor, sufixo) {
    sufixo = sufixo || '';
    var alvo = Number(valor) || 0;

    if (!MOVIMENTO_OK || alvo === 0) {
      elemento.textContent = alvo + sufixo;
      return;
    }

    var duracao = 900;
    var comeco = null;

    function passo(agora) {
      if (comeco === null) { comeco = agora; }
      var fracao = Math.min(1, (agora - comeco) / duracao);
      // easeOutCubic: rápido no início, freia no fim.
      var suave = 1 - Math.pow(1 - fracao, 3);
      elemento.textContent = Math.round(alvo * suave) + sufixo;
      if (fracao < 1) { requestAnimationFrame(passo); }
    }

    requestAnimationFrame(passo);
  }

  /**
   * Zera a largura e deixa a transição do CSS levá-la de volta ao valor.
   *
   * Os dois requestAnimationFrame não são superstição: sem eles o
   * navegador junta as duas escritas no mesmo quadro, conclui que a
   * largura não mudou e não dispara transição nenhuma. O primeiro quadro
   * compromete o zero; o segundo começa o caminho de volta.
   */
  function animarLargura(elemento, porcento) {
    elemento.style.setProperty('width', '0%');
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        elemento.style.setProperty('width', porcento + '%');
      });
    });
  }

  /**
   * Faz algo acontecer quando o elemento entra na tela, uma vez só.
   *
   * IntersectionObserver em vez de ouvir o scroll: o navegador avisa
   * quando cruza o limiar, sem a página recalcular posição a cada pixel.
   * No projetor e no celular a diferença se sente.
   */
  /**
   * Margem que dispara ANTES de o elemento aparecer — 240px abaixo da
   * dobra. Usada por tudo que precisa se reiniciar em zero para animar:
   * o reinício acontece fora da vista, e quando o elemento chega o
   * movimento já está em curso. Sem isso, dá para ver o número final
   * piscar e saltar para zero.
   */
  var PRESTES_A_ENTRAR = '0px 0px 240px 0px';

  function aoEntrarNaTela(elemento, acao, margem) {
    if (!('IntersectionObserver' in window)) { acao(); return; }

    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (!entrada.isIntersecting) { return; }
        observador.unobserve(entrada.target);
        acao(entrada.target);
      });
    }, { rootMargin: margem || '0px 0px -12% 0px', threshold: 0.15 });

    observador.observe(elemento);
  }

  /**
   * Um brilho quente que segue o cursor.
   *
   * É enfeite, e está declarado como tal. Fica atrás de todo o conteúdo,
   * não intercepta clique nenhum (`pointer-events: none`) e some no
   * celular, onde não há cursor para seguir. A posição vai por variável
   * CSS definida por script — a CSP bloqueia `style=` escrito no HTML,
   * mas não o objeto `style` de um elemento.
   */
  function ligarBrilhoDoCursor() {
    if (!MOVIMENTO_OK) { return; }
    if (!window.matchMedia('(pointer: fine)').matches) { return; }

    var brilho = elemento('div', 'brilho-cursor');
    brilho.setAttribute('aria-hidden', 'true');
    document.body.appendChild(brilho);

    var alvoX = window.innerWidth / 2;
    var alvoY = window.innerHeight / 3;
    var x = alvoX;
    var y = alvoY;
    var rodando = false;

    document.addEventListener('pointermove', function (evento) {
      alvoX = evento.clientX;
      alvoY = evento.clientY;
      if (!rodando) { rodando = true; requestAnimationFrame(seguir); }
    }, { passive: true });

    function seguir() {
      // Interpolação: o brilho ARRASTA atrás do cursor em vez de colar
      // nele. Colado parece defeito de renderização; atrasado parece luz.
      x += (alvoX - x) * 0.12;
      y += (alvoY - y) * 0.12;

      brilho.style.setProperty('--x', x.toFixed(1) + 'px');
      brilho.style.setProperty('--y', y.toFixed(1) + 'px');

      if (Math.abs(alvoX - x) > 0.5 || Math.abs(alvoY - y) > 0.5) {
        requestAnimationFrame(seguir);
      } else {
        rodando = false;
      }
    }
  }

  /** Barra fina no topo, com a fração já lida do relatório. */
  function ligarBarraDeProgresso() {
    var barra = elemento('div', 'progresso-leitura');
    barra.setAttribute('aria-hidden', 'true');
    var cheia = elemento('div', 'progresso-cheia');
    barra.appendChild(cheia);
    document.body.appendChild(barra);

    var agendado = false;

    function medir() {
      agendado = false;
      var altura = document.documentElement.scrollHeight - window.innerHeight;
      var fracao = altura > 0 ? window.scrollY / altura : 0;
      cheia.style.setProperty(
        'transform', 'scaleX(' + Math.max(0, Math.min(1, fracao)).toFixed(4) + ')'
      );
    }

    window.addEventListener('scroll', function () {
      // Uma medição por quadro, no máximo. Sem isto, o evento de scroll
      // dispara dezenas de vezes por segundo e cada uma força layout.
      if (!agendado) { agendado = true; requestAnimationFrame(medir); }
    }, { passive: true });

    window.addEventListener('resize', medir, { passive: true });
    medir();
  }

  /** Blocos sobem e aparecem conforme entram na tela. */
  function ligarRevelacao() {
    var alvos = document.querySelectorAll(
      '.secao > .bloco-texto, .secao > .bloco-lista, .secao > .bloco-tabela,' +
      '.secao > .bloco-codigo, .secao > .bloco-figura, .secao > .interativo,' +
      '.capa-corpo > *'
    );

    alvos.forEach(function (alvo) {
      if (!MOVIMENTO_OK) { alvo.classList.add('revelado'); return; }
      alvo.classList.add('a-revelar');
      aoEntrarNaTela(alvo, function (el) { el.classList.add('revelado'); });
    });
  }

  /**
   * Navegação por teclado entre as seções.
   *
   * Quem apresenta no projetor não quer rolar com o mouse. As setas e o
   * j/k do Vim pulam de seção em seção.
   */
  function ligarTeclado() {
    document.addEventListener('keydown', function (evento) {
      if (evento.ctrlKey || evento.metaKey || evento.altKey) { return; }

      // Nunca sequestrar digitação num campo.
      var foco = document.activeElement;
      if (foco && /^(INPUT|TEXTAREA|SELECT)$/.test(foco.tagName)) { return; }

      var adiante = ['ArrowRight', 'ArrowDown', 'j', 'J'];
      var atras = ['ArrowLeft', 'ArrowUp', 'k', 'K'];
      var direcao = adiante.indexOf(evento.key) >= 0 ? 1
        : (atras.indexOf(evento.key) >= 0 ? -1 : 0);
      if (!direcao) { return; }

      // Deixa a seta rolar normalmente dentro de algo que rola sozinho.
      if (foco && foco.closest && foco.closest('.bloco-tabela, pre')) { return; }

      var secoes = [].slice.call(document.querySelectorAll('.capa, .secao'));
      var topoAtual = window.scrollY + 90;
      var indice = 0;
      secoes.forEach(function (s, i) {
        if (s.offsetTop <= topoAtual) { indice = i; }
      });

      var destino = secoes[Math.max(0, Math.min(secoes.length - 1, indice + direcao))];
      if (!destino) { return; }

      evento.preventDefault();
      destino.scrollIntoView({
        behavior: MOVIMENTO_OK ? 'smooth' : 'auto',
        block: 'start',
      });
    });
  }

  /* -------------------------------------------------------------------
     Blocos de conteúdo
     ------------------------------------------------------------------- */

  var BLOCOS = {

    texto: function (bloco) {
      var caixa = elemento('div', 'bloco-texto');
      caixa.appendChild(paragrafos(bloco.md));
      return caixa;
    },

    lista: function (bloco) {
      var ul = elemento('ul', 'bloco-lista');
      (bloco.itens || []).forEach(function (item) {
        var li = elemento('li');
        li.innerHTML = markdown(item);
        ul.appendChild(li);
      });
      return ul;
    },

    tabela: function (bloco) {
      var rolagem = elemento('div', 'bloco-tabela');
      var tabela = elemento('table');

      if (bloco.legenda) {
        var legenda = elemento('caption', null, bloco.legenda);
        tabela.appendChild(legenda);
      }

      var cabeca = elemento('thead');
      var linhaCabeca = elemento('tr');
      (bloco.colunas || []).forEach(function (coluna) {
        var th = elemento('th');
        th.setAttribute('scope', 'col');
        th.innerHTML = markdown(coluna);
        linhaCabeca.appendChild(th);
      });
      cabeca.appendChild(linhaCabeca);
      tabela.appendChild(cabeca);

      var corpo = elemento('tbody');
      (bloco.linhas || []).forEach(function (linha) {
        var tr = elemento('tr');
        linha.forEach(function (celula, indice) {
          // A primeira célula é o cabeçalho da linha: ajuda leitor de
          // tela a dizer de que linha é cada valor.
          var cel = elemento(indice === 0 ? 'th' : 'td');
          if (indice === 0) { cel.setAttribute('scope', 'row'); }
          cel.innerHTML = markdown(celula);
          tr.appendChild(cel);
        });
        corpo.appendChild(tr);
      });
      tabela.appendChild(corpo);

      rolagem.appendChild(tabela);
      return rolagem;
    },

    codigo: function (bloco) {
      var figura = elemento('figure', 'bloco-codigo');

      var pre = elemento('pre');
      var codigo = elemento('code', 'ling-' + (bloco.linguagem || 'text'));
      // textContent, não innerHTML: é código, e não deve ser
      // interpretado como marcação em nenhuma circunstância.
      codigo.textContent = bloco.codigo || '';
      pre.appendChild(codigo);
      figura.appendChild(pre);

      if (bloco.linguagem) {
        var etiqueta = elemento('span', 'etiqueta-ling', bloco.linguagem);
        figura.insertBefore(etiqueta, pre);
      }

      if (bloco.legenda) {
        var legenda = elemento('figcaption');
        legenda.innerHTML = markdown(bloco.legenda);
        figura.appendChild(legenda);
      }

      return figura;
    },

    figura: function (bloco) {
      var figura = elemento('figure', 'bloco-figura');

      var img = elemento('img');
      img.src = bloco.src || '';
      img.alt = bloco.legenda || '';
      img.loading = 'lazy';
      figura.appendChild(img);

      if (bloco.legenda || bloco.comprova) {
        var legenda = elemento('figcaption');
        if (bloco.legenda) {
          legenda.innerHTML = markdown(bloco.legenda);
        }
        if (bloco.comprova) {
          // "O que este print comprova" é o que o manual da disciplina
          // cobra de cada figura — a imagem sozinha não é evidência.
          var comprova = elemento('span', 'comprova');
          comprova.innerHTML = '<strong>Comprova:</strong> ' +
            markdown(bloco.comprova);
          legenda.appendChild(comprova);
        }
        figura.appendChild(legenda);
      }

      return figura;
    },

    interativo: function (bloco, dados) {
      var nome = bloco.componente;
      var montar = COMPONENTES[nome];

      if (!montar) {
        return aviso('Componente interativo desconhecido: "' + nome + '".');
      }

      var caixa = elemento('section', 'interativo');
      caixa.setAttribute('aria-label', 'Componente interativo: ' + nome);

      // Os dados vêm do bloco, se ele os trouxer, ou do `dados` global
      // do conteudo.json. Os dois caminhos existem para o LEIAME poder
      // prometer que nada aqui é obrigatório.
      var proprios = bloco.dados || (dados && dados[nome]) || null;

      if (!proprios && nome !== 'indicadores') {
        return aviso(
          'O componente "' + nome + '" não encontrou dados. ' +
          'Defina "dados.' + nome + '" no conteudo.json.'
        );
      }

      montar(caixa, proprios);
      return caixa;
    }
  };

  /* -------------------------------------------------------------------
     1. as_is_to_be — o fluxo atual e o proposto
     ------------------------------------------------------------------- */

  function montarAsIsToBe(caixa, dados) {
    var estado = 'as_is';

    var topo = elemento('div', 'interativo-topo');
    topo.appendChild(elemento('h3', 'interativo-titulo', 'Fluxo do processo'));

    var botao = elemento('button', 'botao-alternar');
    botao.type = 'button';
    topo.appendChild(botao);
    caixa.appendChild(topo);

    if (dados.legenda) {
      caixa.appendChild(elemento('p', 'interativo-nota', dados.legenda));
    }

    var painel = elemento('div', 'fluxo');
    caixa.appendChild(painel);

    function desenhar() {
      var lado = dados[estado] || {};
      painel.textContent = '';
      painel.className = 'fluxo fluxo-' + (estado === 'as_is' ? 'atual' : 'novo');

      botao.textContent = estado === 'as_is'
        ? 'Ver o fluxo proposto (TO BE) →'
        : '← Ver o fluxo atual (AS IS)';
      botao.setAttribute('aria-pressed', estado === 'to_be' ? 'true' : 'false');

      painel.appendChild(elemento('h4', 'fluxo-titulo', lado.titulo || ''));
      if (lado.resumo) {
        painel.appendChild(elemento('p', 'fluxo-resumo', lado.resumo));
      }

      var ol = elemento('ol', 'fluxo-passos');
      (lado.passos || []).forEach(function (passo) {
        var li = elemento('li', 'passo');

        li.appendChild(elemento('span', 'passo-ator', passo.ator));

        var acao = elemento('p', 'passo-acao');
        acao.innerHTML = markdown(passo.acao);
        li.appendChild(acao);

        if (passo.problema) {
          var ruim = elemento('p', 'passo-problema');
          ruim.innerHTML = '<strong>Falha:</strong> ' + markdown(passo.problema);
          li.appendChild(ruim);
        }
        if (passo.validacao) {
          var bom = elemento('p', 'passo-validacao');
          bom.innerHTML = '<strong>Validação:</strong> ' +
            markdown(passo.validacao);
          li.appendChild(bom);
        }

        ol.appendChild(li);
      });
      painel.appendChild(ol);
    }

    botao.addEventListener('click', function () {
      estado = (estado === 'as_is') ? 'to_be' : 'as_is';
      desenhar();
    });

    desenhar();
  }

  /* -------------------------------------------------------------------
     2. er — o diagrama das cinco tabelas, clicável
     ------------------------------------------------------------------- */

  function montarEr(caixa, dados) {
    var tabelas = dados.tabelas || [];

    caixa.appendChild(elemento('h3', 'interativo-titulo',
      'Modelo de dados — clique numa tabela'));

    if (dados.legenda) {
      caixa.appendChild(elemento('p', 'interativo-nota', dados.legenda));
    }

    // Botões além do SVG: é o caminho de teclado e de leitor de tela.
    // Diagrama clicável sem alternativa textual exclui quem navega por
    // Tab, e a disciplina cobra acessibilidade como requisito.
    var atalhos = elemento('div', 'er-atalhos');
    atalhos.setAttribute('role', 'tablist');
    atalhos.setAttribute('aria-label', 'Tabelas do modelo');
    caixa.appendChild(atalhos);

    var moldura = elemento('div', 'er-moldura');
    moldura.innerHTML = desenharSvgEr(dados);
    caixa.appendChild(moldura);

    var detalhe = elemento('div', 'er-detalhe');
    detalhe.setAttribute('aria-live', 'polite');
    caixa.appendChild(detalhe);

    function selecionar(nome) {
      var tabela = tabelas.filter(function (t) { return t.nome === nome; })[0];
      if (!tabela) { return; }

      atalhos.querySelectorAll('button').forEach(function (b) {
        var ativo = b.dataset.tabela === nome;
        b.classList.toggle('ativo', ativo);
        b.setAttribute('aria-selected', ativo ? 'true' : 'false');
      });

      // A tabela escolhida acende; as que NÃO se relacionam com ela
      // apagam. É o que transforma o diagrama em explicação: dá para ver
      // de relance com quem cada tabela conversa.
      var ligacoes = dados.ligacoes || [];
      var vizinhas = {};
      vizinhas[nome] = true;
      ligacoes.forEach(function (l) {
        if (l.de === nome) { vizinhas[l.para] = true; }
        if (l.para === nome) { vizinhas[l.de] = true; }
      });

      moldura.querySelectorAll('.er-caixa').forEach(function (g) {
        var esta = g.dataset.tabela;
        g.classList.toggle('ativa', esta === nome);
        g.classList.toggle('apagada', !vizinhas[esta]);
      });

      moldura.querySelectorAll('.er-linha, .er-cardinalidade')
        .forEach(function (el) {
          var tocada = el.dataset.de === nome || el.dataset.para === nome;
          el.classList.toggle('realcada', tocada);
          el.classList.toggle('apagada', !tocada);
        });

      detalhe.textContent = '';

      var cabeca = elemento('div', 'er-detalhe-topo');
      cabeca.appendChild(elemento('h4', 'er-nome', tabela.nome));
      if (tabela.papel) {
        cabeca.appendChild(elemento('p', 'er-papel', tabela.papel));
      }
      detalhe.appendChild(cabeca);

      if (tabela.nota) {
        var nota = elemento('p', 'er-nota');
        nota.innerHTML = markdown(tabela.nota);
        detalhe.appendChild(nota);
      }

      detalhe.appendChild(BLOCOS.tabela({
        colunas: ['Coluna', 'Tipo', 'Regra no banco'],
        linhas: (tabela.colunas || []).map(function (c) {
          return ['`' + c.nome + '`', '`' + c.tipo + '`', c.regra || '—'];
        })
      }));

      if ((tabela.indices || []).length) {
        detalhe.appendChild(elemento('h5', 'er-sub', 'Índices'));
        var ul = elemento('ul', 'bloco-lista');
        tabela.indices.forEach(function (indice) {
          var li = elemento('li');
          li.innerHTML = '<code>' + escapar(indice.nome) + '</code> — ' +
            markdown(indice.porque);
          ul.appendChild(li);
        });
        detalhe.appendChild(ul);
      } else {
        detalhe.appendChild(elemento('p', 'er-sem-indice',
          'Nenhum índice próprio além da chave primária e das constraints ' +
          'UNIQUE, que o PostgreSQL indexa sozinho.'));
      }
    }

    tabelas.forEach(function (tabela) {
      var b = elemento('button', 'er-atalho', tabela.nome);
      b.type = 'button';
      b.dataset.tabela = tabela.nome;
      b.setAttribute('role', 'tab');
      b.addEventListener('click', function () { selecionar(tabela.nome); });
      atalhos.appendChild(b);
    });

    moldura.querySelectorAll('.er-caixa').forEach(function (g) {
      g.addEventListener('click', function () {
        selecionar(g.dataset.tabela);
      });
      // Teclado: o diagrama é navegável por Tab, e Enter/espaço abrem a
      // tabela. Diagrama clicável sem isso exclui quem não usa mouse.
      g.addEventListener('keydown', function (evento) {
        if (evento.key === 'Enter' || evento.key === ' ') {
          evento.preventDefault();
          selecionar(g.dataset.tabela);
        }
      });
    });

    // As linhas de ligação se desenham quando o diagrama entra na tela.
    if (MOVIMENTO_OK) {
      var svg = moldura.querySelector('.er-svg');
      if (svg) {
        aoEntrarNaTela(moldura, function () { svg.classList.add('tracando'); });
      }
    }

    if (tabelas.length) { selecionar(tabelas[0].nome); }
  }

  /**
   * Monta o SVG do diagrama a partir das coordenadas do conteudo.json.
   *
   * SVG escrito como texto, e não com createElementNS: é uma única
   * geração, e o texto deixa a estrutura do diagrama legível de uma vez.
   * Todo valor que vem do JSON passa por escapar().
   */
  function desenharSvgEr(dados) {
    var tabelas = dados.tabelas || [];

    var LINHA_COLUNA = 17;   // espaçamento entre nomes de coluna
    var TOPO = 42;           // da borda de cima até a primeira coluna
    var RODAPE = 12;         // folga abaixo da última coluna
    var MAX_COLUNAS = 7;     // além disso, mostra "+ N colunas"

    /**
     * A altura da caixa é CALCULADA, não lida do JSON.
     *
     * O `h` do conteudo.json vira um mínimo. Se ele for menor do que o
     * necessário, os nomes das colunas vazariam para fora da borda — e
     * quem editar o arquivo para acrescentar uma coluna não tem por que
     * saber que precisa também ajustar um número de pixels.
     */
    function alturaDe(t) {
      var total = (t.colunas || []).length;
      var visiveis = Math.min(total, MAX_COLUNAS);
      var extra = total > MAX_COLUNAS ? 1 : 0;
      var precisa = TOPO + (visiveis + extra) * LINHA_COLUNA + RODAPE;
      return Math.max(t.h || 0, precisa);
    }

    var porNome = {};
    var alturas = {};
    var fundo = 0;

    tabelas.forEach(function (t) {
      porNome[t.nome] = t;
      alturas[t.nome] = alturaDe(t);
      fundo = Math.max(fundo, (t.y || 0) + alturas[t.nome]);
    });

    // A moldura acompanha a caixa mais baixa, com uma folga.
    var altura = Math.max(fundo + 20, 200);

    var partes = [
      '<svg viewBox="0 0 540 ' + altura + '" class="er-svg" role="img" ' +
      'aria-label="Diagrama entidade-relacionamento das ' +
      tabelas.length + ' tabelas do modelo">'
    ];

    // As ligações primeiro, para ficarem atrás das caixas.
    (dados.ligacoes || []).forEach(function (ligacao) {
      var a = porNome[ligacao.de];
      var b = porNome[ligacao.para];
      if (!a || !b) { return; }

      var ax = a.x + a.w / 2;
      var ay = a.y + alturas[a.nome] / 2;
      var bx = b.x + b.w / 2;
      var by = b.y + alturas[b.nome] / 2;

      // pathLength="100" normaliza o comprimento da linha para 100
      // unidades, qualquer que seja o tamanho real. Com isso o
      // stroke-dasharray do CSS desenha todas na mesma velocidade, sem
      // o script precisar medir cada uma — e sem `style=` escrito na
      // marcação, que a CSP descartaria.
      var ligadas = ' data-de="' + escapar(ligacao.de) +
        '" data-para="' + escapar(ligacao.para) + '"';

      partes.push(
        '<line class="er-linha"' + ligadas + ' pathLength="100" x1="' + ax +
        '" y1="' + ay + '" x2="' + bx + '" y2="' + by + '"></line>',
        '<text class="er-cardinalidade"' + ligadas + ' x="' + ((ax + bx) / 2) +
        '" y="' + ((ay + by) / 2 - 4) + '" text-anchor="middle">' +
        escapar(ligacao.rotulo || '') + '</text>'
      );
    });

    tabelas.forEach(function (t) {
      partes.push(
        '<g class="er-caixa" data-tabela="' + escapar(t.nome) + '" ' +
        'tabindex="0" role="button" aria-label="Tabela ' + escapar(t.nome) +
        '">',
        '<rect x="' + t.x + '" y="' + t.y + '" width="' + t.w +
        '" height="' + alturas[t.nome] + '" rx="8"></rect>',
        '<text class="er-titulo" x="' + (t.x + 12) + '" y="' + (t.y + 22) +
        '">' + escapar(t.nome) + '</text>'
      );

      var colunas = t.colunas || [];

      colunas.slice(0, MAX_COLUNAS).forEach(function (coluna, i) {
        partes.push(
          '<text class="er-coluna" x="' + (t.x + 12) + '" y="' +
          (t.y + TOPO + i * LINHA_COLUNA) + '">' +
          escapar(coluna.nome) + '</text>'
        );
      });

      if (colunas.length > MAX_COLUNAS) {
        partes.push(
          '<text class="er-coluna er-mais" x="' + (t.x + 12) + '" y="' +
          (t.y + TOPO + MAX_COLUNAS * LINHA_COLUNA) + '">+ ' +
          (colunas.length - MAX_COLUNAS) + ' colunas</text>'
        );
      }

      partes.push('</g>');
    });

    partes.push('</svg>');
    return partes.join('');
  }

  /* -------------------------------------------------------------------
     3. checkout — duas compras disputando o último pacote
     ------------------------------------------------------------------- */

  function montarCheckout(caixa, dados) {
    var passos = dados.passos || [];
    var atual = 0;
    var tocando = false;
    var relogio = null;

    caixa.appendChild(elemento('h3', 'interativo-titulo',
      'Duas compras, um pacote'));

    // O manual proíbe apresentar mockup como tela implementada. O selo
    // e a frase abaixo existem para não haver a menor dúvida sobre o que
    // isto é: uma reprodução do comportamento, não a execução dele.
    var selo = elemento('p', 'selo-simulacao');
    selo.innerHTML = '<strong>' + escapar(dados.aviso || 'Simulação ilustrativa') +
      '</strong> — ' + markdown(dados.explicacao || '');
    caixa.appendChild(selo);

    var pista = elemento('div', 'pista');
    pista.innerHTML =
      '<div class="faixa faixa-ana">' +
      '<span class="faixa-nome">Ana <span class="cadeado" hidden>🔒</span></span>' +
      '<p class="faixa-acao"></p></div>' +

      '<div class="faixa faixa-bruno">' +
      '<span class="faixa-nome">Bruno <span class="cadeado" hidden>🔒</span></span>' +
      '<p class="faixa-acao"></p></div>' +

      '<div class="faixa faixa-banco"><span class="faixa-nome">' +
      escapar(dados.cafe || 'produto') + ' — no banco</span>' +
      '<p class="faixa-acao"></p>' +
      // O contador de estoque é o que torna a disputa visível: é o
      // número que as duas transações querem, e ele só muda no COMMIT.
      '<p class="estoque-vivo"><span class="estoque-rotulo">estoque</span>' +
      '<span class="estoque-numero">—</span></p></div>';
    caixa.appendChild(pista);

    var narracao = elemento('p', 'narracao');
    narracao.setAttribute('aria-live', 'polite');
    caixa.appendChild(narracao);

    var controles = elemento('div', 'controles');
    var btTocar = elemento('button', 'botao-alternar', '▶ Rodar a simulação');
    var btPasso = elemento('button', 'botao-discreto', 'Passo a passo →');
    var btZerar = elemento('button', 'botao-discreto', '↺ Voltar ao início');
    [btTocar, btPasso, btZerar].forEach(function (b) {
      b.type = 'button';
      controles.appendChild(b);
    });
    caixa.appendChild(controles);

    var marcador = elemento('p', 'marcador-passo');
    caixa.appendChild(marcador);

    var estoqueMostrado = null;

    function desenhar() {
      var passo = passos[atual] || {};
      var faixas = pista.querySelectorAll('.faixa-acao');

      faixas[0].textContent = passo.ana || '—';
      faixas[1].textContent = passo.bruno || '—';
      faixas[2].textContent = passo.banco || '—';

      // Estado visual de cada faixa, para o olho acompanhar sem ler.
      pista.querySelector('.faixa-ana').className =
        'faixa faixa-ana' + (passo.ana ? ' ativa' : '');
      pista.querySelector('.faixa-bruno').className =
        'faixa faixa-bruno' +
        (/esperando|ESPERANDO/.test(passo.bruno || '') ? ' esperando' :
          (/ROLLBACK/.test(passo.bruno || '') ? ' falhou' :
            (passo.bruno ? ' ativa' : '')));

      // O cadeado aparece em quem está segurando a linha. É o FOR UPDATE
      // desenhado: enquanto ele está num lado, o outro não lê.
      var cadeados = pista.querySelectorAll('.cadeado');
      cadeados[0].hidden = passo.trava !== 'ana';
      cadeados[1].hidden = passo.trava !== 'bruno';

      // O estoque só muda quando alguém faz COMMIT — e é exatamente esse
      // o ponto da simulação.
      var numero = pista.querySelector('.estoque-numero');
      var saldo = (passo.estoque === undefined || passo.estoque === null)
        ? null : Number(passo.estoque);

      if (saldo === null) {
        numero.textContent = '—';
      } else {
        numero.textContent = String(saldo);
        if (MOVIMENTO_OK && estoqueMostrado !== null && estoqueMostrado !== saldo) {
          // Pisca só quando o número REALMENTE mudou.
          numero.classList.remove('mudou');
          void numero.offsetWidth;   // força o reinício da animação
          numero.classList.add('mudou');
        }
        estoqueMostrado = saldo;
      }

      pista.querySelector('.faixa-banco').classList.toggle(
        'esgotado', saldo === 0
      );

      narracao.innerHTML = passo.nota ? markdown(passo.nota) : '&nbsp;';
      marcador.textContent = 'Passo ' + (atual + 1) + ' de ' + passos.length;
    }

    function avancar() {
      if (atual < passos.length - 1) {
        atual += 1;
        desenhar();
      } else {
        parar();
      }
    }

    function parar() {
      tocando = false;
      if (relogio) { clearInterval(relogio); relogio = null; }
      btTocar.textContent = atual >= passos.length - 1
        ? '▶ Rodar de novo'
        : '▶ Continuar';
    }

    btTocar.addEventListener('click', function () {
      if (tocando) { parar(); return; }
      if (atual >= passos.length - 1) {
        atual = 0;
        estoqueMostrado = null;
        desenhar();
      }
      tocando = true;
      btTocar.textContent = '⏸ Pausar';
      relogio = setInterval(avancar, 1900);
    });

    btPasso.addEventListener('click', function () { parar(); avancar(); });

    btZerar.addEventListener('click', function () {
      parar();
      atual = 0;
      estoqueMostrado = null;
      desenhar();
      btTocar.textContent = '▶ Rodar a simulação';
    });

    // O fecho: a mensagem real da loja e o teste que prova o
    // comportamento. É o que liga a simulação à evidência.
    var fecho = elemento('div', 'fecho-simulacao');
    fecho.appendChild(elemento('p', 'fecho-rotulo',
      'A mensagem que a loja realmente exibe:'));
    var mensagem = elemento('p', 'fecho-mensagem', dados.mensagem_real || '');
    fecho.appendChild(mensagem);
    var prova = elemento('p', 'fecho-prova');
    prova.innerHTML = 'O comportamento acima é verificado pelo teste ' +
      '<code>' + escapar(dados.nome_do_teste || '') + '</code>, em ' +
      '<code>tests/test_checkout.py</code>. A evidência colhida na loja ' +
      'publicada está na seção 9.';
    fecho.appendChild(prova);
    caixa.appendChild(fecho);

    desenhar();
  }

  /* -------------------------------------------------------------------
     4. explain — o plano antes e depois do índice
     ------------------------------------------------------------------- */

  function montarExplain(caixa, dados) {
    caixa.appendChild(elemento('h3', 'interativo-titulo',
      'EXPLAIN ANALYZE — antes e depois do índice'));

    if (dados.legenda) {
      caixa.appendChild(elemento('p', 'interativo-nota', dados.legenda));
    }
    if (dados.nota_volume) {
      var volume = elemento('p', 'interativo-nota interativo-nota-forte');
      volume.innerHTML = markdown(dados.nota_volume);
      caixa.appendChild(volume);
    }

    (dados.casos || []).forEach(function (caso) {
      var bloco = elemento('article', 'explain-caso');

      bloco.appendChild(elemento('h4', 'explain-nome', caso.nome));

      if (caso.consulta) {
        bloco.appendChild(BLOCOS.codigo({
          linguagem: 'sql', codigo: caso.consulta
        }));
      }

      // As duas barras comparam os tempos em ESCALA. Ler "6,713 ms" e
      // "0,900 ms" exige fazer a conta de cabeça; ver uma barra sete
      // vezes maior que a outra não exige nada. O comprimento sai dos
      // números reais do EXPLAIN, não de um valor escolhido a dedo.
      var msAntes = msDoTexto((caso.antes || {}).tempo);
      var msDepois = msDoTexto((caso.depois || {}).tempo);
      var maior = Math.max(msAntes || 0, msDepois || 0);

      var par = elemento('div', 'explain-par');
      [['antes', 'explain-antes', msAntes], ['depois', 'explain-depois', msDepois]]
        .forEach(function (dupla) {
          var lado = caso[dupla[0]] || {};
          var painel = elemento('div', 'explain-lado ' + dupla[1]);
          painel.appendChild(elemento('p', 'explain-lado-titulo', lado.titulo));

          var pre = elemento('pre');
          var cod = elemento('code');
          cod.textContent = lado.plano || '';
          pre.appendChild(cod);
          painel.appendChild(pre);

          var rodape = elemento('div', 'explain-rodape');
          rodape.appendChild(elemento('p', 'explain-tempo', lado.tempo));

          if (dupla[2] !== null && maior > 0) {
            // Raiz quadrada da proporção: com 7,5x de diferença, a barra
            // menor ficaria com 1 pixel numa escala linear e não se
            // leria. A raiz mantém a ordem e devolve a barra pequena ao
            // campo do visível — e a legenda ao lado traz o número exato,
            // que é o que vale.
            var fracao = Number((Math.sqrt(dupla[2] / maior) * 100).toFixed(1));
            var trilho = elemento('div', 'explain-trilho');
            var cheia = elemento('div', 'explain-cheia');

            // Largura certa já; o zero só fora da vista.
            cheia.style.setProperty('width', fracao + '%');
            trilho.appendChild(cheia);
            rodape.appendChild(trilho);

            if (MOVIMENTO_OK) {
              aoEntrarNaTela(painel, function () {
                animarLargura(cheia, fracao);
              }, PRESTES_A_ENTRAR);
            }
          }

          painel.appendChild(rodape);
          par.appendChild(painel);
        });
      bloco.appendChild(par);

      if (caso.ganho) {
        bloco.appendChild(elemento('p', 'explain-ganho', caso.ganho));
      }
      if (caso.licao) {
        var licao = elemento('p', 'explain-licao');
        licao.innerHTML = markdown(caso.licao);
        bloco.appendChild(licao);
      }

      caixa.appendChild(bloco);
    });

    if (dados.preco) {
      var preco = elemento('article', 'explain-preco');
      preco.appendChild(elemento('h4', 'explain-nome', dados.preco.titulo));
      preco.appendChild(BLOCOS.tabela({
        colunas: ['O que', 'Quanto'],
        linhas: dados.preco.linhas || []
      }));
      var texto = elemento('p');
      texto.innerHTML = markdown(dados.preco.texto || '');
      preco.appendChild(texto);
      caixa.appendChild(preco);
    }
  }

  /* -------------------------------------------------------------------
     5. indicadores — leitura ao vivo de /api/resumo
     ------------------------------------------------------------------- */

  function montarIndicadores(caixa) {
    var raiz = document.getElementById('relatorio');
    var endereco = (raiz && raiz.dataset.resumo) || '/api/resumo';

    caixa.appendChild(elemento('h3', 'interativo-titulo',
      'Indicadores ao vivo, da loja publicada'));

    var nota = elemento('p', 'interativo-nota');
    nota.innerHTML = 'Lidos de <code>GET /api/resumo</code> no momento em ' +
      'que esta página abriu. A rota é pública e devolve apenas agregados: ' +
      'participação por região em <strong>porcentagem</strong>, nunca valor ' +
      'em reais, nunca nome de cliente.';
    caixa.appendChild(nota);

    var painel = elemento('div', 'indicadores-vivos');
    painel.setAttribute('aria-live', 'polite');
    painel.appendChild(elemento('p', 'carregando', 'Consultando a loja…'));
    caixa.appendChild(painel);

    var rodape = elemento('div', 'indicadores-rodape');
    caixa.appendChild(rodape);

    function cartao(rotulo, valor, ajuda) {
      var art = elemento('article', 'cartao-vivo');
      art.appendChild(elemento('p', 'cartao-rotulo', rotulo));

      var numero = elemento('p', 'cartao-valor');
      art.appendChild(numero);

      // O valor REAL entra já. Só depois, e só se houver movimento, ele
      // é reiniciado em zero para contar.
      //
      // A ordem importa e custou um defeito: na primeira versão o número
      // nascia em "0" e só virava o valor certo ao entrar na tela. Quem
      // imprimisse a página, ou não rolasse até ali, lia `0 pedidos` — um
      // número ERRADO, não apenas um número sem animação. Animação nunca
      // pode ser a única coisa que torna o dado correto.
      numero.textContent = valor;

      if (MOVIMENTO_OK && (typeof valor === 'number' || /^\d+$/.test(String(valor)))) {
        aoEntrarNaTela(art, function () {
          animarNumero(numero, Number(valor));
        }, PRESTES_A_ENTRAR);
      }

      if (ajuda) { art.appendChild(elemento('p', 'cartao-ajuda', ajuda)); }
      return art;
    }

    function desenharErro(motivo) {
      painel.textContent = '';
      var erro = elemento('div', 'indicadores-erro');
      erro.appendChild(elemento('p', 'erro-titulo',
        'Não foi possível ler os indicadores agora.'));
      erro.appendChild(elemento('p', 'erro-detalhe', motivo));
      erro.appendChild(elemento('p', 'erro-ajuda',
        'O resto desta página não depende dessa consulta. ' +
        'Se a loja estiver fora do ar, os números voltam sozinhos ' +
        'quando ela responder.'));

      var repetir = elemento('button', 'botao-discreto', '↻ Tentar de novo');
      repetir.type = 'button';
      repetir.addEventListener('click', buscar);
      erro.appendChild(repetir);

      painel.appendChild(erro);
      rodape.textContent = '';
    }

    function desenhar(dados) {
      painel.textContent = '';
      rodape.textContent = '';

      var cartoes = elemento('div', 'grade-vivos');
      cartoes.appendChild(cartao(
        'Pedidos no período',
        dados.pedidos_no_periodo,
        'Últimos ' + dados.periodo_dias + ' dias, sem contar cancelados'
      ));
      cartoes.appendChild(cartao(
        'Cafés vendidos',
        dados.cafes_vendidos,
        'Unidades, somadas dos itens dos pedidos'
      ));
      cartoes.appendChild(cartao(
        'Cafés no catálogo',
        dados.cafes_no_catalogo,
        // Sem o número de regiões escrito aqui: ele era "4" fixo no
        // código e viraria mentira no dia em que o catálogo mudasse.
        'Cafés de origem única, lidos do banco'
      ));

      var conc = dados.conciliacao || {};
      var fechou = conc.pedidos === conc.conciliados;
      var cartaoConc = cartao(
        'Pedidos conciliados',
        (conc.conciliados || 0) + ' de ' + (conc.pedidos || 0),
        fechou
          ? 'Todo pedido tem total igual à soma dos itens'
          : 'Há divergência — isso não deveria acontecer'
      );
      cartaoConc.classList.add(fechou ? 'cartao-ok' : 'cartao-alerta');
      cartoes.appendChild(cartaoConc);

      painel.appendChild(cartoes);

      var regioes = dados.participacao_por_regiao || [];
      if (regioes.length) {
        painel.appendChild(elemento('h4', 'sub',
          'Participação por região produtora'));

        var lista = elemento('ul', 'barras-vivas');
        regioes.forEach(function (r) {
          var li = elemento('li', 'barra-viva');
          li.appendChild(elemento('span', 'barra-rotulo', r.regiao));

          var trilho = elemento('span', 'barra-trilho');
          var cheia = elemento('span', 'barra-cheia');

          // Estilo por CSSOM: a CSP bloqueia style= escrito no HTML, mas
          // não bloqueia o objeto style de um elemento. A barra começa em
          // zero e cresce quando entra na tela — a transição de largura
          // está no CSS.
          // Mesma regra dos números: a largura certa entra já, e o
          // reinício em zero só acontece fora da vista. Uma barra vazia
          // na impressão seria um dado errado, não um dado sem animação.
          var largura = Math.max(0, Math.min(100, Number(r.percentual) || 0));
          cheia.style.setProperty('width', largura + '%');

          if (MOVIMENTO_OK) {
            aoEntrarNaTela(li, function () {
              animarLargura(cheia, largura);
            }, PRESTES_A_ENTRAR);
          }

          trilho.appendChild(cheia);
          li.appendChild(trilho);

          li.appendChild(elemento('span', 'barra-valor',
            (Number(r.percentual) || 0).toFixed(1) + '%'));
          lista.appendChild(li);
        });
        painel.appendChild(lista);
      } else {
        painel.appendChild(elemento('p', 'interativo-nota',
          'Nenhuma venda registrada no período consultado.'));
      }

      var quando = new Date(dados.gerado_em);
      var texto = isNaN(quando.getTime())
        ? String(dados.gerado_em || '')
        : quando.toLocaleString('pt-BR');
      rodape.appendChild(elemento('p', 'atualizado',
        'Dados do banco de produção, gerados em ' + texto + '.'));
    }

    function buscar() {
      painel.textContent = '';
      painel.appendChild(elemento('p', 'carregando', 'Consultando a loja…'));

      fetch(endereco, {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
      })
        .then(function (resposta) {
          if (!resposta.ok) {
            throw new Error('a loja respondeu HTTP ' + resposta.status);
          }
          return resposta.json();
        })
        .then(desenhar)
        .catch(function (erro) {
          desenharErro(
            'A consulta a ' + endereco + ' falhou: ' +
            (erro && erro.message ? erro.message : 'erro de rede') + '.'
          );
        });
    }

    buscar();
  }

  /* -------------------------------------------------------------------
     6. testes — a tabela de casos, com filtro
     ------------------------------------------------------------------- */

  function montarTestes(caixa, dados) {
    var casos = dados.casos || [];

    caixa.appendChild(elemento('h3', 'interativo-titulo', 'Casos de teste'));

    if (dados.legenda) {
      caixa.appendChild(elemento('p', 'interativo-nota', dados.legenda));
    }
    if (dados.nota) {
      var nota = elemento('p', 'interativo-nota interativo-nota-forte');
      nota.innerHTML = markdown(dados.nota);
      caixa.appendChild(nota);
    }

    var tipos = ['Todos'];
    casos.forEach(function (c) {
      if (tipos.indexOf(c.tipo) === -1) { tipos.push(c.tipo); }
    });

    var filtros = elemento('div', 'filtros-teste');
    filtros.setAttribute('role', 'group');
    filtros.setAttribute('aria-label', 'Filtrar casos por tipo');
    caixa.appendChild(filtros);

    var contagem = elemento('p', 'contagem-teste');
    contagem.setAttribute('aria-live', 'polite');
    caixa.appendChild(contagem);

    var alvo = elemento('div', 'tabela-testes');
    caixa.appendChild(alvo);

    function desenhar(tipo) {
      var visiveis = (tipo === 'Todos')
        ? casos
        : casos.filter(function (c) { return c.tipo === tipo; });

      filtros.querySelectorAll('button').forEach(function (b) {
        var ativo = b.dataset.tipo === tipo;
        b.classList.toggle('ativo', ativo);
        b.setAttribute('aria-pressed', ativo ? 'true' : 'false');
      });

      contagem.textContent = visiveis.length === casos.length
        ? 'Mostrando todos os casos.'
        : 'Mostrando os casos do tipo "' + tipo + '".';

      alvo.textContent = '';
      alvo.appendChild(BLOCOS.tabela({
        colunas: ['Caso', 'Tipo', 'Entrada', 'Resultado esperado',
          'Resultado obtido', 'Evidência'],
        linhas: visiveis.map(function (c) {
          return [
            c.caso, c.tipo, c.entrada, c.esperado, c.obtido,
            '`' + (c.evidencia || '') + '`'
          ];
        })
      }));
    }

    tipos.forEach(function (tipo) {
      var b = elemento('button', 'filtro-teste', tipo);
      b.type = 'button';
      b.dataset.tipo = tipo;
      b.addEventListener('click', function () { desenhar(tipo); });
      filtros.appendChild(b);
    });

    desenhar('Todos');
  }

  var COMPONENTES = {
    as_is_to_be: montarAsIsToBe,
    er: montarEr,
    checkout: montarCheckout,
    explain: montarExplain,
    indicadores: montarIndicadores,
    testes: montarTestes
  };

  /* -------------------------------------------------------------------
     Montagem da página
     ------------------------------------------------------------------- */

  function montarCapa(meta, secao) {
    var capa = elemento('header', 'capa');
    capa.id = 'sec-' + secao.id;

    capa.appendChild(elemento('p', 'capa-disciplina',
      [meta.instituicao, meta.disciplina].filter(Boolean).join(' · ')));

    var marca = elemento('h1', 'capa-titulo');
    marca.innerHTML = 'Projeto Final<span class="capa-marca">Torra ' +
      '<span class="amp">&amp;</span> Terra</span>';
    capa.appendChild(marca);

    if (meta.subtitulo) {
      capa.appendChild(elemento('p', 'capa-subtitulo', meta.subtitulo));
    }

    var faixa = elemento('p', 'capa-faixa');
    faixa.innerHTML = escapar(meta.segmento || '') +
      '<span class="sep">·</span>' + escapar(meta.contexto || '') +
      '<span class="sep">·</span>' + escapar(meta.banco || '');
    capa.appendChild(faixa);

    var ficha = elemento('dl', 'capa-ficha');
    [
      [meta.grupo_numero || 'Grupo', (meta.grupo || []).join(' · ')],
      ['Professor', meta.professor],
      ['Data', meta.data]
    ].forEach(function (par) {
      if (!par[1]) { return; }
      ficha.appendChild(elemento('dt', null, par[0]));
      ficha.appendChild(elemento('dd', null, par[1]));
    });
    capa.appendChild(ficha);

    var links = meta.links || {};
    var caixaLinks = elemento('p', 'capa-links');
    [
      ['loja', 'Abrir a loja'],
      ['repositorio', 'Código no GitHub'],
      ['relatorio_pdf', 'Relatório em PDF'],
      ['health', 'Health check']
    ].forEach(function (par) {
      if (!links[par[0]]) { return; }
      var a = elemento('a', 'capa-link', par[1]);
      a.href = links[par[0]];
      a.rel = 'noopener';
      if (links[par[0]].indexOf('http') === 0) { a.target = '_blank'; }
      caixaLinks.appendChild(a);
    });
    capa.appendChild(caixaLinks);

    if (meta.aviso) {
      // O manual é explícito: a versão navegável complementa o relatório
      // entregue em documento, não o substitui.
      capa.appendChild(elemento('p', 'capa-aviso', meta.aviso));
    }

    // Os blocos da própria seção 1, depois da ficha.
    var corpo = elemento('div', 'capa-corpo');
    (secao.blocos || []).forEach(function (bloco) {
      var montado = montarBloco(bloco, null);
      if (montado) { corpo.appendChild(montado); }
    });
    capa.appendChild(corpo);

    return capa;
  }

  function montarBloco(bloco, dados) {
    var monta = BLOCOS[bloco && bloco.tipo];
    if (!monta) {
      return aviso('Tipo de bloco desconhecido: "' +
        (bloco && bloco.tipo) + '". Os tipos válidos estão no LEIAME.md.');
    }
    try {
      return monta(bloco, dados);
    } catch (erro) {
      // Um bloco malformado não pode derrubar a página inteira: quem
      // for substituir o conteudo.json precisa ver ONDE errou.
      return aviso('Falha ao montar um bloco "' + bloco.tipo + '": ' +
        (erro && erro.message ? erro.message : erro));
    }
  }

  function montarSecao(secao, dados) {
    var sec = elemento('section', 'secao');
    sec.id = 'sec-' + secao.id;
    sec.setAttribute('aria-labelledby', 'titulo-' + secao.id);

    var titulo = elemento('h2', 'secao-titulo');
    titulo.id = 'titulo-' + secao.id;
    titulo.innerHTML = '<span class="secao-numero">' +
      escapar(secao.numero !== undefined ? secao.numero : '') + '</span>' +
      escapar(secao.titulo || '');
    sec.appendChild(titulo);

    (secao.blocos || []).forEach(function (bloco) {
      var montado = montarBloco(bloco, dados);
      if (montado) { sec.appendChild(montado); }
    });

    return sec;
  }

  function montarIndice(secoes) {
    var indice = document.getElementById('indice-lista');
    if (!indice) { return; }

    secoes.forEach(function (secao) {
      var li = elemento('li');
      var a = elemento('a');
      a.href = '#sec-' + secao.id;
      a.innerHTML = '<span class="indice-numero">' +
        escapar(secao.numero !== undefined ? secao.numero : '·') +
        '</span>' + escapar(secao.titulo || '');
      a.dataset.alvo = 'sec-' + secao.id;
      li.appendChild(a);
      indice.appendChild(li);
    });
  }

  /**
   * Destaca no índice a seção que está na tela.
   *
   * IntersectionObserver em vez de ouvir o evento de scroll: o navegador
   * avisa quando a seção entra ou sai, sem a página recalcular posição a
   * cada pixel rolado. Em projetor e em celular a diferença se sente.
   */
  function acompanharLeitura() {
    var links = {};
    document.querySelectorAll('#indice-lista a').forEach(function (a) {
      links[a.dataset.alvo] = a;
    });

    if (!('IntersectionObserver' in window)) { return; }

    var visiveis = new Set();

    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (entrada.isIntersecting) {
          visiveis.add(entrada.target.id);
        } else {
          visiveis.delete(entrada.target.id);
        }
      });

      Object.keys(links).forEach(function (id) {
        links[id].classList.remove('atual');
      });

      // A primeira seção visível na ordem do documento é a "atual".
      var ordenadas = Object.keys(links).filter(function (id) {
        return visiveis.has(id);
      });
      if (ordenadas.length && links[ordenadas[0]]) {
        links[ordenadas[0]].classList.add('atual');
        links[ordenadas[0]].setAttribute('aria-current', 'true');
      }
    }, { rootMargin: '-80px 0px -60% 0px' });

    document.querySelectorAll('.secao, .capa').forEach(function (sec) {
      observador.observe(sec);
    });
  }

  function ligarMenu() {
    var botao = document.getElementById('abrir-indice');
    var indice = document.getElementById('indice');
    if (!botao || !indice) { return; }

    botao.addEventListener('click', function () {
      var aberto = indice.classList.toggle('aberto');
      botao.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    });

    // No celular o índice cobre a tela; clicar num item precisa fechá-lo.
    indice.addEventListener('click', function (evento) {
      if (evento.target.closest('a')) {
        indice.classList.remove('aberto');
        botao.setAttribute('aria-expanded', 'false');
      }
    });
  }

  function falhaGeral(mensagem) {
    var raiz = document.getElementById('relatorio');
    if (!raiz) { return; }
    raiz.textContent = '';
    var caixa = elemento('div', 'falha-geral');
    caixa.appendChild(elemento('h1', null, 'O conteúdo não pôde ser carregado'));
    caixa.appendChild(elemento('p', null, mensagem));
    caixa.appendChild(elemento('p', null,
      'O texto desta página vive em static/projeto_final/conteudo.json. ' +
      'O formato esperado está documentado em ' +
      'static/projeto_final/LEIAME.md.'));
    raiz.appendChild(caixa);
  }

  function iniciar() {
    var raiz = document.getElementById('relatorio');
    if (!raiz) { return; }

    var endereco = raiz.dataset.conteudo;
    if (!endereco) {
      falhaGeral('A página não sabe de onde ler o conteúdo.');
      return;
    }

    fetch(endereco, { headers: { 'Accept': 'application/json' } })
      .then(function (resposta) {
        if (!resposta.ok) {
          throw new Error('HTTP ' + resposta.status + ' ao buscar o conteúdo');
        }
        return resposta.json();
      })
      .then(function (conteudo) {
        var meta = conteudo.meta || {};
        var secoes = conteudo.secoes || [];
        var dados = conteudo.dados || {};

        if (meta.titulo) { document.title = meta.titulo; }

        raiz.textContent = '';

        secoes.forEach(function (secao, indice) {
          // A primeira seção é a capa e ganha tratamento próprio.
          raiz.appendChild(indice === 0
            ? montarCapa(meta, secao)
            : montarSecao(secao, dados));
        });

        var rodape = elemento('footer', 'rodape-relatorio');
        rodape.innerHTML =
          '<p>' + escapar(meta.titulo || '') + ' — ' +
          escapar((meta.grupo || []).join(', ')) + '</p>' +
          '<p>' + escapar(meta.instituicao || '') + ' · ' +
          escapar(meta.disciplina || '') + ' · ' +
          escapar(meta.professor || '') + '</p>' +
          '<p class="rodape-volta"><a href="/">← Voltar para a loja</a></p>';
        raiz.appendChild(rodape);

        montarIndice(secoes);
        acompanharLeitura();
        ligarMenu();

        // Movimento, por último: tudo acima já funciona sem nada disto.
        ligarBarraDeProgresso();
        ligarRevelacao();
        ligarTeclado();
        ligarBrilhoDoCursor();
      })
      .catch(function (erro) {
        falhaGeral('Falha ao ler ' + endereco + ': ' +
          (erro && erro.message ? erro.message : erro));
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
