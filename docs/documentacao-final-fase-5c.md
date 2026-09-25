# conc_banc — Fase 5c: documentação final (correções de segurança R-02, R-03, R-04, R-05, R-07)

Fase 5c do app de conciliação bancária (Streamlit): corrige cinco achados da
revisão de segurança dedicada (`docs/revisao-seguranca-fase-5.md`, SEC-R-01…07).
Base: `origin/main` (fases 1 a 5b, relatório Executivo único, sem seletor de
formato). Login de teste: `admin` / `admin123` (bootstrap local, app de
teste/estudo, dados 100% sintéticos).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga**
(analogia do dia a dia). Este documento apenas relata o que os agentes
responsáveis executaram e reportaram na issue — nada foi marcado como
verificado sem execução real, e o que não foi verificado está declarado como
tal (seções 8–9). Este documento não altera código nem nenhum outro documento.

> Nota de procedência: os commits `c5a54cf`, `4af64ab`, `988578c`, `cca3069`,
> `b909bb0` (5 rodadas Claude), `74f13ab` (corretiva R-05), `3c0f96e`
> (verificação integrada + catálogo) estão em branches locais de outros agentes
> e **não foram publicados (sem push/PR — o squad não tem credencial Git)**.
> Este arquivo foi escrito e commitado na branch atual sobre `a6ee333`
> (merge da revisão de segurança XCRE-51). O conteúdo abaixo reproduz
> fielmente os relatos dos agentes na issue (XCRE-52), sem reexecução
> independente nesta etapa de documentação.

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Etapa | Commit (local, sem push) | O que faz |
|-------|--------------------------|-----------|
| Rodada 1 — SEC-R-02 (PDF temporário) | `c5a54cf` | `modules/report_executivo.py` + `pages/gerar_relatorio.py`: PDF em diretório privado 0700, arquivo 0600 com nome aleatório, bytes lidos e artefato apagado em `finally`; API passa a devolver bytes |
| Rodada 2 — SEC-R-03 (limites OFX/CSV) | `4af64ab` | `pages/importacao_dados.py`: rejeição pré-parsing (OFX > 20.000 `<STMTTRN>`, CSV > 100.000 linhas / 200 colunas / campo > 10.000 chars), mensagem fixa em português |
| Rodada 3 — SEC-R-04 (formula injection) | `988578c` | `modules/export_divergencias.py`: decisão de "é fórmula?" ignora TAB/CR/LF/espaço/NBSP à esquerda; apóstrofo no início absoluto |
| Rodada 4 — SEC-R-05 (auditoria/log) | `cca3069` | `modules/audit_logger.py`: saneamento único em `log_action` (controles→espaço, truncamento 500 chars, basename), antes do SQLite e do logger |
| Rodada 5 — SEC-R-07 (dependências) | `b909bb0` | `requirements.txt`: 15 dependências diretas com versão exata; `weasyprint==70.0`, `Jinja2==3.1.6` mantidos; `packages.txt` intocado |
| Verificação integrada + catálogo | `3c0f96e` | Só `docs/casos-de-teste.md` (seção Fase 5c, CT-F5C-01…08) + `docs/casos-de-teste.pdf` regenerado (52 → 60 páginas). Nenhum código de produção alterado |
| Corretiva SEC-R-05 (pós re-verificação) | `74f13ab` | `modules/audit_logger.py`: allowlist de chaves de topo + redação de segredo por conteúdo (JWT, hash hex, `rótulo=valor`), inclusive no nome do arquivo |
| este doc | branch atual | `docs/documentacao-final-fase-5c.md` (este arquivo) |

Nenhum número do baseline B×C foi alterado em nenhuma rodada.

## 1. O que foi entregue — versão leiga

Pense no sistema como quem confere o extrato do banco contra a contabilidade.
Esta fase tapou cinco brechas apontadas por uma auditoria: (1) o relatório em
PDF ficava largado numa pasta aberta — agora é feito num cofre que se
autodestrói depois de entregar o arquivo; (2) um arquivo gigante podia travar
o programa — agora há um porteiro que barra arquivos grandes antes mesmo de
abrir; (3) a planilha exportada podia virar armadilha no Excel — agora todo
texto suspeito ganha uma "trava" na frente; (4) o caderno de registros guardava
segredos que não devia — agora só anota o essencial e risca senhas e códigos;
(5) a lista de ingredientes estava sem medida exata — agora cada um tem versão
carimbada. Tudo foi testado de verdade depois. Os trabalhos estão salvos nos
computadores dos agentes, ainda não publicados: falta alguém com acesso ao
GitHub fazer o envio final.

