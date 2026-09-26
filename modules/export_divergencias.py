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

Achado da Fase 5 (CT-F5-05): as tabelas reais de divergência chegam ao
exportador com o valor monetário já formatado como TEXTO em pt-BR só
na aparência (`f"R$ {valor:,.2f}"`, que na verdade é en-US: milhar
',', decimal '.'), então `to_csv(decimal=',')` — que só reformata
colunas numéricas — não tinha efeito nessas células. A normalização
de moeda textual abaixo corrige isso sem depender de mudar o formato
produzido em pages/analise_dados.py.
"""
import re
from typing import List, Optional

import pandas as pd

# Prefixos que planilhas (Excel, LibreOffice, Google Sheets) interpretam
# como início de fórmula quando abrem um CSV.
_PREFIXOS_FORMULA_PERIGOSOS = ('=', '+', '-', '@')

# Caracteres que o Excel/LibreOffice ignoram à esquerda de uma célula ao
# decidir se ela começa com um prefixo de fórmula (revisão de segurança
# dedicada, SEC-R-04, XCRE-52): um valor como "\t=cmd|'/C calc'!A0"
# (TAB antes do "=") ainda é interpretado como fórmula ao abrir o CSV,
# mesmo não começando LITERALMENTE por nenhum dos _PREFIXOS_FORMULA_PERIGOSOS.
# Espaço, TAB, CR, LF e NBSP (non-breaking space, comum em texto colado
# de fontes externas) — só usados para a DECISÃO, nunca para reescrever
# o valor (a sanitização prefixa o texto ORIGINAL, sem remover nada dele).
_CARACTERES_IGNORAVEIS_NA_DETECCAO_DE_FORMULA = ' \t\r\n\xa0'

# As tabelas de divergência (pages/analise_dados.py) formatam valores
# monetários com `f"R$ {valor:,.2f}"` — Python usa o padrão en-US
# (milhar ',', decimal '.'), ex. "R$ 1,300.00" ou "R$ -60.50". Nesse
# ponto o valor já chegou ao exportador como TEXTO, então `decimal=','`
# do to_csv (que só atua em colunas numéricas) não tem efeito. Este
# padrão reconhece essa célula textual para poder reescrevê-la em
# pt-BR sem confundir milhar com decimal.
#
# O grupo de milhar exige exatamente 3 dígitos por grupo (`\d{3}` após
# cada vírgula) de propósito: é o único jeito de diferenciar com
# segurança "R$ 1,300.00" (milhar en-US: vírgula + 3 dígitos, decimal
# '.') de uma célula que já chegasse em pt-BR tipo "R$ 250,00" (aqui a
# vírgula é decimal, só 2 dígitos depois dela — não bate com o grupo de
# milhar e por isso não casa com este padrão, ficando intocada).
_PADRAO_MOEDA_TEXTO_EN_US = re.compile(r'^(R\$\s*)(-?)(\d{1,3}(?:,\d{3})*)(\.\d+)?$')


def _normalizar_moeda_texto_pt_br(valor):
    """Converte uma célula textual "R$ 1,300.00" (en-US: milhar ',',
    decimal '.') para o formato pt-BR "R$ 1.300,00" (milhar '.', decimal
    ','). Só reescreve células que casam exatamente com o padrão
    monetário; qualquer outro texto (descrições, datas já formatadas
    etc.) é devolvido sem alteração."""
    if not isinstance(valor, str):
        return valor

    casamento = _PADRAO_MOEDA_TEXTO_EN_US.match(valor.strip())
    if not casamento:
        return valor

    prefixo, sinal, parte_inteira, parte_decimal = casamento.groups()
    parte_inteira_pt_br = parte_inteira.replace(',', '.')
    parte_decimal_pt_br = ',' + parte_decimal[1:] if parte_decimal else ''
    return f"{prefixo}{sinal}{parte_inteira_pt_br}{parte_decimal_pt_br}"


def _sanitizar_celula_formula(valor):
    """Prefixa com apóstrofo qualquer célula de texto que comece — ou
    que comece por um dos caracteres em _CARACTERES_IGNORAVEIS_NA_DETECCAO_DE_FORMULA
    seguidos de — um caractere de fórmula, forçando a planilha a tratá-la
    como texto literal. O apóstrofo é sempre adicionado no início
    ABSOLUTO do valor original (nunca depois do espaço/TAB/CR/LF/NBSP
    ignorado): como o primeiro caractere passa a ser `'`, a planilha para
    a detecção de fórmula ali, então não importa o que vem depois. Não
    afeta números, datas ou células cujo primeiro caractere não-ignorável
    não seja um desses; a sanitização existe só na cópia exportada, nunca
    no dado exibido em tela ou usado na conciliação."""
    if not isinstance(valor, str):
        return valor
    texto_significativo = valor.lstrip(_CARACTERES_IGNORAVEIS_NA_DETECCAO_DE_FORMULA)
    if texto_significativo.startswith(_PREFIXOS_FORMULA_PERIGOSOS):
        return "'" + valor
    return valor


def _normalizar_e_sanitizar_celula(valor):
    """Aplica primeiro a normalização de moeda textual (en-US -> pt-BR)
    e depois a proteção contra formula injection, na mesma célula."""
    return _sanitizar_celula_formula(_normalizar_moeda_texto_pt_br(valor))


def gerar_csv_divergencias(df: pd.DataFrame, ordenar_por: Optional[List[str]] = None) -> bytes:
    """Gera os bytes do CSV de divergências pronto para download.

    Formato: separador ';', decimal ',' (colunas numéricas; colunas de
    texto já formatadas como moeda, ex. "R$ 1,300.00" — como as tabelas
    reais de pages/analise_dados.py entregam —, são reescritas para o
    padrão pt-BR "R$ 1.300,00"; datas já formatadas "dd/mm/aaaa" são
    preservadas como estão), UTF-8 com BOM (utf-8-sig, para o Excel
    PT-BR abrir sem pedir encoding manual).

    Ordenação determinística: por padrão a ordem das linhas do `df` de
    entrada é preservada (sem embaralhar) — determinística desde que a
    origem já seja determinística, o que é o caso das tabelas de
    divergência (iteram um DataFrame filtrado, nunca um set/dict sem
    ordem). Quando `ordenar_por` é informado, ordena de forma estável
    (mergesort) por essas colunas, garantindo a mesma saída para o
    mesmo conjunto de linhas independente da ordem de chegada.

    Normalização de moeda textual e proteção contra formula injection
    são aplicadas a toda célula de texto do resultado, depois da
    ordenação.
    """
    if ordenar_por:
        df = df.sort_values(by=ordenar_por, kind='mergesort', ignore_index=True)

    df_sanitizado = df.map(_normalizar_e_sanitizar_celula)

    texto_csv = df_sanitizado.to_csv(index=False, sep=';', decimal=',')
    return texto_csv.encode('utf-8-sig')
