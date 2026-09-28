# conc_banc — Fase 7: documentação final (telas de importação, análise e relatório no visual v3 conciso)

Fase 7 do app de conciliação bancária (Streamlit): levar as três telas
restantes (importação, análise, relatório) mais o login/polimento ao visual
CONCISO do design v3 — visão padrão sóbria com poucos elementos, uma ação
principal por tela, sem blocos de ajuda visíveis, sem nome de produto
inventado, sem "meta de cobertura", sem campo de período (período sempre
automático) e sem pré-visualização do PDF — sem mudar a lógica de negócio
(matching, análise, geração do relatório) nem os números do B×C.
Base: `origin/main` (`2f15199`, fases 1 a 6). Dados 100% sintéticos; nenhum
dado real foi usado. Login de teste `admin` / `admin123` (risco ACEITO pelo
usuário, não alterado) e SEC-R-06 (aceito, não alterado).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga**
(analogia do dia a dia). Este documento apenas consolida o que os agentes
responsáveis executaram e reportaram na issue (XCRE-55) — nada foi marcado
como verificado sem execução real, e o que não foi verificado está declarado
como tal (seção 9). Esta etapa de documentação **não executou novos testes**,
**não alterou nenhum código de produção** e **não usou nenhum dado real**;
o único arquivo criado aqui é este próprio documento.

> Nota de procedência: os commits `661bffd`, `c76eb0a`, `715e8aa`,
> `4bb40d5` (implementação, desenvolvedor principal) e `2fecfc1` (rodada
> corretiva dos 3 bloqueadores) estão no histórico público alcançável por
> `git fetch` (branch `agent/assistente-claude-pago/bfd03dafd5d4` contém
> `2fecfc1`). A verificação integrada + catálogo CT-F7 foi registrada pelo
> revisor rápido em `3dffc21` (só docs, branch do revisor). Este arquivo foi
> escrito e commitado na branch atual, avançada em fast-forward até `2fecfc1`
> (mesmos hashes, sem rebase), portanto contém os 5 commits de código. O
> conteúdo abaixo reproduz fielmente os relatos das rodadas na issue, sem
> reexecução nesta etapa.

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Etapa | Commit (local, sem push) | O que faz |
|-------|--------------------------|-----------|
| Item 1 — importação | `661bffd` | `pages/importacao_dados.py` + `tests/test_importacao_opcoes_avancadas.py` (novo, 3 testes): visão padrão só com 2 uploaders + 1 botão; resto em expander "Opções avançadas" |
| Item 2 — análise | `c76eb0a` | `pages/analise_dados.py` + `tests/test_analise_visao_v3.py` (novo, 8 testes): 4 indicadores + 3 abas; aba ativa navy; alertas empilhados removidos |
| Item 3 — relatório | `715e8aa` | `pages/gerar_relatorio.py` + `tests/test_relatorio_visao_v3.py` (novo, 6 testes) (+1 expectativa em `test_home_v3.py`): formulário no corpo, período só texto, sem duplicações |
| Item 4 — login/polimento | `4bb40d5` | `app.py` + `assets/custom.css` (+9 linhas) + `tests/test_login_visao_v3.py` (novo, 4 testes): login em cartão centralizado; padding-top único para as 4 telas |
| R1 — verificação integrada + catálogo | `3dffc21` (branch do revisor) | Só `docs/casos-de-teste.md` (seção Fase 7, CT-F7-01…11) + `docs/casos-de-teste.pdf` regenerado (87 páginas). Nenhum código de produção alterado |
| A1 — re-verificação do arquiteto | sem commit (somente leitura) | `pip-audit -r requirements.txt` limpo + testes direcionados; 3 achados classificados como bloqueadores, 1 como pendência preexistente |
| C1 — rodada corretiva | `2fecfc1` | 3 bloqueadores corrigidos (contraste do Baixar PDF, cartões alinhados, export em Correspondências) + testes ajustados; 20 testes direcionados passando |
| V2 — verificação incremental | sem commit novo | Arquiteto executou localmente os 3 arquivos afetados sobre `2fecfc1`: **20 passed**; revisor rápido impedido por `certificate is not yet valid` (2 tentativas, sem execução) |
| este doc | branch atual | `docs/documentacao-final-fase-7.md` (este arquivo) |

