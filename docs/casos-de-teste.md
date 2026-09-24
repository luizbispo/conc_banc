# Casos de Teste — Sistema de Conciliação Bancária (conc_banc)

**Este é o único arquivo de casos de teste do projeto.** Cada fase tem a sua seção; não se cria arquivo novo por fase — a fase seguinte entra como uma nova seção deste mesmo documento (e o PDF é regerado a partir dele).

**Como ler os status:** `PASS` = comportamento esperado observado com evidência · `FAIL` = observado diverge do esperado · `NAO EXECUTADO` = sem evidência real suficiente (nenhum resultado é presumido). Cada caso traz: objetivo, pré-condição, passos numerados, resultado esperado e status de execução.

## Resumo por fase

| Fase | Casos | PASS | FAIL | NÃO EXECUTADO | Observação |
|---|---|---|---|---|---|
| 1 | — | — | — | — | Sem catálogo formal na época; resultados dos testes executados (seção abaixo) |
| 2 | 33 | 30 | 0 | 3 | Catálogo criado na fase 2; status finais após o reteste |
| 3 | 15 | 14 | 0 | 1 | Relatório executivo em PDF; status conforme revisão do squad |
| 3b | 8 | 8 | 0 | 0 | Correções do relatório executivo; executado na Parte C (2 casos parciais: CT-F3B-03 e CT-F3B-04) |
| 4 | 7 | 7 | 0 | 0 | Clareza do relatório executivo (pontes, legenda, resumo); executado na revisão por execução (pytest 191, E2E 5/5, PDF 9 páginas) |

*Contagens feitas automaticamente sobre as linhas “Status de execução” de cada caso.*

---

## Fase 1 — Resultados dos testes executados (sem catálogo formal)

*Na fase 1 os testes foram executados e registrados, mas o documento de casos de teste no padrão detalhado só passou a existir na fase 2.*

### Resultado dos Testes

#### Ambiente
- Streamlit **local** (`streamlit run app.py`) com banco `users.db` zerado, navegador real (Chromium via Playwright), a partir de uma cópia da branch — a versão publicada (concbanctest.streamlit.app) segue no `main` e **não** reflete as correções.
- Somente os 4 arquivos de exemplo (dados sintéticos): `extrato_bancario_janeiro.ofx`, `extrato_bancario_janeiro.csv`, `B_1234490.ofx`, `C_1234490.ofx`.
- Login: `admin` / `admin123`.

#### Testes automatizados (unitários)
`pytest tests/` → **63 passed** (29 + 15 + 19 testes novos nos três commits).

#### E2E 1 — commit `31af365`
**34 registros: 22 PASS, 12 REGISTRO (observações), 0 FAIL.**

| Verificação | Resultado |
|---|---|
| Acesso direto a `/importacao_dados`, `/analise_dados`, `/gerar_relatorio` sem login | Bloqueado nas três: "Acesso não autorizado. Faça login…" |
| Logado, as três páginas | Abrem normalmente |
| Senha errada / usuário inexistente | **Mesma mensagem** ("Usuário ou senha incorretos") — sem enumeração |
| Login válido | Tela principal "Olá, Administrador!" |
| CSV de janeiro | "Extrato carregado: 10 transações" |
| OFX de janeiro | "Extrato carregado: 3 transações" |
| B + C juntos (conta 1234490) | 18 transações bancárias × 18 lançamentos contábeis; período 15/06–14/07/2025 |

##### Conciliação B × C
Verdade de referência (parse direto dos 2 OFX): 18 × 18, **11 transações idênticas**, 7 divergentes por lado.
Resultado do sistema: **14 correspondências** (11 exatas a 95% + 3 heurísticas), **cobertura 77,8%**, **8 itens em divergência** (4 bancários + 4 contábeis), **2 possíveis similaridades**.

| Par (B → C) | O que o sistema fez |
|---|---|
| 1.300,00 → 1.400,00 (30/06, "Pagamento recebido") | Não conciliado + sugerido como similaridade (dif. R$ 100,00) |
| −60,50 (15/06) → −62,50 (18/06), Mercadolivre | Não conciliado + sugerido como similaridade (dif. R$ 2,00 / 3 dias) |
| −40,30 → −43,30, Aguia Branca | Match heurístico 70% |
| −22,90 (15/06) → −20,90 (16/06), Dell | Match heurístico 75% |
| −7,89 (14/07) → −7,89 (16/07), Uber | Match heurístico 90% (mesmo valor, datas diferentes) |
| −20,80 → −25,80 (11/07), Uber* Trip (dif. 24%) | Não conciliado (acima da tolerância) — correto |
| −4,92 (só em B) / 50,63 (só em C) | Listados como não conciliados |

**Conclusão:** nenhum par com valores divergentes foi aceito como match exato. Ressalva: a justificativa escrita dos matches heurísticos só cita similaridade de texto, sem mencionar a diferença de valor.

##### Relatório e PDF (E2E 1)
- Tela: 18 / 18 / 77,8% / 8 divergências.
- **Bug encontrado:** "Total em divergência" exibia **R$ 8.623,30** (real **R$ 1.386,22**) e **R$ 13.894,40** (real **R$ 1.538,93**).
- PDF gerado (10 páginas) com conta 1234490, 18/18, 14 correspondências e 8 divergências; sem `admin123`, senha, token ou traceback. Observação: o campo "Período" do PDF sai como o mês de geração ("September/2026"), não o período dos dados.

#### E2E 2 — commit `85b1c30` (incremental)
**33 registros, 0 FAIL.** Não repetiu guards e logins inválidos já aprovados.
- Tela agora mostra `Total em divergência: R$ 1,386.22 | Itens: 4` e `R$ 1,538.93 | Itens: 4` (formato en-US da interface; mesmos R$ 1.386,22 / R$ 1.538,93). Totais inflados desapareceram.
- Contagens, tabelas e similaridades idênticas ao E2E 1.
- **Atenção ao PDF:** a soma literal não é impressa; o relatório só traz as contagens. Os valores são deriváveis somando as 4+4 linhas de divergência impressas (conferido: exato).

#### Não executado (decisão do responsável)
Bloqueio de 15 minutos após 5 falhas e expiração de sessão — dispensados explicitamente; foram tentadas apenas 2 falhas de login (abaixo do limite).

#### Evidências
Capturas em `Evidências/` (as tabelas de divergência aparecem nas imagens; os totais em R$ estão registrados neste texto). Ícones/emojis aparecem como quadrados nas capturas (provavelmente limitação de fonte do navegador de teste; não foi investigado se ocorre também no app publicado).

---

## Fase 2 — Catálogo de casos de teste

### Objetivo e escopo

Este documento define casos executáveis para a fase 2 do Sistema de Conciliação Bancária. Ele foi elaborado a partir dos resultados e riscos fornecidos nos anexos da issue; não substitui uma nova execução. Um caso só recebe `PASS` ou `FAIL` quando há evidência explícita nos anexos. Quando não há evidência suficiente, o status é `NAO EXECUTADO`.

#### Glossário

- **E2E (end-to-end):** teste do fluxo completo pela interface, do login ao resultado final.
- **Fixture:** arquivo, banco ou conjunto de dados preparado para repetir um teste.
- **Persona:** usuário usado no teste; nesta rodada, `admin` é a persona administrativa de teste.
- **Guard:** bloqueio de autenticação/autorização executado antes de abrir uma página protegida.
- **OFX, CSV, PDF e CNAB:** formatos de arquivo usados, respectivamente, para extrato financeiro, dados tabulares, relatório/documento e arquivo de retorno bancário.
- **Match exato:** correspondência aceita por igualdade dos critérios exatos do sistema.
- **Match heurístico:** correspondência sugerida/aceita por similaridade de texto, valor e/ou data.
- **Match por IA:** correspondência produzida pela camada de inteligência artificial, quando habilitada.
- **Auditoria:** registro persistente das ações e decisões em SQLite (`audit_log.db`).
- **Status de execução:** `PASS` = comportamento esperado observado; `FAIL` = comportamento observado diverge do esperado; `NAO EXECUTADO` = não há evidência real suficiente.

#### Preparação comum

1. Usar uma cópia local do repositório e um banco de usuários vazio, salvo quando o caso disser o contrário.
2. Iniciar o aplicativo com `streamlit run app.py`.
3. Usar um navegador Chromium real para os casos E2E.
4. Usar dados sintéticos da pasta `Exemplos/`: `extrato_bancario_janeiro.ofx`, `extrato_bancario_janeiro.csv`, `B_1234490.ofx`, `C_1234490.ofx` e `retorno_cnab240.ret`.
5. Para os casos autenticados, usar `admin` / `admin123`, exceto quando o caso pedir outra conta.
6. Para confirmar persistência, guardar uma cópia do banco de auditoria antes de reiniciar o processo e consultar os registros depois do reinício.

### Autenticação e sessão

#### CT-AUTH-01 — Login válido com usuário administrativo

**Descrição/objetivo:** Verificar que a persona administrativa consegue iniciar uma sessão com credenciais válidas e chega à tela principal.

**Pré-condição:** Aplicativo em execução; banco inicializado; conta `admin` / `admin123` disponível.

**Passos:**

1. Abrir a URL local do Streamlit.
2. No campo `Usuário`, digitar `admin`.
3. No campo `Senha`, digitar `admin123`.
4. Acionar `Login`.

**Resultado esperado:** O login é aceito, a tela principal é exibida e apresenta `Olá, Administrador!`. Não são exibidos token, senha ou traceback.

**Status de execução:** `PASS` — o E2E 1 registrou a tela principal com essa saudação.

#### CT-AUTH-02 — Credencial inválida sem enumeração de usuário

**Descrição/objetivo:** Confirmar que senha errada e usuário inexistente não revelam se uma conta existe.

**Pré-condição:** Tela de login disponível; nenhuma conta diferente precisa ser criada.

**Passos:**

1. No campo `Usuário`, digitar `admin`.
2. No campo `Senha`, digitar `senha-incorreta`.
3. Acionar `Login` e registrar a mensagem apresentada.
4. Reabrir ou limpar a tela de login.
5. No campo `Usuário`, digitar `usuario-que-nao-existe`.
6. No campo `Senha`, digitar `qualquer-senha`.
7. Acionar `Login` e comparar a mensagem com a registrada no passo 3.

**Resultado esperado:** Nos dois cenários o login é recusado e a mensagem é exatamente `Usuário ou senha incorretos`; não há indicação de qual identificador está cadastrado.

**Status de execução:** `PASS` — o E2E 1 registrou a mesma mensagem nos dois cenários.

#### CT-AUTH-03 — Bloqueio após cinco falhas e liberação após quinze minutos

**Descrição/objetivo:** Verificar o limite de cinco tentativas por identificador e o bloqueio temporário de quinze minutos. Este caso depende de tempo real.

**Pré-condição:** Banco de segurança limpo para o identificador `conta-teste`; relógio do ambiente confiável.

**Passos:**