---

## 2. SEC-R-02 — PDF temporário privado e apagado (técnico)

**Problema:** o PDF executivo era gerado como arquivo temporário com permissão
0644 (legível por outros usuários da máquina) e nunca apagado.
**Depois:** geração em diretório privado por execução (`tempfile.mkdtemp`,
modo 0700), nome imprevisível (`secrets.token_hex(16)`, sem timestamp), arquivo
0600; os bytes são lidos e arquivo + diretório removidos em `finally` (vale
para sucesso e para exceção). `gerar_relatorio_executivo` passou a devolver
**bytes** em vez de caminho — devolver um caminho para um arquivo já apagado
não faria sentido; dois testes e `pages/gerar_relatorio.py` foram adaptados, e
nenhum caminho interno chega à interface ou ao log.
**Testes:** novo `tests/test_seguranca_pdf_temporario.py` (6 testes, escritos
antes da correção e confirmados falhando antes): modos 0600/0700, imprevisibi-
lidade, remoção após sucesso e após exceção injetada, bytes idênticos, caminho
ausente da mensagem de erro. Focal: 6 + 27 (`test_relatorio_executivo.py`) +
48 passed, 1 skipped.

## 2. SEC-R-02 — versão leiga

Antes o relatório ficava esquecido numa mesa aberta, onde qualquer pessoa da
firma podia ler. Agora ele é montado dentro de um cofre que só o dono abre, e
o cofre é destruído assim que o relatório é entregue em mãos — dando certo ou
errado, não sobra nada para trás.

---

## 3. SEC-R-03 — limites estruturais de OFX/CSV (técnico)

**Problema:** sem teto estrutural; 50 mil transações OFX levavam ~119 s no
parser (crescimento maior que linear) — vetor de negação de serviço.
**Depois:** validação pré-parsing com constantes documentadas (sobrescrevíveis
por env): OFX rejeitado acima de 20.000 ocorrências literais de `<STMTTRN>` nos
bytes crus (contagem barata, case-sensitive); CSV rejeitado acima de 100.000
linhas, 200 colunas ou campo com mais de 10.000 caracteres, em passada única
com `csv.reader`. Rejeição com mensagem fixa em português, sem stack trace.
Achado extra corrigido na rodada: o teto interno do módulo `csv`
(`field_size_limit`) estourava erro cru antes da mensagem fixa — agora é
elevado temporariamente ao limite documentado com restauração em
`try/finally`. Dois testes antigos da Fase 5b que documentavam a ausência de
teto foram ajustados para operar dentro dos novos limites.
**Testes:** novo `tests/test_seguranca_limites_estruturais.py` (19 testes,
sintéticos, falhando antes): OFX 50k rejeitado em < 2 s, limite exato aceito /
limite+1 rejeitado nos três eixos do CSV, arquivos `Exemplos/*` (4 OFX + 5 CSV)
continuam aceitos. Focal: 19 + 66 passed (com limites Fase 5b, validação OFX/
CSV, cache e importação).

## 3. SEC-R-03 — versão leiga

Antes qualquer caminhão gigante podia entrar no pátio e travar tudo por dois
minutos. Agora há uma balança na portaria: passou do peso, volta na hora com
um aviso simples em português — e os caminhões normais (os arquivos de
exemplo) continuam entrando sem problema.

---

## 4. SEC-R-04 — formula injection com prefixo invisível (técnico)

