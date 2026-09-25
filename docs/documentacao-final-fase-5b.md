# conc_banc — Fase 5b: documentação final (CSV pt-BR, desempate do matching, testes de limites)

Fase 5b da revisão do app de conciliação bancária (Streamlit): corrige o FAIL
CT-F5-05 da Fase 5 (CSV sem vírgula decimal nos dados reais), torna o matching
determinístico sob ambiguidade e adiciona testes de limites/DoS/cache.
Base: `origin/fase5-squad-xcre-49` no commit `871e833` ("docs: documentacao
final fase 5"). Login de teste: `admin` / `admin123` (conta bootstrap local,
dados sintéticos em `Exemplos/B_1234490.ofx` e `Exemplos/C_1234490.ofx`).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga**
(analogia do dia a dia). Este documento apenas relata o que os agentes
responsáveis executaram e reportaram na issue — nada foi marcado como
verificado sem execução real, e o que não foi verificado está declarado como
tal (seções 7–8). Este documento não altera código nem nenhum outro documento.

> Nota de procedência: os commits `ef2e18e`, `9ce69f6`, `624d4f8` (3 rodadas)
> e `0dfebee` (catálogo) estão em worktrees/branches locais de outros agentes
> e **não foram publicados (sem push/PR — o squad não tem credencial Git)**.
> Este arquivo foi escrito nesta branch sobre `0dfebee`. O conteúdo abaixo
> reproduz fielmente os relatos dos agentes na issue, sem reexecução
> independente nesta etapa de documentação.

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Etapa | Commit (local, sem push) | O que faz |
|-------|--------------------------|-----------|
| Pré-condição + Rodada 1 — CSV pt-BR real (item 1) | `ef2e18e` | `modules/export_divergencias.py`: nova `_normalizar_moeda_texto_pt_br` + `_normalizar_e_sanitizar_celula`; `tests/test_export_divergencias.py`: 4 testes novos com saída real de `pages/analise_dados.py` + 1 regressão pt-BR |
| Rodada 2 — desempate determinístico (item 2) | `9ce69f6` | `modules/data_analyzer.py::_match_valor_data_exata`: ordena extrato por chave canônica antes do loop; `tests/test_matching_propriedades.py`: teste de ambiguidade reescrito (determinismo) + 1 teste de descrição normalizada |
| Rodada 3 — limites/DoS/cache (item 3) | `624d4f8` | Novo `tests/test_limites_seguranca_fase5b.py` (16 testes). **Nenhum defeito real encontrado — nenhuma correção de produção nesta rodada** |
| Gate do revisor rápido + catálogo | `0dfebee` | Só `docs/casos-de-teste.md` (nova seção Fase 5b, CT-F5B-01…CT-F5B-08; CT-F5-05 reescrito como PASS) + `docs/casos-de-teste.pdf` regenerado (52 páginas). Nenhum arquivo de produção alterado nesta etapa |
| este doc | branch atual | `docs/documentacao-final-fase-5b.md` (este arquivo) |

Nenhum número do baseline B×C foi alterado em nenhuma rodada.

## 1. O que foi entregue — versão leiga

Pense no sistema como quem confere o extrato do banco contra a contabilidade.
Esta fase fez três coisas: (1) consertou a planilha exportada, que saía com
ponto em vez de vírgula nos centavos quando os dados vinham do relatório real;
(2) acabou com um "cara ou coroa" escondido — quando duas linhas do extrato
eram idênticas, o programa escolhia uma dependendo da ordem em que as linhas
chegavam, agora escolhe sempre pela mesma regra; (3) fez testes de esforço
(arquivo gigante, nome malicioso, anexo estranho) para provar que o programa
não trava nem deixa escapar arquivo para pasta errada — e não achou defeito
novo. Depois tudo foi testado de verdade de ponta a ponta. Os trabalhos estão
salvos nos computadores dos agentes, ainda não publicados: falta alguém com
acesso ao GitHub fazer o envio final.

