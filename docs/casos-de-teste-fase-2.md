## Objetivo e escopo

Este documento define casos executáveis para a fase 2 do Sistema de Conciliação Bancária. Ele foi elaborado a partir dos resultados e riscos fornecidos nos anexos da issue; não substitui uma nova execução. Um caso só recebe `PASS` ou `FAIL` quando há evidência explícita nos anexos. Quando não há evidência suficiente, o status é `NAO EXECUTADO`.

### Glossário

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

### Preparação comum

1. Usar uma cópia local do repositório e um banco de usuários vazio, salvo quando o caso disser o contrário.
2. Iniciar o aplicativo com `streamlit run app.py`.
3. Usar um navegador Chromium real para os casos E2E.
4. Usar dados sintéticos da pasta `Exemplos/`: `extrato_bancario_janeiro.ofx`, `extrato_bancario_janeiro.csv`, `B_1234490.ofx`, `C_1234490.ofx` e `retorno_cnab240.ret`.
5. Para os casos autenticados, usar `admin` / `admin123`, exceto quando o caso pedir outra conta.
6. Para confirmar persistência, guardar uma cópia do banco de auditoria antes de reiniciar o processo e consultar os registros depois do reinício.

## Autenticação e sessão

### CT-AUTH-01 — Login válido com usuário administrativo

**Descrição/objetivo:** Verificar que a persona administrativa consegue iniciar uma sessão com credenciais válidas e chega à tela principal.

**Pré-condição:** Aplicativo em execução; banco inicializado; conta `admin` / `admin123` disponível.

**Passos:**

1. Abrir a URL local do Streamlit.
2. No campo `Usuário`, digitar `admin`.
3. No campo `Senha`, digitar `admin123`.
4. Acionar `Login`.

**Resultado esperado:** O login é aceito, a tela principal é exibida e apresenta `Olá, Administrador!`. Não são exibidos token, senha ou traceback.

**Status de execução:** `PASS` — o E2E 1 registrou a tela principal com essa saudação.

### CT-AUTH-02 — Credencial inválida sem enumeração de usuário

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

### CT-AUTH-03 — Bloqueio após cinco falhas e liberação após quinze minutos

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

### CT-AUTH-04 — Migração transparente de senha SHA-256 legada

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

### CT-AUTH-05 — Expiração e invalidação de sessão

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

### CT-AUTH-06 — Logout e revogação do token no servidor

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

## Autorização e páginas protegidas

### CT-AUTHZ-01 — Guards das três páginas sem login

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

### CT-AUTHZ-02 — Acesso autenticado às três páginas

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

### CT-AUTHZ-03 — Respeito a papéis e usuário desativado

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

## Importação e validação de arquivos

### CT-IMP-01 — Importação de CSV de extrato

**Descrição/objetivo:** Verificar o carregamento e a contagem do CSV bancário de janeiro.

**Pré-condição:** Login concluído; arquivo `Exemplos/extrato_bancario_janeiro.csv` disponível.

**Passos:**

1. Abrir `/importacao_dados`.
2. Selecionar o arquivo `extrato_bancario_janeiro.csv` no campo de extrato bancário.
3. Acionar o processamento/carregamento.
4. Ler a mensagem de resultado.

**Resultado esperado:** O sistema aceita o CSV, converte data/valor/descrição e mostra `Extrato carregado: 10 transações`, sem dados fictícios ou erro de parsing.

**Status de execução:** `PASS` — o E2E 1 registrou exatamente 10 transações.

### CT-IMP-02 — Importação de OFX de extrato

**Descrição/objetivo:** Verificar o carregamento de um OFX bancário e a contagem de transações.

**Pré-condição:** Login concluído; arquivo `Exemplos/extrato_bancario_janeiro.ofx` disponível.

**Passos:**

1. Abrir `/importacao_dados`.
2. Selecionar `extrato_bancario_janeiro.ofx` como extrato.
3. Acionar o processamento.
4. Conferir a mensagem e as linhas exibidas.

**Resultado esperado:** O OFX é reconhecido, processado e resulta em `Extrato carregado: 3 transações`, com valores e datas correspondentes ao arquivo.

**Status de execução:** `PASS` — o E2E 1 registrou 3 transações.

### CT-IMP-03 — Importação de PDF

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

### CT-IMP-04 — Importação de CNAB

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

### CT-IMP-05 — Arquivo corrompido ou incompatível

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

### CT-IMP-06 — Arquivo acima do limite de tamanho

**Descrição/objetivo:** Confirmar a recusa antecipada de upload acima do limite configurado e a proteção contra consumo excessivo.

**Pré-condição:** Fixture sintética maior que 10 MB; não usar dados reais.

**Passos:**

1. Abrir a página de importação.
2. Selecionar o arquivo maior que 10 MB.
3. Observar a resposta imediatamente após o upload.
4. Verificar que nenhum parser é executado e que nenhuma transação é exibida.

**Resultado esperado:** O arquivo é rejeitado com mensagem de tamanho excedido, sem travar a aplicação e sem gravar dados parciais.

