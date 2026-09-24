# conc_banc — Fase 3b: documentação final (correções do relatório executivo + catálogo único)

Fase 3b da revisão do app de conciliação bancária (Streamlit): correção das 4 diferenças
entre o relatório executivo da fase 3 (`modules/report_executivo.py` +
`templates/relatorio_executivo.html.j2`) e o modelo do usuário, mais consolidação dos
casos de teste em um único arquivo.
Base: `main` com fases 1, 2 e 3 mescladas + linha da Parte A (itens A1–A4) + linha da
Parte B (catálogo único) unidas por merge + status reais da Parte C + revisão de
segurança + este documento.
Login de teste: `admin` / `admin123` (conta bootstrap local de teste, dados sintéticos
em `Exemplos/B_1234490.ofx` e `Exemplos/C_1234490.ofx`).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga** (analogia do
dia a dia). Nada aqui foi marcado como verificado sem execução real — o que não foi
executado está declarado como NÃO EXECUTADO / NÃO VERIFICADO / parcial. Este documento
não altera nenhum caso de teste; apenas relata o que os agentes responsáveis
executaram e reportaram na issue.

> Nota de procedência: os commits da fase 3b estão em worktrees/branches locais de
> outros agentes e **não foram publicados (sem push — o squad não tem credencial Git)**.
> Este arquivo foi escrito na branch `agent/documentador-muse-gratis/e37fd3374b95`,
> que parte do `main` (fase 3). O conteúdo sobre A1–A4, Parte B, Parte C e segurança
> reproduz fielmente os relatos dos agentes na issue (sem reexecução independente
> nesta etapa de documentação).

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Etapa | Commit / branch | O que faz |
|-------|-----------------|-----------|
| A1 | `1976ede` — rótulo por magnitude | `_linha_match_similaridade` passa a comparar `\|contábil\|` × `\|extrato\|` |
| A3 | `98770fa` — pluralização | `pluralizar()` / `_fmt_contagem()` em `modules/report_executivo.py`, exposto como global do Jinja |
| B | `c0265cc` (Arquiteto) — catálogo único | `docs/casos-de-teste.md` a partir do anexo, `git rm` de `docs/casos-de-teste-fase-2.md` e `docs/casos-de-teste-fase-3.md`, `scripts/gerar_pdf_casos_de_teste.py`, `markdown` em `requirements-dev.txt`, `docs/casos-de-teste.pdf` |
| merge | `ec7ed87` | Une a linha A1+A3 com a linha B (sem conflito, arquivos não se sobrepõem) |
| A2 | `8809bc3` — pares prováveis + ponte detalhada + exposição | Fonte única `identificar_pares_provaveis_similaridade` em `modules/data_analyzer`, tabela de pares prováveis, ponte detalhada, exposição por natureza |
| A4 | `f6f082b` — layout | Período em 1 linha, tabela de similaridade sem quebra, menos página vazia |
| C | `e84708c` (branch `agent/desenvolvedor-revisor-rapido-g/b9d6ed3dc4ea`, parte de `f6f082b`) | Só `docs/casos-de-teste.md` + `docs/casos-de-teste.pdf`: status reais dos 8 casos 3b |
| este doc | branch atual | `docs/documentacao-final-fase-3b.md` (este arquivo) |

Branch da Parte A relatada: `agent/assistente-claude-pago/46897e110a13` (local, sem push).
Invariantes do B×C preservados (condição da issue): 14 correspondências, 77,8% cobertura,
61,1% efetiva, 4+4 divergências, ponte com resíduo R$ 0,00.

## 1. O que foi entregue — versão leiga

Pense no app como um escritório que confere o extrato do banco contra a contabilidade.
A fase 3 tinha entregue um relatório executivo novo, mas com 4 defeitos em relação ao
modelo desenhado pelo dono. Esta fase corrigiu os 4 (rótulo trocado, conteúdo faltando,
plural errado, layout quebrando) sem mudar nenhum número do caso de teste B×C, juntou
todos os cadernos de teste num arquivo só e testou tudo de verdade no navegador. Os
trabalhos estão salvos nos computadores dos agentes, ainda não publicados — falta alguém
com acesso ao GitHub fazer o envio final.

---

## 2. A1 — rótulo de diferença por magnitude (técnico)