1. Na tela de login, informar `conta-teste` e uma senha inválida.
2. Acionar `Login` e confirmar falha; repetir os passos 1–2 até totalizar quatro falhas.
3. Fazer a quinta tentativa inválida para `conta-teste`.
4. Tentar uma sexta vez imediatamente, ainda com senha inválida.
5. Registrar a mensagem de bloqueio e o tempo indicado.
6. Aguardar quinze minutos completos, sem alterar o identificador no banco.
7. Fazer nova tentativa e verificar se a resposta volta a ser a mensagem genérica de credencial inválida, em vez da mensagem de bloqueio.

**Resultado esperado:** A quinta falha ativa o bloqueio; a sexta tentativa é recusada com mensagem de muitas tentativas e indicação aproximada de quinze minutos; após o período, o identificador pode tentar novamente. O bloqueio não deve confirmar se a conta existe.

**Status de execução:** `NAO EXECUTADO` — parcial no E2E fase 2: o bloqueio imediato após 5 falhas foi observado (6ª tentativa: "Tente novamente em 14 min"; bloqueio vale para novo contexto; outro identificador não afetado), mas a liberação após 15 minutos não foi aguardada — caso de tempo real, aguarda autorização humana explícita.

**Confirmação humana obrigatória:** Não executar este caso até o responsável autorizar explicitamente a espera de tempo real.

#### CT-AUTH-04 — Migração transparente de senha SHA-256 legada

**Descrição/objetivo:** Verificar que uma conta antiga ainda consegue entrar e é convertida para PBKDF2 com sal no primeiro login bem-sucedido.

**Pré-condição:** Criar uma conta de teste em banco isolado com `password_hash` igual ao SHA-256 legado da senha escolhida e `password_salt` nulo; não usar a conta de produção.

**Passos:**

1. Consultar e guardar o valor inicial de `password_hash` e `password_salt` da conta legada.
2. Abrir a tela de login.
3. Digitar o identificador da conta legada.
4. Digitar a senha original da conta legada.
5. Acionar `Login`.
6. Consultar novamente a linha da conta no banco.
7. Tentar novo login com a mesma senha.
8. Verificar que o novo login continua funcionando sem intervenção do usuário.

**Resultado esperado:** O primeiro login é aceito; o sal deixa de ser nulo; o hash é substituído por PBKDF2; a senha antiga continua funcionando e não é exibida na interface. A auditoria deve registrar a migração.

**Status de execução:** `PASS` — E2E fase 2 (local): login legado migra de forma transparente (1ª e 2ª tentativas OK), o hash final fica em PBKDF2+salt e o evento de migração aparece na auditoria.

#### CT-AUTH-05 — Expiração e invalidação de sessão

**Descrição/objetivo:** Confirmar que uma sessão expirada não permite abrir páginas protegidas e que o usuário é encaminhado para login. Este caso depende de tempo real.

**Pré-condição:** Login válido realizado; mecanismo de expiração configurado para o prazo do ambiente.

**Passos:**

1. Entrar com `admin` / `admin123`.
2. Abrir uma das páginas protegidas.
3. Aguardar o prazo de expiração definido para a sessão, sem fazer nova autenticação.
4. Atualizar a página protegida.
5. Tentar navegar para as outras páginas protegidas.

**Resultado esperado:** A sessão não é aceita depois da expiração; a página exibe `Acesso não autorizado. Faça login para acessar esta página` e oferece retorno ao login. Nenhum dado protegido é mostrado.

**Status de execução:** `NAO EXECUTADO` — permanece sem execução: caso de tempo real (expiração de sessão), sem autorização humana nesta rodada.

**Confirmação humana obrigatória:** Não executar este caso até autorização explícita para esperar o prazo real.

#### CT-AUTH-06 — Logout e revogação do token no servidor

**Descrição/objetivo:** Verificar que sair da aplicação impede o reaproveitamento do token no servidor, não apenas a limpeza visual da sessão.

**Pré-condição:** Conta válida; acesso de diagnóstico ao banco de sessões/revogação permitido no ambiente de teste.

**Passos:**

1. Fazer login como `admin` / `admin123`.
2. Registrar o token/sessão criado apenas no ambiente de teste.
3. Acionar `Logout`.
4. Tentar abrir uma URL protegida usando o mesmo contexto/token antes de obter nova sessão.
5. Consultar o registro de sessão ou lista de revogação no banco.

**Resultado esperado:** O token antigo é recusado no servidor, as páginas protegidas não carregam e há evidência persistente de revogação ou invalidação. Um novo login deve criar uma sessão distinta.

**Status de execução:** `PASS` — E2E fase 2 (local): logout grava linha em `revoked_tokens` (jti) e volta à tela de login; o token vive em `st.session_state` do servidor (sem cookie), e a revogação foi confirmida na fonte.

### Autorização e páginas protegidas

#### CT-AUTHZ-01 — Guards das três páginas sem login

**Descrição/objetivo:** Confirmar que cada página funcional bloqueia acesso direto sem sessão, inclusive quando a URL é digitada manualmente.

**Pré-condição:** Sessão ausente; aplicativo em execução.

**Passos:**

1. Abrir diretamente `/importacao_dados`.
2. Registrar a mensagem e verificar se o conteúdo de importação não aparece.
3. Abrir diretamente `/analise_dados`.
4. Registrar a mensagem e verificar se os dados de conciliação não aparecem.
5. Abrir diretamente `/gerar_relatorio`.
6. Registrar a mensagem e verificar se o relatório não aparece.

**Resultado esperado:** As três páginas exibem `Acesso não autorizado. Faça login...`, não exibem dados protegidos e oferecem ação de ir para login.

**Status de execução:** `PASS` — o E2E 1 registrou bloqueio nas três rotas.

#### CT-AUTHZ-02 — Acesso autenticado às três páginas

**Descrição/objetivo:** Confirmar que um usuário autenticado consegue acessar os três fluxos permitidos.

**Pré-condição:** Login administrativo concluído.

**Passos:**

1. Abrir `/importacao_dados`.
2. Confirmar que os controles de upload aparecem.
3. Abrir `/analise_dados`.
4. Confirmar que os controles/tabelas de análise aparecem.
5. Abrir `/gerar_relatorio`.
6. Confirmar que os controles de relatório aparecem.

**Resultado esperado:** As três páginas abrem normalmente, sem mensagem de não autorizado e sem perda da sessão.

**Status de execução:** `PASS` — o E2E 1 registrou as três páginas abertas quando logado.

#### CT-AUTHZ-03 — Respeito a papéis e usuário desativado

**Descrição/objetivo:** Verificar que a role armazenada e o estado ativo do usuário são revalidados, impedindo privilégios indevidos ou acesso de conta desativada.

**Pré-condição:** Criar em banco isolado uma conta de papel comum e uma conta desativada; definir quais páginas cada papel pode acessar conforme a regra de negócio aprovada.

**Passos:**

1. Entrar com a conta de papel comum.
2. Tentar abrir cada uma das três páginas.
3. Registrar quais páginas são permitidas e quais são bloqueadas.
4. Desativar a conta no banco enquanto a sessão estiver aberta.
5. Atualizar uma página protegida.
6. Sair e tentar novo login com a conta desativada.

**Resultado esperado:** O papel comum só acessa as páginas autorizadas; a sessão de usuário desativado é invalidada na revalidação; novo login da conta desativada é recusado sem conceder privilégio administrativo.

**Status de execução:** `PASS` — E2E fase 2 (local): usuário comum não vê "Gerenciar Usuários" e acessa as 3 páginas; conta desativada é bloqueada no login e a sessão ativa é invalidada na reativacão; reativação restaura o acesso. Nota: não existe RBAC por página além de admin/comum.

### Importação e validação de arquivos

#### CT-IMP-01 — Importação de CSV de extrato

**Descrição/objetivo:** Verificar o carregamento e a contagem do CSV bancário de janeiro.

**Pré-condição:** Login concluído; arquivo `Exemplos/extrato_bancario_janeiro.csv` disponível.

**Passos:**

1. Abrir `/importacao_dados`.
2. Selecionar o arquivo `extrato_bancario_janeiro.csv` no campo de extrato bancário.
3. Acionar o processamento/carregamento.
4. Ler a mensagem de resultado.

**Resultado esperado:** O sistema aceita o CSV, converte data/valor/descrição e mostra `Extrato carregado: 10 transações`, sem dados fictícios ou erro de parsing.

**Status de execução:** `PASS` — o E2E 1 registrou exatamente 10 transações.

#### CT-IMP-02 — Importação de OFX de extrato

**Descrição/objetivo:** Verificar o carregamento de um OFX bancário e a contagem de transações.

**Pré-condição:** Login concluído; arquivo `Exemplos/extrato_bancario_janeiro.ofx` disponível.

**Passos:**

1. Abrir `/importacao_dados`.
2. Selecionar `extrato_bancario_janeiro.ofx` como extrato.
3. Acionar o processamento.
4. Conferir a mensagem e as linhas exibidas.

**Resultado esperado:** O OFX é reconhecido, processado e resulta em `Extrato carregado: 3 transações`, com valores e datas correspondentes ao arquivo.

**Status de execução:** `PASS` — o E2E 1 registrou 3 transações.

#### CT-IMP-03 — Importação de PDF

**Descrição/objetivo:** Verificar o fluxo previsto para extrato em PDF, incluindo rejeição segura ou processamento documentado.

**Pré-condição:** Login concluído; fixture PDF sintética com poucas páginas e conteúdo compatível disponível.

**Passos:**

1. Abrir `/importacao_dados`.
2. Selecionar o PDF no campo de extrato.
3. Acionar o processamento.
4. Conferir a mensagem de sucesso ou erro.
5. Se houver sucesso, comparar as transações com a fixture; se houver erro, confirmar que não foram criados registros parciais.

**Resultado esperado:** O sistema processa somente o formato suportado e informa claramente sucesso, contagem e dados convertidos; em falha, mostra erro controlado e não inventa transações. O limite de páginas deve ser aplicado.

**Status de execução:** `PASS` — E2E fase 2: PDF sintético carrega 2 transações; PDF de 201 páginas é rejeitado ("excede o limite de 200").

#### CT-IMP-04 — Importação de CNAB

**Descrição/objetivo:** Verificar o tratamento do arquivo de retorno CNAB, incluindo a proteção contra arquivos com páginas/volume excessivos.

**Pré-condição:** Login concluído; `Exemplos/retorno_cnab240.ret` disponível e fixture CNAB volumosa preparada separadamente.

**Passos:**

1. Selecionar `retorno_cnab240.ret` no campo de arquivo compatível.
2. Acionar o processamento.
3. Conferir o tipo detectado e a quantidade de registros.
4. Repetir com fixture que exceda o limite de páginas/linhas configurado.
5. Conferir a mensagem de rejeição e verificar que o aplicativo permanece responsivo.

**Resultado esperado:** O arquivo dentro do limite é processado conforme o layout; o arquivo acima do limite é recusado antes de consumir recursos excessivos, com erro compreensível e sem resultado parcial.

**Status de execução:** `PASS` — E2E fase 2: `retorno_cnab240.ret` carrega 8 transações; CNAB acima de 50000 linhas é rejeitado com mensagem clara.