Total do diff da fase (4 itens + corretiva): 10 arquivos de código/teste,
+1847/−1418 (itens: +1719/−1415; corretiva: +128/−3, dos quais só ~4 linhas
líquidas de produção). Nenhum diff tocou `modules/report_executivo.py`, o
matching ou as constantes do B×C. Nenhum número do baseline B×C foi alterado
em nenhuma rodada (77,8% / 14 de 18 / 8 itens / R$ 147,55).

## 1. O que foi entregue — versão leiga

Pense no sistema como um escritório que confere o extrato do banco contra a
contabilidade. A reforma da entrada (fase 6) já tinha deixado a recepção
limpa; esta fase arrumou as outras três salas mais a porta de entrada: a sala
de entrega dos papéis (importação) agora mostra só duas caixas lado a lado e
um botão de "seguir", com todo o resto guardado numa gaveta fechada chamada
"Opções avançadas"; a sala de conferência (análise) mostra 4 números grandes
e 3 pastas separadas, cada uma com seu botão de salvar em CSV; a sala do
relatório final tem um formulário simples e um botão de gerar, sem nada
repetido das outras salas; e a porta (login) virou um cartão centralizado.
Nada do que estava guardado foi jogado fora — só saiu da vista. Os números
da conferência continuam exatamente os mesmos, e tudo foi testado de
verdade. O trabalho está salvo nos computadores dos agentes, ainda não
publicado: falta alguém com acesso ao GitHub fazer o envio final.

---

## 2. Item 1 — tela de importação (técnico)

**Mudança (`661bffd`):** visão padrão = título "Importação de Dados", 2
uploaders lado a lado em cartões (`st.container(border=True)`, Extrato
Bancário + Lançamentos Contábeis), estado do arquivo (nome, tamanho, tipo
detectado), UMA mensagem de erro por vez e um único botão primário "Ir para
Análise de Dados" (só com dados prontos). Sidebar só com navegação. Nada
apagado: método de importação (Link de Pastas na Nuvem / Links Diretos),
"Validação por Nome de Arquivo", "Permitir OFX no lado contábil", "Guia
Completo", "Modo Desenvolvedor", "Ajuda", prévia dos dataframes e "Analisar
Estrutura do CNAB" foram movidos para um único expander fechado "Opções
avançadas" no fim da página, com comportamento preservado. Conferência
função a função: parsers OFX/CNAB/CSV/PDF, validações e `processar_arquivo`
ficaram byte a byte idênticos — só UI reorganizada, mais remoção de
`st.info`/`st.success` decorativos do caminho padrão.

**Testes (AppTest, escritos antes):** `tests/test_importacao_opcoes_avancadas.py`
(3 testes: 2 uploaders + sidebar só navegação; expander fechado com todos os
recursos; botão primário com dados prontos) + 3 arquivos existentes da página
→ **16 passed**. Sem pytest completo, sem E2E. Diff: 2 arq., +617/−574
(maioria reordenação). Chamadas da rodada: ~29 (dentro do teto de ~35).

## 2. Item 1 — versão leiga

A sala de entrega tinha papéis espalhados por todo lado: botões, guias e
opções avançadas misturados com o essencial. Agora quem entra vê só duas
caixas ("extrato do banco" e "papéis da contabilidade") e um botão de
seguir — todo o resto foi guardado numa gaveta fechada, sem jogar nada fora.
Há testes que abrem a sala e conferem: as duas caixas estão lá, a gaveta
existe e está fechada, e tudo que foi guardado continua dentro dela.

---

## 3. Item 2 — tela de análise (técnico)

