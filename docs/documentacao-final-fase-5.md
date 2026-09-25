# conc_banc — Fase 5: documentação final (5 melhorias de robustez)

Fase 5 (sintética, XCRE-49) do app de conciliação bancária (Streamlit): 5 itens
independentes de robustez/qualidade, maiores que os da fase 4 (envolvem lógica
nova), sem mudar nenhum número do caso B×C (14 correspondências, 77,8%,
efetiva 61,1%, 4+4 divergências, diferença líquida 147,55, resíduo 0,00) nem o
layout do relatório executivo. Base: `main` @ `7bf1e2b` (fase 4).
Login de teste: `admin` / `admin123` (conta bootstrap local, dados sintéticos
em `Exemplos/B_1234490.ofx` e `Exemplos/C_1234490.ofx`).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga**
(analogia do dia a dia). Este documento apenas relata o que os agentes
responsáveis executaram e reportaram na issue — nada foi marcado como
verificado sem execução real, e o que não foi verificado está declarado como
tal. Este documento não altera código nem nenhum outro documento.

> Nota de procedência: os commits `4fbad6d`, `13a3ca3`, `65ddf04`, `265ad97`,
> `6e78c14` (5 itens) e `915d864` (catálogo) estão em worktrees/branches
> locais de outros agentes e **não foram publicados (sem push/PR — o squad não
> tem credencial Git)**. Este arquivo foi escrito nesta branch a partir do
> `main`. O conteúdo abaixo reproduz fielmente os relatos dos agentes na
> issue, sem reexecução independente nesta etapa de documentação. Nenhuma
> verificação foi inventada.

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Item | Commit (local, sem push) | O que faz |
|------|--------------------------|-----------|
| 1 — Validação de entrada OFX/CSV | `4fbad6d` | `validar_entrada_csv` / `validar_entrada_ofx` em `pages/importacao_dados.py`, chamadas em `processar_arquivo` antes do parsing; mensagens fixas em português, sem stack trace nem caminho |
| 2 — Exportação CSV das divergências | `13a3ca3` | Novo `modules/export_divergencias.py::gerar_csv_divergencias` (`;`, decimal `,`, UTF-8 com BOM, anti-formula-injection, ordenação determinística); 3 `to_csv()` de `pages/analise_dados.py` passam a usá-la |
| 3 — Testes de propriedade do matching (só testes) | `65ddf04` | Novo `tests/test_matching_propriedades.py` (17 casos, seed fixa); `modules/data_analyzer.py` intocado; inclui achado de ambiguidade registrado sem correção |
| 4 — Cache do parsing | `265ad97` | `_parsear_csv_cacheado` / `_parsear_ofx_cacheado` com `st.cache_data` (só bytes + encoding); `validar_entrada_csv` / `processar_ofx` passam a usá-las |
| 5 — Log estruturado JSONL | `6e78c14` | Novo `modules/structured_logger.py` (login, carga, análise, relatório; só contagens/formato/duração/categoria) + instrumentação em `app.py`, `pages/importacao_dados.py`, `pages/analise_dados.py`, `pages/gerar_relatorio.py`; `*.jsonl` no `.gitignore` |
| Verificação + catálogo | `915d864` | Só `docs/casos-de-teste.md` (seção única "Fase 5", CT-F5-01…CT-F5-13) + `docs/casos-de-teste.pdf` regenerado (44 páginas) |
| este doc | branch atual | `docs/documentacao-final-fase-5.md` (este arquivo) |

Nenhum item alterou matching, números B×C ou layout — confirmado a cada rodada
pela checagem mínima do invariante de 77,8%.

## 1. O que foi entregue — versão leiga

Pense no app como um escritório que confere o extrato do banco contra a
contabilidade. Esta fase fez 5 reforços sem mexer no resultado da conta:
(1) um "porteiro" que barra arquivo vazio, binário ou com coluna faltando e
avisa em português claro; (2) um botão que exporta as divergências num CSV
brasileiro e protege contra truques de planilha; (3) uma bateria de testes que
checa as regras do pareamento sem mudar o pareamento; (4) uma "fotocópia
guardada" para não reler o mesmo arquivo toda hora; (5) um "diário de bordo"
em formato de máquina que anota o que aconteceu sem anotar senha nem dado
sensível. Tudo foi testado de verdade, e o que não passou ou não deu para
testar está escrito abaixo. Os trabalhos estão salvos nos computadores dos
agentes, ainda não publicados.

---

## 2. Item 1 — validação de entrada (técnico)

