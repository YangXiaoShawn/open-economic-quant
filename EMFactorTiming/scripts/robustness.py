r"""Robustness table for the real-data run.

Rows are alternative specifications; each is computed from saved predictions:

  baseline        the main run (kappa = 120, 20 bp, out of sample 2000-)
  oos 2005        the main run's forecasts for target months from 2005 on. Models are
                  refitted every January on an expanding window, so these forecasts are
                  identical to a rerun with --oos-start 2005.
  --run label=dir separate full reruns: kappa 60 / 240, equal-weighted and uncapped
                  value-weighted factors, time-varying market classification
  cost 10 / 40 bp the main run's forecasts with a different cost per unit of turnover

    python scripts/robustness.py --base reports/jkp_em \
        --run '$\kappa = 60$=reports/jkp_em_kappa60' --run 'Equal-weighted factors=reports/jkp_em_ew'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emft.evaluate import portfolio_returns, portfolio_table, r2_table  # noqa: E402

CELLS = [("enet", "own"), ("enet", "dm_only"), ("gbrt", "own"), ("gbrt", "dm_only")]
PORTS = ["static_ew", "shrink_mean:rule", "enet:own", "enet:dm_only", "gbrt:own", "gbrt:dm_only"]


def _check(run: Path) -> None:
    m = json.loads((run / "run_manifest.json").read_text())
    if m.get("provenance") != "JKP":
        raise SystemExit(f"{run} is not a real-data run")


def summarise(preds: pd.DataFrame, cost_bps: float, label: str) -> dict:
    r2 = r2_table(preds).set_index(["model", "scope"])
    port = portfolio_table(portfolio_returns(preds, cost_bps=cost_bps)).set_index("strategy")
    row = {"spec": label, "shrink_vs_hist": r2.loc[("shrink_mean", "rule"), "r2_vs_hist_pct"],
           "months": int(preds["target_month"].nunique())}
    for m, s in CELLS:
        row[f"r2_{m}_{s}"] = r2.loc[(m, s), "r2_vs_shrink_pct"]
        row[f"t_{m}_{s}"] = r2.loc[(m, s), "cw_t_shrink"]
    for p in PORTS:
        row[f"srnet_{p}"] = port.loc[p, "sharpe_net"]
    return row


def _f(x: float, d: int = 2) -> str:
    return "--" if pd.isna(x) else f"{x:.{d}f}".replace("-", "$-$")


def to_tex(df: pd.DataFrame) -> str:
    lines = [r"\begin{table}[!ht]", r"\centering\footnotesize", r"\caption{Robustness}", r"\label{tab:robust}",
             r"\begin{tabular}{lrrrrrrrrr}", r"\toprule",
             r"\multicolumn{10}{l}{\textit{Panel A: $R^2_{OS}$ (\%) and Clark--West $t$ against the shrinkage mean}} \\",
             r"\addlinespace",
             r" & Shrink.\ vs.\ & \multicolumn{2}{c}{Elastic net, EM} & \multicolumn{2}{c}{Elastic net, DM}"
             r" & \multicolumn{2}{c}{GBRT, EM} & \multicolumn{2}{c}{GBRT, DM} \\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}",
             r"Specification & own mean & $R^2$ & $t$ & $R^2$ & $t$ & $R^2$ & $t$ & $R^2$ & $t$ \\", r"\midrule"]
    stat = df[~df["spec"].str.startswith("Cost")]
    for _, r in stat.iterrows():
        cells = [r["spec"], _f(r["shrink_vs_hist"], 3)]
        for m, s in CELLS:
            cells += [_f(r[f"r2_{m}_{s}"], 3), _f(r[f"t_{m}_{s}"])]
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{10pt}",
              r"\begin{tabular}{lrrrrrr}", r"\toprule",
              r"\multicolumn{7}{l}{\textit{Panel B: net Sharpe ratios of timing portfolios}} \\", r"\addlinespace",
              r" & & Shrinkage & \multicolumn{2}{c}{Elastic net} & \multicolumn{2}{c}{GBRT} \\",
              r"\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
              r"Specification & Static & mean & EM & DM & EM & DM \\", r"\midrule"]
    for _, r in df.iterrows():
        lines.append(" & ".join([r["spec"]] + [_f(r[f"srnet_{p}"]) for p in PORTS]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{4pt}",
              r"\begin{minipage}{0.97\linewidth}\footnotesize",
              r"\textit{Notes:} Emerging-market test set. Baseline: $\kappa=120$, 20 bp per unit of turnover, "
              r"out of sample 2000--2025. ``OOS from 2005'' keeps the baseline forecasts for target months from "
              r"2005, which equal those of a rerun starting in 2005 because models are refitted annually on an "
              r"expanding window. $\kappa$ rows rerun the full pipeline, changing both the benchmark and the "
              r"learned models' anchor. Factor-weighting rows rerun it on equal-weighted or uncapped "
              r"value-weighted JKP factors. ``Time-varying classification'' assigns each country-month the MSCI "
              r"class then in force (Appendix~\ref{app:classification}). Cost rows change only the charge per unit of timing turnover. "
              r"``Shrink.\ vs.\ own mean'' is the $R^2_{OS}$ of the shrinkage mean against the own historical mean. "
              r"EM / DM = trained on emerging / developed markets only.",
              r"\end{minipage}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="reports/jkp_em")
    ap.add_argument("--run", action="append", default=[], help="label=run_dir, repeatable")
    ap.add_argument("--out", default="reports/robustness")
    ap.add_argument("--tex", default="paper/tables/robustness.tex")
    a = ap.parse_args()
    base = Path(a.base)
    _check(base)
    preds = pd.read_parquet(base / "predictions.parquet")
    rows = [summarise(preds, 20, r"Baseline"),
            summarise(preds[preds["target_month"].dt.year >= 2005], 20, "OOS from 2005")]
    for spec in a.run:
        label, d = spec.rsplit("=", 1)
        _check(Path(d))
        rows.append(summarise(pd.read_parquet(Path(d) / "predictions.parquet"), 20, label))
    for c in (10, 40):
        rows.append(summarise(preds, c, f"Cost {c} bp"))
    df = pd.DataFrame(rows)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "robustness.csv", index=False)
    Path(a.tex).write_text(to_tex(df))
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(df.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