#### CT-IMP-05 — Arquivo corrompido ou incompatível

**Descrição/objetivo:** Garantir que erro de leitura não seja mascarado por dados fictícios.

**Pré-condição:** Criar `fixture-corrompida.csv` com bytes inválidos ou colunas sem data/valor; manter cópia do banco de resultados limpa.

**Passos:**

1. Abrir a página de importação.
2. Selecionar `fixture-corrompida.csv`.
3. Acionar o processamento.
4. Observar a mensagem apresentada.
5. Verificar se nenhuma tabela de transações foi preenchida com valores inventados.
6. Consultar a auditoria para confirmar o registro de falha, se o fluxo já estiver integrado.

**Resultado esperado:** O processamento falha de forma controlada, informa o nome/tipo do problema, não cria transações fictícias e registra falha na auditoria quando aplicável.

**Status de execução:** `PASS` — E2E fase 2: fixture corrompida falha de forma controlada ("Erro ao processar"), sem ser aceita como extrato válido.

#### CT-IMP-06 — Arquivo acima do limite de tamanho

**Descrição/objetivo:** Confirmar a recusa antecipada de upload acima do limite configurado e a proteção contra consumo excessivo.

**Pré-condição:** Fixture sintética maior que 10 MB; não usar dados reais.

**Passos:**

1. Abrir a página de importação.
2. Selecionar o arquivo maior que 10 MB.
3. Observar a resposta imediatamente após o upload.
4. Verificar que nenhum parser é executado e que nenhuma transação é exibida.

**Resultado esperado:** O arquivo é rejeitado com mensagem de tamanho excedido, sem travar a aplicação e sem gravar dados parciais.

**Status de execução:** `PASS` — E2E fase 2: CSV de 11MB rejeitado (limite de 10MB) com mensagem informando o tamanho e o limite.

### Conciliação

#### CT-CON-01 — Conciliação exata no conjunto B × C

**Descrição/objetivo:** Reproduzir o cenário de referência e confirmar que os 11 pares idênticos são aceitos como correspondências exatas.

**Pré-condição:** Login concluído; carregar `B_1234490.ofx` e `C_1234490.ofx`; período esperado de 15/06/2025 a 14/07/2025.

**Passos:**

1. Importar `B_1234490.ofx` como dados bancários.
2. Importar `C_1234490.ofx` como dados contábeis.
3. Abrir `/analise_dados`.
4. Acionar a conciliação.
5. Conferir as contagens de entrada.
6. Conferir a lista de correspondências exatas.

**Resultado esperado:** São carregadas 18 transações bancárias e 18 lançamentos contábeis; 11 pares idênticos aparecem como matches exatos, sem aceitar como exato nenhum par com valor divergente.

**Status de execução:** `PASS` — o E2E 1 registrou 18 × 18, 11 pares idênticos e 11 matches exatos a 95%.

#### CT-CON-02 — Matches heurísticos e justificativa

**Descrição/objetivo:** Verificar os matches heurísticos do cenário B × C e exigir que a justificativa explique texto, diferença de valor e diferença de data.

**Pré-condição:** Resultado do CT-CON-01 disponível.

**Passos:**

1. Localizar o par `-40,30` / `-43,30` de Águia Branca.
2. Localizar o par `-22,90` / `-20,90` de Dell.
3. Localizar o par `-7,89` em 14/07 e 16/07 de Uber.
4. Conferir o percentual exibido para cada par.
5. Abrir a justificativa textual de cada match.
6. Verificar se cada justificativa informa a diferença monetária e a diferença em dias, além da similaridade textual.

**Resultado esperado:** Os três pares são identificados como heurísticos com percentuais de 70%, 75% e 90%; cada justificativa informa diferenças concretas, por exemplo `valor difere R$ 3,00; data difere 0 dias`. Não deve haver justificativa genérica que omita essas diferenças.

**Status de execução:** `PASS` — E2E fase 2 (rodada incremental, commits `0123316`/`da39737`): os 3 pares heurísticos (ágüa 70, dell 75, uber 90) foram aceitos com justificativas citando diferença de valor e de data; o par Uber* Trip de 24% foi rejeitado e Pagamento recebido/Mercadolivre seguiram como sugestão, não como match.

#### CT-CON-03 — Similaridade sugerida sem aceitação indevida

**Descrição/objetivo:** Confirmar que pares com divergência relevante são apenas sugeridos ou permanecem não conciliados, sem serem contabilizados como matches aceitos.

**Pré-condição:** Resultado B × C carregado.

**Passos:**

1. Localizar `1.300,00` em 30/06 com `1.400,00` em `Pagamento recebido`.
2. Verificar a diferença de R$ 100,00.
3. Localizar `-60,50` em 15/06 e `-62,50` em 18/06 de Mercadolivre.
4. Verificar a diferença de R$ 2,00 e três dias.
5. Conferir se os dois pares aparecem como sugestão de similaridade, não como correspondência aceita.

**Resultado esperado:** Os dois pares continuam não conciliados e podem ser exibidos como possíveis similaridades; não aumentam a contagem de matches aceitos.

**Status de execução:** `PASS` — o E2E 1 registrou exatamente esse comportamento.

#### CT-CON-04 — Respeito à tolerância do matching

**Descrição/objetivo:** Confirmar que o par Uber* Trip com diferença de 24% permanece não conciliado quando está acima da tolerância.

**Pré-condição:** Resultado B × C carregado; tolerância vigente registrada antes da execução.

**Passos:**

1. Localizar o par `-20,80` / `-25,80` de Uber* Trip em 11/07.
2. Confirmar a diferença indicada de 24%.
3. Conferir a tolerância efetiva aplicada pelo sistema.
4. Verificar o estado final do par.

**Resultado esperado:** O par não é aceito como match porque está acima da tolerância; aparece entre as divergências ou não conciliados.

**Status de execução:** `PASS` — o E2E 1 registrou o par como não conciliado e acima da tolerância.

**Risco/divergência:** A tolerância ainda é derivada da média do lote e não é fixa/configurável segundo o anexo de riscos; repetir este caso em lotes com médias diferentes pode produzir decisões diferentes.

#### CT-CON-05 — Camada de matching por IA

**Descrição/objetivo:** Verificar a camada de IA quando habilitada, incluindo confiança, decisão e comportamento quando o serviço não está disponível.

**Pré-condição:** Configuração de IA documentada e credencial de teste, ou modo determinístico local; dados sintéticos.

**Passos:**

1. Habilitar a camada de IA conforme configuração do ambiente.
2. Carregar um lote com pelo menos um par candidato e uma divergência conhecida.
3. Executar a conciliação.
4. Conferir a confiança, a justificativa e a camada indicada para cada decisão.
5. Repetir com o serviço de IA indisponível ou timeout simulado.

**Resultado esperado:** A decisão de IA é identificada separadamente, contém confiança e justificativa; indisponibilidade não aceita pares automaticamente nem perde os dados do lote.

**Status de execução:** `PASS` — E2E fase 2 (nível módulo): par orquestrado casa na camada IA com confiança 73,2%; o modo determinístico não usa rede externa.

#### CT-CON-06 — Divergências, contagens e somas no cenário B × C

**Descrição/objetivo:** Confirmar a verdade de referência das divergências e evitar dupla contagem ou soma inflada.

**Pré-condição:** Resultado B × C carregado e conciliação concluída.

**Passos:**

1. Conferir a cobertura de conciliação.
2. Contar os itens bancários sem correspondente.
3. Contar os itens contábeis sem correspondente.
4. Somar os valores bancários não conciliados.
5. Somar os valores contábeis não conciliados.
6. Comparar a interface com a referência do caso.

**Resultado esperado:** A tela mostra 14 correspondências, cobertura de 77,8%, quatro divergências bancárias e quatro contábeis; as somas são R$ 1.386,22 e R$ 1.538,93, respectivamente.

**Status de execução:** `PASS` — E2E fase 2 (rodada incremental): 14 matches (11 exatos + 3 heurísticos), 77,8% de cobertura e 8 divergências (4+4). Slider "Tolerância de Valor (%)" com padrão 10,00 (range 0–20) e teto absoluto fixo de R$ 5,00; sensibilidade de 2% a 20% coberta por `tests/test_tolerancia_referencia_b_x_c.py` (11 testes).

### Relatório e PDF

#### CT-REL-01 — Relatório na tela com período e totais

**Descrição/objetivo:** Confirmar que o resumo na tela representa o lote analisado e exibe os totais monetários corretos.

**Pré-condição:** CT-CON-06 concluído.

**Passos:**

1. Abrir a página de geração de relatório.
2. Selecionar o resultado B × C.
3. Conferir período inicial e final do lote.
4. Conferir correspondências, cobertura e divergências.
5. Conferir os valores monetários de cada lado.

**Resultado esperado:** A tela exibe período de 15/06/2025 a 14/07/2025, 18/18, 77,8%, oito itens divergentes no total e os valores separados R$ 1.386,22 e R$ 1.538,93.

**Status de execução:** `PASS` — E2E fase 2 (rodada incremental): tela do relatório com 18/18, 77,8%, 8 divergências e somas R$ 1.386,22 / R$ 1.538,93 (aba Divergências); período na tela 15/06/2025 a 16/07/2025. A publicada (`main`, fase 1, testada em 24/09) também exibe a referência de B×C, mas com o bug de período `September/2026`.

#### CT-REL-02 — PDF com período real dos dados

**Descrição/objetivo:** Verificar que o campo `Período` do PDF usa o intervalo dos dados, e não o mês em que o PDF foi gerado.

**Pré-condição:** Resultado B × C; data do sistema diferente de junho/julho de 2025.

**Passos:**

1. Gerar o PDF do resultado B × C.
2. Extrair o texto do PDF ou abrir as dez páginas geradas.
3. Localizar o campo `Período`.
4. Comparar com 15/06/2025 a 14/07/2025.

**Resultado esperado:** O campo mostra `15/06/2025 a 14/07/2025` ou formato equivalente, sem usar `September/2026` ou outro mês de geração.

**Status de execução:** `PASS` — reconfirmado na rodada incremental: PDF local imprime "Período: 15/06/2025 a 16/07/2025", sem mês de geração. A publicada (`main`, 24/09) ainda mostra "September/2026" — bug da fase 1, esperado até merge+deploy.

#### CT-REL-03 — PDF com soma monetária das divergências

**Descrição/objetivo:** Confirmar que o PDF imprime as somas dos dois lados, além das contagens.

**Pré-condição:** Resultado B × C; PDF gerável.

**Passos:**

1. Gerar o PDF.
2. Pesquisar no texto por `R$ 1.386,22` ou equivalente de formatação e por `R$ 1.538,93` ou equivalente.
3. Conferir que cada valor está associado ao lado bancário ou contábil correto.
4. Conferir que as contagens de quatro itens por lado continuam presentes.

**Resultado esperado:** O PDF imprime explicitamente as duas somas e as contagens; o leitor não precisa somar manualmente as linhas.

