"""BACKTEST_50K.md -> BACKTEST_50K.tex and BACKTEST_50K.pdf via pandoc and tectonic (XeTeX).
Pipe-table separator rows are rewritten so column widths follow the content; the italic caption lines are dropped (pandoc uses the image alt text as the figure caption)."""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); SRC = sys.argv[1] if len(sys.argv) > 1 else "BACKTEST_50K.md"; STEM = os.path.splitext(SRC)[0]
md = open(f"{ROOT}/{SRC}").read()
md = "\n".join(l for l in md.splitlines() if not l.startswith("*Figure ")) + "\n"
md = md.replace("σ", "$\\sigma$").replace("|score|", "$|\\text{score}|$")
def fix_table(lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]; n = max(len(r) for r in rows)
    w = [max(len(r[j]) if j < len(r) else 0 for i, r in enumerate(rows) if i != 1) for j in range(n)]; w = [max(3, min(x, 110)) for x in w]
    lines[1] = "|" + "|".join("-" * x for x in w) + "|"; return lines
out, buf = [], []
for l in md.splitlines() + [""]:
    if l.startswith("|"): buf.append(l)
    else:
        if buf: out += fix_table(buf) if len(buf) > 1 and set(buf[1].replace("|", "").strip()) <= set("-: ") else buf; buf = []
        out.append(l)
tmp = f"{ROOT}/results/_{STEM}_latex.md"; open(tmp, "w").write("\n".join(out))
HEAD = r"""\usepackage{etoolbox}\AtBeginEnvironment{longtable}{\footnotesize}
\usepackage{float}\floatplacement{figure}{H}
\setlength{\parskip}{5pt plus 1pt}\setlength{\parindent}{0pt}
\usepackage{caption}\captionsetup{font=small,skip=4pt,labelformat=empty}
\renewcommand{\arraystretch}{1.15}"""
open(f"{ROOT}/results/_pdf_header.tex", "w").write(HEAD)
common = ["--from", "markdown+pipe_tables", "--shift-heading-level-by=-1", "--columns=60", f"--resource-path={ROOT}", "-V", "geometry:margin=2.1cm", "-V", "papersize=a4", "-V", "fontsize=10pt",
          "-V", "mainfont=texgyreheros-regular.otf", "-V", "mainfontoptions=BoldFont=texgyreheros-bold.otf,ItalicFont=texgyreheros-italic.otf,BoldItalicFont=texgyreheros-bolditalic.otf",
          "-V", "monofont=texgyrecursor-regular.otf", "-V", "monofontoptions=BoldFont=texgyrecursor-bold.otf,Scale=0.9", "-V", "colorlinks=true", "-V", "linkcolor=blue", "-V", "urlcolor=blue",
          "-V", "date=" + __import__("datetime").date.today().strftime("%-d %B %Y"), f"--include-in-header={ROOT}/results/_pdf_header.tex"]
subprocess.run(["pandoc", tmp, "-s", "-o", f"{ROOT}/{STEM}.tex"] + common, check=True)
subprocess.run(["pandoc", tmp, "--pdf-engine=tectonic", "-o", f"{ROOT}/{STEM}.pdf"] + common, check=True, cwd=ROOT)
print(f"{STEM}.tex and {STEM}.pdf written")
