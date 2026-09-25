## Escopo e método

Revisão executada em 25/09/2026 sobre `origin/main` (commit `5217573`), usando somente dados sintéticos. Foram executados os testes existentes, inspeção dirigida do código e provas de conceito em processos/diretórios temporários. Nenhum código de produção foi alterado.

**Resultado geral:** o aplicativo não está apto para uso real sem correções de alta prioridade. Há controles úteis (autorização nas páginas, revogação de JWT, PBKDF2, limite de bytes, escape Jinja e sanitização dos prefixos clássicos de CSV), mas ainda existe uma conta administrativa previsível em banco vazio, exposição local de PDFs financeiros e superfícies de consumo de recursos sem limite estrutural.

## Achados

| ID | Severidade | Área | Localização | Status e evidência executada | Recomendação |
|---|---|---|---|---|---|
| SEC-R-01 | **Alta** | F | `app.py:86-93` | **Confirmado.** `CONCILIACAO_DB_PATH=$(mktemp) ... python3 -c 'import app; app.init_db(); ...'` retornou `BOOTSTRAP [('admin', 'admin')]`; a senha é definida no código como `admin123`. | Remover a senha conhecida. Em primeiro boot, exigir configuração/rotação interativa de uma credencial forte ou um segredo de provisionamento fora do código; não criar admin utilizável por senha pública. |
| SEC-R-02 | **Alta** | B/H | `modules/report_executivo.py:928-932` | **Confirmado.** PoC gerou `/tmp/.../relatorio_executivo_....pdf` com modo `0o644`, tamanho 50227 bytes. O arquivo é nomeado em `tempfile.gettempdir()` e não é apagado pelo gerador; o fluxo leitor também não remove-o (`pages/gerar_relatorio.py:592-594`). | Criar arquivo temporário com permissão privada (`0600`) em diretório privado por execução, usar nome realmente imprevisível e apagar em `finally` após carregar os bytes. Considerar retenção/limpeza de artefatos já abandonados. |
| SEC-R-03 | **Média** | A | `pages/importacao_dados.py:96-116, 421-442` | **Confirmado.** O limite de 10 MB é apenas de bytes (`:31-42`); CSV é lido inteiro sem limite de linhas/colunas e OFX percorre todas as transações. Benchmark executado: CSV de 5.600.193 bytes, 50.000 x 50, consumiu 75,6 MB de memória Python e 0,139 s; CSV de 4.120.891 bytes, 10.000 x 200, consumiu 61,0 MB. O benchmark OFX sintético de 50.000 transações permaneceu em CPU por mais de 75 s sem concluir e foi interrompido. | Impor limites de linhas, colunas, tamanho de campo, profundidade/quantidade de nós OFX e tempo/custo por etapa antes e durante o parsing; rejeitar com mensagem fixa e testar limites sob carga. |
| SEC-R-04 | **Média** | D | `modules/export_divergencias.py:71-79, 113-116` | **Parcialmente confirmado.** A PoC mostrou que `=`, `+`, `-`, `@`, DDE e `HYPERLINK` recebem apóstrofo. Porém `\t=1+1`, `\r=1+1` e `\n=1+1` saem sem apóstrofo; portanto o primeiro caractere perigoso pode ser ocultado após controle de espaço. O valor numérico `-12.5` permaneceu numérico; `R$ -60.50` virou `R$ -60,50` sem ser tratado como fórmula. | Normalizar/remover ou neutralizar TAB, CR, LF e espaços de controle à esquerda antes da checagem, e aplicar uma política de exportação segura para todos os valores textuais. Manter testes com os payloads completos e com negativos legítimos. |
| SEC-R-05 | **Média** | E | `modules/audit_logger.py:120-168, 174-190, 241-262, 264-302`; `app.py:143-180, 213-220` | **Confirmado.** O logger de auditoria persiste `file_name`, descrições, `details`, IDs e motivos sem uma lista de campos proibidos. PoC gravou `('alice\\nINJECT', 'Upload descricao=R$999 token=synthetic', '{"senha": "synthetic"}')` em SQLite e também emitiu a descrição no logger padrão. O JSONL estruturado escapou a quebra de linha, mas isso não protege o SQLite/logger de auditoria. | Reduzir auditoria a campos permitidos e categorias; nunca persistir senha, hash, token, conteúdo, descrição financeira ou caminho. Sanitizar/estruturar valores controlados pelo usuário e evitar interpolação em mensagens de log. Rever permissões e acesso ao banco de auditoria. |
| SEC-R-06 | **Média** | F | `modules/auth_middleware.py:31-49, 194-229` | **Confirmado como risco operacional de produção.** Sem `CONCILIACAO_SECRET_KEY`, dois processos produziram chaves diferentes (`b981...cea2b` e `dae5...e953`), invalidando sessões entre reinícios/processos. O código apenas registra warning e continua. O rate limit também é somente por identificador (`:197-218`), sem camada de origem confiável. | Em produção, falhar ao iniciar se a chave não estiver definida, com segredo forte em gerenciamento externo. Adicionar limitação no proxy/WAF confiável e monitoramento, sem confiar em `X-Forwarded-For` controlado pelo cliente. |
| SEC-R-07 | **Média** | G | `requirements.txt:1-15` | **Confirmado** que a maioria das dependências não tem versão fixada (`streamlit`, `pandas`, `numpy`, `plotly`, `ofxparse`, `PyJWT`, `requests`, etc.). **Não verificado** o inventário de vulnerabilidades: `pip-audit` não está instalado e não foi instalado durante a revisão. | Fixar versões e hashes em arquivo de lock/constraints, atualizar sob processo controlado e executar `pip-audit`/scanner equivalente em CI e antes de release. Fixar também dependências transitivas relevantes. |