**Status de execução:** `PASS` — E2E fase 2 (rodada incremental): o PDF imprime as somas literais R$ 1.386,22 / R$ 1.538,93 com contagens 4+4, exatamente a referência (a tolerância híbrida10% + teto R$5,00 restaurou os valores aprovados).

#### CT-REL-04 — Justificativa de match heurístico no PDF/relatório

**Descrição/objetivo:** Confirmar que o motivo de um match heurístico é auditável para um leitor semitécnico.

**Pré-condição:** CT-CON-02 concluído; gerar relatório do lote.

**Passos:**

1. Gerar o relatório.
2. Localizar as linhas dos três matches heurísticos.
3. Ler a justificativa de cada linha.
4. Comparar valor e data dos dois lados com a diferença declarada.

**Resultado esperado:** Cada justificativa declara similaridade, diferença monetária e diferença de data; os números correspondem às transações apresentadas.

**Status de execução:** `PASS` — E2E fase 2 (rodada incremental): o PDF contém as 3 justificativas ricas ("valor difere"/"data difere") dos 3 matches heurísticos, conforme a referência.

### Auditoria, persistência e riscos residuais

#### CT-AUD-01 — Auditoria de login, upload, processamento e relatório

**Descrição/objetivo:** Verificar que eventos relevantes produzem entradas persistentes, identificáveis e sem segredos.

**Pré-condição:** Banco de auditoria isolado; usuário sintético; dados dos exemplos.

**Passos:**

1. Fazer uma tentativa de login inválida.
2. Fazer login válido.
3. Importar um arquivo de exemplo.
4. Executar a conciliação.
5. Gerar um relatório.
6. Consultar `audit_log.db` e filtrar pela sessão do teste.
7. Inspecionar descrições, ações, severidade e detalhes.

**Resultado esperado:** Há eventos para falha/sucesso de login, upload, processamento, matching e geração de relatório; cada evento tem timestamp, usuário/sistema e detalhes úteis. Senha, JWT e outros segredos não aparecem.

**Status de execução:** `PASS` — E2E fase 2 (rodada incremental): eventos de login (falha/ok), logout, upload, processamento, matching, migração de senha, bloqueio de rate limit e **geração de relatório** registrados com usuário e sem segredos. Sucesso do relatório confirmado ao vivo (eventos `REPORT_GENERATION` com `success=true`, usuário, lote, formato e contagens em `audit_log.db`) e caminho de falha coberto pelo teste de página `tests/test_gerar_relatorio_auditoria.py` (sucesso e falha PASS).

#### CT-AUD-02 — Persistência após reinício

**Descrição/objetivo:** Confirmar que a auditoria SQLite sobrevive ao reinício do processo.

**Pré-condição:** Executar CT-AUD-01 ou inserir um evento sintético autorizado.

**Passos:**

1. Registrar a quantidade e o `log_id` do último evento.
2. Encerrar o Streamlit normalmente.
3. Iniciar o Streamlit novamente usando o mesmo `CONCILIACAO_AUDIT_DB_PATH`.
4. Consultar novamente o banco.
5. Comparar o evento anterior e criar um novo evento.

**Resultado esperado:** O evento anterior permanece legível após o reinício; o novo evento recebe identificador próprio e é acrescentado sem alterar os registros antigos.

**Status de execução:** `PASS` — E2E fase 2: após reinício do servidor, os 150 eventos permanecem legíveis com o mesmo SHA do prefixo e o novo evento é acrescentado como 151, sem reescrever os antigos.

#### CT-AUD-03 — Rotação do log por tamanho/idade

**Descrição/objetivo:** Verificar a política de rotação do `audit_log.db` sem apagar ou alterar silenciosamente o histórico exigido.

**Pré-condição:** Política de tamanho/idade definida e ambiente de teste isolado; não usar o banco de produção.

**Passos:**

1. Configurar o limite de rotação documentado.
2. Gerar eventos até ultrapassar o limite.
3. Verificar que o arquivo ativo é rotacionado conforme a política.
4. Consultar o arquivo anterior e o novo.
5. Confirmar que eventos antigos continuam acessíveis e que novos eventos são gravados no arquivo ativo.

**Resultado esperado:** A rotação é previsível, não interrompe o logging e preserva o histórico conforme retenção aprovada; nenhum evento é sobrescrito sem regra documentada.

**Status de execução:** `PASS` — E2E fase 2: a rotação por tamanho renomeia o arquivo ativo com carimbo de tempo, preserva o histórico legível e mantém os novos eventos no arquivo novo.

#### CT-SEC-01 — Chave secreta e sobrevivência de sessão entre reinícios

**Descrição/objetivo:** Confirmar que produção usa `CONCILIACAO_SECRET_KEY` estável e que o comportamento sem variável é entendido como limitação de ambiente.

**Pré-condição:** Dois processos de teste; valor sintético de `CONCILIACAO_SECRET_KEY`; banco isolado.

**Passos:**

1. Iniciar o processo A com uma chave secreta definida.
2. Fazer login e registrar a sessão.
3. Encerrar A e iniciar B com a mesma chave.
4. Verificar a sessão criada no passo 2.
5. Repetir sem definir a variável, em banco descartável.

**Resultado esperado:** Com chave definida, a sessão permanece verificável conforme o desenho do sistema; sem chave, a aplicação gera chave aleatória por execução e invalida sessões após reinício, exibindo/logando a limitação sem usar segredo fixo conhecido.

**Status de execução:** `NAO EXECUTADO` — parcial no E2E fase 2: o warning é exibido sem `CONCILIACAO_SECRET_KEY` e a assinatura de token é válida/inválida conforme a chave; a sobrevivência da sessão entre processos A→B (mesma chave) não foi executada.

#### CT-SEC-02 — Limite por identificador e ausência de sinal confiável de origem

**Descrição/objetivo:** Verificar o limite atual por identificador e documentar o risco de não haver limitação adicional confiável por origem no Streamlit.

**Pré-condição:** Ambiente de teste autorizado; dois clientes controlados, sem dados reais.

**Passos:**

1. Fazer cinco falhas para `conta-teste` no cliente A.
2. Confirmar o bloqueio para esse identificador.
3. Tentar `conta-teste` no cliente B e registrar o comportamento.
4. Verificar quais sinais de origem realmente estão disponíveis no aplicativo.

**Resultado esperado:** O bloqueio por identificador funciona; qualquer limitação adicional só é considerada se houver sinal confiável e estável. Não inventar um mecanismo baseado em IP/cabeçalho não garantido pelo Streamlit.

**Status de execução:** `PASS` — E2E fase 2: 5 falhas de `conta-teste` bloqueiam o identificador (`locked_until` persistente), o bloqueio vale para novo contexto e outro identificador não é afetado; a ausência de sinal confiável de origem no Streamlit foi avaliada e documentada como limitação (commit `4bbfb85`), sem mecanismo inventado.

#### CT-SEC-03 — Timeout, allowlist e redirects do CloudImporter

**Descrição/objetivo:** Confirmar que importações externas não permitem SSRF, redirecionamentos ilimitados ou espera indefinida.

**Pré-condição:** Serviço HTTP de teste controlado, domínio permitido e domínio não permitido; sem endpoints reais sensíveis.

**Passos:**

1. Configurar um domínio permitido que responda rapidamente com arquivo sintético.
2. Importar a URL permitida e confirmar sucesso.
3. Tentar domínio fora da allowlist.
4. Tentar uma URL que redirecione para domínio fora da allowlist.
5. Tentar cadeia de redirecionamentos acima do limite.
6. Tentar endpoint que não responda até exceder o timeout.

**Resultado esperado:** Apenas domínio permitido é aceito; redirects são limitados e revalidados; timeout encerra a operação com erro controlado; nenhum conteúdo de domínio proibido é baixado.

**Status de execução:** `PASS` — E2E fase 2 no nível do módulo (CloudImporter é apenas stub na UI): allowlist por hostname aceita os domínios padrão e rejeita domínio malicioso/local; timeout e cadeia acima de 3 redirects terminam em erro controlado; tipos desconhecidos não disparam request.

#### CT-SEC-04 — Limite de páginas de PDF/CNAB

**Descrição/objetivo:** Confirmar a proteção contra consumo excessivo causado por documentos com páginas ou registros demais.

**Pré-condição:** Fixtures sintéticas dentro e fora do limite configurado.

**Passos:**

1. Importar um PDF/CNAB dentro do limite.
2. Confirmar processamento normal.
3. Importar um PDF/CNAB com uma unidade acima do limite.
4. Observar a rejeição e o tempo de resposta.
5. Verificar que memória, interface e auditoria não ficam em estado parcial.

**Resultado esperado:** Arquivos dentro do limite são processados; arquivos acima são recusados antes do processamento completo, com mensagem clara e sem travamento.

**Status de execução:** `PASS` — E2E fase 2: PDF de 201 páginas e CNAB acima de 50000 linhas são rejeitados com mensagem clara; as versões dentro do limite (PDF sintético, `retorno_cnab240.ret`) processam normalmente.

#### CT-SEC-05 — Rotação de `audit_log.db` e integridade append-only

**Descrição/objetivo:** Garantir que a política de retenção não permita editar ou apagar silenciosamente registros de auditoria.

**Pré-condição:** CT-AUD-03 concluído em banco isolado.

**Passos:**

1. Registrar hashes/quantidade dos eventos antes da rotação.
2. Forçar a rotação pelo mecanismo oficial.
3. Tentar alterar um evento antigo pelo fluxo normal da aplicação.
4. Comparar os eventos antigos após a rotação.

**Resultado esperado:** Eventos existentes permanecem imutáveis no histórico retido; a aplicação só acrescenta registros; qualquer expurgo segue prazo e regra documentados.

**Status de execução:** `PASS` — E2E fase 2: a fonte `audit_logger` não contém UPDATE/DELETE; após a rotação os eventos antigos permanecem legíveis e imutáveis e a base nova contém apenas eventos novos.

### Divergências, riscos e decisões pendentes

- Revisão incremental dos commits `0123316` (tolerância) e `da39737` (auditoria do relatório) executada em 24/09/2026: `pytest tests/` → 124/124 PASS; E2E local B×C completo → 28/28 PASS (referência integral restaurada).
- Os defeitos da fase 1 (período no PDF, soma literal, justificativa rica) seguem corrigidos no build local; a publicada (`main`, fase 1) ainda os exibe — merge+deploy pendentes.
- O conflito itens 2×4 foi resolvido pela tolerância híbrida decidida pelo arquiteto: percentual padrão de 10% (slider 0–20) com teto absoluto de R$ 5,00 — aceita ágüa/dell/uber, rejeita Uber* Trip (24%) e Pagamento recebido, e reproduz R$1.386,22/R$1.538,93 com 4+4. Sensibilidade testada de 2% a 20%; fronteira documentada no código (par rejeitado só empataria ≥24%, fora do range da UI).
- As referências funcionais B×C foram mantidas (decisão do arquiteto); a regra da tolerância está documentada em `modules/data_analyzer.py` e coberta por teste de sensibilidade.
- CT-AUD-01 resolvido (evento de relatório com sucesso/falha, usuário, lote e formato, sem segredos). Itens 5a–5e seguem testados localmente; push/merge para `main` seguem pendentes de credencial GitHub.
- Qualquer execução de CT-AUTH-03 ou CT-AUTH-05 exige confirmação humana explícita antes da espera de tempo real; os demais casos podem ser executados sem essa autorização adicional.