**Antes:** CSV vazio/binário/sem colunas só falhava dentro de
`pd.read_csv`/`ofxparse`, e a mensagem crua da exceção (inglês) ia para
`st.error`. **Depois:** duas funções puras e testáveis barram antes do
parsing — extensão `.csv`/`.ofx`, vazio, binário (heurística por byte NUL,
independente de decodificação), encoding (`utf-8` → `latin-1` → `cp1252` →
`iso-8859-1`, mesma ordem dos demais parsers), colunas obrigatórias (ao menos
uma "data" + uma "valor", mesmos padrões de `modules/file_processor.py`) e
cabeçalho `OFX`. Reaproveitado sem mudar semântica: limite
`MAX_FILE_SIZE_BYTES = 10*1024*1024` = **10.485.760 bytes (10 MiB)**, embora a
mensagem diga só "10MB".
Testes focados: `tests/test_validacao_entrada_ofx_csv.py` — **17 passed**
(coleta real; o relato da rodada declarou "22", contagem que não confere —
ver CT-F5-03). Sem suíte completa/E2E/rasterização nesta rodada.

## 2. Item 1 — versão leiga

Era como entregar qualquer papel na portaria e só descobrir o erro lá dentro,
com um carimbo em inglês. Agora o porteiro confere na entrada (tamanho,
tipo, se está em branco, se é ilegível, se tem as colunas de data e valor) e
diz em português o que está errado, sem mostrar caminho interno nem erro
técnico. Detalhe: o limite é 10 MiB (um pouco mais que "10 milhões de bytes"),
mas o aviso resume como "10MB".

---

## 3. Item 2 — exportação CSV das divergências (técnico)

Nova `gerar_csv_divergencias(df, ordenar_por=None) -> bytes`: separador `;`,
decimal `,` (só em coluna numérica via `to_csv(decimal=',')`; colunas já
formatadas como texto — ex. `R$ 1.234,56`, datas `dd/mm/aaaa` — preservadas),
UTF-8 com BOM (`utf-8-sig`), anti-formula-injection (célula de texto iniciada
por `=`/`+`/`-`/`@` recebe apóstrofo; só na cópia exportada), ordem de entrada
preservada por padrão + `ordenar_por` estável opcional. Os 3 `to_csv()` de
`pages/analise_dados.py` (aba Divergências) passam a usá-la.
Testes focados: `tests/test_export_divergencias.py` — **14 passed**
(sintéticos) + 1 checagem B×C mínima verde. Fora de escopo e não tocado:
`pages/gerar_relatorio.py` mantém 3 `to_csv()` puros (sem BOM/`;`/proteção).

## 3. Item 2 — versão leiga

O botão de "baixar divergências" agora entrega um CSV no padrão brasileiro
(ponto-e-vírgula, BOM para o Excel abrir com acento) e coloca um apóstrofo na
frente de qualquer célula que comece com `=`, `+`, `-` ou `@` — isso impede
que a planilha execute a célula como fórmula (golpe clássico). Mas atenção:
nos dados reais o decimal com vírgula **não funcionou** (ver seção 7, FAIL) —
esse ponto ficou pendente.

---

## 4. Item 3 — testes de propriedade do matching + achado (técnico)

Só testes, `modules/data_analyzer.py` intocado. 17 casos com seed fixa:
invariância à ordem (inversão + embaralho com RNG), unicidade (nenhum id em
dois pares), recomposição (casados + divergentes = total por lado, em valor e
contagem), idempotência (chamadas repetidas, instância nova ou reaproveitada).
**Achado real, registrado sem correção** (`65ddf04`,
`test_matching_ambiguidade_mesma_data_e_valor_depende_da_ordem_das_linhas`):
`_match_valor_data_exata` consome o candidato na ordem de `iterrows()`; com
ambiguidade (2 extratos valor=100 mesma data × 1 contábil igual), ordem
`[1,2]` casa `(1,10)`, ordem `[2,1]` casa `(2,10)` — a forma (1 par + 1 sobra)
é igual, o id casado muda. Teste verde porque descreve o comportamento real,
sem `skip`/`xfail` nem asserção enfraquecida. Impacto B×C: nenhum (sem
duplicatas de valor+data no cenário de referência).
Testes: **17 passed** + B×C mínimo + `test_data_analyzer.py` 6 passed.

## 4. Item 3 — versão leiga

Em vez de testar um caso só, testaram as "regras do jogo" do pareamento: tanto
faz a ordem das linhas, ninguém pode aparecer em dois pares, a soma tem que
fechar, repetir tem que dar igual. Acharam um caso em que a ordem importa: se
houver dois lançamentos idênticos (mesmo valor e data) disputando um só do
outro lado, quem chega primeiro leva — qual nome casa muda com a ordem. Foi
anotado como achado e **não consertado** (regra da fase), e não afeta a conta
B×C de referência.

