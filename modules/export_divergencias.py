# modules/export_divergencias.py
"""Exportação CSV das divergências (issue XCRE-49, Fase 5, item 2).

Antes, as páginas de resultado exportavam as tabelas de divergência com
`DataFrame.to_csv(index=False)` puro: separador ',', decimal '.'/o que
o pandas escolhesse célula a célula, sem BOM (Excel PT-BR interpreta
como um único bloco de texto ou corrompe acentos) e sem nenhuma
proteção contra formula injection — uma descrição de transação vinda de
um extrato bancário de terceiro e começando por "=", "+", "-" ou "@"
seria interpretada como fórmula ao abrir o CSV no Excel/LibreOffice.

`gerar_csv_divergencias` centraliza a serialização correta: separador
';', decimal ',', UTF-8 com BOM e proteção contra formula injection.
Não decide QUAIS linhas entram no relatório (isso continua em
pages/analise_dados.py, sem mudança de números ou matching) — só como
elas são serializadas para download.
"""
from typing import List, Optional

import pandas as pd

# Prefixos que planilhas (Excel, LibreOffice, Google Sheets) interpretam
# como início de fórmula quando abrem um CSV.
_PREFIXOS_FORMULA_PERIGOSOS = ('=', '+', '-', '@')


def _sanitizar_celula_formula(valor):
    """Prefixa com apóstrofo qualquer célula de texto que comece por um
    caractere de fórmula, forçando a planilha a tratá-la como texto
    literal. Não afeta números, datas ou células que não comecem por
    esses caracteres; a sanitização existe só na cópia exportada, nunca
    no dado exibido em tela ou usado na conciliação."""
    if isinstance(valor, str) and valor.startswith(_PREFIXOS_FORMULA_PERIGOSOS):
        return "'" + valor
    return valor


def gerar_csv_divergencias(df: pd.DataFrame, ordenar_por: Optional[List[str]] = None) -> bytes:
    """Gera os bytes do CSV de divergências pronto para download.

    Formato: separador ';', decimal ',' (colunas numéricas; colunas que
    já vêm formatadas como texto, ex. "R$ 1.234,56" ou datas
    "dd/mm/aaaa", são preservadas como estão), UTF-8 com BOM
    (utf-8-sig, para o Excel PT-BR abrir sem pedir encoding manual).

    Ordenação determinística: por padrão a ordem das linhas do `df` de
    entrada é preservada (sem embaralhar) — determinística desde que a
    origem já seja determinística, o que é o caso das tabelas de
    divergência (iteram um DataFrame filtrado, nunca um set/dict sem
    ordem). Quando `ordenar_por` é informado, ordena de forma estável
    (mergesort) por essas colunas, garantindo a mesma saída para o
    mesmo conjunto de linhas independente da ordem de chegada.

    Proteção contra formula injection é aplicada a toda célula de texto
    do resultado, depois da ordenação.
    """
    if ordenar_por:
        df = df.sort_values(by=ordenar_por, kind='mergesort', ignore_index=True)

    df_sanitizado = df.map(_sanitizar_celula_formula)

    texto_csv = df_sanitizado.to_csv(index=False, sep=';', decimal=',')
    return texto_csv.encode('utf-8-sig')