**Antes:** `_linha_match_similaridade` usava o sinal algébrico (contábil − extrato). Em
despesas (valores negativos) isso invertia o sentido: uma despesa maior no contábil
(−43,30 contra −40,30) saía como "3,00 a menos".
**Depois:** compara `|valor contábil|` com `|valor extrato|`: maior → "X a mais no
contábil"; menor → "X a menos no contábil"; igual → "Sem diferença de valor" (a
diferença de data continua mostrada à parte). Vale para débitos e créditos. A ponte
continua algébrica (contábil − extrato), com a legenda do sinal explícita.
**B×C esperado e confirmado:** Águia Branca (−40,30 / −43,30) = "3,00 a mais no
contábil"; Dell (−22,90 / −20,90) = "2,00 a menos no contábil"; Uber\* Trip = sem
diferença de valor (data difere 2 dias). Testes para despesa, receita e igualdade.

## 2. A1 — versão leiga

Antes a etiqueta dizia o contrário do certo quando a conta era de gasto: se a
contabilidade tinha lançado um valor maior, o relatório dizia "a menos". Agora ele
compara o tamanho dos dois valores sem se confundir com o sinal de menos, como comparar
duas contas de cabeça para baixo pelo valor absoluto. A conta de fechamento no fim
continua do jeito de contador (com sinal), só a etiqueta que foi consertada.

---

## 3. A2 — pares prováveis, ponte detalhada e exposição por natureza (técnico)

**Antes:** a seção 5 perdia conteúdo que o app já calculava em `analise_dados`: as
possíveis correspondências por similaridade não apareciam no PDF, só existia a ponte
compacta, e alertas/manchete/recomendações usavam o maior item bruto isolado.
**Depois:**
- (a) Tabela "Pares prováveis apontados pelo sistema" na seção 5, reusando o cálculo
  existente via fonte única nova `modules.data_analyzer.identificar_pares_provaveis_similaridade`
  (a Parte A passou a reusar em vez de recalcular). B×C: Salonlin −60,50/−62,50
  (dif. R$ 2,00) e Pagamento recebido 1.300,00/1.400,00 (dif. R$ 100,00).
- (b) Ponte detalhada linha a linha como visão adicional, quando houver pares por regra
  objetiva entre os itens em aberto (mesma descrição normalizada + mesma data + valor
  diferente; ex.: Uber\* Trip 11/07/2025, −20,80 no extrato e −25,80 no contábil). Pares
  fora da lista do sistema são rotulados "hipótese do analista" (B×C: Uber\* Trip,
  dif. R$ 5,00). A ponte detalhada também fecha com resíduo R$ 0,00 (se não fechar, o
  relatório diz isso). A ponte compacta determinística continua como padrão.
- (c) Alertas, manchete/takeaways e recomendações usam a exposição agrupada por
  natureza: soma das |diferenças| dos pares prováveis + itens em aberto sem par,
  separada em recebimentos (créditos) e pagamentos (débitos). B×C: "Principal exposição:
  recebimentos, R$ 150,63" (= 100,00 + 50,63 sem par) e recomendação de prioridade alta
  "Investigar os recebimentos de R$ 1.400,00 e R$ 50,63" com impacto R$ 150,63.
- Duas decisões de design documentadas no código: o limiar do alerta crítico (R$ 500,00)
  foi revisado e **mantido**, mas agora se aplica à exposição já agrupada (no B×C o
  crítico não dispara: 150,63 < 500,00; há teste confirmando que dispara quando a
  exposição excede o limiar); a recomendação de prioridade alta da exposição principal
  passou a ser incondicional quando há exposição.
- Não tocadas as cópias duplicadas dessa lógica em `pages/analise_dados.py` e
  `pages/gerar_relatorio.py` (código Streamlit pré-existente) — débito técnico
  pré-existente registrado pelo implementador.

## 3. A2 — versão leiga

Antes o relatório escondia duas coisas úteis: a lista de "candidatos a par" que o
sistema já sugeria na tela e o passo a passo da conta de fechamento. Agora ele mostra
os candidatos numa tabela, mostra a conta detalhada linha por linha (marcando com a
etiqueta "hipótese do analista" o que é palpite, não certeza do sistema) e resume o
risco somando tudo por tipo: quanto está em aberto em recebimentos, quanto em
pagamentos. No caso de teste, o maior risco são R$ 150,63 em recebimentos — é para onde
o relatório manda olhar primeiro. O alarme de valor alto continua nos R$ 500,00, mas
agora ele olha para esse total somado, não para um item sozinho.

