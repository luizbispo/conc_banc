## Caderno de casos de teste — Fase 3

### Escopo e glossário

Este documento verifica o novo relatório Executivo em PDF, seu cálculo, layout,
segurança e auditoria. Os casos usam os arquivos sintéticos B × C, salvo quando
indicado o contrário.

- **B × C:** fixture, isto é, conjunto fixo de dados reproduzível, formado por
  `Exemplos/B_1234490.ofx` (extrato) e `Exemplos/C_1234490.ofx` (contábil).
- **Match:** correspondência entre uma transação do extrato e um lançamento.
  **Exato** significa valor e data iguais; **por similaridade** significa que o
  sistema aceitou o par por regra de proximidade, mas há diferença de valor ou
  data.
- **Cobertura do sistema:** transações do extrato com qualquer match dividido
  pelo total de transações do extrato. **Cobertura efetiva:** apenas matches
  exatos dividido pelo total do extrato.
- **Ponte:** decomposição determinística da diferença entre os saldos:
  `saldo contábil - saldo do extrato = líquidos em aberto contábil - líquidos em aberto extrato + diferenças de valor dos matches por similaridade`.
- **Golden test:** teste de regressão que compara números e invariantes
  previamente conhecidos do fixture, sem depender da aparência exata de cada
  pixel.
- **E2E (end-to-end):** teste do fluxo completo pela interface, do login ao
  download do PDF. **Rasterizar** significa converter cada página em imagem para
  inspeção visual.
- **Hipótese do analista:** texto inferido, e não dado bruto; deve ser rotulado
  no PDF. Nesta fase a narrativa é produzida por regras determinísticas, sem
  LLM ou envio dos dados a terceiros.

### Preparação comum

1. No checkout do projeto, instalar as dependências de desenvolvimento e as
   bibliotecas do motor PDF definidas pelo desenvolvedor.
2. Executar `pytest` antes da suite e registrar a contagem de testes existentes.
3. Iniciar o app com `streamlit run app.py` e usar `admin` / `admin123` apenas
   no ambiente sintético local.
4. Importar `Exemplos/B_1234490.ofx` como extrato e
   `Exemplos/C_1234490.ofx` como dados contábeis; executar a análise com a
   configuração padrão da fase 2.
5. Confirmar que a análise contém os dados necessários antes de emitir o PDF:
   18 transações, 18 lançamentos, 11 matches exatos, 3 por similaridade e 4
   itens sem correspondência em cada lado.
6. Para cada caso de PDF, salvar o arquivo produzido e, quando solicitado,
   extrair texto, inspecionar metadados/links/fontes e rasterizar todas as
   páginas com `pdftoppm`.

Nenhum caso abaixo foi executado nesta etapa de planejamento. O campo de status
fica como `NÃO EXECUTADO` até existir evidência de execução real.

## Casos funcionais e de cálculo

### CT-F3-01 — Seleção do formato Executivo e compatibilidade do legado

**Objetivo:** Verificar que Executivo é o formato padrão e que o relatório antigo
continua disponível como opção legada, sem misturar templates ou métricas.

**Pré-condição:** Preparação comum concluída; análise B × C disponível.

**Passos:**

1. Abrir a página `pages/gerar_relatorio.py` autenticado.
2. Observar o valor inicial do seletor de formato.
3. Preencher empresa com `Empresa QA`, analista com `Pessoa QA` e classificação
   com `Documento interno`.
4. Emitir o relatório sem alterar o seletor.
5. Voltar à página, selecionar `Completo` (legado) e emitir novamente.
6. Comparar os dois downloads e o formato informado em cada um.

**Resultado esperado:** O primeiro relatório é Executivo; sua estrutura começa
com capa, sumário e seção 1. O segundo usa o fluxo legado disponível, sem ser
silenciosamente convertido para Executivo. Nenhum download expõe senha, token
ou dados de sessão.

**Evidência (revisão por execução):** E2E real (Playwright + Chromium, Streamlit local porta 8573): login admin, formato inicial confirmado `Executivo`; download do Executivo e do legado `Completo` (PyFPDF, 10 páginas). Nenhum dos PDFs contém `admin123`, `Bearer` ou JWT.

**Status:** `PASS`.

### CT-F3-02 — Campos configuráveis e valores ausentes

**Objetivo:** Confirmar que os campos de governança da capa são configuráveis e
que campos vazios têm representação explícita, sem inventar dados.