**Status de execução:** `PASS` — E2E fase 2: CSV de 11MB rejeitado (limite de 10MB) com mensagem informando o tamanho e o limite.

## Conciliação

### CT-CON-01 — Conciliação exata no conjunto B × C

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

### CT-CON-02 — Matches heurísticos e justificativa

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

**Status de execução:** `FAIL` — E2E fase 2 (local): as justificativas agora citam diferença de valor e de data (Parte A), mas somente 2 de 3 pares foram aceitos (ágüa e uber; dell rejeitado pela tolerância percentual fixa de 2%); confianças 90/95.

### CT-CON-03 — Similaridade sugerida sem aceitação indevida

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

### CT-CON-04 — Respeito à tolerância do matching

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

### CT-CON-05 — Camada de matching por IA

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

### CT-CON-06 — Divergências, contagens e somas no cenário B × C

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

**Status de execução:** `FAIL` — build local (Parte A, tolerância fixa 2%): 12 matches, 66,7% de cobertura e 12 itens em divergência, divergindo da referência aprovada (14 / 77,8% / 8). Publicada (`main`, testada em 24/09): 14 / 77,8% / 8, conforme a referência.

## Relatório e PDF

### CT-REL-01 — Relatório na tela com período e totais

**Descrição/objetivo:** Confirmar que o resumo na tela representa o lote analisado e exibe os totais monetários corretos.

**Pré-condição:** CT-CON-06 concluído.

**Passos:**

1. Abrir a página de geração de relatório.
2. Selecionar o resultado B × C.
3. Conferir período inicial e final do lote.
4. Conferir correspondências, cobertura e divergências.
5. Conferir os valores monetários de cada lado.

**Resultado esperado:** A tela exibe período de 15/06/2025 a 14/07/2025, 18/18, 77,8%, oito itens divergentes no total e os valores separados R$ 1.386,22 e R$ 1.538,93.

**Status de execução:** `FAIL` — local: cobertura 66,7%, 12 divergências e somas na tela R$ 1.449,42 / R$ 1.603,13 (formato EN `1,449.42`/`1,603.13`), fora da referência; publicada (`main`, 24/09): 77,8%, 8 divergências e somas `1,386.22`/`1,538.93`, conforme a referência. Período da tela local: 15/06/2025 a 16/07/2025.

### CT-REL-02 — PDF com período real dos dados

**Descrição/objetivo:** Verificar que o campo `Período` do PDF usa o intervalo dos dados, e não o mês em que o PDF foi gerado.

**Pré-condição:** Resultado B × C; data do sistema diferente de junho/julho de 2025.

**Passos:**

1. Gerar o PDF do resultado B × C.
2. Extrair o texto do PDF ou abrir as dez páginas geradas.
3. Localizar o campo `Período`.
4. Comparar com 15/06/2025 a 14/07/2025.

**Resultado esperado:** O campo mostra `15/06/2025 a 14/07/2025` ou formato equivalente, sem usar `September/2026` ou outro mês de geração.

**Status de execução:** `PASS` — local (Parte A): o PDF imprime "Período: 15/06/2025 a 16/07/2025", sem mês de geração (o fim fica 2 dias após a referência 14/07 por incluir lançamentos contábeis). Publicada (`main`, 24/09): ainda "September/2026" — bug da fase 1 presente, esperado até merge+deploy da Parte A.

### CT-REL-03 — PDF com soma monetária das divergências

**Descrição/objetivo:** Confirmar que o PDF imprime as somas dos dois lados, além das contagens.

**Pré-condição:** Resultado B × C; PDF gerável.

**Passos:**

1. Gerar o PDF.
2. Pesquisar no texto por `R$ 1.386,22` ou equivalente de formatação e por `R$ 1.538,93` ou equivalente.
3. Conferir que cada valor está associado ao lado bancário ou contábil correto.
4. Conferir que as contagens de quatro itens por lado continuam presentes.

**Resultado esperado:** O PDF imprime explicitamente as duas somas e as contagens; o leitor não precisa somar manualmente as linhas.

**Status de execução:** `FAIL` — local: a soma literal passou a ser impressa no PDF, porém no valor R$ 1.449,42 / R$ 1.603,13 com contagens 6+6, e não na referência R$ 1.386,22 / R$ 1.538,93 com 4+4 (efeito da tolerância fixa de 2%). Publicada (`main`, 24/09): continua sem somas no PDF (bug da fase 1) com contagens 4+4.

### CT-REL-04 — Justificativa de match heurístico no PDF/relatório

**Descrição/objetivo:** Confirmar que o motivo de um match heurístico é auditável para um leitor semitécnico.

**Pré-condição:** CT-CON-02 concluído; gerar relatório do lote.

**Passos:**

1. Gerar o relatório.
2. Localizar as linhas dos três matches heurísticos.
3. Ler a justificativa de cada linha.
4. Comparar valor e data dos dois lados com a diferença declarada.

**Resultado esperado:** Cada justificativa declara similaridade, diferença monetária e diferença de data; os números correspondem às transações apresentadas.

