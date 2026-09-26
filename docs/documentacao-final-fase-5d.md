# conc_banc — Fase 5d: documentação final (migração PyPDF2 → pypdf e mensagem única de limite)

Fase 5d do app de conciliação bancária (Streamlit): troca a biblioteca de
leitura/escrita de PDF (`PyPDF2` 3.0.1 → `pypdf==6.19.0`, fechando o último
achado do `pip-audit`) e corrige a rejeição de arquivos acima do limite
(OFX/CSV), que mostrava 3 mensagens onde deveria mostrar 1.
Base: `origin/main` (`22fd0fd`, com as fases 1 a 5c). Dados 100% sintéticos;
nenhum dado real foi usado. Login de teste `admin` / `admin123` (risco aceito,
não alterado) e SEC-R-06 (chave JWT sem variável, aceito, não alterado).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga**
(analogia do dia a dia). Este documento apenas consolida o que os agentes
responsáveis executaram e reportaram na issue (XCRE-53) — nada foi marcado
como verificado sem execução real, e o que não foi verificado está declarado
como tal (seção 7). Esta etapa de documentação **não executou novos testes**
e **não alterou** `docs/casos-de-teste.md` nem nenhum código.

> Nota de procedência: os commits `1c81a9f` (D1), `2dfcc5a` (D2) e `abb3aa6`
> (R1 — seção Fase 5d do catálogo, CT-F5D-01…08) estão na branch
> `agent/desenvolvedor-revisor-rapido-g/128ce88986da` (**sem push — o squad
> não tem credencial Git**). Este arquivo foi escrito e commitado na branch
> atual, que foi avançada em fast-forward até `abb3aa6` e portanto contém
> D1, D2 e R1 (mesmos hashes, sem rebase). O conteúdo abaixo reproduz
> fielmente os relatos das rodadas D1, D2, R1 e A1 na issue, sem reexecução
> nesta etapa.

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Etapa | Commit (local, sem push) | O que faz |
|-------|--------------------------|-----------|
| D1 — migração de PDF | `1c81a9f` (5 arquivos, +61/−7) | `pages/importacao_dados.py`, `requirements.txt`, `tests/test_importacao_limites.py`, `tests/test_relatorio_executivo.py`, `tests/test_report_generator.py`: troca `PyPDF2` por `pypdf==6.19.0` + 2 testes novos de contrato da lib |
| D2 — mensagem única por limite | `2dfcc5a` (3 arquivos, +368/−12) | `modules/structured_logger.py`, `pages/importacao_dados.py`, `tests/test_importacao_mensagem_unica_limite.py` (novo, 5 testes): allowlist + sentinela de rejeição |
| R1 — verificação integrada + catálogo | `abb3aa6` | Só `docs/casos-de-teste.md` (seção Fase 5d, CT-F5D-01…08) + `docs/casos-de-teste.pdf` regenerado (67 páginas). Nenhum código de produção alterado |
| A1 — re-verificação independente | sem commit (worktree limpo antes e depois) | `pip-audit` limpo + 3 cenários de PDF re-executados; conclusão **FECHADO**, sem divergência funcional vs R1 |
| este doc | branch atual | `docs/documentacao-final-fase-5d.md` (este arquivo) |

Nenhum número do baseline B×C foi alterado em nenhuma rodada.

## 1. O que foi entregue — versão leiga

Pense no sistema como quem confere o extrato do banco contra a contabilidade.
Esta fase fez dois consertos: (1) trocou uma peça enferrujada e sem conserto
(a biblioteca `PyPDF2`, com falha de segurança conhecida) por uma peça nova e
vistoriada (`pypdf`, mesma função de ler e montar PDFs); (2) corrigiu a
"central de avisos": quando um arquivo gigante era barrado na porta, o sistema
gritava a mesma recusa três vezes de jeitos diferentes — agora avisa uma única
vez, clara. Tudo foi testado de verdade depois, inclusive com um extrato
falso de 25.000 lançamentos. Os trabalhos estão salvos nos computadores dos
agentes, ainda não publicados: falta alguém com acesso ao GitHub fazer o
envio final.

---

## 2. D1 — migração PyPDF2 → pypdf==6.19.0 (técnico)