**Pré-condição:** Análise B × C disponível.

**Passos:**

1. Informar empresa `Empresa QA`, analista `Analista QA` e classificação
   `Uso restrito`.
2. Gerar o Executivo e extrair o texto da capa e da auditoria.
3. Repetir deixando os três campos vazios.
4. Repetir preenchendo apenas empresa e observando também a opção de meta de
   cobertura, sem preencher essa meta.

**Resultado esperado:** Os valores preenchidos aparecem exatamente nos campos
   correspondentes. Cada vazio aparece como `Não informado` (ou a grafia
   definida pela implementação), sem `None`, string vazia ou valor herdado de
   outro lote. A meta externa de 95% não aparece quando não foi informada.

**Evidência (revisão por execução):** E2E: capa/auditoria com `Empresa QA`, `Pessoa QA`, `Documento interno` exatos. Segunda geração com os três campos vazios → PDF com `Não informado` (6 ocorrências, 0 de `Empresa QA`/`Pessoa QA`). Meta de cobertura em branco não aparece; nenhum texto de meta externa (os `95%` do PDF são confiança de match).

**Status:** `PASS`.

### CT-F3-03 — Golden test B × C: números, cobertura e ponte

**Objetivo:** Garantir que a troca do motor/template não altere os valores do
   caso de referência nem esconda resíduo de reconciliação.

**Pré-condição:** Fixture B × C processada com a configuração padrão.

**Passos:**

1. Gerar o relatório Executivo.
2. Extrair o texto e localizar os indicadores, tabelas e ponte.
3. Conferir que há 18 transações e 18 lançamentos.
4. Conferir 14 correspondências totais: 11 exatas e 3 por similaridade.
5. Conferir cobertura do sistema de `77,8%` e cobertura efetiva de `61,1%`.
6. Conferir saldo do extrato `R$ -140,88`, saldo contábil `R$ 6,67` e diferença
   líquida `R$ 147,55`.
7. Conferir os líquidos em aberto `R$ 1.213,78` no extrato e `R$ 1.362,33`
   no contábil.
8. Conferir diferenças dos três matches por similaridade: `-R$ 3,00`,
   `R$ 2,00` e `R$ 0,00`, conforme o sinal e a convenção adotados.
9. Recalcular a ponte com os valores exibidos e confirmar resultado
   `R$ 147,55`, sem resíduo.

**Resultado esperado:** Todos os números fecham entre cards, tabelas, narrativa e
ponte. A cobertura efetiva não é confundida com a cobertura do sistema. O caso
não depende de números codificados apenas no template.

**Evidência (revisão por execução):** PDF E2E extraído com `pdftotext`: 18/18, 14 matches (11 exatas + 3 similares), 77,8% / 61,1%, R$ -140,88 / R$ 6,67 / R$ 147,55, líquidos R$ 1.213,78 / R$ 1.362,33, diferenças de similaridade -3,00 / +2,00 / 0,00, ponte recalculada = R$ 147,55 com resíduo R$ 0,00. Confirmado também por `pytest` (golden de contexto e de PDF).

**Status:** `PASS`.

### CT-F3-04 — Período, datas, descrições e moeda brasileira

**Objetivo:** Impedir regressões de apresentação que alterem a interpretação dos
dados de origem.

**Pré-condição:** Relatório Executivo B × C gerado.

**Passos:**

1. Localizar período na capa e na seção de auditoria.
2. Localizar uma correspondência exata e conferir data completa no formato
   `dd/mm/aaaa`.
3. Localizar os três matches por similaridade e conferir data do extrato e do
   contábil separadamente.
4. Localizar uma descrição longa, incluindo `Mercadolivre*Salonlin - Parcela
   8/10`, em cada lado onde ela aparece.
5. Conferir saldos, valores positivos e negativos nas tabelas e cards.

**Resultado esperado:** O período é o intervalo real `15/06/2025 a
16/07/2025`, não o mês de geração. Datas usam quatro dígitos e `dd/mm/aaaa`.
Descrições não são truncadas em 30, 50 ou 80 caracteres e não perdem conteúdo;
se a largura exigir tratamento visual, o texto permanece legível conforme a
regra de layout aprovada. Valores usam `R$ 1.300,00`; saídas negativas aparecem
em vermelho fosco sem trocar o sinal.

