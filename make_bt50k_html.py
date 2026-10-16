"""Render BACKTEST_50K.md to one self-contained page (figures embedded) -> BACKTEST_50K.html."""
import os, re, base64
from markdown_it import MarkdownIt
ROOT = os.path.dirname(os.path.abspath(__file__))
html = MarkdownIt("commonmark").enable("table").render(open(f"{ROOT}/BACKTEST_50K.md").read())
html = re.sub(r'src="(results/[^"]+\.png)"', lambda m: 'src="data:image/png;base64,' + base64.b64encode(open(f"{ROOT}/{m.group(1)}", "rb").read()).decode() + '"', html)
html = html.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
toc = []
def anchor(m):
    slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", m.group(2)).lower()).strip("-"); toc.append((m.group(1), slug, m.group(2))); return f'<h{m.group(1)} id="{slug}">{m.group(2)}</h{m.group(1)}>'
html = re.sub(r"<h([12])>(.*?)</h\1>", anchor, html)
nav = "".join(f'<li class="l{lv}"><a href="#{slug}">{txt}</a></li>' for lv, slug, txt in toc[1:])
CSS = """
:root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--rule:#e1e0d9;--accent:#2a78d6}
*{box-sizing:border-box}html{background:var(--surface)}
body{margin:0 auto;max-width:1040px;padding:40px 24px 80px;background:var(--surface);color:var(--ink);font:16px/1.55 -apple-system,"Helvetica Neue",Arial,sans-serif}
h1{font-size:28px;line-height:1.2;margin:56px 0 12px;letter-spacing:-0.01em}h1:first-of-type{margin-top:0}
h2{font-size:20px;margin:40px 0 10px;padding-top:14px;border-top:1px solid var(--rule)}
p,li{color:var(--ink)}p>em:only-child{color:var(--ink2);font-size:14px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{font:13px ui-monospace,Menlo,monospace;background:#f0efec;padding:1px 5px;border-radius:4px;overflow-wrap:anywhere}
hr{border:0;border-top:1px solid var(--rule);margin:48px 0}
img{display:block;width:100%;height:auto;margin:20px 0 6px;border:1px solid var(--rule);border-radius:6px}
.tbl{overflow-x:auto;margin:14px 0 22px}
table{border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;min-width:60%}
th,td{padding:7px 14px 7px 0;text-align:left;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-weight:600;color:var(--ink2);border-bottom:1px solid #c3c2b7;white-space:nowrap}
nav{margin:18px 0 8px;padding:14px 18px;border:1px solid var(--rule);border-radius:6px;font-size:14px}
nav ul{list-style:none;margin:0;padding:0;columns:2;column-gap:32px}nav li.l1{font-weight:600;margin-top:6px}nav li.l2{padding-left:14px}
@media(max-width:640px){body{padding:24px 16px 56px}nav ul{columns:1}h1{font-size:23px}}
@media print{body{max-width:none;padding:0}nav{display:none}h1{break-before:page}h1:first-of-type{break-before:auto}img,.tbl{break-inside:avoid}}
"""
first = html.index("</h1>") + 5
page = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Euribor €50k backtest</title><style>{CSS}</style></head><body>{html[:first]}<nav><ul>{nav}</ul></nav>{html[first:]}</body></html>'
open(f"{ROOT}/BACKTEST_50K.html", "w").write(page); print("BACKTEST_50K.html written,", round(len(page) / 1e6, 1), "MB,", len(toc), "headings,", html.count("<img"), "figures,", html.count("<table>"), "tables")