---

## 4. A3 — plural correto (técnico)

**Antes:** "11 casamento(s) são exatos", "8 item(ns)".
**Depois:** helper `pluralizar()` / `_fmt_contagem()` em `modules/report_executivo.py`,
exposto como global do Jinja e usado em todo o template e módulo (1 casamento /
N casamentos; 1 item / N itens), com concordância verbal onde faz sentido ("1 par tem"
/ "3 pares têm"). Testes para 0, 1 e N.

## 4. A3 — versão leiga

Antes o texto vinha com aquele "(s)" de formulário mal preenchido. Agora o relatório
escreve português certo: "1 casamento", "3 casamentos", "1 item", "0 itens".

---

## 5. A4 — layout (técnico)

**Antes:** período da capa ("15/06/2025 a 16/07/2025") quebrava em 2 linhas; descrições
como "Aguia Branca - Passage - Parcela 6/6" quebravam em 2 linhas na tabela de
casamentos por similaridade; seção 8 forçava quebra de página antes de si.
**Depois:** período com `white-space:nowrap`; tabela de similaridade com
`table-layout:fixed` + `colgroup` dimensionado (só `width` no `<th>` não bastava — o
auto layout do WeasyPrint priorizava as outras colunas); seção 8 sem quebra forçada.
Medido por rasterização (pixel, não só `pdfinfo`): 9 páginas no B×C (limite 10),
páginas de corpo com 5% a 38% vazias abaixo do último conteúdo (diretriz: ~40%).

## 5. A4 — versão leiga

Antes a capa cortava a data em duas linhas e a tabela espremia os nomes em duas linhas.
Agora a data fica inteira numa linha só, os nomes ficam inteiros numa linha só e o
relatório ficou com 9 páginas bem preenchidas, sem página quase vazia à toa. Tudo
conferido olhando cada página como imagem, não só pelo número de páginas.

---

## 6. Parte B — catálogo único de casos de teste (técnico)

`docs/casos-de-teste.md` criado a partir do anexo (conteúdo idêntico, já consolidava
fases 1–3), com `git rm` de `docs/casos-de-teste-fase-2.md` e
`docs/casos-de-teste-fase-3.md` — nenhum caso nem resultado perdido. A seção reservada
"Fase 3b" foi substituída por 8 casos detalhados no padrão do squad
(CT-F3B-01…CT-F3B-08: objetivo, pré-condição, passos numerados com dados concretos,
resultado esperado, "**Status de execução:**" com `PASS`/`FAIL`/`NAO EXECUTADO` só com
evidência). Tabela "Resumo por fase" atualizada contando só linhas de status (não a
legenda). Casos antigos afetados pela Parte A tiveram texto e status atualizados com
evidência e mudança registrada na seção 3b. `scripts/gerar_pdf_casos_de_teste.py`
adicionado ao repo, `markdown` ao `requirements-dev.txt`, `docs/casos-de-teste.pdf`
gerado e commitado junto com o `.md`. Nenhum outro arquivo de casos criado.

## 6. Parte B — versão leiga

Antes havia um caderno de testes por fase, espalhados. Agora existe um caderno único
com tudo, e o PDF dele é gerado por um script guardado no próprio projeto. A seção da
fase 3b tem 8 testes novos bem detalhados (passo a passo com os arquivos B e C de
verdade), e o resumo conta só teste de verdade, não linha de legenda.

---

## 7. Evidências reais — pytest, E2E, PDF e rasterização (técnico)

Tudo abaixo foi rodado de verdade pelo revisor rápido no commit `f6f082b` (A+B); nada
aqui é presumido:

- **pytest:** `185 passed, 1 skipped` em ~21 s (repetido após a edição do catálogo:
  `185 passed, 1 skipped` em ~19 s). Baseline era 144. O skip é intencional (cenário
  0/0/0/0 que não se aplica à função testada). Suite inclui golden B×C, unitários de
  magnitude/plural/pares/ponte/exposição e testes de rasterização com `pdftoppm` real.
- **E2E real (Streamlit local porta 8577 + Playwright/Chromium headless): 7/7 `PASS`** —
  login `admin/admin123`, importação de `B_1234490.ofx` e `C_1234490.ofx`, "Executar
  Análise de Correspondências", formato padrão confirmado como Executivo, download do
  Executivo, download do legado Completo (10 páginas, PyFPDF) e Executivo com campos de
  capa vazios.