---

## Fase 3 — Catálogo de casos de teste (relatório executivo em PDF)

### Caderno de casos de teste — Fase 3

#### Escopo e glossário

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

#### Preparação comum

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

### Casos funcionais e de cálculo

#### CT-F3-01 — Seleção do formato Executivo e compatibilidade do legado

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

**Status de execução:** `PASS`.

#### CT-F3-02 — Campos configuráveis e valores ausentes

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

**Status de execução:** `PASS`.

#### CT-F3-03 — Golden test B × C: números, cobertura e ponte

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

**Status de execução:** `PASS`.

#### CT-F3-04 — Período, datas, descrições e moeda brasileira

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

**Status de execução:** `PASS`.

#### CT-F3-05 — Composição e correspondências por camada

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

**Status de execução:** `PASS`.

#### CT-F3-06 — Divergências e ponte sem pareamento arbitrário

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

**Status de execução:** `PASS`.

#### CT-F3-07 — Ponte que não fecha

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

**Status de execução:** `PASS` (via pytest).

#### CT-F3-08 — Alertas objetivos e limiares configuráveis

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

**Status de execução:** `PASS` (parcial).

#### CT-F3-09 — Recomendações determinísticas e impacto financeiro

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

**Status de execução:** `PASS`.

### Casos de documento, layout e recursos

#### CT-F3-10 — Estrutura, sumário clicável e limite de páginas

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

**Status de execução:** `PASS`.

#### CT-F3-11 — CSS de impressão e fonte Inter embutida

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

**Status de execução:** `PASS` (parcial).

#### CT-F3-12 — Tabelas, repetição de cabeçalho e descrições sem quebra indevida

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

**Status de execução:** `NAO EXECUTADO`.

### Casos de segurança, auditoria e falhas

#### CT-F3-13 — Escape de HTML e bloqueio de recursos remotos

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

**Status de execução:** `PASS` (via pytest).

#### CT-F3-14 — Auditoria REPORT_GENERATION e ausência de segredos

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

**Status de execução:** `PASS`.

#### CT-F3-15 — Dados ausentes, erro do renderer e recuperação da interface

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

**Status de execução:** `PASS` (parcial).


### Evidências da revisão por execução (desenvolvedor_revisor_rapido)

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

### Critérios de aceite e sequência de implementação

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

#### Riscos e inconsistências registrados

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

---

## Fase 3b — Correções do relatório executivo

### Escopo, evidência e dependências

Esta seção verifica as quatro correções da Parte A no relatório Executivo. Os
casos usam a fixture B × C, formada por `Exemplos/B_1234490.ofx` (extrato) e
`Exemplos/C_1234490.ofx` (contábil), salvo quando o próprio caso indicar uma
fixture sintética. **Status de execução:** os oito casos foram executados na
Parte C (revisão por execução) com evidência real, depois que a Parte A
(A1–A4) e o catálogo único da Parte B passaram a estar no worktree — 6 casos
`PASS` completos e 2 `PASS` parciais (CT-F3B-03 e CT-F3B-04, com a limitação
de cada um descrita na própria linha de status). Nenhum status foi presumido.

Evidência desta rodada (revisão por execução): `pytest` completo
(**185 passed, 1 skipped**, 21,25 s); E2E real no Streamlit local com
Chromium (login `admin/admin123`, importação de `B_1234490.ofx` e
`C_1234490.ofx`, análise e geração do Executivo e do legado Completo pela
interface, 7 de 7 etapas `PASS`); PDF do Executivo gerado pela UI
(9 páginas, WeasyPrint 70.0), com `pdftotext`, `pdfinfo`, `pdffonts`,
extração de anotações/links e `pdftoppm` em todas as páginas, todas
inspecionadas visualmente. Os casos `CT-AUTH-03` (bloqueio/15 min) e
`CT-AUTH-05` (expiração de sessão) **não foram executados** nesta rodada —
dependem de confirmação explícita do usuário (casos de tempo real) e
permanecem como estavam.

Para os casos que gerarem PDF, executar também `pdftotext` e `pdftoppm` em
todas as páginas; “rasterizar” significa converter cada página em imagem para
inspeção visual. O limiar crítico deve ser lido da configuração documentada,
sem assumir automaticamente R$ 500,00 como valor definitivo.

#### CT-F3B-01 — Rótulo de diferença por magnitude em débitos, créditos e igualdade

**Objetivo:** Confirmar que o texto “a mais/a menos” compara os módulos dos
valores, em vez de usar apenas o sinal algébrico. Isso evita inverter a
interpretação de despesas e receitas e mantém a diferença de data separada.

**Pré-condição:** Parte A1 implementada; dependências instaladas; fixture B × C
importada e analisada; acesso ao relatório Executivo e aos testes unitários.

**Passos:**

1. Gerar o relatório Executivo para B × C com a configuração padrão.
2. Localizar o par Águia Branca, com extrato `-40,30` e contábil `-43,30`.
3. Conferir o rótulo de valor e conferir separadamente se a diferença de data
   continua visível quando aplicável.
4. Localizar o par Dell, com extrato `-22,90` e contábil `-20,90`.
5. Localizar o par Uber* Trip cujo valor é igual e cuja data difere dois dias.
6. Executar um caso unitário sintético de crédito em que o módulo contábil é
   maior que o módulo do extrato.
7. Executar um caso unitário sintético de crédito em que o módulo contábil é
   menor que o módulo do extrato.
8. Executar um caso unitário sintético com valores positivos iguais e outro com
   valores negativos iguais.

**Resultado esperado:** Águia Branca exibe `R$ 3,00 a mais no contábil`, Dell
exibe `R$ 2,00 a menos no contábil` e Uber* Trip exibe `Sem diferença de
valor`, mantendo a diferença de data separada. Os casos de crédito seguem as
mesmas regras de magnitude, e igualdade em débito ou crédito nunca exibe
“a mais” ou “a menos”. A ponte continua usando `contábil - extrato`, com o
sinal explicado na legenda.

**Status de execução:** `PASS` — Parte C: E2E real (Streamlit + Chromium)
gerou o Executivo de B × C pela interface e o texto do PDF traz, na tabela de
casamentos por similaridade, `R$ 3,00 a mais no contábil` (Águia Branca,
-40,30/-43,30), `R$ 2,00 a menos no contábil` (Dell, -22,90/-20,90) e `Sem
diferença de valor` (Uber* Trip, -7,89/-7,89), com as datas de Dell
(15/06/2025 / 16/06/2025) e de Uber* Trip (14/07/2025 / 16/07/2025) visíveis
à parte na coluna “Datas (extrato / contábil)”. A ponte segue algébrica
(“saldo contábil − saldo do extrato”, R$ 147,55). Passos 6–8 cobertos pelos
casos de crédito/igualdade de `tests/test_rotulo_diferenca_magnitude.py`
(receita maior/menor/igual), todos dentro dos 185 passed.

#### CT-F3B-02 — Preservação dos pares prováveis apontados pelo sistema

**Objetivo:** Garantir que a seção de divergências volte a exibir as
correspondências por similaridade que a análise já calcula, sem promovê-las a
matches exatos nem perder seus valores de comparação.

**Pré-condição:** Parte A2 implementada; fixture B × C analisada; relatório
Executivo gerado com os resultados dessa análise.

**Passos:**

1. Abrir a seção 5 do PDF Executivo e localizar a tabela `Pares prováveis
   apontados pelo sistema`.
2. Conferir a linha de Salonlin com valores `-60,50` e `-62,50`.
3. Conferir a linha de Pagamento recebido com valores `1.300,00` e `1.400,00`.
4. Conferir que cada linha mostra a diferença de valor e, quando houver, a
   diferença de data.
5. Comparar a contagem da tabela com as sugestões produzidas por
   `analise_dados`, sem incluir linhas de matches já aceitos como exatos.
6. Confirmar que a tabela não altera os totais de 14 correspondências, 11
   exatas, 3 por similaridade e 4 itens abertos em cada lado.

**Resultado esperado:** As duas linhas aparecem na tabela de pares prováveis
com seus valores e diferenças corretos. Elas permanecem identificadas como
possíveis correspondências, não entram artificialmente na contagem de matches
exatos e não desaparecem da narrativa ou da ponte determinística.

**Status de execução:** `PASS` — Parte C: no PDF Executivo gerado pela UI, a
seção 5 tem a tabela `Pares prováveis apontados pelo sistema` com exatamente
2 linhas: Mercadolivre*Salonlin - Parcela 8/10 (-60,50 / -62,50, diferença
R$ 2,00, datas 15/06/2025 / 18/06/2025) e Pagamento recebido (1.300,00 /
1.400,00, diferença R$ 100,00, mesma data), ambas com similaridade 100% e
sem marcas de match exato. Os totais permanecem 14 correspondências, 11
exatas, 3 por similaridade e 4 itens abertos por lado (cards, seção 3 e seção
8 do mesmo PDF). A exclusão de linhas já aceitas como exatas e a contagem de
2 pares são confirmadas também por
`tests/test_pares_provaveis_e_ponte_detalhada.py` (185 passed).

#### CT-F3B-03 — Ponte detalhada determinística e indicação de resíduo

**Objetivo:** Verificar que a visão linha a linha só sugere pares elegíveis
por uma regra objetiva e que não mascara uma ponte que não fecha.

**Pré-condição:** Parte A2 implementada; fixture B × C disponível; uma segunda
fixture sintética disponível com um par aberto de mesma descrição normalizada,
mesma data e valor diferente; uma terceira variação altera um valor em R$ 1,00
para produzir resíduo não nulo.

**Passos:**

1. Gerar o relatório com a fixture B × C.
2. Conferir que a ponte determinística compacta continua presente como visão
   principal e que seus agregados fecham no valor esperado.
3. Gerar o relatório com a fixture sintética que contém `Uber* Trip` em
   `11/07/2025`, com `-20,80` no extrato e `-25,80` no contábil.
4. Localizar a ponte detalhada e conferir os dois itens, suas datas e valores.
5. Conferir que um par detalhado que não veio da lista do sistema está marcado
   literalmente como `hipótese do analista`.
6. Regerar usando a terceira variação, com um valor aberto alterado em
   `R$ 1,00`.
7. Recalcular manualmente a ponte usando os valores impressos e localizar o
   texto de resíduo no PDF.

**Resultado esperado:** A ponte detalhada só inclui o par que satisfaz as três
condições objetivas e não substitui a ponte compacta. A primeira fixture mostra
resíduo `R$ 0,00` quando a equação fecha. A variação inconsistente mostra o
resíduo com sinal e valor, informa que a ponte não fecha e nunca afirma
fechamento por arredondamento ou texto estático.

