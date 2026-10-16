"""Command-line entry point: ``python -m euribor <step>``. Run ``python -m euribor --help`` for the steps."""
import argparse
import sys

from . import config

STEPS = {
    "fetch": ("download the public source series into data/raw (see --source)", "sources", "main"),
    "futures": ("build the synthetic quarterly Euribor futures and the continuous series", "futures", "main"),
    "features": ("build the monthly feature matrix and next-month target", "features", "main"),
    "backtest": ("run every strategy variant on one contract", "backtest", "main"),
    "montecarlo": ("bootstrap, no-skill nulls, deflated Sharpe, CPCV and nested walk-forward", "montecarlo", "main"),
    "account": ("EUR 50,000 account simulation and its Monte Carlo, both windows", "account", "main"),
    "charts": ("draw every figure into reports/figures", "charts", "main"),
    "reports": ("write REPORT.md, BACKTEST_50K.md and BACKTEST_50K_APPENDIX.md", "reports", "main"),
    "render": ("render a report to HTML (default) or PDF: render [--pdf] [FILE.md]", "render", None),
    "collect-eurex": ("append the latest Eurex FEU3 settlements to data/raw/eurex_feu3_history.csv", "sources", "collect_eurex"),
}
PIPELINE = ["futures", "features", "backtest", "montecarlo", "account", "charts", "reports"]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m euribor", description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="steps:\n" + "\n".join(f"  {k:14s} {v[0]}" for k, v in STEPS.items())
                                     + "\n  all            every step from futures to reports, in order (no download)")
    parser.add_argument("step", choices=list(STEPS) + ["all"])
    parser.add_argument("--source", nargs="*", help="fetch: only these sources (ecb, bundesbank, eurostat, epu, fred, bis, tic, eurex)")
    parser.add_argument("--pdf", action="store_true", help="render: produce PDF through pandoc and tectonic instead of HTML")
    parser.add_argument("file", nargs="?", default="BACKTEST_50K.md", help="render: Markdown file in reports/")
    args = parser.parse_args(argv)
    config.ensure_dirs()
    steps = PIPELINE if args.step == "all" else [args.step]
    for step in steps:
        _, module_name, function = STEPS[step]
        module = __import__(f"euribor.{module_name}", fromlist=[module_name])
        if step == "fetch":
            module.main(args.source)
        elif step == "render":
            (module.to_pdf if args.pdf else module.to_html)(args.file)
        else:
            getattr(module, function)()
        if len(steps) > 1:
            print(f"--- {step} done", file=sys.stderr)


if __name__ == "__main__":
    main()