- **PDF Executivo gerado pela UI:** `pdfinfo` 9 páginas A4 WeasyPrint 70.0 com título;
  `pdffonts` 4 faces Inter embutidas, nenhuma não embutida; 32 destinos internos do
  sumário, 0 links externos/URI; `pdftotext -layout` sem nenhuma ocorrência de `(s)`,
  `(ns)` ou `(es)`; invariantes impressos: 18/18, 14 correspondências, 11 exatas,
  3 por similaridade, 77,8%, 61,1%, 4+4 abertos, R$ −140,88 / R$ 6,67 / R$ 147,55,
  resíduo R$ 0,00 nas duas pontes.
- **Rasterização (`pdftoppm -r 110`) + inspeção visual das 9 páginas:** período em uma
  linha na capa e contracapa; Águia Branca, Dell e Uber\* Trip em uma linha sem corte;
  maior faixa vazia por página de corpo 6,8%–35,4% (abaixo de ~40%); sumário 60,2%
  (estrutura de lista curta, justificado); sem corte ou sobreposição.
- **Execuções extras (mesmo gerador do app, 3 PDFs):** fixture com 0 abertos e com
  1 casamento + 1 item → "1 casamento é exato", "1 item segue sem par", "0 itens em
  aberto", "Nenhum item."; B×C com +R$ 1,00 num aberto → pontes continuam R$ 0,00
  (ver limitação); limiar R$ 100,00 → alerta `critico` citando "R$ 150,63, acima do
  limiar de R$ 100,00 configurado para este alerta"; limiar restaurado para 500,00.
- **Status gravados (resumo 3b: 8 casos, 8 PASS, 0 FAIL):** CT-F3B-01 PASS; CT-F3B-02
  PASS; CT-F3B-03 PASS (parcial, passo 6 — ver limitações); CT-F3B-04 PASS (parcial,
  passo 5 — ver limitações); CT-F3B-05 PASS; CT-F3B-06 PASS; CT-F3B-07 PASS; CT-F3B-08
  PASS. `docs/casos-de-teste.pdf` regenerado (32 páginas, WeasyPrint). Anexos na issue:
  `casos-de-teste.pdf`, `relatorio_executivo_bxc.pdf`, `bxc_limiar_alerta_100.pdf`,
  `pg-1.png`, `pg-4.png`.

## 7. Evidências — versão leiga

Todos os 185 testes automáticos passam. O teste de verdade no navegador passou nas
7 etapas (entrar, importar os dois arquivos, analisar, baixar os dois relatórios).
O PDF tem 9 páginas, fonte embutida, índice clicável só interno (nada de internet),
português sem "(s)" e todos os números batendo com o esperado. Cada página foi olhada
como foto, uma por uma. Dos 8 testes novos, todos passam — 2 deles com uma ressalva
pequena explicada abaixo. Nada foi "achado" sem rodar de verdade.

---

## 8. Revisão de segurança — veredito sem crítico/alto (técnico)

Revisão dedicada no worktree em `e84708c`, só com dados sintéticos (sem espera real),
com leitura integral de `modules/report_executivo.py`, `templates/relatorio_executivo.html.j2`,
`modules/audit_logger.py`, `modules/auth_middleware.py`, `pages/gerar_relatorio.py`,
`scripts/gerar_pdf_casos_de_teste.py` e os dois OFX, mais render Jinja isolado,
`URLFetcher` e 1 PDF sintético:

1. **Escape OK:** Jinja com `autoescape=select_autoescape(["html","j2"])`; todos os
   campos de OFX/UI interpolados como `{{ var }}` sem `|safe`/`Markup` (0 ocorrências);
   payloads `<script>`/`<img onerror>`/` <b>` saem como `&lt;script&gt;` etc. Teste
   existente cobre o mesmo comportamento.
2. **HTML/injeção OK no Executivo:** template sem `unsafe_allow_html`; os únicos
   `unsafe_allow_html=True` do repo estão em `pages/gerar_relatorio.py` e
   `pages/analise_dados.py` para CSS/preview — fora do caminho do PDF. Script de casos
   usa `html.escape(titulo)`.
3. **Recursos remotos OK:** `URLFetcher(allowed_protocols=["data"])` com
   `base_url=None`; `https`/`http`/`file:///etc/passwd`/`ftp://` rejeitados com
   `ValueError`, só `data:` permitido (fonte Inter em base64). Template sem URL externa.
