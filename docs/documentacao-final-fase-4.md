# conc_banc — Fase 4: documentação final (clareza do relatório executivo, 3 itens)

Fase 4 da revisão do app de conciliação bancária (Streamlit): 3 ajustes pequenos e
independentes só na clareza da seção 5 do relatório executivo
(`modules/report_executivo.py` + `templates/relatorio_executivo.html.j2`), sem mudar
nenhum número do caso B×C. Base: `main` com fases 1, 2, 3 e 3b + os commits da fase 4
(listados abaixo, em worktrees locais de outros agentes, sem push).
Login de teste: `admin` / `admin123` (conta bootstrap local de teste, dados sintéticos
em `Exemplos/B_1234490.ofx` e `Exemplos/C_1234490.ofx`).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga** (analogia do
dia a dia). Este documento apenas relata o que os agentes responsáveis executaram e
reportaram na issue — nada foi marcado como verificado sem execução real, e o que não
foi verificado está declarado como tal na seção 8. Este documento não altera código nem
nenhum outro documento.

> Nota de procedência: os commits `5a00031`, `3021236`, `1f358e0` (3 rodadas) e
> `90e6c76` (catálogo) estão em worktrees/branches locais de outros agentes e **não
> foram publicados (sem push/PR — o squad não tem credencial Git)**. Este arquivo foi
> escrito nesta branch a partir do `main`. O conteúdo abaixo reproduz fielmente os
> relatos dos agentes na issue, sem reexecução independente nesta etapa de
> documentação.

---

## 1. O que foi entregue — commits e arquivos (técnico)

| Etapa | Commit (local, sem push) | O que faz |
|-------|--------------------------|-----------|
| Rodada 1 — pontes consistentes | `5a00031` | `calcular_ponte()` expõe `ajuste_similaridade_abs_fmt` + `ajuste_similaridade_operador`; seção 5 ganha 2 linhas na tabela (ajuste por similaridade e líquida após ajuste) + parágrafo com **R$ 148,55 − R$ 1,00 = R$ 147,55** |
| Rodada 2 — legenda de rótulos | `3021236` | Parágrafo único de legenda (1–2 linhas) no início da seção 5: "par provável apontado pelo sistema" × "hipótese do analista" |
| Rodada 3 — resumo dos itens em aberto | `1f358e0` | Nova função `_resumo_itens_abertos()` + linha no início da seção 5: **4 em par provável + 2 em par por hipótese + 2 sem par = 8** |
| Verificação + catálogo | `90e6c76` | Só `docs/casos-de-teste.md` (seção única "Fase 4", CT-F4-01…CT-F4-07) + `docs/casos-de-teste.pdf` regenerado (37 páginas) |
| este doc | branch atual | `docs/documentacao-final-fase-4.md` (este arquivo) |

Nenhum valor do baseline B×C foi recalculado — só apresentação/texto explicativo.

## 1. O que foi entregue — versão leiga

Pense no relatório como a conta final de um escritório que confere o extrato do banco
contra a contabilidade. Os números já estavam certos, mas três trechos confundiam quem
lia: a conta de fechamento parecia não bater, dois nomes de etiqueta não eram
explicados, e faltava um resumão no começo dizendo quantos itens estavam em cada
situação. Esta fase consertou só o texto — os números continuam os mesmos — e testou
tudo de verdade. Os trabalhos estão salvos nos computadores dos agentes, ainda não
publicados: falta alguém com acesso ao GitHub fazer o envio final.

---

## 2. Rodada 1 — pontes consistentes (técnico)

**Problema:** a seção 5 mostrava a ponte compacta fechando em R$ 147,55 e a "ponte
detalhada" fechando em R$ 148,55 (líquido dos itens em aberto antes do ajuste de
R$ 1,00 das diferenças por similaridade), sem explicar a passagem entre os dois.
**Depois:** a tabela detalhada traz `R$ 148,55` → linha `Ajuste das diferenças aceitas
por similaridade … R$ -1,00` (com nota "não é um valor novo") → `R$ 147,55`, e um
parágrafo em linguagem simples fecha com a fórmula em negrito
**R$ 148,55 − R$ 1,00 = R$ 147,55**, explicando que o R$ 1,00 é o mesmo ajuste já
somado na ponte compacta. Teste: `test_ponte_expoe_ajuste_de_similaridade_como_operacao_de_sinal_unico`
+ `test_pdf_explicita_a_passagem_da_ponte_detalhada_para_a_compacta` → 2 passed.