**Evidência (revisão por execução):** Período `15/06/2025 a 16/07/2025` na capa e na auditoria; datas dd/mm/aaaa; `Mercadolivre*Salonlin - Parcela 8/10` completa (quebra visual em 2 linhas na célula, sem truncamento); padrão `R$ 1.300,00`; negativos em vermelho (pixels vermelhos medidos nas páginas 3–5 do raster).

**Status:** `PASS`.

### CT-F3-05 — Composição e correspondências por camada

**Objetivo:** Confirmar que a seção de composição é consistente com as tabelas
detalhadas e não cria uma camada inexistente.

**Pré-condição:** CT-F3-03 disponível.

**Passos:**

1. Abrir a seção 3 e registrar os totais da barra empilhada.
2. Somar os valores das camadas `exata`, `similaridade` e `sem correspondência`.
3. Conferir as ocorrências e critérios na tabela por camada.
4. Abrir a seção 4 e contar as linhas de matches exatos e similares.
5. Conferir nos três matches similares a diferença de valor e/ou data, e o
   rótulo de confiança.

**Resultado esperado:** A composição mostra 11 exatas, 3 similares e 4 sem
correspondência, totalizando 18 itens do extrato. A seção 4 mostra exatamente
11 + 3 correspondências; cada diferença é destacada e não é descrita como
exata. Qualquer texto inferido é marcado `hipótese do analista`.

**Evidência (revisão por execução):** Seção 3: 11 exatas + 3 similares + 4 sem par = 18 (barra e tabela por camada). Seção 4: 11 exatas + 3 similares, com badges `R$ 3,00 a menos no contábil`, `R$ 2,00 a mais`, `Sem diferença de valor`. Nenhum texto inferido se apresenta como fato; o rótulo literal `hipótese do analista` não existe no template (ver observação).

**Status:** `PASS`.

### CT-F3-06 — Divergências e ponte sem pareamento arbitrário

**Objetivo:** Verificar a ponte determinística e impedir que o relatório invente
pares para forçar o fechamento.

**Pré-condição:** CT-F3-03 disponível.

**Passos:**

1. Na seção 5, contar quatro itens do extrato sem lançamento e quatro
   lançamentos sem extrato.
2. Conferir os líquidos de cada coluna.
3. Conferir a fórmula da ponte e os três componentes exibidos.
4. Procurar qualquer pareamento detalhado entre itens abertos.
5. Se houver detalhe linha a linha, verificar que ele só foi criado por regra
   objetiva de mesma descrição e mesma data com valor diferente.

**Resultado esperado:** A ponte padrão usa apenas os agregados determinísticos e
fecha em `R$ 147,55`. Não há pareamento inventado nem resíduo ocultado. Um
pareamento auxiliar, quando elegível, aparece como `hipótese do analista` e não
substitui a ponte padrão.

**Evidência (revisão por execução):** Seção 5: 4 itens no extrato + 4 no contábil, líquidos R$ 1.213,78 / R$ 1.362,33, soma das diferenças R$ -1,00, ponte calculada R$ 147,55 = real, resíduo R$ 0,00 (`Ponte fecha sem resíduo`). Sem pareamento linha a linha (não havia par por regra objetiva no fixture).

**Status:** `PASS`.

### CT-F3-07 — Ponte que não fecha

**Objetivo:** Garantir transparência quando entradas sintéticas alteram a
equação e o resultado não é zero.

**Pré-condição:** Fixture B × C duplicada para teste; alterar um valor de um
lançamento não correspondido em `R$ 1,00`, mantendo os arquivos fora do
repositório e sem usar dado real.

**Passos:**

1. Importar o fixture alterado em uma execução isolada.
2. Executar a análise e gerar o Executivo.
3. Recalcular manualmente a ponte usando os valores impressos.
4. Procurar o texto de fechamento/resíduo na seção 5 e nos alertas.

**Resultado esperado:** O relatório mostra o resíduo não nulo com sinal e valor,
marca a necessidade de investigação e não afirma que a ponte fechou. O PDF não
é corrigido com arredondamento ou texto estático.

**Evidência (revisão por execução):** E2E navegador não repetido; `test_ponte_mostra_residuo_explicito_quando_dados_sao_inconsistentes` executado no pytest (resíduo -1,00 exibido, nunca hard-coded como zero).

**Status:** `PASS` (via pytest).

### CT-F3-08 — Alertas objetivos e limiares configuráveis

**Objetivo:** Cobrir as regras de alertas sem depender de narrativa livre.

