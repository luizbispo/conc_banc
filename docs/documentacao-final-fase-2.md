# conc_banc — Fase 2: documentação final

Fase 2 da revisão do app de conciliação bancária (Streamlit): correções pendentes (Parte A),
documento de casos de teste (Parte B) e execução + revisões (Parte C).
Base: `main` 7aaa6bf (fase 1 mesclada no PR #1) + 10 commits da Parte A na branch
`agent/assistente-claude-pago/14085821e089`. Login de teste: `admin` / `admin123`
(credencial padrão de ambiente de teste, dados sintéticos em `Exemplos/`).

Cada seção traz a versão **técnica** (termo correto) e a versão **leiga** (analogia do dia a dia).

---

## 1. O que mudou — os 10 commits (técnico)

| # | Commit | O que faz |
|---|--------|-----------|
| 1 | `a3396bf` | PDF do relatório: período real dos dados + soma em R$ das divergências de cada lado |
| 2 | `b65df36` | Justificativa do match heurístico cita diferença de valor (R$) e de data (dias) |
| 3 | `c3a321e` | Tolerância de matching explícita/configurável + auditoria de cada decisão (par, confiança, camada) |
| 4 | `8c65ec2` | Logout revoga o JWT no servidor (lista de revogação por `jti`) |
| 5 | `ec0ec23` | Limite de páginas PDF (200) e linhas CNAB (50.000); CloudImporter com timeout (15 s), allowlist por hostname e máx. 5 redirects |
| 6 | `fb27a51` | Rotação de `audit_log.db` por tamanho (50 MB), preservando append-only |
| 7 | `4bbfb85` | Documenta que o rate limit é só por identificador (sem IP confiável no Streamlit) |
| 8 | `824ac27` | Remove `modules/user_manager.py` (código morto/divergente, confirmado sem importadores via grep) |
| 9 | `0123316` | Ajuste final da tolerância: percentual padrão 10% (slider 0–20%) + teto absoluto fixo de R$ 5,00 (menor dos dois vale); teste de sensibilidade |
| 10 | `da39737` | `log_report_generation` ganha `success`/`error_message`/`lote` e passa a ser chamado por `pages/gerar_relatorio.py` nos 4 pontos de saída (resolve CT-AUD-01) |

## 1. O que mudou — versão leiga

Pense no app como um escritório que confere extratos do banco contra a contabilidade.
Esta fase fez 10 consertos: o relatório em PDF passou a mostrar o período certo e o
valor total das diferenças (antes mostrava o mês em que foi gerado e só a quantidade);
cada conciliação "por aproximação" agora explica o porquê (diferença de valor e de data);
sair do sistema agora realmente cancela sua credencial; arquivos gigantes ou sites
desconhecidos são barrados na porta; e o livro de registros (auditoria) ganhou controle
de tamanho e passou a anotar também cada relatório gerado.

---

## 2. Decisões de tolerância (técnico)

- Requisito original (Parte A, item 4): tolerância derivada da média do lote era instável;
  torná-la explícita e configurável.
- Primeira tentativa (`c3a321e`): percentual fixo de 2%. Efeito medido no cenário de
  referência B×C (`Exemplos/B_1234490.ofx` × `C_1234490.ofx`): caiu de 14 para 12 matches
  (66,7% de cobertura, 6+6 divergências, somas R$ 1.449,42 / R$ 1.603,13) — conflito com
  as referências exigidas (14 / 77,8% / 4+4 / R$ 1.386,22 / R$ 1.538,93).
- Decisão do arquiteto: manter as referências funcionais; ajustar a tolerância, não as
  referências. Só atualizar referências com decisão explícita de produto.
- Solução final (`0123316`): tolerância efetiva = **menor entre percentual (padrão 10%,
  slider 0–20% na UI) e teto absoluto de R$ 5,00** (constante fixa, fora da UI).
  Motivo: um percentual puro não separa "Dell" (aceitar, 8,73%) de "Pagamento recebido"
  (rejeitar, 7,69% mas R$ 100,00) — o teto absoluto resolve. Resultado validado nos
  arquivos reais: 11 exatos + 3 heurísticos = 14, 77,8%, 4+4, R$ 1.386,22 / R$ 1.538,93;
  Uber* Trip 24% e Pagamento/MercadoLivre ficam como sugestão. Fronteira documentada no
  código: empate exato em R$ 5,00 só aceitaria a partir de ~24% (fora do range da UI),
  sem efeito no comportamento padrão.

## 2. Decisões de tolerância — versão leiga

Conciliar "por aproximação" exige dizer o quanto de diferença ainda vale como empate.
A primeira régua (2%) era rígida demais e deixou de fora empates corretos. A régua final
é dupla: vale a menor entre "10% do valor" e "no máximo R$ 5,00 de diferença". Assim,
uma diferença pequena em valor alto passa, mas R$ 100,00 de diferença nunca passa —
e o caso de teste padrão volta a bater exatamente com o esperado.

---

## 3. Auditoria REPORT_GENERATION / CT-AUD-01 (técnico)

- Achado: `log_report_generation` existia em `modules/audit_logger.py`, mas
  `pages/gerar_relatorio.py` nunca o chamava — evento ausente (CT-AUD-01 FAIL na
  primeira revisão, evidência `phaseD_d1.json`).
- Correção (`da39737`): método ganha `success`/`error_message`/`lote`
  (conta + período, sem segredos); a página chama nos 4 pontos de saída
  (caminho nulo, arquivo inexistente, arquivo vazio, exceção, sucesso) com usuário,
  lote, formato e contagens. Testes `tests/test_gerar_relatorio_auditoria.py` (2/2)
  executam a página real com clique simulado (sucesso e falha).
- Evidência E2E: 4 eventos `REPORT_GENERATION success=true, user=admin,
  lote="1234490 | 15/06/2025 a 16/07/2025", formato=completo` gravados em
  `audit_log.db`; varredura sem vazamento de credenciais. CT-AUD-01: FAIL → **PASS**.

## 3. Auditoria do relatório — versão leiga

O "livro de registros" anotava quase tudo, menos a emissão de relatórios — como uma
portaria que registra entradas mas esquecia de anotar quando alguém retirava um documento.
Agora cada relatório gerado (ou cada falha ao gerar) é anotado com quem pediu, qual
lote e qual formato, sem anotar senhas.

---

## 4. Resultados reais dos testes (técnico)

- `pytest tests/`: **124/124 passando** (108 herdados + 16 novos da rodada final).
- E2E local (navegador headless, fixtures reais B×C): **28/28 PASS** — 14 matches
  (11 exatos + 3 heurísticos), 77,8%, 8 divergências (4+4), somas na tela e no PDF
  R$ 1.386,22 / R$ 1.538,93, período real 15/06/2025 a 16/07/2025 na tela e no PDF,
  justificativas ricas, PDF sem credenciais.
- Documento `docs/casos-de-teste-fase-2.md`: **31 PASS / 0 FAIL / 3 NÃO EXECUTADO**
  (evolução: rodada anterior 25 PASS / 6 FAIL — CON-02, CON-06, REL-01, REL-03, REL-04,
  AUD-01 — todos resolvidos pelos commits `0123316` + `da39737`).
- App publicada `https://concbanctest.streamlit.app/` (ainda no `main` 7aaa6bf, fase 1):
  fluxo principal executado (17/18 PASS; único FAIL = bug de período já corrigido no
  branch local). Publicada reflete a Parte A só após merge + reimplantação no
  Streamlit Cloud.

## 4. Resultados — versão leiga

Todos os 124 testes automáticos passam. O teste completo de ponta a ponta (abrir o app
de verdade, entrar, importar os dois extratos, analisar e gerar o PDF) passou nas 28
etapas, com os números exatamente iguais aos esperados. Dos 34 casos do catálogo, 31
passam e 3 ficaram para depois de propósito (explicados abaixo) — nenhum falhando.

---

## 5. Revisão de segurança — veredito APROVADO, sem bloqueadores (técnico)

Escopo: os 10 commits + evidências E2E. Conferido: PBKDF2-HMAC-SHA256 (260k iterações,
salt por usuário, migração de legado SHA-256, `hmac.compare_digest`, mensagem de login
genérica + hash dummy anti-enumeração); `SECRET_KEY` via `CONCILIACAO_SECRET_KEY` ou
gerada por execução; guards revalidam usuário/`jti` no banco; revogação de JWT no logout
com limpeza de expirados; rate limit 5 falhas/15 min por identificador (limitação por IP
documentada como inviável no Streamlit — `X-Forwarded-For` forjável); limites de upload
(10 MB), PDF (200 págs) e CNAB (50.000 linhas) via env; CloudImporter com timeout,
allowlist por hostname (`host == dominio ou subdomínio`, sem bypass por substring) e
5 redirects; rotação de auditoria por tamanho preservando append-only (único `DELETE`
legítimo: tokens expirados, fora da trilha); remoção de `user_manager.py`; grep sem
segredos hardcoded; logs/relatórios/screenshots sem credenciais; dados de teste
sintéticos.

## 5. Segurança — versão leiga

Um revisor de segurança examinou tudo e **aprovou**: senhas guardadas com técnica forte,
mensagens de erro que não entregam quem existe, saída que realmente cancela o acesso,
limites contra arquivos maliciosos e contra sites falsos, livro de registros à prova de
adulteração e nenhum vazamento de senha nos relatórios ou registros.

---

## 6. Não executados — sem resultado inventado (técnico e leigo)

- **CT-AUTH-03** (bloqueio de 15 min após 5 falhas): bloqueio observado, mas a liberação
  após 15 min reais **NÃO EXECUTADA** — exige espera de tempo real com autorização
  humana explícita (regra da issue; dispensa da fase 1 não se estende).
- **CT-AUTH-05** (expiração de sessão): **NÃO EXECUTADO** pelo mesmo motivo.
- **SEC-01 parcial**: **NÃO EXECUTADO** na parte que depende de tempo real.
- Em leigo: três testes exigem "esperar o relógio de verdade" (15 minutos, sessão
  expirar). A regra do projeto proíbe executá-los sem um "sim" explícito do dono,
  então ficaram pendentes — nenhum resultado foi presumido.

---

## 7. Recomendações não bloqueadoras (técnico + leigo)

1. **Senha padrão `admin/admin123`** (baixa): exigir troca no primeiro acesso ou seed
   via env `CONCILIACAO_ADMIN_PASSWORD`. Leigo: a chave reserva vem de fábrica igual
   para todos — trocar na estreia ou configurar por ambiente.
2. **JWT de 24h** (baixa): considerar 2–8h ou refresh token. Leigo: o crachá de acesso
   vale 24h; se for perdido sem logout, vale até expirar — encurtar reduz a janela.
3. **Rotação por idade da auditoria** (info): acrescentar `CONCILIACAO_AUDIT_MAX_AGE_DIAS`
   se compliance exigir (hoje só por tamanho). Leigo: o livro troca de volume quando
   enche; falta trocar também por prazo, se a regra da empresa pedir.

---

## 8. Como aplicar / estado de entrega

- Commits na branch `agent/assistente-claude-pago/14085821e089` (+ revisões na branch
  do revisor); **push para o GitHub bloqueado neste ambiente por falta de credencial** —
  cabe ao usuário revisar e publicar (merge + push a partir de um contexto com acesso).
- A versão publicada só reflete a Parte A após merge no `main` e reimplantação automática.
- Este arquivo: `docs/documentacao-final-fase-2.md`, commitado na branch de documentação.