---

## 5. Item 4 — cache do parsing (técnico)

Achado de contexto: `cache_manager` (`modules/performance_optimizer.py`) já
existia mas nunca era usado no parsing real — cada rerun do Streamlit
reprocessava o upload. Também tem bug preexistente (`time.time()` sem `import
time`), não tocado (fora de escopo). O item isolou o núcleo em duas funções
puras com `st.cache_data` (só `bytes` + `encoding`), sem sessão/nome/credencial;
metadados de sessão aplicados depois. `st.cache_data` devolve cópia — mutação
externa não contamina (testado) + guarda de regressão na assinatura.
Testes: `tests/test_cache_parsing.py` — **9 passed** (bytes iguais não
reparseiam, diferentes reparseiam, encoding diferente invalida, sem
contaminação, sem coluna de sessão) + item 1 intacto (17) + B×C mínimo.
Cache em rerun real do Streamlit: **NÃO VERIFICADO** (não observável pela UI).

## 5. Item 4 — versão leiga

Antes, toda vez que você mexia na página, o app relia o arquivo inteiro do
zero. Agora ele guarda a "fotocópia" pelo conteúdo (impressão digital dos
bytes): se é o mesmo arquivo, reaproveita; se mudou uma vírgula, lê de novo.
O teste confirma isso no laboratório, mas ninguém conseguiu ver a economia
acontecendo de verdade na tela — esse ponto ficou como não verificado.

---

## 6. Item 5 — log estruturado JSONL (técnico)

Não existia log JSON linha a linha (só `basicConfig` texto livre; `audit_logger`
SQLite é outro sistema, mais detalhado). Novo `modules/structured_logger.py`
com rotação por tamanho igual à do `AuditLogger`, configurável por
`CONCILIACAO_STRUCTURED_LOG_PATH` / `..._MAX_SIZE_MB`; 4 eventos só com
contagens/formato/duração/categoria fixa (`log_login`, `log_carga_arquivo`,
`log_analise`, `log_geracao_relatorio`); `registrar()` recusa com `ValueError`
sem gravar campo com nome proibido; `log_*` só aceitam motivos de conjunto
fixo (nunca mensagem crua de exceção). Integração real (só instrumentação):
`app.login_user` (5 desfechos; usuário só no sucesso),
`processar_arquivo` (categoria via `_categorizar_motivo_carga_arquivo`, nunca a
mensagem com nome do upload), `analise_dados` (contagens agregadas),
`gerar_relatorio` (5 desfechos). `.gitignore`: `*.jsonl`.
Testes: `tests/test_structured_logger.py` — **23 passed** (parseabilidade,
4 eventos, rotação, varredura B×C sintética, 2 integrações via `login_user`
real) + regressões de itens 1/4, auditoria, autenticação e B×C mínimo.

## 6. Item 5 — versão leiga

Criaram um "diário de bordo" que escreve uma linha por acontecimento (login,
carga, análise, relatório) num formato que máquina lê fácil, anotando só
quantidades e tempos — nunca senha, nome de transação ou valor. Ele até se
recusa a gravar se alguém tentar passar um campo proibido. Ressalva: no login
com sucesso ele grava `"usuario": "admin"` — é só o nome, não segredo, mas
foge do combinado "só contagens" e ficou para a segurança avaliar.

---

## 7. Resultados reais da verificação integrada (técnico + leigo)

Reportados pelo desenvolvedor_revisor_rápido, com execução real (nada corrigido
na verificação; divergências isoladas abaixo):

- **Suíte completa:** `python3 -m pytest tests/ -q` → **271 passed, 1 skipped,
  40 warnings em 25,43 s** (2 execuções, mesmo resultado). Baseline fase 4:
  191 passed, 1 skipped → **+80** = 17 + 14 + 17 + 9 + 23 (os 5 arquivos
  novos). Ignorado: o mesmo do baseline (`test_pluralizacao.py:94`). Em leigo:
  todos os testes automáticos passaram, 1 pulado de propósito.
- **E2E real 13/13 PASS:** Streamlit local porta 8591 + Chromium headless,
  só sintéticos; vazio e binário barrados em português sem `Traceback`/caminho;
  fluxo login → importação B×C (18×18) → análise → CSV → PDF; métricas
  (`18/18`, "14 com correspondência", `77.8%`, `Itens em Divergência 8`); CSV
  (BOM `EF BB BF`, `;`, 4 linhas, `dd/mm/aaaa`, 0 fórmulas); PDF Executivo
  (60.468 bytes). Servidores encerrados.