## 2. Rodada 1 — versão leiga

Era como uma conta que terminava em dois valores diferentes sem dizer por quê. Agora o
relatório mostra a "conta intermediária" e a linha que liga uma à outra, do tipo
"148,55 menos 1,00 dá 147,55" — o R$ 1,00 é um desconto que já existia na outra conta,
não um número novo.

---

## 3. Rodada 2 — legenda de rótulos (técnico)

**Depois:** parágrafo único de legenda (1–2 linhas), uma única vez no início da seção 5:
**"par provável apontado pelo sistema"** = correspondência calculada automaticamente por
similaridade (valor, data e texto parecidos); **"hipótese do analista"** = par
encontrado só por regra objetiva de mesma descrição + mesma data, sem respaldo do
sistema. Fecha dizendo que os dois ainda precisam de confirmação manual antes de virar
ajuste. Teste: `test_pdf_contem_legenda_dos_rotulos_par_provavel_e_hipotese`
(legenda 1 vez, rótulos e baseline intactos) +
`test_pdf_continua_com_no_maximo_10_paginas_apos_a_legenda` (PDF segue com 9 páginas)
→ 2 passed.

## 3. Rodada 2 — versão leiga

O relatório usava dois apelidos ("par provável" e "hipótese") sem dizer o que cada um
queria dizer. Agora tem um mini-dicionário logo no começo da seção: um é o "palpite do
computador" (ele achou parecido), o outro é uma "pista por regra simples" (mesmo nome e
mesma data). E avisa: nenhum dos dois vale sozinho, alguém precisa confirmar.

---

## 4. Rodada 3 — resumo dos itens em aberto (técnico)

**Depois:** linha no início da seção 5 com as contagens derivadas da **saída real** de
`_construir_ponte_detalhada` (não hard-coded), via `_resumo_itens_abertos()`, usando os
rótulos da legenda da Rodada 2. No B×C real: **4 em par provável apontado pelo sistema
+ 2 em par por hipótese do analista + 2 sem par nenhum = 8** (cada par conta os dois
lados, extrato + contábil, como itens individuais, para somar com o total de itens em
aberto). Cruzamento: 2 pares prováveis × 2 lados = 4, 1 par por hipótese × 2 = 2,
2 sem par = 2, contra "Extrato sem lançamento (4)" + "Lançamentos sem extrato (4)".
Teste: `test_pdf_resumo_itens_abertos_soma_8_extraida_do_relatorio` (extrai as 3
contagens do texto renderizado por regex e confirma soma 8) +
`test_resumo_itens_abertos_soma_bate_com_total_sem_par_sintetico` (cenário sintético)
→ 2 passed.

## 4. Rodada 3 — versão leiga

Faltava um placar no começo da seção: "dos 8 itens sem match, quantos estão em cada
situação?". Agora tem: 4 já têm palpite do computador, 2 têm só a pista simples e 2 não
têm par nenhum — 4 + 2 + 2 = 8, a conta fecha. O número é contado de verdade do
relatório, não digitado à mão.

---

## 5. Resultados reais da verificação (técnico + leigo)

Reportados pelo desenvolvedor_revisor_rápido, com execução real de comandos:

- **Suíte completa:** `pytest -q` → **191 passed, 1 skipped** (baseline da fase 3b era
  185 passed, 1 skipped; a diferença é exatamente os **6 testes novos** das 3 rodadas,
  0 falhas). Em leigo: rodaram todos os testes automáticos do projeto — 191
  passaram, 1 foi pulado de propósito, nenhum quebrou.
- **6 testes novos isolados:** 6 passed (os 2 de cada rodada listados acima).
- **E2E real 5/5:** Streamlit local + Chromium/Playwright, banco zerado, só
  `B_1234490.ofx` e `C_1234490.ofx` — login `admin/admin123`, importação, análise,
  formato `Executivo`, geração e download do PDF pela UI (60.362 bytes, mensagem
  "Relatório Executivo gerado com sucesso").
- **PDF Executivo B×C:** **9 páginas** (limite ≤ 10), A4, WeasyPrint 70.0; as 9 páginas
  foram rasterizadas (`pdftoppm`) e inspecionadas uma a uma — legíveis, sem corte.
- **Invariantes B×C confirmados no texto real extraído:** 14 correspondências de 18
  (77,8%), efetiva 61,1% (11 exatas), 4 + 4 divergências = 8, saldos extrato
  R$ −140,88 / contábil R$ 6,67, diferença líquida **R$ 147,55**, resíduo **R$ 0,00**,
  recálculo 1.362,33 − 1.213,78 − 1,00 = 147,55.