**Mudança (`c76eb0a`):** visão padrão = título, botão primário "Executar
Análise de Correspondências" e, depois de rodar, 4 indicadores (Cobertura de
análise, Correspondências X/Y, Itens em aberto, Diferença líquida = soma
contábil − soma extrato, formato `R$ {valor:,.2f}` já usado no projeto).
3 abas de nível superior — Correspondências / Divergências / Similaridade —
são as mesmas 3 listas de antes, sem misturar: Divergências mostra as duas
listas como seções separadas (não mais sub-abas), Similaridade virou aba
própria; cada lista com seu exportador CSV (`gerar_csv_divergencias` da fase
5b, nenhum exportador novo). Estatísticas Detalhadas, Dashboard Interativo e
Detalhes Técnicos viraram abas aninhadas num expander fechado "Detalhes".
CSS da aba ativa corrigido: texto + sublinhado navy `#002D72` (cor dos
botões do tema v3), sem fundo azul `#0078D4` nem sublinhado vermelho
`#FF4B4B`. Alertas de sucesso empilhados no topo removidos; caminho de erro
intacto. Único ajuste colateral: renomeado `st.metric("Correspondências")`
duplicado no Dashboard para "Total de Correspondências". Matching,
tolerâncias e cálculos intocados.

**Testes (AppTest, escritos antes, dados sintéticos com 2 correspondências +
1 em aberto de cada lado):** `tests/test_analise_visao_v3.py` (8 testes:
botão + ausência dos indicadores antes de rodar; 4 indicadores corretos
depois; 3 abas sem vazamento de Estatísticas/Dashboard; Divergências com 2
listas + 2 CSVs; Similaridade vazia sem quebrar; expander "Detalhes";
botão "GERAR RELATÓRIO"; CSS navy) + 5 arquivos existentes → **87 passed**.
Sem pytest completo, sem E2E. Diff: 2 arq., +545/−297. Chamadas: ~55 (acima
do teto de ~35 — registrado na rodada: exploração da API de tabs/expanders
aninhados do AppTest justificou o estouro; item fechou limpo em 1 commit).

## 3. Item 2 — versão leiga

A sala de conferência agora tem um botão grande de "conferir" e, depois,
quatro números grandes na parede (quanto foi conferido, quantos bateram,
quantos faltam, quanto sobra de diferença) e três pastas separadas — uma
para o que bateu, uma para o que não bateu, uma para os parecidos — cada
uma com seu botão de salvar. Os painéis complicados foram para uma gaveta.
A aba aberta agora é marcada com um traço azul-marinho, não mais com fundo
azul e traço vermelho. A conta em si (o jeito de comparar) não mudou.

---

## 4. Item 3 — tela de relatório (técnico)

**Mudança (`715e8aa`):** título "Relatório Final"; formulário (Nome da
Empresa, Nome do Contador/Analista, Classificação, Observações) saiu da
sidebar para o corpo (2 colunas + texto); período 100% automático
(`calcular_periodo_real`, sem override desde a fase 6) exibido como texto
somente-leitura "📅 Período: dd/mm/aaaa a dd/mm/aaaa, calculado dos
arquivos"; botão primário "Gerar Relatório" (key
`btn_gerar_relatorio_analise` preservada, usada pelos testes de auditoria);
depois de gerar: link "📥 Baixar PDF" + mensagem de sucesso; sem
pré-visualização/iframe (já removido na fase 6). Removidos "Resumo da
Análise" e "Sumário Executivo" (gráficos + abas) — duplicavam a análise e,
conferido no código, não alimentavam o PDF (`gerar_relatorio_executivo`
calcula tudo de `resultados_analise`/`extrato_df`/`contabil_df`; a variável
`divergencias_tabela` nunca era repassada) — junto com 4 funções auxiliares
mortas + import `SequenceMatcher` não usado. Em "Próximas Ações": removidos
botões que só duplicavam a sidebar; mantido "Nova Importação" (limpa a
sessão). PDF, auditoria (`audit.log_report_generation`) e log intocados.
`test_home_v3.py`: título de navegação "Relatório de Análise" → "Relatório
Final" (intencional, acompanha o novo título).