**Problema:** a checagem só olhava o primeiro caractere bruto (`=`, `+`, `-`,
`@`); um TAB/CR/LF/espaço antes do `=` passava batido, mas Excel/LibreOffice
ignoram esse prefixo e executam a fórmula ao abrir o CSV.
**Depois:** a decisão usa o valor com TAB/CR/LF/espaço/NBSP removidos à
esquerda (`lstrip`, só para decidir); o apóstrofo de proteção é prefixado no
**início absoluto** do valor original — a planilha para de detectar fórmula ao
ver `'` primeiro. Números reais nunca entram na checagem (`isinstance str`);
monetários chegam sempre como `"R$ …"`, então `"R$ -60,50"` legítimo nunca é
confundido com fórmula.
**Testes:** `tests/test_export_divergencias.py` estendido (18 → 55 testes):
4 prefixos × 5 invisíveis, repetições, misturas, DDE e HYPERLINK, textos
legítimos sem apóstrofo indevido, negativos legítimos via round-trip. Focal:
55 passed.

## 4. SEC-R-04 — versão leiga

Era como um crachá falso com um espaço invisível na frente do nome — o porteiro
lia "espaço + chefe" e deixava passar, mas lá dentro valia como "chefe".
Agora o porteiro ignora esses disfarces invisíveis na hora de decidir, e carimba
uma trava na frente de tudo que for suspeito — sem carimbar preço negativo
legítimo.

---

## 5. SEC-R-05 — auditoria e log sem filtro (técnico, com corretiva)

**Problema:** campos controlados pelo usuário iam crus para o SQLite e para o
logger (quebra de linha injetava registro; caminho/token vazavam; senha, hash,
JWT, descrição de transação podiam ser persistidos).
**Rodada 4 (`cca3069`):** saneamento único em `log_action` (por onde todos os
`log_*` passam): controles (CR/LF/C0/DEL) → espaço, truncamento em 500 chars,
`log_file_upload` reduz a basename antes de montar a descrição. A re-verificação
independente do arquiteto mostrou que isso **não bastava**: senha/hash/JWT/
descrição como chave de `details` continuavam persistidos, e segredo no próprio
nome do arquivo sobrevivia ao basename → classificado `NÃO FECHADO`.
**Corretiva (`74f13ab`):** duas defesas complementares — (1) allowlist de
chaves de topo em `details`/`metadata` (inventário real de todos os call sites;
chave fora da lista é descartada — `senha`/`hash`/`token`/`descricao_transacao`
nunca estiveram nela); (2) redação por conteúdo (JWT de 3 segmentos, hash hex
≥ 32 chars, padrão `rótulo=valor` como `token=…`) em qualquer texto restante,
inclusive no nome do arquivo. Nova re-verificação independente: `FECHADO`.
**Testes:** `tests/test_seguranca_saneamento_auditoria.py` (17 testes na rodada
4, 14 falhavam antes; 28 na corretiva, 8 novos falhavam antes): usuário
`alice\nINJECT`, controles variados, `token=` no nome/diretório, truncamento,
SQLite + logger (`caplog`) sem segunda linha nem segredo. Focal final: 28 +
15 (audit/relatório/análise) + 10 (login/logout) passed.

## 5. SEC-R-05 — versão leiga

O caderno de registros anotava tudo que o visitante ditava — inclusive senha
e recado confidencial, e até quebra de linha para falsificar a página seguinte.
A primeira reforma limpou a caligrafia, mas ainda guardava o que não devia. A
reforma final fez duas coisas: só aceita os campos da lista oficial (o resto
vai para o lixo antes de anotar) e passa caneta preta em cima de qualquer coisa
com cara de senha ou código, até no nome do arquivo. Auditores independentes
confirmaram: agora o caderno só tem o essencial.

---

## 6. SEC-R-07 — dependências com versão exata (técnico)

**Problema:** `requirements.txt` sem pins exatos — instalação irreprodutível.
**Depois:** 15 dependências diretas fixadas pelo `pip freeze` real do venv de
teste (`streamlit==1.64.0`, `pandas==2.3.3`, `numpy==2.2.6`, `plotly==7.1.0`,
`ofxparse==0.21`, `PyPDF2==3.0.1`, `fpdf==1.7.2`, `python-dotenv==1.2.3`,
`PyJWT==2.3.0`, `requests==2.34.2`, `openpyxl==3.1.5`,
`python-dateutil==2.9.0.post0`, `scikit-learn==1.7.2`, `weasyprint==70.0`,
`Jinja2==3.1.6`). `packages.txt` intocado.
**Verificação real:** 3 venvs limpos via `uv venv --python` (3.10.12, 3.12.14,
3.13.15) + `uv pip install -r requirements.txt` + smoke `AppTest` (`import
app`): `SMOKE OK` nos três, sem ajuste de pin. Novos
`tests/test_smoke_import_app.py` + `tests/test_seguranca_dependencias_fixadas.py`
(4 passed).
**`pip-audit`** (venv separado, fora do repo): 11 vulnerabilidades conhecidas
em 2 pacotes — `PyPDF2 3.0.1` (PYSEC-2026-1835, fix 3.9.0) e `PyJWT 2.3.0`
(múltiplos IDs, fixes 2.4.0/2.12.0/2.13.0). **Sem upgrade nesta fase** por
decisão de escopo: fixar o que os testes usam, não trocar versão; PyJWT mexe
com autenticação e exige verificação própria. Decisão pendente do squad/usuário.