4. **Credenciais/segredos OK (1 observação de baixa):** sem chave hardcoded; `SECRET_KEY`
   via `CONCILIACAO_SECRET_KEY` ou `token_hex(32)`; seed `admin123` só como hash PBKDF2
   para bootstrap local; PDFs (sintético + E2E) sem `admin123`/`Bearer `/`eyJhbGciOi`/
   `Traceback`; auditoria sem senha/token e sem stacktrace (`error_message=str(e)`).
   **Débito pré-existente (baixa, herdado, fora do Executivo):**
   `pages/importacao_dados.py` e `pages/analise_dados.py` exibem `traceback.format_exc()`
   via `st.code` para usuário autenticado — expõe caminhos internos na UI, não vaza
   para PDF nem auditoria. Recomendação não bloqueante: mensagem genérica + stack só em
   log interno.
5. **Dados sintéticos OK.** Nenhum achado médio/alto/crítico introduzido pela 3b.

## 8. Segurança — versão leiga

Um revisor de segurança tentou ataques de verdade (texto malicioso, buscar arquivo da
máquina pela internet, procurar senha vazada) e não achou nada grave: o relatório
neutraliza texto perigoso, não busca nada na internet e não vaza senha no PDF nem no
livro de registros. Fica um aviso antigo, que não é desta fase: em caso de erro na tela
de importação, o sistema mostra detalhes técnicos demais para quem está logado — convém
trocar por mensagem simples no futuro, sem pressa.

---

## 9. Limitações e o que permanece NÃO VERIFICADO (técnico e leigo)

1. **CT-AUTH-03 (bloqueio/~15 min) e CT-AUTH-05 (expiração de sessão): NÃO EXECUTADOS.**
   Casos de tempo real; a regra do squad exige confirmação explícita do usuário. Em
   leigo: são testes que demoram de propósito (esperar o sistema bloquear/expirar) e
   ninguém autorizou a espera.
2. **CT-F3B-03, passo 6 — parcial:** a variação com +R$ 1,00 num aberto não produz
   resíduo não nulo (a decomposição recalculada continua fechando em R$ 0,00). O caminho
   de resíduo não nulo só foi verificado em nível de módulo (2 testes unitários).
   Sugestão registrada pelo revisor: o arquiteto revisar o enunciado do passo.
3. **CT-F3B-04, passo 5 — parcial:** no B×C o alerta crítico não dispara
   (150,63 < 500,00) e o PDF padrão não imprime o número do limiar; ele está
   documentado no código (`ALERTA_DIVERGENCIA_VALOR_MINIMA`, com justificativa da
   revisão) e só aparece no texto quando o alerta dispara (comprovado no PDF com limiar
   100,00 anexado).
4. **Streamlit Cloud: NÃO VERIFICADO.** Nenhum deploy nesta rodada.
5. **Commits locais, sem push:** todo o trabalho da 3b está em branches locais
   (`46897e110a13` Parte A, `b9d6ed3dc4ea` Parte C, esta branch de documentação) —
   falta merge + push + reimplantação pelo responsável do projeto.
6. **Débito pré-existente de traceback na UI** (item 8.4 acima) — mantido, sem correção
   nesta issue.
7. **Escopo da segurança:** sem E2E de navegador nem rasterização completa nessa etapa,
   sem verificação de supply-chain profunda (pins de `weasyprint`/`jinja2` apenas
   observados).
8. **Tempo/tokens:** Parte C levou ~20 min de execução real; os tokens por agente
   estavam incompletos no relato porque segurança e documentação ainda não tinham
   rodado.

---

## 10. Como aplicar / estado de entrega

- Reunir as linhas locais (Parte A + Parte B via `ec7ed87`, Parte C via `e84708c`, este
  documento) numa branch única, revisar o diff, rodar `pytest -q` de confirmação,
  fazer merge e push, e reimplantar se houver Cloud.
- Anexos já na issue (não neste repo nesta branch): Executivo do E2E
  (`relatorio_executivo_bxc.pdf`), PDF com limiar 100 (`bxc_limiar_alerta_100.pdf`),
  catálogo (`casos-de-teste.pdf`), páginas rasterizadas (`pg-1.png`, `pg-4.png`).
- Este arquivo: `docs/documentacao-final-fase-3b.md`, para validação do usuário
  (antes/depois de A1–A4, Parte B, evidências, segurança e NÃO VERIFICADO acima).