**Testes (AppTest, escritos antes):** `tests/test_relatorio_visao_v3.py`
(6 testes: título, formulário no corpo, período só-texto com datas certas,
ausência de meta/preview/iframe, ausência das duplicações, key preservada +
fluxo com `gerar_relatorio_executivo` mockado) + 6 arquivos existentes →
**82 passed**. Sem pytest completo, sem E2E. Diff: 3 arq., +316/−493 (maioria
remoção de código morto/duplicado). Chamadas: ~30 (dentro do teto).

## 4. Item 3 — versão leiga

A sala do relatório final tinha, além do formulário, cópias dos gráficos e
resumos da sala ao lado — ocupando espaço à toa, porque o boletim impresso
é montado sozinho com os dados originais, não com essas cópias. As cópias
foram retiradas (e o código que só servia para elas, apagado), o formulário
saiu da lateral e foi para o meio da mesa, e o período aparece como um
aviso fixo ("de 15 de junho a 16 de julho de 2025, descoberto dos arquivos"),
sem campo para digitar. O botão gera o PDF, e depois aparece o link de
baixar — sem mostrar o PDF dentro da página.

---

## 5. Item 4 — login e polimento (técnico)

**Mudança (`4bb40d5`):** login conforme `mockup-login`: cartão centralizado
(`st.columns` + `st.container(border=True)`), título "🔐 Sistema de
Conciliação Bancária" (texto já existente), campos "Username ou Email" /
"Senha", aba "Registrar" preservada; botão "Entrar" virou `type="primary"`
(consistência com os demais). `assets/custom.css`: 1 regra de `padding-top`
em `.block-container` valendo para as 4 telas (o `aplicar_tema()` injeta o
mesmo CSS em toda página). `login_user`/`logout_user`/`register_user`
intocados — zero mudança de comportamento.

**Testes (AppTest, escritos antes — lacuna real: nenhum teste dirigia a UI
de login/sair/cadastro, só as funções Python):** `tests/test_login_visao_v3.py`
(4 testes: título+cartão+abas+campos; login via formulário; logout via
"Sair"; cadastro + login do novo usuário) + 6 arquivos existentes → **61
passed**. Sem pytest completo, sem E2E. Diff: 3 arq., +241/−51. Chamadas:
~28 (dentro do teto).

**Nota registrada pelo desenvolvedor para o revisor:** rodando
`test_home_v3.py::test_cartao_navega_para_a_pagina_correspondente` isolado,
o caso "Relatório Final" estoura o timeout de 3 s do AppTest — pré-existente
antes do item 4 (import a frio do WeasyPrint via `modules.report_executivo`),
some quando outro teste "esquenta" o import no mesmo processo; fora do
escopo do item, não mexido.

## 5. Item 4 — versão leiga

A porta de entrada era um formulário esticado na página toda; agora é um
cartão no centro, com o mesmo nome, os mesmos campos e a mesma aba de
cadastro — só a aparência mudou, e o botão de entrar ganhou o mesmo destaque
dos outros botões importantes. Um único ajuste de respiro no topo vale para
todas as telas de uma vez. As fechaduras (entrar, sair, cadastrar) não foram
trocadas. Faltavam testes que realmente digitassem na porta em vez de só
testar a fechadura por dentro — foram criados 4.

---

## 6. R1 — verificação integrada: pytest, E2E, invariantes e PDF (técnico)

Executada pelo revisor rápido sobre `4bb40d5` (fast-forward dos 4 commits
sobre `2f15199`, sem rebase), com seção **Fase 7 (CT-F7-01…11)** no catálogo
+ PDF regenerado (commit `3dffc21`, só docs, branch do revisor).
Ambiente: Python 3.10.12, pytest 9.1.1, Streamlit 1.64.0, Playwright 1.62 +
Chromium headless, WeasyPrint 70. Dados 100% sintéticos (OFXs B/C de exemplo
+ OFX sintético de 25.000 transações gerado pelo roteiro).