**Problema:** `PyPDF2` está descontinuada e a versão 3.0.1 tinha a
vulnerabilidade PYSEC-2026-1835, sem correção na própria lib. O app lia o PDF
enviado pelo usuário em `pages/importacao_dados.py` (`processar_pdf`,
~linha 1092) e vários testes importavam `PyPDF2` direto.

**Mudança:** busca completa (`grep -rniI "PyPDF2"` em app, `pages/`,
`modules/`, `tests/`, `requirements.txt`) achou 4 usos, todos migrados para
`pypdf` (API básica compatível: `PdfReader`/`PdfWriter`). `requirements.txt`
passou a fixar `pypdf==6.19.0` — a mais recente publicada no PyPI no momento
da execução, escolhida por passar no `pip-audit`, não por ser a do ambiente.
Restam apenas menções textuais a `PyPDF2` em documentos históricos (fases
anteriores) e em docstrings de 2 testes novos; nenhum `import` de `PyPDF2`
permanece no código (confirmado por `grep` e, na R1, por bloqueio de import).

**Compatibilidade registrada:** `pypdf` usa hierarquia de exceções diferente
(ex.: `PdfStreamError` em vez de `PdfReadError`); o `except Exception` já
existente em `processar_pdf` absorve a diferença — coberto por teste novo de
PDF malformado. Leitura continua respeitando `MAX_PDF_PAGINAS`.

**Validação da rodada:** instalação limpa (`uv venv`, fora do repo) + `import
app` em Python 3.10.12, 3.12.14 e 3.13.15 — OK nas três (venvs removidas
depois). Testes da área (`test_importacao_limites.py`,
`test_report_generator.py`, `test_relatorio_executivo.py`): **41 passed** nas
3 versões. `pip-audit -r requirements.txt --no-deps` em venv separada:
**"No known vulnerabilities found"**.

## 2. D1 — versão leiga

A peça que lê PDFs era de um fabricante que faliu e tinha um defeito sem
conserto. O mecânico trocou pela peça nova do mesmo encaixe, testou o carro
em três modelos de motor (Python 3.10, 3.12 e 3.13) e a vistoria de segurança
(`pip-audit`) saiu limpa.

---

## 3. D2 — uma única mensagem na rejeição por limite (técnico)