---

## 2. Rodada 1 — CSV pt-BR nos dados reais (técnico)

**Problema (FAIL CT-F5-05):** `pages/analise_dados.py` monta as células
monetárias como texto en-US via `f"R$ {valor:,.2f}"` (ex. `"R$ -60.50"`,
`"R$ 1,300.00"`). `to_csv(decimal=',')` só atua em colunas numéricas, por
isso não tinha efeito nessas células de texto.
**Depois:** `gerar_csv_divergencias` normaliza a célula textual en-US para
pt-BR antes da sanitização de fórmula (`R$ -60.50`→`R$ -60,50`;
`R$ 1,300.00`→`R$ 1.300,00`), com regex que exige grupos de milhar com
exatamente 3 dígitos — célula já pt-BR (`R$ 1.234,56`) fica intocada.
Separador `;`, BOM e proteção contra formula injection preservados.
**Testes:** 4 novos usando as funções reais de `pages/analise_dados.py`
(negativo, milhar, zero, tabela de similaridades) + 1 regressão pt-BR.
Focal: `pytest tests/test_export_divergencias.py
tests/test_analise_dados_auditoria.py tests/test_data_analyzer.py` →
**26 passed**.

## 2. Rodada 1 — versão leiga

A planilha exportada saía com "ponto" nos centavos (padrão americano) porque
os valores já chegavam prontos como texto e o ajuste de vírgula não pegava
texto. Agora o programa traduz esse texto para o padrão brasileiro ("vírgula"
nos centavos, "ponto" no milhar) antes de salvar, sem mexer em quem já estava
certo — como trocar a etiqueta de preço sem rasgar a proteção antifraude.

---

## 3. Rodada 2 — desempate determinístico (técnico)

**Problema (achado da Fase 5):** `_match_valor_data_exata` iterava o extrato
na ordem física de chegada; com 2 linhas de mesmo valor/data e 1 lançamento
equivalente, o par formado dependia da ordem das linhas.
**Depois:** o extrato é ordenado por chave canônica de conteúdo — descrição
normalizada (`strip().casefold()`), `id` só como último desempate, com
fallback se não houver coluna `descricao` — antes do loop. Critério de
valor/data inalterado; nenhum outro módulo tocado.
**Testes:** o teste que documentava a ambiguidade passou a afirmar
determinismo nas duas permutações; novo teste ("Zebra" id 1 × "Abacaxi"
id 2) prova que vence o conteúdo, não o id nem a posição.
Focal (matching/análise/export/relatório/tolerância): **98 passed**.
Invariantes B×C conferidos explicitamente
(`test_padrao_do_sistema_reproduz_referencia_b_x_c` verde, 77,8% literal).

## 3. Rodada 2 — versão leiga

Era como desempatar dois candidatos iguais no "quem chegou primeiro na
fila". Agora o desempate é pelo nome em ordem alfabética (e só em último
caso pelo número de cadastro) — a mesma entrada sempre dá o mesmo resultado,
não importa a ordem da fila. A regra de quem pode empatar não mudou, só o
critério de desempate.

---

## 4. Rodada 3 — limites, DoS, temporários e cache (técnico)

**Escopo:** testes primeiro, derivados de limites já existentes
(`MAX_FILE_SIZE_BYTES` = 10 MiB; `MAX_PDF_PAGINAS`/`MAX_CNAB_LINHAS` já
cobertos na Fase 5, não duplicados). Novo arquivo
`tests/test_limites_seguranca_fase5b.py` (16 testes):
1. CSV com 50k linhas, 2.000 colunas e célula de 500 KB (dentro dos 10 MiB):
   aceitos, sem truncar nem travar (< 10 s). CSV não tem teto separado de
   linhas/colunas — documentado, não é lacuna nova.
2. OFX com DOCTYPE/ENTITY aninhadas ("billion laughs", ~3M caracteres se
   expandisse): `ofxparse` (BeautifulSoup + `html.parser`, não DTD-aware)
   **não expande** a entidade — chega literal no MEMO, ~17 ms. Defesa
   estrutural pré-existente, nada corrigido.
