#!/usr/bin/env python3
"""Gera o PDF do arquivo UNICO de casos de teste (docs/casos-de-teste.md).

Uso:
    python gerar_pdf_casos_de_teste.py [entrada.md] [saida.pdf] [--fonts=DIR]

Padroes: entrada = docs/casos-de-teste.md ; saida = docs/casos-de-teste.pdf ;
fontes Inter = assets/fonts/ (arquivos inter-latin-{400,500,600,700}-normal.woff2). Sem as fontes,
usa Segoe UI/Arial do sistema.
Requer: pip install weasyprint markdown  (weasyprint ja e' dependencia do app; markdown so' para este script).
O PDF e' 100% derivado do .md: nao edite o PDF, edite o .md e gere de novo.
"""
import base64, html, os, re, sys
import markdown
from weasyprint import HTML

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
entrada = args[0] if len(args) > 0 else "docs/casos-de-teste.md"
saida = args[1] if len(args) > 1 else "docs/casos-de-teste.pdf"
fonts_dir = opts.get("fonts", "assets/fonts")

md_text = open(entrada, encoding="utf-8-sig").read()
titulo = (re.search(r"^#\s+(.+)$", md_text, flags=re.M) or [None, "Casos de Teste"])[1]
corpo = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc", "sane_lists"],
                          extension_configs={"toc": {"toc_depth": "2-3"}})

# status coloridos
def cor(m):
    txt = m.group(1)
    cls = "pass" if txt.startswith("PASS") else "fail" if txt.startswith("FAIL") else "na"
    return f'<code class="st {cls}">{txt}</code>'
corpo = re.sub(r"<code>((?:PASS|FAIL|NAO EXECUTADO|NÃO EXECUTADO)[^<]*)</code>", cor, corpo)

face = ""
for w in (400, 500, 600, 700):
    p = os.path.join(fonts_dir, f"inter-latin-{w}-normal.woff2")
    if os.path.exists(p):
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        face += f'@font-face{{font-family:"Inter";font-weight:{w};src:url(data:font/woff2;base64,{b64}) format("woff2");}}\n'

css = face + """
@page{size:A4 portrait;margin:16mm 15mm 18mm;
 @bottom-left{content:"Casos de teste · conc_banc";font:8pt Inter,'Segoe UI',Arial,sans-serif;color:#64748b}
 @bottom-right{content:"Página " counter(page) " de " counter(pages);font:8pt Inter,'Segoe UI',Arial,sans-serif;color:#64748b}}
html{font-family:Inter,'Segoe UI',Arial,sans-serif;font-size:9.6pt;line-height:1.5;color:#0f1f38}
h1{font-size:21pt;color:#0b2545;letter-spacing:-.02em;margin:0 0 8px;padding-bottom:8px;border-bottom:2.5px solid #0b2545}
h2{font-size:14.5pt;color:#0b2545;margin:22px 0 6px;padding-bottom:5px;border-bottom:1.5px solid #0b2545;break-before:page;break-after:avoid}
h2:first-of-type{break-before:auto}
h3{font-size:11.5pt;color:#13315c;margin:16px 0 4px;break-after:avoid}
h4{font-size:10.3pt;color:#0b2545;margin:16px 0 3px;padding:5px 8px;background:#eef3f7;border-left:3px solid #13315c;break-after:avoid}
h5{font-size:9.6pt;margin:10px 0 2px;break-after:avoid}
p{margin:4px 0 6px}
ol,ul{margin:3px 0 7px;padding-left:20px}li{margin:1.5px 0}
table{width:100%;border-collapse:collapse;margin:6px 0 10px;font-size:8.6pt;break-inside:avoid}
th{background:#f6f7f9;text-align:left;border-top:1.5px solid #0b2545;border-bottom:1px solid #d9dfe8;padding:4px 6px}
td{border-bottom:1px solid #e9edf3;padding:3px 6px;vertical-align:top}
code{font-family:'Cascadia Mono',Consolas,monospace;font-size:8.4pt;background:#f1f4f8;padding:0 3px;border-radius:2px}
pre{background:#f6f7f9;border:1px solid #e9edf3;padding:6px 8px;font-size:8pt;white-space:pre-wrap;break-inside:avoid}pre code{background:none;padding:0}
code.st{font-family:inherit;font-weight:700;font-size:8.4pt;padding:1px 7px;border-radius:99px;border:1px solid}
code.pass{background:#f3f6fa;color:#1f4e79;border-color:#c3d1e0}
code.fail{background:#faf1f1;color:#6f2a2a;border-color:#d3a5a5}
code.na{background:#fbf7ee;color:#6b4f12;border-color:#d9c28f}
hr{border:0;border-top:1px solid #d9dfe8;margin:14px 0}
em{color:#475569}
.toc{border:1px solid #d9dfe8;border-radius:3px;padding:6px 14px;margin:10px 0 14px;font-size:9pt}
.toc ul{list-style:none;padding-left:14px;margin:1px 0}.toc>ul{padding-left:0}
.toc a{color:#0b2545;text-decoration:none}
"""
doc = f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(titulo)}</title><style>{css}</style></head><body>{corpo}</body></html>'
# sumario: insere apos o primeiro bloco introdutorio (antes do primeiro h2)
try:
    toc_html = markdown.Markdown(extensions=["toc"], extension_configs={"toc": {"toc_depth": "2"}})
    toc_html.convert(md_text)
    doc = doc.replace("<h2", f'<div class="toc"><strong>Sumário</strong>{toc_html.toc}</div><h2', 1)
except Exception:
    pass
HTML(string=doc, base_url=os.getcwd()).write_pdf(saida)
print("PDF gerado:", saida)