**Problema (achado do E2E da 5c):** ao subir um OFX com 25.000 transações, o
app mostrava a mensagem certa ("tem 25000 transações, acima do limite de
20000 transações por importação") **mais** duas redundantes ("motivo de carga
de arquivo desconhecido: 'limite_transacoes_excedido'" e "Não foi possível
extrair dados do arquivo").

**Causa raiz (confirmada por leitura de código; diferente da hipótese inicial
da issue):** duas camadas. (1) `_categorizar_motivo_carga_arquivo`
(`pages/importacao_dados.py`) já categorizava os 4 motivos de limite, mas a
allowlist `MOTIVOS_CARGA_ARQUIVO` (`modules/structured_logger.py`) não os
continha — `log_carga_arquivo` levantava `ValueError`, capturada pelo `except`
amplo de `processar_arquivo` (2ª mensagem). (2) `processar_arquivo` devolvia
`None`, indistinguível de "nada extraído", e o fluxo de upload exibia a
mensagem genérica por cima (3ª mensagem).

**Correção:** allowlist passa a conter os 4 motivos (`limite_transacoes_`,
`limite_linhas_`, `limite_colunas_`, `limite_campo_excedido`);
`processar_arquivo` devolve a sentinela `ARQUIVO_REJEITADO_POR_LIMITE` em vez
de `None` nas rejeições por limite; os 4 chamadores
(`pages/importacao_dados.py:1361`, `:1373`, `:1453`, `:1489`) usam
`isinstance(df, pd.DataFrame)` e só mostram a mensagem genérica quando o
retorno é `None` de verdade. Preservados: arquivos válidos, erros de parsing
não relacionados e o limite de páginas de PDF.

**Testes (TDD — escritos antes da correção, falharam antes, passaram depois):**
novo `tests/test_importacao_mensagem_unica_limite.py` (padrão de
`tests/test_seguranca_limites_estruturais.py`): 4 testes em `processar_arquivo`
(OFX 25k; CSV linhas/colunas/campo) + 1 de página completa via
`streamlit.testing.v1.AppTest` (em processo, não é E2E) que reproduziu as 3
mensagens exatas antes da correção. Suíte da área na rodada: **131 passed**.

## 3. D2 — versão leiga

Quando o porteiro barrava um arquivo gigante, ele avisava certo — mas aí o
escritório, sem entender o código do aviso, gritava "erro desconhecido!" e a
recepção completava "não consegui ler nada!". O conserto teve duas partes:
ensinar o escritório os 4 códigos de recusa e dar ao porteiro um carimbo
próprio de "barrado no limite", para a recepção não falar por cima. Os testes
encenaram a confusão antes do conserto (3 avisos) e confirmaram 1 aviso só
depois.

---

## 4. R1 — verificação integrada: pytest, E2E, invariantes e PDF (técnico)

Checkout em fast-forward de `22fd0fd` até `2dfcc5a` — mesmos hashes de D1/D2,
sem rebase. `git diff --stat 22fd0fd..2dfcc5a` → 7 arquivos, +429/−19.

- **Suíte completa:** `python3 -m pytest tests/ -q` → **393 passed, 1 skipped**
  (3 execuções: 46,07 s / 47,09 s / 55,87 s; 394 coletados). Baseline
  `22fd0fd`: 386 passed + 1 skipped → **+7 testes**. Único skip:
  `tests/test_pluralizacao.py:94` (igual ao baseline). Migração confirmada por
  execução: área PDF/importação/relatório/smoke rodada com `PyPDF2` bloqueado
  no `sys.meta_path` → **47 passed**.
- **E2E real** (Streamlit local porta 8593 + Chromium headless via Playwright,
  banco zerado, `admin`/`admin123`, ~105 s): **21 de 21 verificações PASS,
  0 FAIL** — login, importação 18×18, análise, 3 CSVs baixados, PDF Executivo
  baixado. OFX de 25.000 → **exatamente UMA mensagem de erro** (4 alertas no
  total: 2 `st.info`, 1 do spinner, 1 erro com "tem 25000 transações, acima do
  limite de 20000"); 0 ocorrências de "motivo de carga de arquivo
  desconhecido", "Não foi possível extrair" ou `Traceback`; log estruturado
  grava `motivo=limite_transacoes_excedido, sucesso=false` sem `ValueError`.
- **Invariantes B×C (idênticos na UI e no PDF):** 18×18, 11+3=14, **77,8%**,
  efetiva **61,1%**, **4+4** divergências, somas 1.386,22 / 1.538,93,
  diferença líquida **147,55**, resíduo **0,00**.
- **PDF Executivo:** `pdfinfo` → **9 páginas**, A4, WeasyPrint 70.0, 60.462
  bytes; 4 faces Inter embutidas; texto com "77,8%", "61,1%", "Diferença
  líquida de R$ 147,55", "Resíduo … R$ 0,00"; 0 ocorrências sensíveis
  (`admin123`, `Bearer`, `eyJ`, `Traceback`, `/home/`, `/tmp/`, `users.db`);
  `diff` contra o baseline da 5c = 12 linhas, só o carimbo de hora — fora o
  carimbo, texto idêntico. Rasterização não repetida (fora do escopo).
- **Falhas:** nenhuma; nada devolvido a D1/D2. Registro completo em
  CT-F5D-01…08 no arquivo único `docs/casos-de-teste.md`.
- **Evidências anexadas na issue:** `f5d_resultados_e2e.json` (21
  verificações) e `f5d_ofx25000.png` (captura da rejeição com 1 mensagem).

## 4. R1 — versão leiga

Depois dos dois consertos, um inspetor refez tudo de verdade: rodou a bateria
completa de testes (393 passaram, 1 pulado como antes), dirigiu o programa de
ponta a ponta num navegador de mentira (21 checagens, todas OK), conferiu que
os números do extrato contra a contabilidade continuam batendo (77,8%, R$
147,55 de diferença, zero de resto) e que o relatório final segue com 9
páginas e o mesmo conteúdo. E confirmou a estrela da fase: o extrato gigante
de 25.000 lançamentos agora recebe um único aviso claro.

---

## 5. A1 — re-verificação independente do arquiteto (técnico)

Base: commit `abb3aa6` (contém D1, D2 e a seção Fase 5d). Worktree limpo
antes e depois — sem alterações.

- **`pip-audit` em venv separada (fora do repo, removida depois):**
  `uv venv --python 3.10`, instalação de `pip-audit 2.10.1`,
  `pip-audit -r requirements.txt --no-deps` → **"No known vulnerabilities
  found"**. `requirements.txt` fixa `pypdf==6.19.0`; a vulnerabilidade antiga
  do `PyPDF2` não se reproduziu.
- **Leitura independente dos três PDFs** (dados sintéticos, `pypdf` 6.19.0):
  `pytest tests/test_importacao_limites.py::test_pdf_valido_com_texto_extrai_transacoes
  ::test_pdf_malformado_nao_gera_excecao_nao_tratada
  ::test_pdf_acima_do_limite_de_paginas_e_rejeitado -q` → **3 passed**
  (válido extrai transações; malformado trata sem exceção; acima de
  `MAX_PDF_PAGINAS` rejeita com mensagem de limite).
- **Conclusão: A1 FECHADO.** Sem divergência funcional vs R1 (R1 rodara 47
  testes da área com `PyPDF2` bloqueado; A1 re-executou de forma focada os 3
  cenários, 3/3 PASS). Ressalva documental mantida: menções históricas a
  `PyPDF2` em documentos, sem uso em código.

## 5. A1 — versão leiga

Um segundo inspetor, sem repetir tudo, refez por conta própria as duas
checagens críticas: a vistoria de segurança da lista de ingredientes (limpa)
e a leitura de 3 PDFs falsos (um bom, um estragado, um grande demais) — os 3
se comportaram como o esperado. Carimbo: fechado, sem divergência.

---

## 6. Comandos relevantes (executados nas rodadas, não nesta etapa)

```bash
# D1 — auditoria de usos e versão
grep -rniI "PyPDF2" app pages modules tests requirements.txt
pip-audit -r requirements.txt --no-deps        # venv separada, fora do repo
uv venv --python 3.10|3.12|3.13 && uv pip install -r requirements.txt
python -c "import app"                          # + pypdf.__version__ == 6.19.0
pytest tests/test_importacao_limites.py tests/test_report_generator.py tests/test_relatorio_executivo.py

# D2 — área afetada (131 passed)
pytest tests/test_importacao_mensagem_unica_limite.py tests/test_importacao_limites.py \
  tests/test_seguranca_limites_estruturais.py tests/test_validacao_entrada_ofx_csv.py \
  tests/test_structured_logger.py tests/test_limites_seguranca_fase5b.py \
  tests/test_cache_parsing.py tests/test_report_generator.py tests/test_relatorio_executivo.py \
  tests/test_smoke_import_app.py

# R1 — completa + migração por bloqueio de import
python3 -m pytest tests/ -q                     # 393 passed, 1 skipped
# + área PDF/importação/relatório/smoke com PyPDF2 bloqueado no sys.meta_path → 47 passed
# E2E: streamlit run app.py (porta 8593) + Playwright/Chromium headless → 21/21 PASS

# A1 — independente
/tmp/<venv>/bin/pip-audit -r requirements.txt --no-deps   # No known vulnerabilities found
python3 -m pytest tests/test_importacao_limites.py::test_pdf_valido_com_texto_extrai_transacoes \
  tests/test_importacao_limites.py::test_pdf_malformado_nao_gera_excecao_nao_tratada \
  tests/test_importacao_limites.py::test_pdf_acima_do_limite_de_paginas_e_rejeitado -q   # 3 passed
```

---

## 7. O que NÃO foi verificado — limitações explícitas (técnico e leigo)

- **`CT-AUTH-03` (bloqueio após 5 falhas + liberação em 15 min) e `CT-AUTH-05`
  (expiração de sessão): NAO EXECUTADO por decisão humana** — a autorização de
  espera em tempo real dada na abertura da fase foi expressamente revogada
  pelo usuário antes da rodada R2 ("NÃO executar… ficam `NAO EXECUTADO`, sem
  alegar resultado"). Nenhum PASS/FAIL é inferido para esses casos; o catálogo
  os mantém `NAO EXECUTADO`. *Leigo: dois testes que exigem esperar de
  verdade (15 minutos trancado; sessão que expira) foram cancelados pelo dono
  — ficam como "não feitos", sem chute de resultado.*
- Limites CSV no navegador: mensagem única confirmada por pytest (nível de
  `processar_arquivo`); cobertura de página via AppTest só no cenário OFX —
  nenhum CSV acima do limite subiu ao navegador.
- `PyPDF2` segue instalado no ambiente global do revisor (resíduo fora do
  `requirements.txt`); a prova de migração foi por bloqueio de import
  (47 passed) + instalação limpa da D1, não por ausência do pacote.
- Possível duplicação de mensagem em outras categorias (ex.:
  `tamanho_excedido`) não foi investigada — fora do escopo (só os 4 motivos de
  limite citados).
- Contagem de erros no E2E usou regra de texto (Streamlit 1.64 não expõe
  `data-alert-type` nos alertas) — registrado na evidência R1.
- Evidências brutas (telas, CSVs, PDF, JSON, log) ficam fora do repositório;
  os anexos na issue são o JSON das 21 verificações e a captura da rejeição.
- Publicação pendente: squad sem credencial Git — commits só em worktrees
  locais, sem push/PR.

---

## 7b. Adendo — limitações da revisão de segurança final (técnico e leigo)

Revisão de segurança final (somente leitura, sobre `abb3aa6` + `77bc707`,
sem dados reais, sem CT-AUTH-03/05, sem alterar código/documentação;
riscos aceitos `admin/admin123` e chave JWT sem variável preservados):
**sem bloqueio para mover a issue a `in_review`**, condicionado a manter
explícitas as limitações abaixo. São recomendações/limitações de cobertura,
**não** falhas impeditivas da entrega atual:

1. **Limites CSV sem upload de navegador:** a mensagem única no nível de
   página foi comprovada no fluxo de upload único para OFX (R1/E2E); os
   limites de CSV (linhas, colunas, campo) foram cobertos no nível de
   `processar_arquivo` (pytest), mas nenhum CSV acima do limite subiu ao
   navegador. Limitação de cobertura — não é evidência de stack trace ou
   vazamento.
2. **Modo de validação por nome de arquivo:** se todos os arquivos forem
   rejeitados por limite, o bloco final ainda pode exibir a mensagem
   genérica de estado da conciliação ("Não foi possível processar os
   arquivos para conciliação"). É mensagem de estado, não stack trace nem
   conteúdo do upload — mas esse modo não está comprovado como "uma única
   mensagem" em todos os cenários.
3. **`audit.log_file_upload` e nome de arquivo:** o `file_name` é saneado
   como basename (controles/segredos redigidos), mas o `error_message`
   recebe a mensagem de validação com o nome do arquivo — um nome
   controlado pelo usuário pode permanecer refletido nesse campo. Não há
   conteúdo do PDF/OFX/CSV nem stack trace; recomendação para trabalho
   posterior: normalizar também esse campo se o requisito for não persistir
   nenhum nome controlado pelo usuário.
4. **Exceção de PDF com `str(e)`, sem fuzzing:** a captura de exceção de
   PDF exibe `str(e)` ao usuário; a evidência executada não mostra stack
   trace, mas não houve teste de fuzzing para provar que toda mensagem de
   exceção do `pypdf` é livre de detalhes internos. Não bloqueia o aceite
   da rejeição por limite.

*Leigo: o inspetor de segurança liberou a entrega, mas deixou quatro
ressalvas honestas para o futuro — (1) os limites de planilha foram testados
na bancada, não no navegador; (2) num modo alternativo de envio pode sobrar
um aviso genérico no fim; (3) o nome do arquivo pode ficar registrado no
caderno de auditoria (só o nome, nunca o conteúdo); (4) a mensagem de erro de
PDF mostra o texto do erro sem prova completa de que nunca vaza detalhe
interno. Nada disso trava esta entrega.*

---

## 8. Tokens por agente e por rodada

O runtime não expõe contador de tokens aos agentes; **nenhum número é
declarado** — registrar valor inventado seria falsificação. Situação por
rodada, conforme os próprios relatos na issue: D1 (sem acesso a contador),
D2 (sem acesso a contador), R1 (métrica não exposta pelo ambiente), A1
(runtime não expõe contador) e esta documentação (sem contador disponível).