## 6. SEC-R-07 — versão leiga

A receita dizia "farinha e açúcar" sem marca nem quantidade — cada cozinha
saía diferente. Agora cada ingrediente tem marca e peso carimbados, e a receita
foi testada em três fogões diferentes (Python 3.10, 3.12 e 3.13): funcionou nos
três. Um exame extra achou 11 alertas em dois ingredientes (PyPDF2 e PyJWT),
mas trocar a marca no meio da reforma podia quebrar a fechadura da porta
(login) — então ficou registrado para decidir depois, com calma.

---

## 7. Classificação final de segurança (técnico + leiga)

| Achado | Classificação | Base |
|--------|---------------|------|
| SEC-R-02 (PDF temporário) | **FECHADO** | PoC independente do arquiteto em `b909bb0`: dir 0700, arquivo 0600, limpeza em sucesso e exceção, bytes íntegros |
| SEC-R-03 (limites OFX/CSV) | **FECHADO** | PoC independente: OFX 50k rejeitado em 0,001 s, CSV nos 3 eixos rejeitado, limite exato aceito, sem traceback |
| SEC-R-04 (formula injection) | **FECHADO** | PoC independente: 11 payloads neutralizados; números e `R$ -60,50` intactos |
| SEC-R-05 (auditoria/log) | **FECHADO** | Primeira PoC: `NÃO FECHADO`; após corretiva `74f13ab`, nova PoC (SQLite + logger, 2 registros, sem segredo): `FECHADO` |
| SEC-R-01 (admin/admin123) | **Risco aceito pelo usuário** | Sem alteração, por decisão explícita: app de teste/estudo, fora de produção |
| SEC-R-06 (JWT sem secret) | **Risco aceito pelo usuário** | Sem alteração, por decisão explícita: mantém aviso, não falha ao iniciar; produção deve definir `CONCILIACAO_SECRET_KEY` |
| SEC-R-07 (dependências) | Pins fixados + auditoria registrada | `pip-audit`: 11 vulnerabilidades (PyPDF2/PyJWT) registradas, sem upgrade — decisão pendente |

Em linguagem leiga: quatro portas foram trancadas e o cadeado foi testado por
um auditor que tentou arrombar de verdade (não só olhou o cadeado); duas portas
ficaram abertas de propósito porque o dono mandou — é casa de estudo, não de
produção — com o aviso de trancá-las se um dia virar produção; e a despensa
teve os potes etiquetados, com dois alertas de validade anotados para resolver
depois.

---

## 8. Verificação integrada real — o que foi executado (técnico)

Revisor rápido, checkout em `b909bb0`, Python 3.10.12, pytest 9.1.1, dados 100%
sintéticos:

- `pytest tests/ -q` ×4: **375 passed, 1 skipped** (~47–56 s); baseline Fase 5b
  era 292 + 1 → **+83 testes**; único ignorado segue `test_pluralizacao.py:94`.
- Segurança focal: 46 passed (PDF temporário, limites, saneamento, smoke, pins);
  export/relatório/limites Fase 5b: 98 passed.
- E2E real (Streamlit local porta 8592 + Playwright/Chromium headless):
  **18/18 PASS** (~75 s) — login `admin/admin123` em banco zerado, validação de
  entrada, importar B + C (18 × 18), analisar (cobertura 77,8%, 14
  correspondências, 8 divergências), baixar 3 CSVs (BOM, `;`, dd/mm/aaaa, pt-BR,
  0 célula-fórmula), gerar e baixar o Executivo.