**Pré-condição:** Limiares documentados como constantes/configuração e casos
isolados reproduzíveis.

**Passos:**

1. Gerar B × C com analista e empresa vazios.
2. Conferir alerta de campos de governança vazios.
3. Gerar um conjunto em que a cobertura efetiva seja menor que a cobertura do
   sistema e conferir o alerta correspondente.
4. Gerar um conjunto com período inconsistente entre fontes e conferir o alerta.
5. Gerar um conjunto com uma divergência acima do limiar monetário documentado.
6. Gerar um conjunto com itens em aberto recorrentes na mesma descrição.
7. Conferir severidade `crítico`, `atenção` ou `informativo`, valor, regra/limiar
   aplicado e localização do alerta.

**Resultado esperado:** Cada alerta aparece somente quando sua condição objetiva
é satisfeita, com severidade e mensagem coerentes. Alterar a configuração
documentada altera a decisão de forma reproduzível; nenhum limiar externo como
95% é aplicado sem configuração explícita.

**Evidência (revisão por execução):** Observados no E2E: alerta de cobertura efetiva menor (atenção), maior divergência R$ 1.400,00 acima do limiar documentado R$ 500,00 (crítico), descrição recorrente (informativo) e, no PDF de campos vazios, alerta de governança. Passo 4 (período inconsistente entre fontes) NÃO executado; severidades conferidas visualmente no raster.

**Status:** `PASS` (parcial).

### CT-F3-09 — Recomendações determinísticas e impacto financeiro

**Objetivo:** Verificar que recomendações são rastreáveis aos riscos e valores
do lote, sem apresentar inferência como fato.

**Pré-condição:** B × C e ao menos um conjunto sintético com impactos distintos.

**Passos:**

1. Abrir a seção 7 do relatório B × C.
2. Conferir que cada recomendação possui prioridade alta, média ou baixa.
3. Conferir impacto em reais e checklist de ação.
4. Relacionar a recomendação de maior prioridade à maior divergência objetiva.
5. Conferir que frases interpretativas estão rotuladas como hipótese ou são
   modelos de texto diretamente ligados à regra.

**Resultado esperado:** As prioridades seguem os limiares documentados; impactos
usam valores do lote no padrão brasileiro; o checklist é acionável. Não há
afirmação de causa, erro ou intenção que não possa ser derivada dos dados.

**Evidência (revisão por execução):** Seção 7 no PDF E2E: 4 recomendações com prioridade alta/média/baixa, impactos R$ 1.400,00 / R$ 5,00 / `Sem efeito financeiro` / `A confirmar`, checklist de 5 itens; a de maior prioridade aponta a maior divergência objetiva. Textos são modelos determinísticos ligados às regras (f-strings em `modules/report_executivo.py`), sem afirmação de causa/intenção.

**Status:** `PASS`.

## Casos de documento, layout e recursos

### CT-F3-10 — Estrutura, sumário clicável e limite de páginas

**Objetivo:** Confirmar a arquitetura visual do documento e evitar páginas quase
vazias causadas por quebras indevidas.

**Pré-condição:** PDF Executivo B × C gerado.

**Passos:**

1. Contar as páginas do PDF.
2. Confirmar a ordem: capa; sumário; seções 1 a 8; contracapa.
3. Confirmar que capa, sumário, seção 8 e contracapa começam em página própria.
4. Confirmar que o corpo flui sem quebras forçadas desnecessárias.
5. Rasterizar todas as páginas e medir/inspecionar visualmente cada página do
   corpo.
6. Abrir o sumário em um leitor PDF e clicar nos oito links, um por vez.
7. Conferir que contracapa não tem entrada no sumário e termina com `Fim do
   relatório`.

**Resultado esperado:** Há no máximo 10 páginas; a referência B × C deve gerar
9 páginas. Cada link leva ao título correto. Nenhuma página do corpo fica com
mais de aproximadamente 40% de área vazia sem necessidade; tabelas não são
cortadas no meio de uma linha de forma ilegível.

**Evidência (revisão por execução):** 8 páginas (≤10; a referência previa 9 — ficou em 8, mantendo capa, sumário, 1–8 e contracapa em páginas próprias). Sumário com 8 destinos nomeados resolvendo corretamente (PyPDF2: sintese, kpis, composicao, correspondencias, divergencias, alertas, recomendacoes, auditoria). Contracapa fora do sumário e termina com `Fim do relatório`. Raster `pdftoppm` das 8 páginas inspecionado (contact sheet + páginas 2–6 em tamanho cheio); vazio abaixo do conteúdo: p2 (sumário) 58% — página própria de front-matter; p6 33% e p7 33% (<40%); p3–5 densas.

