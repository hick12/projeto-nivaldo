# Evidências

Entrega 4 do slide 41. Este documento reúne as provas de que o modelo, a
transação e o deploy funcionam.

> **Estado atual:** os blocos marcados com `PENDENTE` aguardam a execução
> contra o banco. O procedimento para preencher cada um está descrito acima
> dele — é copiar a saída real do terminal, nunca transcrever de memória.

---

## 1. Estrutura do banco

### 1.1 Tabelas criadas

```bash
psql -U torra_app -d torra_terra -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
```

**Esperado:** `categorias`, `clientes`, `itens_pedido`, `pedidos`, `produtos`.

```
PENDENTE — colar a saída
```

### 1.2 Constraints

Seção 1.2 de `SQL/consultas.sql`. É o que o professor avalia diretamente.

**Esperado:** 5 `PRIMARY KEY`, 5 `FOREIGN KEY`, 3 `UNIQUE`
(`categorias.nome`, `clientes.email`, `uq_itens_pedido_produto_moagem`) e
os `CHECK` de preço, estoque, SCA, torra, moagem, status, quantidade e peso.

```
PENDENTE — colar a saída
```

### 1.3 Índices

```bash
psql -U torra_app -d torra_terra -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND indexname LIKE 'idx_%' ORDER BY indexname;"
```

**Esperado:** os quatro — `idx_itens_pedido`, `idx_pedidos_cliente`,
`idx_produtos_categoria`, `idx_produtos_nome`.

```
PENDENTE — colar a saída
```

---

## 2. Testes automatizados

```bash
pytest -v
```

**Esperado:** 11 testes, todos passando.

| Teste | O que prova |
|---|---|
| `test_compra_normal_grava_pedido_itens_e_baixa_estoque` | RF05 no caminho feliz |
| `test_estoque_insuficiente_faz_rollback_completo` | Rollback total + mensagem nomeando o café |
| `test_produto_inexistente_nao_finaliza_o_pedido` | Pedido não fecha |
| `test_preco_negativo_e_recusado_pelo_banco` | `ck_produtos_preco` |
| `test_estoque_negativo_e_recusado_pelo_banco` | `ck_produtos_estoque` |
| `test_pontuacao_sca_fora_da_faixa_e_recusada` | `ck_produtos_sca` |
| `test_moagem_invalida_e_recusada_pelo_banco` | `ck_itens_moagem` |
| `test_senha_nunca_e_gravada_em_texto_puro` | RNF03 |
| `test_mesmo_cafe_em_moagens_diferentes_vira_duas_linhas` | `itens_pedido` é entidade |
| `test_preco_unitario_fica_congelado_apos_reajuste` | Histórico preservado |
| `test_carrinho_vazio_nao_gera_pedido` | Guarda de entrada |

```
PENDENTE — colar a saída completa do pytest -v
```

---

## 3. O cenário de erro — a demonstração principal

É o que mais impressiona na apresentação. Roteiro em quatro passos.

### Passo 1 — o estado antes

```bash
psql -U torra_app -d torra_terra -c "SELECT id, nome, estoque FROM produtos WHERE estoque < 5 ORDER BY estoque;"
```

```bash
psql -U torra_app -d torra_terra -c "SELECT (SELECT COUNT(*) FROM pedidos) AS pedidos, (SELECT COUNT(*) FROM itens_pedido) AS itens;"
```

O `Chapada Geisha` vem do `seed.sql` com **estoque 1**, de propósito.

```
PENDENTE — colar a saída
```

### Passo 2 — a tentativa que falha

Na loja: abrir o Chapada Geisha, escolher **quantidade 2**, adicionar ao
carrinho e finalizar a compra.

**Esperado na tela:**

> Estoque insuficiente de Chapada Geisha: voce pediu 2 e temos 1 em estoque.

```
PENDENTE — print da tela
```

### Passo 3 — a prova de que nada foi gravado

As mesmas duas consultas do passo 1. **Os números precisam ser idênticos.**

```
PENDENTE — colar a saída
```

### Passo 4 — nenhum pedido órfão

Seção 3.3 de `SQL/consultas.sql`. Um pedido sem item seria prova de
transação quebrada pela metade.

**Esperado:** zero linhas.

```
PENDENTE — colar a saída
```

---

## 4. A compra que dá certo

### 4.1 Pedido persistido

Seção 2.1 de `SQL/consultas.sql`.

```
PENDENTE — colar a saída
```

### 4.2 Itens com moagem e preço congelado

Seção 2.2 de `SQL/consultas.sql`.

```
PENDENTE — colar a saída
```

### 4.3 Estoque reduzido

Comparar o estoque do café comprado antes e depois. A diferença precisa ser
exatamente a quantidade do pedido.

```
PENDENTE — colar a saída
```

### 4.4 O total bate com a soma dos itens

Seção 1.8 de `SQL/consultas.sql`. **Esperado: zero linhas.**

```
PENDENTE — colar a saída
```

---

## 5. Índices e `EXPLAIN`

Seção 4 de `SQL/consultas.sql`.

**Leia a ressalva antes de tirar o print:** com 12 cafés o planejador escolhe
`Seq Scan` mesmo com o índice existindo — ler a tabela inteira é mais barato
quando ela cabe em uma página. Isso não invalida o índice; é a decisão certa
para o volume atual.

Para ver o `Index Scan` aparecer, use o gerador de carga da seção 4.5 (200 mil
linhas), rode `ANALYZE produtos` e repita o `EXPLAIN`.

### 5.1 Com 12 cafés

```
PENDENTE — colar o plano
```

### 5.2 Com 200 mil linhas, sem índice

```
PENDENTE — colar o plano (Seq Scan)
```

### 5.3 Com 200 mil linhas, com índice

```
PENDENTE — colar o plano (Index Scan)
```

---

## 6. Segurança

### 6.1 A senha não está em texto puro

```bash
psql -U torra_app -d torra_terra -c "SELECT id, nome, email, LEFT(senha_hash, 30) || '...' AS hash FROM clientes;"
```

**Esperado:** hashes começando com `scrypt:32768:8:1$`.

```
PENDENTE — colar a saída
```

### 6.2 Nenhum segredo no repositório

```bash
git log --all --oneline -- .env
```

**Esperado:** saída vazia — o `.env` nunca foi versionado.

```
PENDENTE — colar a saída
```

### 6.3 A aplicação não usa o superusuário

```bash
psql -U postgres -c "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname='torra_app';"
```

**Esperado:** `rolsuper = f`.

```
PENDENTE — colar a saída
```

---

## 7. Backup e restauração

Procedimento completo no `README.md`. O que precisa ser evidenciado:

1. O `pg_dump` gerou o arquivo e ele tem tamanho maior que zero
2. O `pg_restore` rodou em um banco novo, sem erro
3. As contagens de `produtos`, `pedidos` e `itens_pedido` **batem** entre
   origem e destino

Backup que nunca foi restaurado não é backup.

```
PENDENTE — colar a saída da comparação
```

---

## 8. Deploy

- [ ] `https://nivaldo.felipefurlan.com.br` abre com cadeado de HTTPS
- [ ] O catálogo carrega os cafés vindos do banco de produção
- [ ] Cadastro e login funcionam
- [ ] Carrinho aceita a escolha de moagem
- [ ] O checkout grava o pedido e reduz o estoque
- [ ] O cenário de erro funciona **em produção**
- [ ] "Meus pedidos" mostra o histórico com os itens
- [ ] `git push` na `main` dispara deploy novo automaticamente

```
PENDENTE — prints e URL
```