**Status de execução:** `FAIL` — local: formato rico ("valor difere"/"data difere") presente, porém apenas 1 match heurístico impresso no PDF (< 3 esperados) pela nova tolerância; publicada (`main`, 24/09): 3 matches heurísticos apenas com similaridade textual, sem diferença de valor/data.

## Auditoria, persistência e riscos residuais

### CT-AUD-01 — Auditoria de login, upload, processamento e relatório

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

**Status de execução:** `FAIL` — E2E fase 2: eventos de login (falha/ok), logout, upload, processamento, matching, migração de senha e bloqueio de rate limit são registrados com usuário e sem segredos; falta o evento de geração de relatório (`log_report_generation` existe, mas `pages/` nunca o chama).

### CT-AUD-02 — Persistência após reinício

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

### CT-AUD-03 — Rotação do log por tamanho/idade

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

### CT-SEC-01 — Chave secreta e sobrevivência de sessão entre reinícios

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

### CT-SEC-02 — Limite por identificador e ausência de sinal confiável de origem

**Descrição/objetivo:** Verificar o limite atual por identificador e documentar o risco de não haver limitação adicional confiável por origem no Streamlit.

**Pré-condição:** Ambiente de teste autorizado; dois clientes controlados, sem dados reais.

**Passos:**

1. Fazer cinco falhas para `conta-teste` no cliente A.
2. Confirmar o bloqueio para esse identificador.
3. Tentar `conta-teste` no cliente B e registrar o comportamento.
4. Verificar quais sinais de origem realmente estão disponíveis no aplicativo.

**Resultado esperado:** O bloqueio por identificador funciona; qualquer limitação adicional só é considerada se houver sinal confiável e estável. Não inventar um mecanismo baseado em IP/cabeçalho não garantido pelo Streamlit.

**Status de execução:** `PASS` — E2E fase 2: 5 falhas de `conta-teste` bloqueiam o identificador (`locked_until` persistente), o bloqueio vale para novo contexto e outro identificador não é afetado; a ausência de sinal confiável de origem no Streamlit foi avaliada e documentada como limitação (commit `4bbfb85`), sem mecanismo inventado.

### CT-SEC-03 — Timeout, allowlist e redirects do CloudImporter

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

### CT-SEC-04 — Limite de páginas de PDF/CNAB

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

### CT-SEC-05 — Rotação de `audit_log.db` e integridade append-only

**Descrição/objetivo:** Garantir que a política de retenção não permita editar ou apagar silenciosamente registros de auditoria.

**Pré-condição:** CT-AUD-03 concluído em banco isolado.

**Passos:**

1. Registrar hashes/quantidade dos eventos antes da rotação.
2. Forçar a rotação pelo mecanismo oficial.
3. Tentar alterar um evento antigo pelo fluxo normal da aplicação.
4. Comparar os eventos antigos após a rotação.

**Resultado esperado:** Eventos existentes permanecem imutáveis no histórico retido; a aplicação só acrescenta registros; qualquer expurgo segue prazo e regra documentados.

**Status de execução:** `PASS` — E2E fase 2: a fonte `audit_logger` não contém UPDATE/DELETE; após a rotação os eventos antigos permanecem legíveis e imutáveis e a base nova contém apenas eventos novos.

## Divergências, riscos e decisões pendentes

- Execução de24/09/2026: pública (`concbanctest.streamlit.app`, `origin/main` = fase 1) e local (build `5e83698` com os8 commits da Parte A) foram testadas com o mesmo fluxo B×C; diferenças registradas nesta issue e nos artefatos `e2e_artifacts/` do revisor.
- Defeitos da fase1 confirmados NA PUBLICADA (período `September/2026` no PDF, ausência de soma literal no PDF, justificativa heurística só com similaridade) e corrigidos NO BUILD LOCAL (período real; soma literal impressa; justificativa com diferença de valor/data).
- O cenário B×C divergiu entre os dois builds: publicada14 matches / 77,8% /8 divergências (referência); local12 /66,7% /12 — a tolerância fixa de2% rejeita pares que a média do lote aceitava (dell), e as somas da tela/PDF viram R$1.449,42 / R$1.603,13. Os itens2 e4 da Parte A conflitam como executados: a soma pedida (R$1.386,22 / R$1.538,93) não é alcançável com a tolerância atual — decidir se revisa a tolerância ou se atualiza a referência.
- A tolerância agora é fixa e documentada (item4 implementado); os valores de referência do capítulo de divergências precisam ser redefinidos ou a tolerância recalibrada antes de nova aprovação de resultado.
- Itens5a–5e testados localmente (revogação no logout, limites de páginas, CloudImporter endurecido, rotação de `audit_log.db`, remoção de `modules/user_manager.py`); rate limit segue só por identificador, com a limitação documentada. Nada disso está publicado até o merge no `main`.
- Qualquer execução de CT-AUTH-03 ou CT-AUTH-05 exige confirmação humana explícita antes da espera de tempo real; os demais casos podem ser executados sem essa autorização adicional.