| Verificação | Resultado real |
|---|---|
| Suíte completa | `pytest tests/ -q` → **446 passed, 1 skipped** (80,44 s; 447 coletados) vs base da issue (425) → **+21**, todos nos 4 arquivos novos da fase (8+6+4+3); único skip = `test_pluralizacao.py:94`, pré-existente |
| E2E real | Streamlit porta 8597 + navegador, viewport 1440×2200, banco/audit/log isolados e zerados (5 execuções; a reportada é a 5ª, com roteiro corrigido) → **41 PASS / 2 FAIL em 43 verificações** |
| Login/Home | abas Login/Registrar, `admin`/`admin123` loga → Home; logout volta; Home com exatamente 3 botões de etapa, 0 duplicados |
| Importação | 2 uploaders lado a lado, estado `B_1234490.ofx · 4.5KB · Tipo: OFX`, 1 erro por vez, 1 botão `Ir para Análise`, sidebar só navegação, "Opções avançadas" fechado com recursos movidos |
| OFX 25.000 | 5.150.574 bytes; exatamente 1 mensagem de limite 20000, `mensagens_duplicadas=[]` |
| Análise | 4 indicadores **77,8% / 14/18 / 8 itens / R$ 147,55** (= B×C da base), 3 abas, 8/8 expanders fechados, 0 alertas empilhados, aba ativa navy `#002D72` sem fundo azul/vermelho |
| Exportações CSV | 3 downloads reais (Divergências Bancárias 1264 B, Contábeis 1240 B, Similaridades 677 B) — **Correspondências sem botão** (achado §7) |
| Relatório/PDF | 4 campos certos, período só texto `15/06/2025 a 16/07/2025`, `meta=False`, `campo_periodo=False`, `iframes=0`; PDF Executivo **60.292 bytes, 9 páginas**, 0 "meta", 0 credencial/caminho/`Traceback` |
| B×C preservado | fase 7 **não mudou nenhum número** |
| Mockups | 5 telas página-inteira + 5 montagens lado a lado anexadas na issue; divergências corretas/propositais: login sem logo "SB"/link Ajuda (issue proíbe nome inventado e manda ajuda p/ Opções avançadas); relatório sem período editável/preview (exigido pela issue); uploader nativo do Streamlit em vez de dropzone própria ("adapte ao que o Streamlit consegue"); home mantém botão navy sob cada cartão (herdado da fase 6, fora de escopo) |
| Catálogo | CT-F7: **8 PASS · 2 FAIL (CT-F7-05 export por aba, CT-F7-10 visuais) · 1 NAO EXECUTADO (CT-F7-11, fora de escopo incl. CT-AUTH-03/05)**; PDF do catálogo: **87 páginas** |

Ajustes da rodada foram **no script de E2E, não na app**. Caça ativa a
visuais: contraste 0 ofensores em login/home/análise/relatório; 0
sobreposição visível; 0 botões duplicados; 0 emoji quebrado; área branca
inferior = viewport 2200 px, não buraco de layout.

## 6. R1 — versão leiga

Depois da obra, um inspetor passou o pente-fino de verdade: rodou todos os
446 testes automáticos (21 novos, todos verdes), dirigiu o sistema num
navegador de verdade do login até baixar o relatório (43 checagens: 41
certas, 2 com problema — ver seção 7), conferiu que os números da
conciliação não mudaram nem uma vírgula, que o PDF tem 9 páginas com o
período correto, fotografou as 5 telas inteiras e comparou com os desenhos
(anotando cada diferença honestamente). O caderno de testes ganhou 11 casos
novos e foi refeito com 87 páginas. Achou 4 problemas (seção 7) e não mexeu
em nada — deixou para o arquiteto julgar e para o desenvolvedor corrigir.

---

## 7. A1 + C1 — os 4 achados, o julgamento e a correção (técnico)

O arquiteto re-verificou sem alterar código: `pip-audit -r requirements.txt`
→ **No known vulnerabilities found** (37 vulnerabilidades do ambiente global
fora do escopo, separadas da auditoria); testes direcionados → **17
passed**; "Opções avançadas" confirmado com teste executado (1 expander
fechado, recursos preservados, sidebar sem configs); relatório confirmado
(formulário no corpo, período texto `15/06/2025 a 16/07/2025`, sem meta,
sem período editável, sem iframe, download só após gerar); PDF 9 páginas
confirmado. Classificação:

1. **Link "📥 Baixar PDF" com contraste 2,7796:1 (branco sobre `#4CAF50`,
   mínimo AA 4,5) — CORRIGIR.** Ação principal de saída ilegível; legado
   (desde `56693c8`), mas inaceitável manter no fluxo entregue.
2. **`st.success` da importação a 4,4956:1 (mín. 4,5) — pendência
   PREEXISTENTE não bloqueante, registrada.** Faltam 0,09%; estilo padrão do
   Streamlit, já existia antes da fase 7.
3. **Cartões da importação desalinhados (~61 px; título de Lançamentos
   Contábeis fora do container, `importacao_dados.py:1023-1024` vs `:780-781`)
   — CORRIGIR.** Único defeito introduzido pela fase 7; viola o item 4.
4. **Aba Correspondências sem botão Exportar CSV (2 em Divergências, 1 em
   Similaridade) — CORRIGIR.** Critério "Exportar CSV por aba" incompleto;
   exportadores da 5b preservados, mas contrato da fase exige a aba que
   falta; teste antigo não cobria.

**Correção (`2fecfc1`, testes antes do código, 1 commit):** (1) cor do link
trocada para navy `#002D72`/branco (~13:1, mesma dos botões primários) —
só o `style`, `href`/`download` idênticos, razão recalculada pela fórmula
WCAG de luminância; (2) `st.subheader("📊 Lançamentos Contábeis")` movido
para dentro do `st.container(border=True)` — mesma estrutura nas 2 colunas;
(3) `st.download_button` na aba Correspondências com o mesmo
`gerar_csv_divergencias` (proteção anti formula-injection, pt-BR), sem
misturar listas. `st.success` intocado conforme o julgamento. Testes: 1
novo/ajustado por bloqueador (contraste WCAG reproduzindo os 2,7796:1 antes
da correção; estrutura alinhada dos 2 cartões; Correspondências com
exatamente 1 exportador sem mudar as demais) — **20 passed** nos 3 arquivos,
sem pytest completo, sem E2E. Diff: 6 arq., +128/−3 (produção: ~4 linhas
líquidas). Chamadas: ~30. Matching, PDF e B×C intocados.

## 7. A1 + C1 — versão leiga

O segundo inspetor confirmou que as peças não têm vulnerabilidade conhecida
e que nada foi jogado fora — mas carimbou 3 consertos obrigatórios e 1
aviso: (1) o link verde de baixar o PDF tinha letra branca quase invisível
— trocado pelo azul-marinho dos outros botões, mesma cor, agora legível;
(2) as duas caixas da importação estavam tortas, uma com o título para fora
— endireitadas; (3) a pasta "o que bateu" era a única sem botão de salvar
— ganhou o seu, igual aos outros; (4) uns avisos verdes têm um contraste
0,09% abaixo do ideal, mas isso vem do padrão do sistema e já existia antes
— fica anotado, sem travar a entrega. Cada conserto ganhou seu teste antes,
e os 20 testes passaram.

---

## 8. V2 — verificação incremental da corretiva (técnico)

Escopo deliberadamente restrito, definido pelo coordenador após queda de
runtime no fim de semana (2 falhas `runtime did not reconnect`/`runtime
unavailable`, sem relação com o trabalho): rodar **somente os 3 arquivos de
teste afetados** e reconfirmar contraste/alinhamento/exportação + B×C
inalterado — **sem repetir a suíte completa nem o E2E completo**.

- O revisor rápido recebeu a tarefa **2 vezes e não conseguiu executar
  nenhuma**: ambas as tentativas morreram no runtime com
  `certificate is not yet valid`, antes de qualquer teste. Nenhum resultado
  do revisor existe para esta etapa — e nenhuma falha de produto ou de teste
  foi observada (o erro é externo, de certificado do ambiente).