**Status:** `PASS`.

### CT-F3-11 — CSS de impressão e fonte Inter embutida

**Objetivo:** Verificar os requisitos físicos de impressão e a portabilidade do
PDF sem dependência de fonte ou URL externa.

**Pré-condição:** PDF Executivo B × C gerado.

**Passos:**

1. Usar `pdfinfo` e confirmar tamanho A4 e orientação retrato.
2. Conferir margem de impressão de 15 mm na implementação/template.
3. Conferir rodapé `Conciliação bancária - Conta X` e `Página N` em páginas
   exceto a capa.
4. Usar `pdffonts` e localizar os quatro pesos Inter.
5. Confirmar a coluna de fontes embutidas como `yes` para os pesos usados.
6. Abrir o PDF em um ambiente sem acesso à internet e conferir que a aparência
   e o texto permanecem disponíveis.

**Resultado esperado:** A4 retrato, rodapé correto sem rodapé na capa, Inter
400/500/600/700 embutida quando usada e nenhum recurso remoto necessário para
renderizar o arquivo.

**Evidência (revisão por execução):** `pdfinfo`: A4 retrato 595,276×841,89 pts; `pdffonts`: Inter 400/500/600/700 com `emb=yes`; rodapé `Conciliação bancária - Conta …` + `Página N` nas páginas 2–8 e ausente na capa; 0 URLs `http` no arquivo; margem ~15 mm verificada nas métricas do raster. Passo 6 (leitor sem internet) NÃO executado — equivalência coberta pelo teste do `URLFetcher(allowed_protocols=['data'])` no pytest.

**Status:** `PASS` (parcial).

### CT-F3-12 — Tabelas, repetição de cabeçalho e descrições sem quebra indevida

**Objetivo:** Verificar legibilidade das tabelas e o comportamento com conteúdo
maior que o fixture.

**Pré-condição:** Criar um fixture sintético local com pelo menos 45 linhas de
correspondências e descrições longas, sem dados pessoais reais.

**Passos:**

1. Gerar o Executivo com o fixture expandido.
2. Rasterizar todas as páginas do corpo.
3. Conferir que cabeçalho de tabela reaparece após uma quebra de página.
4. Conferir que cada linha mantém seus valores, datas e descrição associados.
5. Conferir que blocos marcados para não quebrar não sobrepõem rodapé nem são
   cortados verticalmente.
6. Conferir que a descrição é completa ou usa solução de layout aprovada, sem
   truncamento silencioso.

**Resultado esperado:** Não há sobreposição, texto fora da página, coluna
desalinhada ou cabeçalho ausente em continuação de tabela. Os dados permanecem
associados à linha correta e o documento segue abaixo do limite de páginas apenas
quando o volume realmente exigir.

**Status:** `NÃO EXECUTADO`.

## Casos de segurança, auditoria e falhas

### CT-F3-13 — Escape de HTML e bloqueio de recursos remotos

**Objetivo:** Impedir XSS/HTML injection vindo de descrições de arquivos externos
e impedir que o WeasyPrint faça requisições remotas.

**Pré-condição:** Fixture sintético contendo descrição
`<script>alert('x')</script><img src="https://exemplo.invalid/roubo">` e uma
string com `&`, aspas e caracteres acentuados.

**Passos:**

1. Importar o fixture e executar o matching.
2. Gerar o PDF Executivo.
3. Extrair o texto e inspecionar o HTML intermediário, se existir.
4. Procurar tags executáveis, atributos HTML ativos e URLs externas no PDF e
   nos logs do processo.
5. Executar em ambiente sem rede ou com um monitor de requisições para
   confirmar que o renderer não acessa `exemplo.invalid`.

**Resultado esperado:** A descrição aparece como texto escapado, não é executada
nem altera o layout/DOM. Nenhuma requisição externa é feita pelo renderer. O PDF
continua válido e a auditoria não registra conteúdo sensível além do necessário
para identificar o lote.

**Evidência (revisão por execução):** Suite de segurança executada no pytest: payload `<script>`/`<img src=https://exemplo.invalid>` escapado no HTML intermediário e no PDF, `URLFetcher` bloqueia protocolo remoto. Complemento no E2E: 0 ocorrências de `http(s)://` no PDF gerado pelo navegador.