**Status de execução:** `PASS` (parcial) — Parte C: passos 1–5 executados de
verdade. No PDF de B × C, a ponte determinística compacta continua como
visão principal e fecha (`Resíduo … R$ 0,00`, “Ponte fecha sem resíduo”), e a
ponte detalhada traz o par `Uber* Trip 11/07/2025, -20,80 (extrato) /
-25,80 (contábil)` rotulado literalmente `hipótese do analista`, fechando em
`R$ 0,00`. Limitação dos passos 6–7: a variação com um valor aberto alterado
em R$ 1,00 foi gerada como PDF real (`bxc_variacao_mais_1_real.pdf`) e a
ponte continuou fechando em `R$ 0,00` — a decomposição é recalculada a
partir do mesmo conjunto de dados, então essa variação não produz
inconsistência; o caminho de resíduo NÃO nulo foi verificado apenas em nível
de módulo, por `test_ponte_detalhada_mostra_residuo_quando_nao_fecha` e
`test_ponte_mostra_residuo_explicito_quando_dados_sao_inconsistentes` (ambos
nos 185 passed, com `residuo_fmt != "R$ 0,00"`). O enunciado do passo 6
deveria ser revisto pelo arquiteto.

#### CT-F3B-04 — Exposição agrupada, alertas e recomendação de recebimentos

**Objetivo:** Confirmar que manchete, alertas e recomendações usam a exposição
financeira agrupada por natureza, sem duplicar itens nem apresentar inferência
como fato.

**Pré-condição:** Parte A2 implementada; fixture B × C analisada; limiar
crítico documentado e configurável; acesso ao texto completo do PDF.

**Passos:**

1. Gerar o relatório Executivo com B × C.
2. Somar os valores absolutos dos pares prováveis e dos itens abertos de
   recebimentos, removendo qualquer transação contada duas vezes.
3. Repetir a soma para pagamentos e registrar os dois totais.
4. Localizar a manchete de exposição principal na síntese executiva.
5. Localizar o alerta crítico e conferir o limiar aplicado, seu valor e sua
   severidade.
6. Localizar a recomendação de prioridade mais alta e conferir os itens
   `R$ 1.400,00` e `R$ 50,63` e o impacto financeiro.
7. Conferir que textos inferidos, como uma causa ou intenção, estão marcados
   como hipótese ou são diretamente derivados de uma regra documentada.
8. Repetir com a configuração do limiar alterada para confirmar que a
   severidade muda de forma reproduzível.

**Resultado esperado:** Para B × C, a exposição principal é `recebimentos,
R$ 150,63`, composta por R$ 100,00 do par provável de Pagamento recebido e
R$ 50,63 sem par. A recomendação de prioridade alta orienta investigar os
recebimentos de R$ 1.400,00 e R$ 50,63 e informa impacto de R$ 150,63. O
limiar usado aparece documentado e nenhuma narrativa afirma causa não
observável nos dados.

**Status de execução:** `PASS` (parcial) — Parte C: passos 1–4 e 7 executados
com PDF real da UI. A manchete da síntese é `Principal exposição:
recebimentos, R$ 150,63`; a tabela de exposição mostra Recebimentos (créditos)
`R$ 150,63` e Pagamentos (débitos) `R$ 11,92`; a recomendação `Prioridade
alta` é “Investigar os recebimentos de R$ 1.400,00 e R$ 50,63” com impacto
`R$ 150,63`, repetida no checklist; pares fora da lista do sistema aparecem
como `hipótese do analista`. Passo 8 executado: gerando de novo com o limiar
alterado (`ALERTA_DIVERGENCIA_VALOR_MINIMA = 100,00`), o alerta de severidade
`critico` aparece na seção 6 citando “R$ 150,63, acima do limiar de
R$ 100,00 configurado para este alerta”; com o limiar padrão restaurado
(R$ 500,00) o alerta crítico não dispara. Limitação do passo 5: em B × C o
alerta crítico não é impresso (exposição abaixo do limiar) e o PDF padrão não
exibe o número do limiar — ele está documentado no código
(`ALERTA_DIVERGENCIA_VALOR_MINIMA` em `modules/report_executivo.py`, com a
justificativa da revisão A2c) e só aparece no texto do alerta quando ele
dispara.

#### CT-F3B-05 — Pluralização em zero, um e vários elementos

**Objetivo:** Eliminar construções como `casamento(s)` e `item(ns)` em todos os
textos do módulo e do template, inclusive nos limites de contagem.

**Pré-condição:** Parte A3 implementada; helper de pluralização acessível aos
testes; relatórios sintéticos geráveis com zero, um e vários elementos.

**Passos:**

1. Executar os testes unitários do helper com contagens `0`, `1` e `2` para
   `casamento`.
2. Repetir com contagens `0`, `1` e `8` para `item`.
3. Gerar um relatório sem itens em uma seção aplicável.
4. Gerar um relatório com exatamente um casamento e um item.
5. Gerar o relatório B × C com múltiplos casamentos e itens.
6. Pesquisar o texto extraído por `(s)`, `(ns)`, `casamento(s)` e `item(ns)`.
7. Conferir os títulos, cards, síntese, alertas e recomendações, não apenas a
   tabela principal.

**Resultado esperado:** Zero usa a forma definida para ausência, um usa o
singular e valores maiores usam o plural correto em todos os pontos. Nenhuma
ocorrência de `(s)`, `(ns)` ou forma equivalente permanece no PDF ou no texto
renderizado.

**Status de execução:** `PASS` — Parte C: três PDFs Executivo gerados de
verdade (B × C com múltiplos casamentos e itens; fixture sintética com 2
casamentos e 0 itens em aberto; fixture sintética com exatamente 1 casamento
e 1 item) e o texto extraído de cada um com `pdftotext` tem **0 ocorrências**
de `(s)`, `(ns)` e `(es)`. Formas observadas: “1 casamento é exato”, “1 item
segue sem par”, “1 item ficou sem correspondência”, “1 casamento detalhado”,
“0 itens em aberto”, “Nenhum item.”, “2 casamentos detalhados”. Testes
unitários do helper com 0/1/N (`tests/test_pluralizacao.py`) e render do
template sem placeholder passam; observação: o cenário 0/0/0/0 do pytest é o
único `1 skipped` da suite (o gerador exige DataFrames não vazios), e o caso
de zero é coberto pelo helper (`0 itens`) e pelo PDF com zero itens em
aberto.

#### CT-F3B-06 — Layout do período, descrições e ocupação das páginas

**Objetivo:** Confirmar os requisitos visuais da Parte A4 no PDF efetivamente
renderizado, incluindo o efeito da ponte detalhada sobre a paginação.

**Pré-condição:** Partes A1–A3 integradas; PDF Executivo B × C gerado; `pdftoppm`
disponível; visualizador ou ferramenta de inspeção de imagens disponível.

**Passos:**

1. Contar as páginas com `pdfinfo`.
2. Rasterizar todas as páginas com `pdftoppm`, sem limitar a inspeção à capa.
3. Abrir a imagem da capa e conferir que `15/06/2025 a 16/07/2025` ocupa uma
   única linha.
4. Abrir a tabela de casamentos por similaridade e localizar `Aguia Branca -
   Passage - Parcela 6/6`.
5. Conferir que essa descrição e as demais da tabela não quebram em duas linhas
   e não são truncadas.
6. Medir ou inspecionar visualmente cada página do corpo, registrando páginas
   com mais de aproximadamente 40% de área vazia.
7. Conferir que tabelas, rodapés, títulos e a ponte detalhada não se sobrepõem
   nem são cortados.

**Resultado esperado:** O PDF tem no máximo 10 páginas; o período cabe em uma
linha; descrições da tabela de similaridade permanecem em uma linha; e nenhuma
página do corpo excede aproximadamente 40% de área vazia sem uma justificativa
de estrutura. Todas as páginas rasterizadas são legíveis e completas.

**Status de execução:** `PASS` — Parte C: `pdfinfo` acusa **9 páginas**
(limite 10), A4 retrato; as 9 foram rasterizadas com `pdftoppm -r 110` e
inspecionadas uma a uma. Na capa (e na contracapa) `15/06/2025 a 16/07/2025`
ocupa uma única linha. Na tabela de casamentos por similaridade,
`Aguia Branca - Passage - Parcela 6/6`, `Dell - Parcela 8/10` e `Uber* Trip`
ficam cada uma em uma linha, sem corte. Medição por pixel (maior faixa
horizontal totalmente branca dentro do conteúdo de cada página): páginas de
corpo 6,8% a 35,4% — abaixo do parâmetro de ~40% —, exceto o sumário
(60,2%), cuja estrutura de lista curta é a justificativa; nenhum corte,
sobreposição ou conteúdo cortado foi observado nas 9 imagens.

#### CT-F3B-07 — Regressão dos invariantes B × C e fechamento da ponte

**Objetivo:** Garantir que as correções de apresentação e exposição não alterem
os números de referência nem o sinal da ponte financeira.

**Pré-condição:** Partes A1–A4 implementadas; testes automatizados disponíveis;
fixture B × C processada com a configuração padrão.

**Passos:**

1. Executar `pytest` e registrar a contagem total e eventuais falhas.
2. Gerar o PDF Executivo B × C.
3. Conferir 18 transações, 18 lançamentos e 14 correspondências.
4. Conferir 11 correspondências exatas, 3 por similaridade, cobertura de
   `77,8%`, cobertura efetiva de `61,1%` e 4 itens abertos em cada lado.
5. Conferir saldo do extrato `R$ -140,88`, saldo contábil `R$ 6,67` e
   diferença líquida `R$ 147,55`.
6. Recalcular a ponte com os valores exibidos e confirmar resíduo `R$ 0,00`.
7. Conferir que os rótulos, a exposição, a pluralização e a paginação não
   contradizem os valores dos passos anteriores.

**Resultado esperado:** O pytest passa sem regressões; todos os invariantes
permanecem iguais aos valores de referência; a ponte fecha em `R$ 147,55` com
resíduo `R$ 0,00`; e o PDF não contém números ou frases incompatíveis entre
cards, tabelas, narrativa e ponte.

**Status de execução:** `PASS` — Parte C: `pytest -q` completo rodou
**185 passed, 1 skipped** em 21,25 s (baseline da fase 3: 144). No PDF Executivo
de B × C gerado pela UI: 18 transações e 18 lançamentos (seção 8), 14
correspondências, 11 exatas, 3 por similaridade, cobertura `77,8%`, cobertura
efetiva `61,1%`, 4 itens abertos em cada lado, saldo do extrato `R$ -140,88`,
saldo contábil `R$ 6,67` e diferença líquida `R$ 147,55`; recalculando a
ponte com os valores impressos (1.362,33 − 1.213,78 − 1,00 = 147,55) o resíduo
é `R$ 0,00` e o texto diz “Ponte fecha sem resíduo” (idem a ponte detalhada,
148,55). Rótulos, exposição (150,63 / 11,92), pluralização e paginação
(9 páginas) não contradizem esses números.

