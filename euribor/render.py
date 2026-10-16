"""Render a report's Markdown to a self-contained HTML page or, via pandoc and tectonic, to PDF.

Both read the Markdown from reports/ and resolve the figure links (``figures/...``) relative to that folder.
"""
import base64
import datetime as dt
import re
import subprocess
import sys

from .config import REPORTS, RESULTS

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

LATEX_HEADER = r"""\usepackage{etoolbox}\AtBeginEnvironment{longtable}{\footnotesize}
\usepackage{float}\floatplacement{figure}{H}
\setlength{\parskip}{5pt plus 1pt}\setlength{\parindent}{0pt}
\usepackage{caption}\captionsetup{font=small,skip=4pt,labelformat=empty}
\renewcommand{\arraystretch}{1.15}"""


def to_html(source="BACKTEST_50K.md", title="Euribor €50k backtest"):
    """One self-contained page with the figures embedded as base64 and a two-column table of contents."""
    from markdown_it import MarkdownIt

    md_path = REPORTS / source
    html = MarkdownIt("commonmark").enable("table").render(md_path.read_text())

    def embed(match):
        data = base64.b64encode((REPORTS / match.group(1)).read_bytes()).decode()
        return f'src="data:image/png;base64,{data}"'

    html = re.sub(r'src="(figures/[^"]+\.png)"', embed, html)
    html = html.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
    toc = []

    def anchor(match):
        level, text = match.group(1), match.group(2)
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-")
        toc.append((level, slug, text))
        return f'<h{level} id="{slug}">{text}</h{level}>'

    html = re.sub(r"<h([12])>(.*?)</h\1>", anchor, html)
    nav = "".join(f'<li class="l{level}"><a href="#{slug}">{text}</a></li>' for level, slug, text in toc[1:])
    first = html.index("</h1>") + 5
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><style>{CSS}</style></head><body>{html[:first]}<nav><ul>{nav}</ul></nav>{html[first:]}</body></html>')
    out = md_path.with_suffix(".html")
    out.write_text(page)
    print(f"{out.name} written, {len(page) / 1e6:.1f} MB, {len(toc)} headings, {html.count('<img')} figures, {html.count('<table>')} tables")
    return out


def _fit_table_widths(lines):
    """Rewrite a pipe table's separator row so pandoc sizes columns by content."""
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    n = max(len(r) for r in rows)
    widths = [max(len(r[j]) if j < len(r) else 0 for i, r in enumerate(rows) if i != 1) for j in range(n)]
    widths = [max(3, min(w, 110)) for w in widths]
    lines[1] = "|" + "|".join("-" * w for w in widths) + "|"
    return lines


def to_pdf(source="BACKTEST_50K.md"):
    """Markdown -> .tex and .pdf through pandoc with the tectonic engine. Italic figure-caption lines are dropped (pandoc uses the alt text)."""
    md_path = REPORTS / source
    stem = md_path.stem
    md = "\n".join(line for line in md_path.read_text().splitlines() if not line.startswith("*Figure ")) + "\n"
    md = md.replace("σ", "$\\sigma$").replace("|score|", "$|\\text{score}|$")
    out, table = [], []
    for line in md.splitlines() + [""]:
        if line.startswith("|"):
            table.append(line)
            continue
        if table:
            is_table = len(table) > 1 and set(table[1].replace("|", "").strip()) <= set("-: ")
            out += _fit_table_widths(table) if is_table else table
            table = []
        out.append(line)
    RESULTS.mkdir(exist_ok=True)
    tmp_md = RESULTS / f"_{stem}_latex.md"
    tmp_md.write_text("\n".join(out))
    header = RESULTS / "_pdf_header.tex"
    header.write_text(LATEX_HEADER)
    common = ["--from", "markdown+pipe_tables", "--shift-heading-level-by=-1", "--columns=60", f"--resource-path={REPORTS}",
              "-V", "geometry:margin=2.1cm", "-V", "papersize=a4", "-V", "fontsize=10pt",
              "-V", "mainfont=texgyreheros-regular.otf",
              "-V", "mainfontoptions=BoldFont=texgyreheros-bold.otf,ItalicFont=texgyreheros-italic.otf,BoldItalicFont=texgyreheros-bolditalic.otf",
              "-V", "monofont=texgyrecursor-regular.otf", "-V", "monofontoptions=BoldFont=texgyrecursor-bold.otf,Scale=0.9",
              "-V", "colorlinks=true", "-V", "linkcolor=blue", "-V", "urlcolor=blue",
              "-V", "date=" + dt.date.today().strftime("%-d %B %Y"), f"--include-in-header={header}"]
    subprocess.run(["pandoc", str(tmp_md), "-s", "-o", str(REPORTS / f"{stem}.tex")] + common, check=True)
    subprocess.run(["pandoc", str(tmp_md), "--pdf-engine=tectonic", "-o", str(REPORTS / f"{stem}.pdf")] + common, check=True, cwd=REPORTS)
    print(f"{stem}.tex and {stem}.pdf written")


if __name__ == "__main__":
    to_html(*sys.argv[1:2])