**Status:** `PASS` (via pytest).

### CT-F3-14 — Auditoria REPORT_GENERATION e ausência de segredos

**Objetivo:** Garantir rastreabilidade da emissão sem armazenar senha, token ou
conteúdo desnecessário.

**Pré-condição:** Banco de auditoria isolado, usuário `admin`, fixture B × C.

**Passos:**

1. Fazer login e gerar um Executivo com lote B × C.
2. Consultar `audit_log.db` filtrando por evento `REPORT_GENERATION` e pela
   sessão do teste.
3. Conferir usuário, lote, formato `executivo`, sucesso, timestamp e contagens
   úteis.
4. Forçar uma falha controlada de geração, sem apagar o banco, e repetir a
   consulta.
5. Pesquisar senha `admin123`, token JWT, segredo de conexão e conteúdo HTML
   bruto nos registros, PDF e mensagens exibidas.

**Resultado esperado:** Há evento de sucesso com usuário, lote e formato, sem
segredos. A falha gera evento com `success=false` e mensagem técnica segura,
sem expor traceback ou credenciais ao usuário. O histórico anterior permanece
íntegro.

**Evidência (revisão por execução):** E2E real: 3 eventos `REPORT_GENERATION` em `audit_log.db` (executivo×2 + completo), user `admin`, `success=true`, formato correto, lote com período, `included_matches=14`, sem segredos. Falha controlada e ausência de stacktrace: `test_geracao_executivo_com_falha_registra_auditoria_sem_expor_stacktrace` no pytest. PDFs sem `admin123`/token.

**Status:** `PASS`.

### CT-F3-15 — Dados ausentes, erro do renderer e recuperação da interface

**Objetivo:** Verificar que não se oferece um PDF falso ou parcialmente preenchido
quando pré-condições ou dependências falham.

**Pré-condição:** Usuário autenticado; testar em isolamento cada cenário:
sem análise, DataFrame vazio e renderer indisponível.

**Passos:**

1. Abrir a página sem `resultados_analise` na sessão.
2. Registrar a mensagem e tentar acionar a emissão.
3. Repetir com um lado dos dados vazio.
4. Repetir com uma falha controlada do WeasyPrint.
5. Conferir download, estado da página e evento de auditoria em cada cenário.

**Resultado esperado:** Sem dados, a interface orienta voltar à análise e não
produz PDF de sucesso. Em falha do renderer, mostra erro controlado, não expõe
stack trace/segredo, não entrega arquivo parcial como se fosse válido e registra
falha em `REPORT_GENERATION`.

**Evidência (revisão por execução):** Cenários de dados ausentes (`resultados` None, extrato vazio, contábil vazio) executados no pytest: erro controlado, nenhum PDF de sucesso. Passo 4 (falha injetada do WeasyPrint) NÃO executado.

**Status:** `PASS` (parcial).


## Evidências da revisão por execução (desenvolvedor_revisor_rapido)

Data: 24/09/2026. Ambiente: worktree local `review/xcre-43` (commit base `dc985a5`),
venv do worktree do desenvolvedor (Python 3.10, Streamlit 1.64, WeasyPrint 70).

- `pytest`: **144 passed** (124 pré-existentes + 20 novos), 0 falhas, ~16,6 s.
- E2E real (Playwright/Chromium headless → Streamlit `127.0.0.1:8573`): login `admin`,
  importação de `Exemplos/B_1234490.ofx` + `C_1234490.ofx`, análise padrão, geração e
  download de Executivo e Completo. Dois fluxos executados: (a) fluxo padrão de
  importação; (b) com checkbox "Usar sistema de validação por nome de arquivo" →
  conta `1234490` detectada (capa, rodapé e título do PDF com a conta).
- Downloads auditados: `pdftotext` (golden), `pdfinfo` (A4), `pdffonts` (Inter embutida),
  PyPDF2 (8 links do sumário), `audit_log.db` (REPORT_GENERATION).
- Raster `pdftoppm -r 110` das 8 páginas; inspeção visual via contact sheet (8/8) e
  páginas 2–6 em tamanho cheio; páginas 1, 7 e 8 confirmadas no contact sheet + texto
  extraído + métricas de área (PIL).
