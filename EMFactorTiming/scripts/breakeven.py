"""Break-even trading cost of each timing portfolio against a benchmark portfolio.

Monthly net return at cost c (per unit of turnover) is gross - c * turnover, averaged over
countries, so it is linear in c and can be recomputed from portfolio_monthly.csv without
rerunning anything. The break-even cost is the c at which the timing portfolio's net
Sharpe ratio equals the benchmark's. "never" means the timing portfolio's Sharpe ratio is
below the benchmark's even at zero cost.

    python scripts/breakeven.py --run Baseline=reports/jkp_em --run "Equal-weighted factors=reports/jkp_em_ew"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

CELLS = [("enet:own", "Elastic net, EM"), ("enet:dm_only", "Elastic net, DM"),
         ("gbrt:own", "GBRT, EM"), ("gbrt:dm_only", "GBRT, DM")]
MAX_BP = 2000.0


def sharpe(g: pd.DataFrame, c_bp: float) -> float:
    net = g["gross"].to_numpy() - c_bp / 1e4 * g["turnover"].to_numpy()
    return float(np.sqrt(12) * net.mean() / net.std(ddof=1))


def breakeven(timing: pd.DataFrame, bench: pd.DataFrame) -> float:
    """Cost in bp at which the two net Sharpe ratios are equal; NaN if timing never wins."""
    diff = lambda c: sharpe(timing, c) - sharpe(bench, c)  # noqa: E731
    if diff(0.0) <= 0:
        return np.nan
    if diff(MAX_BP) > 0:
        return np.inf
    lo, hi = 0.0, MAX_BP
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if diff(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def _f(x: float) -> str:
    return "never" if np.isnan(x) else (f"$>${MAX_BP:.0f}" if np.isinf(x) else f"{x:.0f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="label=run_dir, repeatable")
    ap.add_argument("--out", default="reports/robustness/breakeven.csv")
    ap.add_argument("--tex", default="paper/tables/breakeven.tex")
    a = ap.parse_args()
    rows = []
    for spec in a.run:
        label, d = spec.rsplit("=", 1)
        if json.loads((Path(d) / "run_manifest.json").read_text()).get("provenance") != "JKP":
            raise SystemExit(f"{d} is not a real-data run")
        m = pd.read_csv(Path(d) / "portfolio_monthly.csv")
        by = {s: g.sort_values("target_month") for s, g in m.groupby("strategy")}
        row = {"spec": label}
        for s, _ in CELLS:
            row[f"vs_static_{s}"] = breakeven(by[s], by["static_ew"])
            row[f"vs_shrink_{s}"] = breakeven(by[s], by["shrink_mean:rule"])
        rows.append(row)
    df = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)

    lines = [r"\begin{table}[!ht]", r"\centering\small",
             r"\caption{Break-even trading cost of timing portfolios (basis points per unit of turnover)}",
             r"\label{tab:breakeven}", r"\begin{tabular}{lrrrr}", r"\toprule",
             "Specification & " + " & ".join(lab for _, lab in CELLS) + r" \\", r"\midrule"]
    for _, r in df.iterrows():
        lines.append(r["spec"] + " & " + " & ".join(_f(r[f"vs_static_{s}"]) for s, _ in CELLS) + r" \\")
    pos = [(r["spec"], lab, r[f"vs_shrink_{s}"]) for _, r in df.iterrows() for s, lab in CELLS
           if not np.isnan(r[f"vs_shrink_{s}"])]
    if not pos:
        shrink_note = "Against the shrinkage-mean portfolio no timing portfolio has a positive break-even cost."
    else:
        shrink_note = ("Against the shrinkage-mean portfolio the break-even cost is positive only for "
                       + "; ".join(f"{lab} ({spec.lower()}, {_f(v)} bp)" for spec, lab, v in pos) + ".")
    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{4pt}",
              r"\begin{minipage}{0.95\linewidth}\footnotesize",
              r"\textit{Notes:} Cost per unit of monthly timing turnover at which the timing portfolio's net "
              r"Sharpe ratio equals that of the static equal-weight factor portfolio, which is charged the same "
              r"cost on its own turnover. ``never'': the timing portfolio's Sharpe ratio is lower even at zero "
              r"cost. EM / DM = trained on emerging / developed markets only. " + shrink_note,
              r"\end{minipage}", r"\end{table}"]
    Path(a.tex).write_text("\n".join(lines) + "\n")
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(df.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