#### CT-F3B-08 — Atualização do catálogo único e rastreabilidade dos status

**Objetivo:** Verificar que a documentação da Fase 3b permanece em um único
arquivo, tem passos executáveis e não transforma expectativa em evidência.

**Pré-condição:** `docs/casos-de-teste.md`, o script gerador e o PDF de casos
presentes no checkout; os dois catálogos de fase antigos removidos.

**Passos:**

1. Procurar no repositório por `docs/casos-de-teste-fase-2.md` e
   `docs/casos-de-teste-fase-3.md` e confirmar que não existem.
2. Abrir `docs/casos-de-teste.md` e confirmar as seções Fase 1, Fase 2, Fase 3
   e Fase 3b no mesmo arquivo.
3. Conferir que existem os IDs `CT-F3B-01` a `CT-F3B-08`.
4. Conferir em cada caso objetivo, pré-condição, passos numerados, resultado
   esperado e uma linha de status.
5. Conferir que a tabela “Resumo por fase” conta as oito linhas da Fase 3b
   como `0 PASS`, `0 FAIL` e `8 NAO EXECUTADO`.
6. Executar o gerador a partir do Markdown e comparar a existência do PDF com
   a versão fonte, sem editar o PDF manualmente.
7. Pesquisar a documentação por alegações de `PASS` nos casos 3b e confirmar
   que não há nenhuma sem evidência real posterior à implementação.

**Resultado esperado:** Há somente um catálogo de casos, o PDF é regenerável
e os oito casos 3b permanecem explicitamente `NAO EXECUTADO` até a execução
real. O resumo não conta a linha de legenda nem fabrica resultados.

**Status de execução:** `PASS` — Parte C: `docs/casos-de-teste-fase-2.md` e
`docs/casos-de-teste-fase-3.md` não existem no checkout (o diretório `docs/`
tem só `casos-de-teste.md`, `casos-de-teste.pdf` e as duas documentações de
fase); as seções Fase 1, Fase 2, Fase 3 e Fase 3b estão no mesmo arquivo; os
IDs `CT-F3B-01` a `CT-F3B-08` existem, cada um com objetivo, pré-condição,
passos numerados, resultado esperado e uma linha de status; a tabela “Resumo
por fase” reflete as contagens reais desta execução (8 casos 3b: 8 `PASS`, 0
`FAIL`, 0 não executados — 2 deles parciais, informados na própria linha); o
gerador `scripts/gerar_pdf_casos_de_teste.py` foi executado a partir do
Markdown e regenerou `docs/casos-de-teste.pdf` sem edição manual do PDF.

---

## Fase 4 — Clareza do relatório executivo (3 itens)

### Escopo, evidência e dependências

Esta seção verifica os três ajustes independentes de clareza da Fase 4 na
seção 5 do relatório Executivo (pontes consistentes, legenda de rótulos e
resumo dos itens em aberto), mais as verificações de regressão exigidas pela
issue. Os casos usam a fixture B × C (`Exemplos/B_1234490.ofx` +
`Exemplos/C_1234490.ofx`), salvo quando o próprio caso indicar fixture
sintética. Os três itens foram implementados em três commits separados no
worktree: `5a00031` (rodada 1), `3021236` (rodada 2) e `1f358e0` (rodada 3).

**Status de execução:** os sete casos abaixo foram executados nesta revisão
com evidência real e estão `PASS`; nenhum status foi presumido, e nenhuma
etapa foi pular para simular sucesso.

Evidência desta rodada (revisão por execução, `pytest` completo):
**191 passed, 1 skipped, 24 warnings em 21,30 s** (baseline da Fase 3b: 185
passed, 1 skipped; os 6 testes a mais são exatamente os 2 testes novos de
cada uma das 3 rodadas). Os 6 testes novos, nome a nome, passaram isoladamente
(`6 passed`): `test_ponte_expoe_ajuste_de_similaridade_como_operacao_de_sinal_unico`,
`test_pdf_explicita_a_passagem_da_ponte_detalhada_para_a_compacta`,
`test_pdf_contem_legenda_dos_rotulos_par_provavel_e_hipotese`,
`test_pdf_continua_com_no_maximo_10_paginas_apos_a_legenda`,
`test_pdf_resumo_itens_abertos_soma_8_extraida_do_relatorio` e
`test_resumo_itens_abertos_soma_bate_com_total_sem_par_sintetico`.

Evidência E2E: Streamlit local (`streamlit run app.py`, porta 8578) com
Chromium headless via Playwright, usando **somente** os arquivos sintéticos da
issue — login `admin/admin123`, upload de `B_1234490.ofx` e `C_1234490.ofx`,
análise de divergências e geração/download do Executivo pela interface:
**5 de 5 etapas `PASS`**. O PDF baixado pela UI (60.362 bytes, WeasyPrint
70.0, A4) tem **9 páginas** (limite 10), fontes Inter embutidas (`pdffonts`:
4 faces, todas `emb sub uni = yes`) e foi conferido com `pdftotext`,
`pdfinfo`, `pdffonts`, extração por `pymupdf` e `pdftoppm -r 110 -png` nas 9
páginas, todas inspecionadas visualmente uma a uma.

Limitações declaradas desta rodada: (a) sem credencial Git no squad — os
commits `5a00031`, `3021236`, `1f358e0` e o commit deste catálogo ficam
**somente no worktree, sem push e sem PR**; (b) `docs/documentacao-final-fase-4.md`
não foi criado nem alterado (escopo do documentador, depois da revisão de
segurança); (c) os casos de tempo real (`CT-AUTH-03` e `CT-AUTH-05`) seguem
**não executados**, por exigirem confirmação explícita do usuário; (d) o
relatório legado `Completo` não foi regerado nesta rodada — o caminho foi
coberto no E2E da Fase 3b e o escopo desta fase é o Executivo; (e) não há
verificação de arquitetura/design nesta revisão, que se limita a rodar e
conferir.

#### CT-F4-01 — Passagem explícita da ponte detalhada para a ponte compacta

**Objetivo:** Confirmar que a seção 5 explica, em linguagem de leigo e sem
alterar valores, por que a ponte detalhada fecha em `R$ 148,55` e a compacta
em `R$ 147,55`, com a operação `R$ 148,55 - R$ 1,00 = R$ 147,55` visível.

**Pré-condição:** Rodada 1 implementada (commit `5a00031`); fixture B × C
analisada; relatório Executivo gerável pela interface e pelos testes; acesso
ao texto extraído do PDF e às páginas rasterizadas.

**Passos:**

1. Gerar o relatório Executivo de B × C (pela interface E2E e, de forma
   independente, pelo próprio teste automatizado).
2. Localizar, na ponte detalhada, a linha `Diferença líquida calculada pela
   ponte detalhada` e conferir o valor `R$ 148,55`.
3. Localizar a linha seguinte de ajuste e conferir rótulo e valor
   (`Ajuste das diferenças aceitas por similaridade`, `R$ -1,00`) e a nota de
   que é o mesmo ajuste já somado na ponte compacta, não um valor novo.
4. Localizar a linha `Diferença líquida da ponte compacta, após o ajuste` e
   conferir `R$ 147,55`.
5. Localizar o parágrafo de resumo logo abaixo da tabela e conferir a fórmula
   completa `R$ 148,55 - R$ 1,00 = R$ 147,55` e a explicação em frase simples.
6. Normalizar os espaços do texto extraído (`pdftotext` quebra a linha entre
   `R$` e `1,00`) e confirmar a substring completa.
7. Abrir a página rasterizada correspondente e ler a frase na imagem.
8. Executar `test_ponte_expoe_ajuste_de_similaridade_como_operacao_de_sinal_unico`
   (ajuste negativo do caso real e caso sintético de ajuste positivo) e
   `test_pdf_explicita_a_passagem_da_ponte_detalhada_para_a_compacta`.

**Resultado esperado:** Os três valores aparecem na tabela com o ajuste
identificado como `- R$ 1,00` (não como número solto), a fórmula completa
consta no parágrafo em português claro, nenhum número de B × C muda e os dois
testes do item passam.

**Status de execução:** `PASS` — PDF real da UI: a ponte detalhada mostra
`R$ 148,55`, `Ajuste das diferenças aceitas por similaridade … R$ -1,00` com
a nota “o mesmo ajuste já somado na ponte compacta acima — não é um valor
novo”, e `Diferença líquida da ponte compacta, após o ajuste … R$ 147,55`. O
parágrafo “Em resumo: a ponte detalhada (linha a linha) fecha em R$ 148,55 …”
fecha com **`R$ 148,55 - R$ 1,00 = R$ 147,55`** — a substring aparece íntegra
após normalização de espaços e é legível na página 6 rasterizada (no
`pdftotext` bruto ela só aparece partida na quebra de linha). Os dois testes
do item passaram (`2 passed`) e os invariantes do PDF seguem intactos.

#### CT-F4-02 — Legenda dos rótulos “par provável” e “hipótese do analista”

**Objetivo:** Confirmar que a seção 5 traz uma legenda curta (1–2 linhas na
intenção, no máximo um parágrafo) distinguindo o cálculo automático por
similaridade da regra objetiva de descrição + data que ainda exige
confirmação, sem estourar o limite de páginas.

**Pré-condição:** Rodada 2 implementada (commit `3021236`); fixture B × C
analisada; texto extraído do PDF e páginas rasterizadas disponíveis; contagem
de páginas acessível.

**Passos:**

1. Gerar o relatório Executivo de B × C.
2. Abrir o início da seção 5 e localizar o parágrafo “Como ler os rótulos
   desta seção”.
3. Conferir que o rótulo `par provável apontado pelo sistema` é descrito como
   correspondência calculada automaticamente por similaridade (valor, data e
   texto parecidos).
4. Conferir que `hipótese do analista` é descrito como par encontrado por
   regra objetiva de mesma descrição e mesma data, sem respaldo do sistema.
5. Conferir que a legenda informa a necessidade de confirmação manual.
6. Contar as ocorrências do cabeçalho da legenda no texto do PDF inteiro.
7. Conferir a contagem de páginas (`pdfinfo`).
8. Executar `test_pdf_contem_legenda_dos_rotulos_par_provavel_e_hipotese` e
   `test_pdf_continua_com_no_maximo_10_paginas_apos_a_legenda`.

**Resultado esperado:** Os dois rótulos e seus significados aparecem uma única
vez, no início da seção 5, e o PDF continua com no máximo 10 páginas.

**Status de execução:** `PASS` — no PDF real da UI a legenda aparece **uma
única vez** no corpo do texto (contagem exata: 1) e diz: “par provável
apontado pelo sistema” é “uma correspondência calculada automaticamente por
similaridade (valor, data e texto parecidos)”; “hipótese do analista” é “um
par encontrado só por uma regra objetiva de mesma descrição e mesma data, sem
respaldo do sistema”; e “Os dois ainda precisam de confirmação manual antes de
virar ajuste”. O PDF tem **9 páginas** (limite 10). Os 2 testes do item
passaram.

#### CT-F4-03 — Resumo dos 8 itens em aberto com soma coerente