- Diante do impedimento repetido, o arquiteto deu segunda opinião objetiva e
  executou ele mesmo, no checkout local do commit correto (`2fecfc1`),
  somente os 3 arquivos (`test_relatorio_visao_v3.py`,
  `test_importacao_opcoes_avancadas.py`, `test_analise_visao_v3.py`):
  **20 passed**, 1 warning de depreciação WeasyPrint/HarfBuzz. Sem rede,
  sem dados reais, sem CT-AUTH-03/05, sem espera de tempo real.
- Os 20 testes cobrem os 3 ajustes (contraste WCAG do Baixar PDF, cartões
  alinhados, export próprio em Correspondências); evidências anteriores
  registram B×C e `st.success` marginal inalterados.
- **Decisão registrada: aceitar com ressalva.** A correção incremental está
  verificada localmente no commit correto, sem depender do runtime com erro
  de certificado; a ressalva operacional é que a execução *pelo revisor
  rápido* continua impedida pelo certificado. Não repetir E2E/suíte completa
  foi intencional e não invalida os resultados anteriores já registrados
  (446 testes e E2E 41/43 antes da corretiva). A issue saiu de `blocked` e
  voltou a `in_progress` para esta documentação final.

## 8. V2 — versão leiga

Faltava só reconferir os 3 consertos, sem refazer tudo. O inspetor de campo
tentou duas vezes, mas o carro dele não ligou (um erro de certificado do
computador, nada a ver com a obra) — então um segundo técnico fez a mesma
checagem restrita no lugar certo e confirmou: os 20 testes passam. A entrega
vale **com essa ressalva honesta**: o conserto foi conferido, mas não foi o
inspetor original quem conseguiu rodar — o carro dele continua sem ligar.

---

## 9. O que NÃO foi verificado — limitações explícitas (técnico e leigo)

- **`CT-AUTH-03` (bloqueio após 5 falhas + liberação em 15 min) e
  `CT-AUTH-05` (expiração de sessão em 24 h): NÃO EXECUTADOS por dependerem
  de espera de tempo real.** Excluídos por decisão do usuário antes de
  qualquer execução (registrado em CT-F7-11); nenhum PASS/FAIL é inferido.
  *Leigo: dois testes que exigem esperar de verdade ficaram como "não
  feitos" — sem chute de resultado.*
- **Verificação incremental sem o revisor rápido.** As 2 tentativas do
  revisor morreram em `certificate is not yet valid` antes de executar;
  quem executou os 20 testes foi o arquiteto, localmente sobre `2fecfc1`.
  *Leigo: o carimbo final da vistoria veio do segundo técnico, porque o
  primeiro ficou sem computador funcionando.*
- **Sem repetição de pytest completo/E2E após a corretiva — intencional.**
  A suíte completa (446) e o E2E (41/43) valem para `4bb40d5`; sobre
  `2fecfc1` valem os 20 direcionados + 17 da re-verificação + invariantes
  B×C reconfirmados. Mudanças de produção na corretiva somam ~4 linhas
  (cor, reordenação, 1 bloco de exportação), sem tocar matching/PDF/B×C.
  *Leigo: depois dos 3 consertos pequenos, refez-se só a prova dos
  consertos — não a vistoria inteira do prédio; os consertos não mexeram na
  estrutura.*
- **`st.success` marginal (4,4956:1) permanece como está** — pré-existente,
  documentado, não bloqueante; se o aceite exigir WCAG AA estrito, corrigir
  o tema em rodada separada.
- **Timeout isolado pré-existente:** `test_home_v3.py::...Relatório Final`
  sozinho estoura 3 s (import a frio do WeasyPrint); some com o import
  aquecido; fora de escopo, não mexido.
- **Sem push/PR por falta de credencial.** O squad não tem credencial Git:
  os commits da fase + este documento existem nos branches locais, sem
  entrega no GitHub nesta rodada. Falta alguém com acesso fazer o envio.
  *Leigo: o trabalho está pronto mas guardado nos computadores dos agentes;
  ninguém conseguiu publicar ainda.*