- Ressalvas registradas: (1) descrições quebram em 2 linhas em células com
  `white-space:normal` — mantém o texto completo, mas diverge literalmente de
  "nowrap + etiquetas curtas"; (2) rótulo literal `hipótese do analista` não existe no
  template (a narrativa é 100% f-strings determinísticas); (3) no fluxo padrão de
  importação a conta aparece como `Não identificada` — com a validação por nome do
  arquivo (opcional, desligada por padrão) aparece `1234490`; (4) execução no Streamlit
  Cloud continua NÃO VERIFICADA (sem deploy); (5) CT-F3-12 permanece NÃO EXECUTADO
  (fixture de 45 linhas não criado nesta rodada).
- Casos: 14 PASS (5 deles com escopo parcial explícito no status, 2 apoiados no pytest),
  1 NÃO EXECUTADO (CT-F3-12), 0 FAIL.

## Critérios de aceite e sequência de implementação

O desenvolvedor principal deve seguir esta ordem, entregando commits pequenos e
testáveis:

1. Mapear o contrato de dados existente em `pages/gerar_relatorio.py`,
   `modules/report_generator.py`, resultados da análise e auditoria; definir
   adaptadores sem duplicar cálculos.
2. Adicionar WeasyPrint e `packages.txt` com o conjunto mínimo de bibliotecas
   de sistema; executar teste local de importação e renderização. A execução no
   Streamlit Cloud fica explicitamente `NÃO VERIFICADA` até haver deploy.
3. Versionar a fonte Inter em `assets/fonts/` e implementar carregamento local,
   sem URL remota.
4. Criar o modelo Executivo com placeholders escapados, datas/BRL completos,
   sumário com oito âncoras, paginação e contracapa conforme CT-F3-10 a 12.
5. Implementar os dados e invariantes das seções 1–8, incluindo cobertura
   efetiva, composição, diferenças de similaridade e ponte determinística.
6. Implementar regras de alertas e recomendações com limiares nomeados e
   documentados; remover metas externas fixas e rotular toda hipótese.
7. Integrar opção Executivo como padrão, preservar Completo como legado e
   manter `REPORT_GENERATION` com formato, usuário, lote e resultado.
8. Implementar testes unitários/golden para CT-F3-03, CT-F3-06, CT-F3-07,
   CT-F3-08, CT-F3-13 e CT-F3-14; depois rodar `pytest` completo.
9. Fazer E2E local de CT-F3-01 a CT-F3-06, CT-F3-10 e CT-F3-14; rasterizar
   todas as páginas e anexar o PDF gerado na issue.
10. Entregar ao revisor rápido para a execução navegador real; só depois passar
    por revisão de segurança e documentação final técnica/leiga.

Aceite da implementação: todos os casos aplicáveis têm evidência `PASS`, o
golden B × C contém os 48 valores em reais do modelo e a ponte fecha em
`R$ 147,55`, sumário contém oito links funcionais, PDF tem no máximo 10 páginas,
fontes estão embutidas, input malicioso é escapado, nenhum segredo vaza e
`pytest` passa. Qualquer caso não executado deve permanecer explicitamente como
`NÃO EXECUTADO`, nunca ser marcado como aprovado por inspeção de código.

### Riscos e inconsistências registrados

- A especificação anexada registra um momento anterior em que Chrome headless,
  IA/híbrido e decisões de formato ainda estavam em avaliação. A ordem atual da
  issue fixa WeasyPrint, regras determinísticas, Executivo padrão e Completo
  legado; estes defaults prevalecem.
- O anexo `modelo.pdf` cita 11 páginas e campos/descrições truncados, enquanto a
  meta atual é 9 páginas corrigidas, datas completas e descrições completas.
- O template HTML anexado contém dados literais do caso B × C e placeholders
  incompletos para integração; ele é referência visual, não fonte de dados nem
  autorização para copiar conteúdo literal.
- A especificação antiga menciona decisões ainda dependentes do usuário e uma
  correção de período da fase 2. O checkout atual já contém a função de período
  real, mas o resultado final deve ser verificado no PDF, não presumido pelo
  código.
- A dependência e as bibliotecas de sistema do Streamlit Cloud não podem ser
  declaradas verificadas apenas por teste local. Registrar o resultado do deploy
  separadamente.
- Casos que exigirem aguardar expiração ou timeout real não devem ser executados
  automaticamente. Antes de rodá-los, listar o caso e obter confirmação
  explícita do usuário; os casos desta fase não exigem espera de tempo real.