- Invariantes B×C: 18 × 18, 11 + 3 = 14, 77,8%, efetiva 61,1%, 4 + 4
  divergências, somas 1.386,22 / 1.538,93, líquida 147,55, resíduo 0,00.
- PDF executivo: **9 páginas**, A4, WeasyPrint 70.0, 60.457 bytes, 4 faces Inter
  embutidas, texto 20.200 bytes, varredura 0 de segredos/caminhos/traceback;
  texto idêntico ao baseline 5b além do carimbo de hora; raster 6/9 páginas byte
  a byte iguais (p1/p8/p9 só no retângulo da hora).
- Evidência R-02 no E2E: página + alertas sem caminho interno.
- `pip list` × `requirements.txt`: 15 diretas batem; `packages.txt` fora do diff.
- Catálogo: `docs/casos-de-teste.md` ganhou a seção **Fase 5c (CT-F5C-01…08 —
  7 PASS, 1 NÃO EXECUTADO)**; PDF 52 → **60 páginas** (421.293 bytes).

## 8. Versão leiga

Depois das reformas, um fiscal fez a vistoria completa: rodou todos os 375
testes (passaram), dirigiu o programa de verdade como um usuário (login,
importar extratos, analisar, baixar planilhas e relatório — 18 passos, todos
OK), conferiu que os números do extrato continuam batendo e que o relatório
tem as mesmas 9 páginas de antes (só mudou o relógio). O manual de testes
ganhou um capítulo novo e foi reimpresso.

---

## 9. O que NÃO foi feito / limitações (técnico + leiga)

1. **CT-AUTH-03 e CT-AUTH-05: `NÃO EXECUTADO`** (CT-F5C-08), por decisão
   explícita do usuário após queda de rede: bloqueio de 15 min (CT-AUTH-03) e
   expiração de sessão de 24 h (CT-AUTH-05) exigem espera de tempo real; sem
   confirmação para executá-los, seguem sem resultado alegado. Leiga: dois
   testes que exigem esperar o relógio (15 min e até 24 h) ficaram para depois,
   com autorização do dono.
2. **`pip-audit`: vulnerabilidades sem upgrade** — 11 entradas em PyPDF2 3.0.1
   e PyJWT 2.3.0 registradas, nenhum pin elevado nesta fase (ver seção 6).
3. **Não repetido na verificação integrada:** instalação limpa 3.12/3.13 e
   `pip-audit` (valem os registros da Rodada 5); prova de que os testes novos
   falhavam no código anterior (vale o registro de cada rodada).
4. **Não repetido nas PoCs do arquiteto:** pytest completo, E2E, rasterização,
   instalação limpa e `pip-audit` — as PoCs são dirigidas e não substituem a
   suíte; concorrência/memória sob carga real (R-03) e abertura do CSV em
   Excel/LibreOffice (R-04) não foram testados.
5. **R-01/R-06 intocados por decisão do usuário** (riscos aceitos, seção 7).
6. **R-05 teve um ciclo extra:** primeira versão foi reprovada (`NÃO FECHADO`)
   e só a corretiva `74f13ab` fechou — o registro acima conta as duas
   tentativas sem esconder a primeira.
7. **Nada publicado:** todos os commits da fase são locais (sem push/PR).

---

## 10. Tokens por agente e por rodada (técnico)

| Agente / rodada | Tokens |
|-----------------|--------|
| Claude Rodada 1 (R-02) | ~99k (turno único) |
| Claude Rodada 2 (R-03) | ~121k (turno único) |
| Claude Rodada 3 (R-04) | ~106k (turno único) |
| Claude Rodada 4 (R-05) | ~113k (turno único) |
| Claude Rodada 5 (R-07) | ~95k (turno único) |
| Claude corretiva R-05 | ~112k (turno único) |
| Revisor rápido (verificação integrada) | sem métrica no runtime (não declarado) |
| Arquiteto (plano + 3 re-verificações) | sem métrica no runtime (não declarado) |
| Documentador (este arquivo) | sem métrica no runtime (não declarado) |

Nenhum número de token acima foi estimado por esta etapa: os seis valores do
Claude são os declarados por ele em cada rodada; revisor/arquiteto informaram
explicitamente que o ambiente não expõe a métrica, e nenhum número foi
inventado para eles.