- **Invariantes B×C:** 18×18, 11 exatos + 3 heurísticos = **14**, **77,8%**,
  efetiva **61,1%**, **4+4** divergências, **R$ 1.386,22** / **R$ 1.538,93**,
  líquida **R$ 147,55**, resíduo **R$ 0,00**, ponte fecha. Idênticos ao baseline.
- **PDF × baseline (`7bf1e2b`):** 9 páginas A4 nos dois, WeasyPrint 70.0;
  texto (`pdftotext -layout`) idêntico nas 20.200 bytes **exceto 3 linhas do
  carimbo** (`10:55` × `10:51`); raster 72 dpi: 6/9 páginas byte a byte iguais,
  páginas 1/8/9 com 34/31/40 pixels (0,006–0,008%) dentro do retângulo da data.
  **Layout e números inalterados.** Sem `admin123`/Bearer/JWT/`Traceback`.
- **Log real:** 8 linhas, 8 JSONs válidos (login ×2, carga ×4, análise ×1,
  relatório ×1); varredura contra senha/hash/conteúdo/descrições/valores/
  caminho/`Traceback`: **0 ocorrências**.
- **Catálogo:** `docs/casos-de-teste.md` seção Fase 5 com **CT-F5-01…CT-F5-13
  (11 PASS, 1 FAIL, 1 NÃO EXECUTADO)**; PDF regerado pelo pipeline real
  (`scripts/gerar_pdf_casos_de_teste.py`) → **44 páginas**. Commit `915d864`.

### Tabela CT-F5 (status reais, sem presunção)

| Caso | Assunto | Status |
|------|---------|--------|
| CT-F5-01 | Vazio barrado na UI | PASS |
| CT-F5-02 | Binário barrado na UI | PASS |
| CT-F5-03 | Extensão/colunas/encoding/10 MiB (automatizado) | PASS (com divergência de contagem: 17 coletados, não 22) |
| CT-F5-04 | CSV real: BOM, `;`, datas, 4 divergências | PASS |
| CT-F5-05 | CSV real: decimal `,` | **FAIL** — sai `R$ -60.50`, `R$ -4.92`, `R$ 1,300.00`, `R$ -20.80`; `decimal=','` só vale p/ coluna numérica, tabelas reais chegam como texto en-US |
| CT-F5-06 | Anti-formula-injection | PASS (sintéticos; 0 células maliciosas no B×C real) |
| CT-F5-07 | Propriedades do matching + ambiguidade | PASS (17/17; achado registrado, sem impacto B×C) |
| CT-F5-08 | Cache por hash | PASS (9/9; rerun real NÃO VERIFICADO) |
| CT-F5-09 | JSONL real sem sensível | PASS (8/8 JSONs, 0 ocorrências; ressalva `usuario: admin`) |
| CT-F5-10 | Suíte completa 271/1 | PASS |
| CT-F5-11 | Invariantes B×C | PASS |
| CT-F5-12 | PDF/layout idêntico | PASS |
| CT-F5-13 | Itens não verificáveis | **NÃO EXECUTADO** (registro, não teste) |

---

## 8. Economia de cota — tokens por rodada (técnico + leigo)

Regra da issue: 1 item por rodada para o Claude (desenvolvedor_principal), sem
suíte completa/E2E/raster por ele. Valores **reportados pelo próprio Claude**
(não verificáveis pelo revisor):

| Rodada | Consumo aprox. reportado |
|--------|--------------------------|
| Item 1 (validação) | ~154 mil tokens |
| Item 2 (export CSV) | ~110 mil tokens |
| Item 3 (propriedades + achado) | ~95 mil tokens |
| Item 4 (cache) | ~100 mil tokens |
| Item 5 (log JSONL) | ~140 mil tokens |
| **Total desenvolvedor principal** | **~599 mil tokens agregados** |

Em leigo: para economizar, cada reforço foi feito separado, um por vez, e o
robô que fez anotou quanta "energia" gastou em cada um. A soma dá cerca de 599
mil. Esses números vieram do próprio robô — ninguém mediu de fora.
**Sem push e sem PR** — o squad não tem credencial Git.

---

## 9. Segurança — revisão bloqueada + segunda opinião (técnico + leigo)