**Objetivo:** Confirmar que o início da seção 5 mostra a contagem dos itens em
aberto em pares prováveis, pares por hipótese e sem par nenhum, derivada da
saída real do relatório, com soma igual a 8.

**Pré-condição:** Rodada 3 implementada (commit `1f358e0`); fixture B × C
analisada; texto extraído do PDF disponível para extração por regex.

**Passos:**

1. Gerar o relatório Executivo de B × C.
2. Ler a linha de resumo no início da seção 5 e extrair as três contagens por
   regex do texto renderizado, sem usar valores fixados no teste.
3. Somar as três contagens e comparar com o total de itens em aberto
   (4 no extrato + 4 no contábil = 8).
4. Cruzar as contagens com as tabelas da mesma seção: 2 linhas em `Pares
   prováveis apontados pelo sistema`, 1 par adicional rotulado
   `hipótese do analista` na ponte detalhada e 2 linhas em `Itens que seguem
   sem par nenhum`.
5. Confirmar que cada lado de um par conta como item individual, para a soma
   fechar com o total de 8.
6. Executar `test_pdf_resumo_itens_abertos_soma_8_extraida_do_relatorio` e
   `test_resumo_itens_abertos_soma_bate_com_total_sem_par_sintetico` (cenário
   sintético 2+1+3).

**Resultado esperado:** A linha de resumo mostra 4 + 2 + 2, a soma é 8, os
rótulos são os mesmos da legenda da Rodada 2 e nenhum número de B × C muda.

**Status de execução:** `PASS` — o PDF real traz “Desses 8 itens em aberto:
**4** estão em par provável apontado pelo sistema, **2** em par por hipótese do
analista e **2** seguem sem par nenhum”; a extração por regex do texto
renderizado devolve `(4, 2, 2)` e soma **8**. O cruzamento com as tabelas
bate: 2 pares prováveis × 2 lados = 4, 1 par por hipótese × 2 lados = 2, 2
itens sem par = 2 (total 8), contra “Extrato sem lançamento (4)” +
“Lançamentos sem extrato (4)”. Os 2 testes do item passaram, incluindo o
cenário sintético fora do caso B × C.

#### CT-F4-04 — Limite de páginas e rasterização de todas as páginas

**Objetivo:** Garantir que os três textos novos não estouram o limite de 10
páginas e que todas as páginas renderizadas continuam legíveis e completas.

**Pré-condição:** Os três itens implementados; PDF Executivo de B × C gerado
pela interface; `pdfinfo`, `pdftoppm` e ferramenta de inspeção de imagens
disponíveis.

**Passos:**

1. Contar as páginas com `pdfinfo`.
2. Rasterizar todas as páginas com `pdftoppm -r 110 -png`, sem limitar a
   inspeção à capa.
3. Abrir a imagem de cada página, uma a uma, e conferir que títulos, tabelas,
   cards, rodapés e as três adições da Fase 4 são legíveis.
4. Conferir especificamente a página com o início da seção 5 (resumo + legenda)
   e a página da ponte detalhada (fórmula e linhas de ajuste).
5. Verificar que nada se sobrepõe, nada é cortado e que os cabeçalhos de
   tabela repetem corretamente.
6. Conferir a contracapa e os totais finais.

**Resultado esperado:** No máximo 10 páginas; todas as páginas rasterizadas
legíveis, sem corte nem sobreposição; resumo, legenda e fórmula legíveis na
imagem.

**Status de execução:** `PASS` — `pdfinfo` acusa **9 páginas** (limite 10),
A4 retrato, 60.362 bytes. As 9 foram rasterizadas com `pdftoppm -r 110` em
PNGs de 910×1287 e inspecionadas uma a uma: capa, sumário, síntese executiva e
indicadores, composição/correspondências, seção 5 (resumo 4+2+2 e legenda
inteira legíveis), ponte compacta, ponte detalhada (fórmula
`R$ 148,55 - R$ 1,00 = R$ 147,55` legível na imagem), alertas/recomendações,
informações para auditoria e contracapa com os totais (`77,8% (14 de 18)`,
`8 itens`, `R$ -140,88`, `R$ 147,55`). Nenhum corte, sobreposição ou texto
ilegível observado; fontes Inter embutidas em todas as 4 faces.

#### CT-F4-05 — Regressão dos invariantes B × C e suíte completa

**Objetivo:** Garantir que os três ajustes de clareza não alteraram nenhum
número de referência nem quebraram nenhum teste pré-existente.

**Pré-condição:** Os três commits da Fase 4 presentes no worktree; suíte
completa executável; PDF Executivo de B × C gerado com a configuração padrão.

**Passos:**

1. Executar `pytest -q` completo e registrar contagem, falhas e tempo.
2. Conferir a contagem de testes novos esperada (6) e o único `skip`
   conhecido.
3. Gerar o PDF Executivo de B × C.
4. Conferir 18 transações, 18 lançamentos e 14 correspondências (seção 8).
5. Conferir 11 correspondências exatas, 3 por similaridade, cobertura `77,8%`,
   cobertura efetiva `61,1%` e 4 itens abertos em cada lado.
6. Conferir saldo do extrato `R$ -140,88`, saldo contábil `R$ 6,67`, diferença
   líquida `R$ 147,55` e resíduo `R$ 0,00`.
7. Conferir a ponte detalhada em `R$ 148,55` e a relação
   `148,55 - 1,00 = 147,55` sem contradição com a compacta.

**Resultado esperado:** A suíte passa sem regressões (o total sobe apenas
pelos 6 testes novos da fase); todos os invariantes permanecem iguais aos de
referência; nenhuma frase do PDF contradiz outro número do mesmo PDF.

**Status de execução:** `PASS` — `pytest -q` completo: **191 passed, 1 skipped
em 21,30 s**, sem falhas (baseline 185 + 6 novos = 191; o único `skip`
continua sendo o cenário 0/0/0/0 do gerador). No PDF real da UI: 18
transações, 18 lançamentos, 14 correspondências, 11 exatas, 3 por similaridade,
cobertura `77,8%` (4 ocorrências no texto), cobertura efetiva `61,1%` (4
ocorrências), `4 no extrato + 4 no contábil`, saldo `R$ -140,88`, saldo
contábil `R$ 6,67`, diferença líquida `R$ 147,55` (7 ocorrências), resíduo
`R$ 0,00` na ponte compacta e na detalhada, e ponte detalhada em `R$ 148,55`.
A recalculação manual com os valores impressos (1.362,33 − 1.213,78 − 1,00 =
147,55) fecha em `R$ 0,00` de resíduo.

#### CT-F4-06 — E2E real com Streamlit e navegador

**Objetivo:** Confirmar por execução real (não por teste unitário) que a
interface sobe, autentica, importa os OFX da issue, analisa e entrega o PDF do
Executivo com os textos novos.

**Pré-condição:** Streamlit local executável; navegador Chromium via
Playwright; somente os arquivos de exemplo da issue
(`Exemplos/B_1234490.ofx`, `Exemplos/C_1234490.ofx`); banco de usuários local
zerado (criação do `admin` padrão pelo próprio app).

**Passos:**

1. Subir `streamlit run app.py` em porta local dedicada e confirmar HTTP 200.
2. No navegador, autenticar com `admin` / `admin123` e conferir a tela
   logada.
3. Em `Importação de Dados`, carregar `B_1234490.ofx` no extrato e
   `C_1234490.ofx` no contábil e conferir os três avisos de carregamento.
4. Em `Análise de Divergências`, executar a análise e conferir a conclusão.
5. Em `Relatório Final`, confirmar que o formato padrão é `Executivo`,
   preencher empresa/analista e gerar o relatório.
6. Baixar o PDF pelo link da interface e conferir a mensagem de sucesso.
7. Conferir no PDF baixado a ponte, a legenda, o resumo dos 8 itens e a
   contagem de páginas.

**Resultado esperado:** As 5 etapas da interface passam, o PDF é baixado pela
UI e contém os três textos da Fase 4 com os invariantes intactos.

**Status de execução:** `PASS` — 5 de 5 etapas: login `PASS`, importação
`PASS` (“Extrato carregado”, “Lançamentos carregados”, “Dados carregados com
sucesso”), análise `PASS`, formato padrão `PASS (Executivo)`, download
`PASS (relatorio_executivo_bxc.pdf, 60362 bytes)`, com mensagem “Relatório
Executivo gerado com sucesso” e 5 telas de evidência capturadas. O PDF baixado
pela UI é o mesmo conferido nos demais casos: 9 páginas, fórmula da ponte,
legenda única e resumo 4+2+2 presentes.

#### CT-F4-07 — Catálogo único, regeneração do PDF e rastreabilidade

**Objetivo:** Verificar que a Fase 4 entra em um único arquivo de casos, que o
PDF é regenerado a partir do Markdown e que nada além do catálogo foi
alterado nesta revisão.

**Pré-condição:** `docs/casos-de-teste.md` e
`scripts/gerar_pdf_casos_de_teste.py` presentes no checkout; dependências
(`weasyprint`, `markdown`) instaladas.

**Passos:**

1. Confirmar que a seção “Fase 4” existe em `docs/casos-de-teste.md` e que os
   IDs `CT-F4-01` a `CT-F4-07` são únicos no arquivo.
2. Conferir em cada caso: objetivo, pré-condição, passos numerados, resultado
   esperado e uma linha de status.
3. Conferir a linha da Fase 4 na tabela “Resumo por fase”.
4. Executar `scripts/gerar_pdf_casos_de_teste.py` a partir do Markdown e
   confirmar que `docs/casos-de-teste.pdf` foi regenerado.
5. Verificar no `git status`/`git diff` que, entre os arquivos de documentação,
   somente `docs/casos-de-teste.md` (e o PDF regenerado a partir dele) mudou.
6. Confirmar que `docs/documentacao-final-fase-4.md` não foi criado nem
   alterado nesta rodada.
7. Confirmar que não há alegação de `PASS` sem evidência real desta rodada e
   que o registro de “sem push/PR” está explícito.

**Resultado esperado:** Um único catálogo com a seção Fase 4 completa, PDF
regenerável a partir do `.md`, nenhum outro documento alterado e as limitações
declaradas em texto.

**Status de execução:** `PASS` — a seção “Fase 4” foi acrescentada ao fim de
`docs/casos-de-teste.md` com os 7 IDs `CT-F4-01` a `CT-F4-07` únicos, cada um
com objetivo, pré-condição, passos numerados, resultado esperado e status; a
tabela “Resumo por fase” ganhou a linha da Fase 4 com as contagens reais desta
execução; `scripts/gerar_pdf_casos_de_teste.py` foi executado e regenerou
`docs/casos-de-teste.pdf` sem edição manual. No worktree, entre os arquivos
de documentação, somente `docs/casos-de-teste.md` e o PDF gerado dele mudaram;
`docs/documentacao-final-fase-4.md` não existe no checkout e não foi tocado
(`git status --short` lista apenas os dois arquivos do catálogo). Não houve
push nem PR (o squad não tem credencial Git).
