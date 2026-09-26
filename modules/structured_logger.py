# modules/structured_logger.py
"""Log estruturado JSONL (issue XCRE-49, Fase 5, item 5).

Antes deste módulo, não havia nenhum log operacional em JSON linha a
linha no projeto: o `logging.basicConfig` de cada módulo (ver
modules/audit_logger.py, modules/data_analyzer.py etc.) escreve texto
livre no stream padrão de logging, sem formato estruturado e sem
rotação. A trilha de auditoria em modules/audit_logger.py (SQLite,
append-only) é um sistema DIFERENTE e deliberadamente mais detalhado
(inclui nome de arquivo enviado, descrições de decisão) — não é o que
este item pede: aqui o objetivo é um log ENXUTO e seguro de inspecionar
(só contagens, formato, duração e categorias fixas de motivo; nunca
senha, hash, credencial, conteúdo de arquivo, descrição de transação,
valor monetário identificável, caminho local ou stack trace), para
diagnosticar operação (login, carga de arquivo, análise, geração de
relatório) sem risco de vazar dado sensível caso o arquivo seja
inspecionado ou compartilhado.

Destino e rotação: não existia nenhum destino de log estruturado
previamente. Este módulo REUTILIZA o mesmo esquema de rotação por
tamanho já usado por modules/audit_logger.py (arquivo ativo renomeado
com sufixo de timestamp ao ultrapassar o limite; nenhuma linha
existente é tocada ou apagada; só decide quando começar um arquivo
novo), para manter o projeto consistente em como arquivos de log
crescem. Caminho e limite configuráveis por variável de ambiente
(mesmo padrão de nomes já usado pelo audit_logger):
- CONCILIACAO_STRUCTURED_LOG_PATH (default: "eventos_estruturados.jsonl")
- CONCILIACAO_STRUCTURED_LOG_MAX_SIZE_MB (default: 50, igual ao audit_logger)
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Categorias de motivo fixas e curtas: nunca a mensagem crua de uma
# exceção ou validação (que pode conter nome de arquivo ou outro
# detalhe do dado processado) — só um código estável.
MOTIVOS_LOGIN = {
    'sucesso', 'usuario_nao_encontrado', 'senha_incorreta',
    'usuario_inativo', 'limite_de_tentativas',
}
MOTIVOS_CARGA_ARQUIVO = {
    'sucesso', 'arquivo_vazio', 'arquivo_binario', 'encoding_invalido',
    'colunas_obrigatorias_faltando', 'tamanho_excedido', 'extensao_invalida',
    'cabecalho_invalido', 'nenhum_dado_extraido', 'erro_parsing',
    'erro_desconhecido', 'limite_transacoes_excedido', 'limite_linhas_excedido',
    'limite_colunas_excedido', 'limite_campo_excedido',
}
MOTIVOS_GENERICO_SUCESSO_FALHA = {'sucesso', 'falha'}

# Nomes de campo que NUNCA podem aparecer em um evento, mesmo que um
# chamador passe por engano: guarda em tempo de execução, não só de
# revisão de código. Comparação por substring (case-insensitive) nas
# CHAVES dos campos extra — os campos fixos de cada log_* já são
# escolhidos para nunca colidir com esta lista.
_TERMOS_PROIBIDOS_EM_CHAVE = (
    'senha', 'password', 'hash', 'token', 'jwt', 'credencial',
    'credential', 'secret', 'conteudo', 'content', 'descricao',
    'description', 'caminho', 'path', 'stack_trace', 'traceback',
    'valor', 'amount',
)


def _validar_campos_extra(campos: Dict[str, Any]) -> None:
    """Recusa (ValueError) gravar um evento se alguma chave dos campos
    extra contiver um termo proibido — falha alto e visível em vez de
    gravar dado sensível silenciosamente."""
    for chave in campos:
        chave_lower = str(chave).lower()
        for termo in _TERMOS_PROIBIDOS_EM_CHAVE:
            if termo in chave_lower:
                raise ValueError(
                    f"Campo '{chave}' não é permitido em log estruturado "
                    f"(contém termo proibido '{termo}')"
                )


class StructuredLogger:
    """Grava eventos operacionais como JSON Lines (um objeto JSON por
    linha), com rotação por tamanho no mesmo esquema de AuditLogger."""

    def __init__(self, caminho: Optional[str] = None, max_size_mb: Optional[int] = None):
        self.caminho = caminho or os.getenv(
            "CONCILIACAO_STRUCTURED_LOG_PATH", "eventos_estruturados.jsonl"
        )
        limite_mb = (
            max_size_mb if max_size_mb is not None
            else int(os.getenv("CONCILIACAO_STRUCTURED_LOG_MAX_SIZE_MB", "50"))
        )
        self.max_size_bytes = limite_mb * 1024 * 1024

    def _rotacionar_se_necessario(self) -> None:
        """Arquiva o arquivo ativo se ele já ultrapassou o limite de
        tamanho, e deixa um arquivo novo ser criado no caminho
        original pela própria escrita seguinte (open 'a')."""
        if not os.path.exists(self.caminho):
            return
        if os.path.getsize(self.caminho) < self.max_size_bytes:
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        destino = f"{self.caminho}.{timestamp}"
        if os.path.exists(destino):
            destino = f"{destino}_{uuid.uuid4().hex[:8]}"
        os.rename(self.caminho, destino)

    def registrar(self, evento_tipo: str, **campos: Any) -> Dict[str, Any]:
        """Grava um evento com `evento_tipo` (ex.: 'login',
        'carga_arquivo', 'analise', 'geracao_relatorio') e os campos
        informados. Levanta ValueError sem gravar nada se algum campo
        tiver nome de uma chave proibida."""
        _validar_campos_extra(campos)

        registro = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'evento': evento_tipo,
            **campos,
        }

        linha = json.dumps(registro, ensure_ascii=False, default=str, sort_keys=True)

        self._rotacionar_se_necessario()
        with open(self.caminho, 'a', encoding='utf-8') as f:
            f.write(linha + "\n")

        return registro

    def log_login(self, sucesso: bool, motivo: str, duracao_segundos: float,
                  usuario: Optional[str] = None) -> Dict[str, Any]:
        """Evento de tentativa de login. `usuario` é o nome de usuário
        digitado (identificador, não segredo); nunca senha ou hash."""
        if motivo not in MOTIVOS_LOGIN:
            raise ValueError(f"motivo de login desconhecido: {motivo!r}")
        campos: Dict[str, Any] = {
            'sucesso': bool(sucesso),
            'motivo': motivo,
            'duracao_segundos': round(float(duracao_segundos), 6),
        }
        if usuario is not None:
            campos['usuario'] = str(usuario)
        return self.registrar('login', **campos)

    def log_carga_arquivo(self, formato: str, sucesso: bool, motivo: str,
                          registros: int, tamanho_bytes: int,
                          duracao_segundos: float) -> Dict[str, Any]:
        """Evento de carga de arquivo (OFX/CSV/etc.). Só formato,
        contagem de registros, tamanho em bytes, duração e uma
        categoria fixa de motivo — nunca o nome do arquivo, seu
        conteúdo ou a mensagem de erro completa exibida ao usuário."""
        if motivo not in MOTIVOS_CARGA_ARQUIVO:
            raise ValueError(f"motivo de carga de arquivo desconhecido: {motivo!r}")
        return self.registrar(
            'carga_arquivo',
            formato=str(formato),
            sucesso=bool(sucesso),
            motivo=motivo,
            registros=int(registros),
            tamanho_bytes=int(tamanho_bytes),
            duracao_segundos=round(float(duracao_segundos), 6),
        )

    def log_analise(self, total_extrato: int, total_contabil: int,
                    total_matches: int, total_divergencias: int,
                    duracao_segundos: float) -> Dict[str, Any]:
        """Evento de execução da análise (matching). Só contagens
        agregadas e duração — nunca ids, descrições ou valores das
        transações envolvidas."""
        return self.registrar(
            'analise',
            total_extrato=int(total_extrato),
            total_contabil=int(total_contabil),
            total_matches=int(total_matches),
            total_divergencias=int(total_divergencias),
            duracao_segundos=round(float(duracao_segundos), 6),
        )

    def log_geracao_relatorio(self, formato: str, sucesso: bool,
                              matches_incluidos: int, divergencias_incluidas: int,
                              duracao_segundos: float,
                              motivo: str = 'sucesso') -> Dict[str, Any]:
        """Evento de geração de relatório. Só formato, contagens
        incluídas, duração e sucesso/falha — nunca o caminho do PDF
        gerado nem a mensagem de erro completa."""
        if motivo not in MOTIVOS_GENERICO_SUCESSO_FALHA:
            raise ValueError(f"motivo de geração de relatório desconhecido: {motivo!r}")
        return self.registrar(
            'geracao_relatorio',
            formato=str(formato),
            sucesso=bool(sucesso),
            motivo=motivo,
            matches_incluidos=int(matches_incluidos),
            divergencias_incluidas=int(divergencias_incluidas),
            duracao_segundos=round(float(duracao_segundos), 6),
        )


_structured_logger: Optional[StructuredLogger] = None


def get_structured_logger() -> StructuredLogger:
    """Retorna a instância global do logger estruturado."""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger()
    return _structured_logger