## Controles verificados e sem achado confirmado

- `pytest -q`: **292 passed, 1 skipped, 48 warnings em 35,43 s**.
- O cache de parsing usa somente bytes e encoding para a chave (`pages/importacao_dados.py:96-116, 421-442`), e os testes existentes confirmam cópia por chamada e ausência de credenciais/sessão no núcleo. Não foi demonstrado vazamento de dados distintos entre usuários; permanece o risco residual de retenção de conteúdo sensível no cache global do processo.
- A PoC renderizou `<script>alert(1)</script>` como `&lt;script&gt;...` no ambiente Jinja (`select_autoescape` em `modules/report_executivo.py:59-62`).
- `_url_fetcher_seguro = URLFetcher(allowed_protocols=["data"])` (`modules/report_executivo.py:53-56`) bloqueia HTTP/HTTPS/arquivo local no PDF. As fontes são embutidas como `data:`; não foi observado SSRF ou leitura local via campos testados.
- O processamento de uploads não grava o nome do upload como caminho local; o principal risco confirmado de temporários é o PDF do relatório (SEC-R-02). Não foi demonstrado path traversal executável no fluxo de upload.
- JWT expira em 24 horas, tem `jti` e revogação no logout; páginas relevantes chamam `enforce_auth`/`require_auth`. Isso não elimina SEC-R-01 e SEC-R-06.

## Itens não verificados

- `pip-audit` e vulnerabilidades transitivas: ferramenta ausente no ambiente; não houve instalação/download adicional.
- Teste end-to-end no Streamlit publicado: não executado nesta revisão local; não foram usadas credenciais externas.
- Limites de memória/CPU sob concorrência real e comportamento do proxy/reverse proxy: o benchmark foi de processo único local. O benchmark OFX foi interrompido após mais de 75 s para não manter carga desnecessária.
- Cenários com symlink/race contra diretório temporário compartilhado: não executados; SEC-R-02 já é confirmado pelo modo `0644` e retenção observados.

## Comandos e provas principais

```text
pytest -q
292 passed, 1 skipped, 48 warnings in 35.43s

python3 PoC de exportação/log/PDF
CSV: prefixos = + - @, DDE e HYPERLINK receberam apóstrofo;
TAB/CR/LF seguidos de fórmula permaneceram sem apóstrofo.
PDF_PATH /tmp/.../relatorio_executivo_....pdf MODE 0o644 SIZE 50227

python3 PoC de bootstrap/rate limit
BOOTSTRAP [('admin', 'admin')]
após 5 falhas: login bloqueado por limite de tentativas

python3 pip-audit -r requirements.txt
/bin/bash: pip-audit: command not found
```

Os dados usados nas provas foram sintéticos; nenhum segredo real foi incluído neste relatório.