**Revisão dedicada NÃO REALIZADA (bloqueada):** 3 tentativas do revisor de
segurança terminaram em `agent_error.unknown` ("Unexpected server error"),
sem produzir resultado. Por regra de limite de tentativas, a etapa não foi
repetida uma 4ª vez. Status oficial: **NÃO EXECUTADO / BLOQUEADO por
indisponibilidade do provedor**.

**Segunda opinião (arquiteto, sem editar código, sem espera real):**

| Área | Classificação | Avaliação |
|---|---|---|
| Limite de upload | Verificado, com ressalva | 10 MiB aplicado antes do parsing (teste + E2E); vazio/binário barrados sem stack trace; mensagem "10MB" imprecisa |
| DoS/memória de parsing | NÃO VERIFICÁVEL | Sem teste de pressão/concorrência/entradas adversariais; limite de bytes reduz risco, não prova CPU/memória |
| Traversal/nome de arquivo | NÃO VERIFICÁVEL | Mensagens não expõem caminho, mas sem auditoria de temporários/cache/logs/destinos |
| CSV injection — novo exportador | Verificado só em sintéticos | Apóstrofo p/ `=`/`+`/`-`/`@` comprovado; sem payload malicioso no fluxo E2E real |
| CSV injection — exportações legadas | Risco/achado | 3 botões em `pages/gerar_relatorio.py` com `to_csv()` puro — superfície potencial até sanitizar |
| Logs estruturados | Verificado, com achado | 8 JSONL válidos, 0 vazamentos na varredura; rejeição runtime de campos proibidos |
| `usuario: admin` no log | Risco baixo | Identificador, não segredo, mas viola "só contagens…"; remover ou trocar por id de sessão não reversível |
| Mensagens de erro | Verificado no escopo exercitado | Vazio/binário em português, sem caminho/`Traceback`; demais exceções de terceiros não comprovadas |
| Autenticação/exposição | Parcial; lacuna | Login/E2E sem expor `admin123`/Bearer/JWT; expiração e 15 min NÃO EXECUTADOS (exigem autorização) |
| Temporários/cache/isolamento | NÃO VERIFICÁVEL | Cache só em testes instrumentados; sem evidência de limpeza/permissões/isolamento entre sessões |
| Matching | Risco operacional documentado | Ambiguidade registrada, sem impacto B×C; manter explícito, não tratar como resolvido |

Em leigo: o "cadeado" dedicado nunca conseguiu entrar — o sistema dele caiu 3
vezes. Um segundo especialista fez só uma vistoria pelos papéis: o básico
(limite, recados em português, diário sem senha) parece bom, mas faltam os
testes de ataque de verdade (arquivo gigante malicioso, nome de arquivo
virando caminho, vários usuários ao mesmo tempo, tempo de bloqueio de login).
Três pendências concretas: os botões antigos de exportar de outra página
continuam sem proteção, o diário grava o nome `admin`, e o CSV real não saiu
com vírgula (FAIL acima). Nada disso foi consertado nesta fase.

---

## 10. Limitações — o que NÃO foi verificado (técnico + leigo)

1. **Segurança profunda NÃO EXECUTADA** — DoS adversarial, traversal/
   temporários, cache em rerun real, autenticação temporal e exportações
   legadas seguem pendentes (ver seção 9).
2. **CT-F5-05 = FAIL** — decimal `,` não atendido nos dados reais (requisito
   funcional do item 2 pendente; números/layout/PDF não afetados).
3. **Cache em rerun real NÃO VERIFICADO** — só 9 testes instrumentados;
   injeção com dado malicioso real idem (B×C não tem célula `=`/`+`/`-`/`@`).
4. **`CT-AUTH-03` (15 min) e `CT-AUTH-05` (expiração) NÃO EXECUTADOS** —
   exigem confirmação humana explícita; seguem como na fase 4.
5. **Relatório legado `Completo`, nuvem/produção e app publicado NÃO
   VERIFICADOS** — só ambiente local; arquitetura/design fora do escopo
   (só "rodar e conferir").
6. **Contagem do item 1 divergente** — relato disse 22, coleta real é 17
   (comportamento PASS, contagem do relato errada); `gerar_relatorio.py` sem
   proteção e bug `cache_manager` (`time` sem import) registrados como
   pendências preexistentes/fora de escopo.
7. **Sem push/PR** — 5 commits + catálogo só em worktrees locais.

Em leigo: o que ficou de fora — o teste de ataque de verdade, o teste com o
olho no rerun da tela, os dois testes de espera de login, o relatório antigo,
a nuvem e o envio final para o GitHub. E um ponto vermelho: o CSV real não
respeitou a vírgula decimal pedida. Tudo está anotado para ninguém achar que
passou sem ter passado.