- **Mockups são referência qualitativa**, sem baseline numérica de pixels;
  contraste/sobreposição valem para o visível no viewport 1440×2200.
  Evidências brutas do E2E ficam fora do repo; os anexos na issue são as
  telas, montagens, cenário OFX 25.000 e recorte dos cartões.
- Revisor de segurança gratuito não usado, conforme a issue (checagem ficou
  com o arquiteto). Revisão limitada a rodar e conferir: arquitetura, design
  e segurança mais profunda seguem com o arquiteto, como definido para os
  cargos.

---

## 10. Comandos relevantes (executados nas rodadas, não nesta etapa)

```bash
# Implementação (1 commit por item, teste AppTest antes do código)
# item 1: pytest <test_importacao_opcoes_avancadas + 3 arquivos da página> → 16 passed
# item 2: pytest <test_analise_visao_v3 + 5 arquivos>                       → 87 passed
# item 3: pytest <test_relatorio_visao_v3 + 6 arquivos>                     → 82 passed
# item 4: pytest <test_login_visao_v3 + 6 arquivos>                         → 61 passed

# R1 — verificação integrada (revisor rápido, sobre 4bb40d5)
python3 -m pytest tests/ -q                    # 446 passed, 1 skipped (80,44 s)
# E2E: Streamlit local :8597 + Playwright/Chromium, viewport 1440x2200
#   → 41 PASS / 2 FAIL em 43 verificações; PDF 9 páginas; B×C inalterado
python3 scripts/gerar_pdf_casos_de_teste.py    # catálogo → 87 páginas (3dffc21)

# A1 — re-verificação (arquiteto, somente leitura)
pip-audit -r requirements.txt                  # No known vulnerabilities found
python3 -m pytest tests/test_importacao_opcoes_avancadas.py \
  tests/test_relatorio_visao_v3.py tests/test_analise_visao_v3.py -q  # 17 passed

# C1 — corretiva (desenvolvedor, 1 commit 2fecfc1, ~30 chamadas, +128/−3)
python3 -m pytest tests/test_relatorio_visao_v3.py \
  tests/test_importacao_opcoes_avancadas.py tests/test_analise_visao_v3.py -q  # 20 passed

# V2 — incremental (arquiteto, local, sobre 2fecfc1; revisor impedido 2× por certificado)
python3 -m pytest tests/test_relatorio_visao_v3.py \
  tests/test_importacao_opcoes_avancadas.py tests/test_analise_visao_v3.py -q  # 20 passed
```

---

## 11. Tokens, chamadas e diff por rodada

O runtime não expõe a este documentador um contador próprio de consumo;
**nenhum número é declarado para esta etapa** — registrar valor inventado
seria falsificação. Situação por rodada, conforme os relatos na issue:

- Desenvolvedor principal: item 1 ~29 chamadas, diff +617/−574 (reordenação);
  item 2 ~55 chamadas (estouro registrado: exploração da API AppTest),
  diff +545/−297; item 3 ~30 chamadas, diff +316/−493 (remoção de código
  morto); item 4 ~28 chamadas, diff +241/−51; corretiva C1 ~30 chamadas,
  diff +128/−3 (~4 linhas líquidas de produção + testes). Contagens de
  tokens por rodada do desenvolvedor não foram declaradas nos comentários —
  nenhum número é presumido aqui.
- Revisor rápido: suíte 446 passed + E2E 41/43 com 13 anexos na issue;
  consumo de tokens não declarado no relato — nenhum número presumido. Na
  etapa V2, 2 tentativas sem execução (`certificate is not yet valid`).
- Arquiteto: `pip-audit` limpo, 17 passed na re-verificação, 20 passed na
  V2 local; consumo de tokens não declarado — nenhum número presumido.
- Esta documentação: sem contador disponível no ambiente; nenhum número
  individual é atribuído a qualquer rodada além do que cada agente declarou
  nos próprios comentários (chamadas e diffs acima).