- **Catálogo:** `docs/casos-de-teste.md` ganhou uma única seção "Fase 4" com
  **CT-F4-01…CT-F4-07** no padrão do squad + linha da Fase 4 no "Resumo por fase";
  `docs/casos-de-teste.pdf` regenerado (**37 páginas**). Anexos do revisor: catálogo
  PDF, `relatorio_executivo_bxc.pdf` baixado pela UI e páginas 5–6 rasterizadas.

---

## 6. Economia de cota — tokens por rodada (técnico + leigo)

Regra da issue: 1 item por rodada para o Claude (desenvolvedor_principal), sem
verificação pesada por ele. Valores **reportados pelo próprio Claude** (não
verificáveis pelo revisor):

| Rodada | Consumo aprox. reportado |
|--------|--------------------------|
| R1 (pontes) | ~110 mil tokens |
| R2 (legenda) | ~14 mil tokens |
| R3 (resumo) | ~19 mil tokens |

Em leigo: para economizar, cada pedacinho foi feito separado, um de cada vez, e o
robô que fez anotou quanta "energia" gastou em cada um. Esses números vieram do
próprio robô — ninguém mediu de fora.

**Sem push e sem PR** — o squad não tem credencial Git; os commits ficam somente nos
worktrees locais.

---

## 7. Segurança — aprovação (técnico + leigo)

O revisor de segurança fez a checagem curta e deu **APROVADO, sem bloqueador**:

- `admin/admin123` é **credencial bootstrap local sintética, de teste**: criada só se
  não existir (`app.py:87`, hash PBKDF2 com salt, banco `*.db` não commitado), usada
  só no E2E local com banco zerado. Aparece em claro só no seed e nos passos de teste
  do catálogo — esperado, não é vazamento de senha real. `SECRET_KEY` não é hard-coded
  (`auth_middleware.py:39-43`: usa `CONCILIACAO_SECRET_KEY` ou `secrets.token_hex(32)`).
- OFX `B_1234490.ofx`/`C_1234490.ofx`: dados sintéticos (UUID v4 como ACCTID, MEMOs
  genéricos), sem CPF/CNPJ/e-mail real.
- PDFs/PNGs anexados: sem `admin123`, sem PII; `casos-de-teste.pdf` cita
  `admin/admin123` só como passo de teste.
- **Recomendação não bloqueante (produção futura):** manter o rótulo "conta bootstrap
  local de teste"; se houver deploy produtivo, exigir troca no primeiro acesso ou
  desabilitar o seed quando `CONCILIACAO_SECRET_KEY` estiver definido.

Em leigo: o "cadeado" foi checado e passou. O usuário `admin` com senha `admin123` é
só uma chave de brinquedo para testar na própria máquina — não é senha de verdade de
ninguém. Se um dia o app for para a internet de verdade, aí sim precisa trocar essa
fechadura.

---

## 8. Limitações — o que NÃO foi verificado (técnico + leigo)

1. **Sem reexecução independente de E2E/rasterização pelo segurança** — a checagem de
   segurança foi estática (leituras + `grep` + inspeção binária dos PDFs) e confiou na
   evidência do revisor rápido; reexecutar o E2E e re-rasterizar seria a verificação
   completa.
2. **Relatório legado `Completo` não foi regerado** nesta fase (escopo era só o
   Executivo; caminho coberto no E2E da fase 3b).
3. **Casos de tempo real continuam não executados** (`CT-AUTH-03` bloqueio/15 min e
   `CT-AUTH-05` expiração de sessão) — exigem confirmação humana explícita e não
   faziam parte desta fase.
4. **Sem avaliação arquitetural** — a revisão foi "rodar e conferir". A convenção de
   contagem da Rodada 3 (cada lado de um par conta como item individual, para somar 8)
   não recebeu segunda opinião de design; se o squad quiser, é escopo do arquiteto.

Em leigo: o que ficou de fora — o guarda conferiu os papéis mas não refez o teste do
navegador por conta própria; o relatório antigo ("Completo") não foi gerado de novo
porque não era o foco; dois testes que precisam de espera de verdade (bloqueio e
expiração de login) continuam sem rodar porque precisam de uma pessoa autorizando; e
ninguém opinou sobre o desenho geral da solução, só se ela funciona.