3. Nomes com `../`, `..\`, NUL e quebra de linha: `validar_formato_nome`
   (regex ancorada `^(B|C)_(\d+)\.(ext)$`) já rejeita; validação nunca usa o
   nome para acessar o filesystem.
4. Cache CSV/OFX: prova comportamental (dois uploads de mesmo conteúdo com
   nomes diferentes, um com traversal → 1 só parse real): chave não depende
   de nome/caminho; conteúdo diferente invalida.
**Resultado: nenhum defeito real encontrado — nenhuma correção de produção.**
Focal: novos + validação/cache relacionados → **47 passed**.

## 4. Rodada 3 — versão leiga

Foi um "teste de esforço": jogar arquivo enorme, nome com truque de invasão
(`../`) e anexo com pegadinha para ver se o programa trava, explode a
memória ou salva arquivo na pasta errada. O programa passou em tudo e nenhum
conserto foi preciso — os limites e proteções já existiam e seguraram a
onda.

---

## 5. Gate do revisor rápido — resultados reais (técnico)

Base: checkout em `624d4f8`; `git status` limpo antes e depois; **nenhum
arquivo de produção alterado nesta etapa**.

- **Pytest completo:** `python3 -m pytest tests/ -q` → **292 passed,
  1 skipped** (3 repetições: 30,92 s / 30,39 s / 29,84 s). Baseline Fase 5:
  271 + 1 → **+21 testes** (`test_limites_seguranca_fase5b.py` +16,
  `test_export_divergencias.py` 14→18, `test_matching_propriedades.py`
  17→18). Ignorado: `tests/test_pluralizacao.py:94` (pré-existente).
- **E2E real** (Streamlit local porta 8591 + Chromium headless/Playwright,
  só dados `Exemplos/`): **17/17 PASS, 0 FAIL** — vazio/binário sem
  `Traceback` nem caminho; carga 18×18; análise (`18`, `18`, delta
  `14 com correspondência`, `77.8%`, `8` divergências, `14`
  correspondências); BOM + `;` + datas + 0 célula de fórmula nos CSVs; PDF
  baixado (60.465 bytes). Evidências (4 screenshots, 3 CSVs, PDF, JSON) em
  diretório fora do repo.
- **Invariantes B×C** (UI, tela e PDF): 18×18; 11 exatos + 3 heurísticos =
  **14**; cobertura **77,8%**; efetiva **61,1%**; **4+4** divergências;
  somas 1.386,22 / 1.538,93; líquida **147,55**; resíduo **0,00**; ponte
  fecha. Idênticos nos três pontos.
- **CSV pt-BR real (CT-F5-05 → PASS):** downloads das 3 abas, 4/4 células
  `Valor_*` pt-BR em cada (ex. `R$ -60,50`, `R$ 1.300,00`, `R$ 50,63`,
  `R$ 1.400,00`); BOM, `;`, datas `dd/mm/aaaa` intactos; 0 célula
  `=`/`+`/`-`/`@`.
- **PDF executivo:** `pdfinfo` → **9 páginas**, A4, WeasyPrint 70.0;
  `pdffonts` → 4 faces Inter emb/sub/uni; varredura → 0 ocorrências de
  `admin123`, `password`, `Bearer`, `eyJ`, `Traceback`, `sqlite`, `/home/`,
  `users.db`. Texto **20.200 bytes idênticos** nos 3 PDFs (5b×5×baseline
  Fase 4) após remover carimbo de hora e ordenar linhas; raster 72 dpi:
  **6/9 páginas byte a byte iguais** vs Fase 5 (p1/p8/p9 só no retângulo da
  hora; p4 difere — ver SEC-5B-06).
- **Catálogo:** `docs/casos-de-teste.md` — nova seção Fase 5b
  (**CT-F5B-01…CT-F5B-08**: 7 PASS, 1 NÃO EXECUTADO), CT-F5-05 reescrito
  como PASS com evidência, nota no CT-F5-07 e nos achados da Fase 5, linha
  Fase 5b no resumo. Commit `0dfebee` (só md + pdf, 52 páginas).

## 5. Gate do revisor rápido — versão leiga

Depois das três mudanças, um revisor rodou tudo de verdade: quase 300 testes
automáticos passaram, e um robô abriu o programa no navegador e conferiu 17
coisas (login, carga dos arquivos, conta 18×18 fechando em 77,8%, planilhas
com vírgula certa, relatório de 9 páginas para baixar). Os números da conta
(14 pares, 8 divergências, R$ 147,55) bateram em todos os lugares. O caso que
estava reprovado (planilha com ponto) agora passa.

---

## 6. Segurança: revisão dedicada NÃO realizada + segunda opinião (técnico)

**A revisão dedicada de segurança NÃO foi realizada.** O revisor de segurança
gratuito foi invocado 3 vezes consecutivas e as 3 tentativas terminaram em
falha de provedor (`agent_error.unknown`, "Unexpected server error") sem
produzir nenhum relatório. Conforme a regra da issue, após a 3ª falha a
estratégia mudou: o arquiteto produziu uma **segunda opinião baseada apenas
nas evidências já existentes** (relatos das rodadas + gate rápido) — ela
**não é uma revisão independente, não substitui a execução dedicada e a Fase
5b NÃO está aprovada em segurança**.

### SEC-5B-01 — DoS por tamanho/estrutura — Médio, risco residual não fechado
Evidência: 50k linhas / 2.000 colunas / célula 500 KB dentro dos 10 MiB, sem
travar (< 10 s); OFX com entidades em ~17 ms sem expansão. **Não verificado:**
concorrência, memória limitada, arquivos no/acima do teto, combinações
largura×linhas custosas dentro dos 10 MiB. Decisão: sem defeito reproduzido,
nenhuma correção exigível; antes de qualquer selo, teste adversarial com
medição de tempo/memória.

### SEC-5B-02 — Path traversal, nomes e temporários — Baixo nas evidências; verificação incompleta
Evidência: `../`, `..\`, NUL e quebra de linha rejeitados pela regex
ancorada; nome não é usado para acesso ao filesystem. **Não verificado:**
diretórios temporários, symlinks, colisões, permissões, limpeza após exceção,
concorrência. Afirmar só "nomes maliciosos cobertos pelos testes citados".

### SEC-5B-03 — Cache em rerun e isolamento de chave — Médio, parcialmente verificado
Evidência: teste comportamental (mesmo conteúdo/nomes diferentes → 1 parse;
conteúdo diferente invalida; chave sem caminho). **Não verificado:** rerun
real do Streamlit (não observável pela UI), escopo/TTL, invalidação por
versão de parser, mutabilidade do retorno, isolamento entre usuários/sessões.
Separar "cache instrumentado: coberto" de "rerun/concorrência/isolamento:
não verificados".

### SEC-5B-04 — CSV e formula injection — Baixo no coberto; payloads completos não auditados
Evidência: exports reais com BOM/`;`/datas e 0 célula `=`/`+`/`-`/`@`;
proteção exercitada com payloads sintéticos. **Não verificado:** dados reais
não continham payload perigoso; faltam matriz completa de prefixos, espaços/
tabulações precedentes, aspas, quebras de linha, Unicode. Não declarar
"formula injection completamente auditada".

### SEC-5B-05 — Logging e exposição de dados — Baixo, evidência insuficiente
Evidência: 8 linhas JSONL válidas; PDF sem `admin123`/`password`/`Bearer`/
JWT/`sqlite`/caminhos/`users.db`. **Não verificado:** redaction sob erro,
nomes/caminhos temporários, conteúdo de transações, stack traces, correlação
entre usuários. Revisão adversarial de redaction pendente.

### SEC-5B-06 — Ordem canônica no PDF — compatibilidade, NÃO segurança (aceita)
O desempate (Rodada 2) mudou a **ordem observável das 11 linhas de
"Casamentos exatos"** (antes: ordem de chegada; agora: descrição
normalizada) — visível no raster da p4 (9.541 px, 1,90%). **Decisão do
líder: a ordem canônica global foi aceita.** Conteúdo idêntico (mesmas 11
linhas/valores, subtotal `R$ -1.283,57`), totais, invariantes B×C, layout e
9 páginas preservados (texto idêntico após ordenação). Não é FAIL nem
vulnerabilidade; fica registrada como mudança compatível aceita. Recomendação
futura do arquiteto (restringir a reordenação aos empatados reais) segue como
melhoria opcional, não exigência.

## 6. Segurança — versão leiga

A vistoria de segurança de verdade **não aconteceu**: o vistoriador foi
chamado 3 vezes e o sistema dele caiu as 3 vezes antes de entregar qualquer
relatório. No lugar, o arquiteto deu uma segunda opinião lendo os testes que
já existiam — útil, mas **não vale como aprovação de segurança**. Resumo:
nada indica invasão ou defeito grave, mas seguem sem checagem profunda o
comportamento sob ataque pesado ao mesmo tempo, a pasta de arquivos
temporários, o isolamento do "atalho de memória" entre usuários, todos os
truques possíveis de fórmula maliciosa na planilha e o sigilo total dos
registros. E a nova ordem alfabética das 11 linhas no relatório **foi aceita
pela chefia**: mesmos valores e totais, só a ordem mudou.

---

## 7. Limitações e o que NÃO foi verificado (técnico + leiga)

- **Segurança dedicada: NÃO executada** (3× `agent_error.unknown`); sem selo
  de segurança — aceite final condicionado ao responsável humano aceitar a
  lacuna ou a uma futura revisão dedicada.
- `CT-AUTH-03` (15 min) e `CT-AUTH-05` (expiração de sessão): **não
  executados** — casos de tempo real, exigem confirmação do usuário.
  (Leiga: dois testes que exigem esperar 15 minutos com o cronômetro ligado
  ficaram de fora.)
- Cache em reruns reais, concorrência/memória, temporários/symlinks,
  payloads completos de fórmula e redaction adversarial de logs: **não
  verificados** (detalhes em SEC-5B-01…05).
- Geração repetida do PDF na mesma rodada não foi feita (comparação contra
  2 baselines); log estruturado conferido só no escopo da Fase 5.
- **Tokens por agente/rodada: indisponíveis** — o ambiente de execução não
  expõe a métrica; nenhum número é declarado (todos os agentes relataram o
  mesmo, com chamadas bem abaixo do teto de ~35 por rodada). Não inventar
  números.

---

## 8. Como conferir (comandos reais reportados)

```bash
git fetch origin fase5-squad-xcre-49   # base 871e833 "docs: documentacao final fase 5"
python3 -m pytest tests/ -q            # 292 passed, 1 skipped
pytest tests/test_export_divergencias.py tests/test_analise_dados_auditoria.py tests/test_data_analyzer.py  # 26 passed (R1)
pytest tests/test_data_analyzer.py tests/test_tolerancia_referencia_b_x_c.py tests/test_pares_provaveis_e_ponte_detalhada.py tests/test_relatorio_executivo.py tests/test_matching_propriedades.py tests/test_export_divergencias.py tests/test_analise_dados_auditoria.py  # 98 passed (R2)
pytest tests/test_limites_seguranca_fase5b.py -v  # 16 passed (R3)
pytest tests/test_limites_seguranca_fase5b.py tests/test_validacao_entrada_ofx_csv.py tests/test_importacao_limites.py tests/test_cache_parsing.py -q  # 47 passed (R3+relacionados)
```

Este documento declara apenas cobertura com evidência acima; todo o resto
está marcado como não verificado.
