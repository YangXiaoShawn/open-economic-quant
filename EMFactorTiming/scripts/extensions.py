"""Table of the two exploratory extensions: real-time forecast shrinkage and U.S. state variables.

Panel A compares each learned model with its "_rs" version (forecast deviation scaled by a
slope estimated inside each training window) on capped value-weighted and equal-weighted
factors. Panel B compares models with and without the U.S. state variables on the sample
where all of them exist (feature months from 1990-01, so out of sample 2001-2025).

    python scripts/extensions.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

MODELS = [("ols", "OLS"), ("enet", "Elastic net"), ("gbrt", "GBRT")]
SCOPES = ("own", "dm_only")


def _load(run: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if json.loads((run / "run_manifest.json").read_text()).get("provenance") != "JKP":
        raise SystemExit(f"{run} is not a real-data run")
    r2 = pd.read_csv(run / "r2_oos.csv").set_index(["model", "scope"])
    port = pd.read_csv(run / "portfolios.csv").set_index("strategy")
    preds = pd.read_parquet(run / "predictions.parquet", columns=["model", "scope", "target_month", "scale"])
    return r2, port, preds


def _cells(r2: pd.DataFrame, port: pd.DataFrame, model: str) -> dict:
    row = {}
    for s in SCOPES:
        row[f"r2_{s}"] = r2.loc[(model, s), "r2_vs_shrink_pct"]
        row[f"t_{s}"] = r2.loc[(model, s), "cw_t_shrink"]
        row[f"sr_{s}"] = port.loc[f"{model}:{s}", "sharpe_net"]
    return row


def _mean_scale(preds: pd.DataFrame, model: str, scope: str) -> float:
    g = preds[(preds["model"] == model) & (preds["scope"] == scope)]
    return float(g.groupby(g["target_month"].dt.year)["scale"].first().mean())


def _f(x: float, d: int = 2) -> str:
    return "--" if pd.isna(x) else f"{x:.{d}f}".replace("-", "$-$")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rs", default="reports/jkp_em_rs")
    ap.add_argument("--rs-ew", default="reports/jkp_em_ew_rs")
    ap.add_argument("--no-macro", default="reports/jkp_em_from1990")
    ap.add_argument("--macro", default="reports/jkp_em_macro")
    ap.add_argument("--out", default="reports/robustness/extensions.csv")
    ap.add_argument("--tex", default="paper/tables/extensions.tex")
    a = ap.parse_args()

    rows = []
    for panel, label, run in (("A", "Capped value-weighted factors", a.rs), ("A", "Equal-weighted factors", a.rs_ew)):
        r2, port, preds = _load(Path(run))
        for m, name in MODELS:
            rows.append({"panel": panel, "block": label, "model": name, "variant": "As estimated", **_cells(r2, port, m)})
            rows.append({"panel": panel, "block": label, "model": name, "variant": "Real-time shrinkage",
                         **_cells(r2, port, f"{m}_rs"), "scale_own": _mean_scale(preds, f"{m}_rs", "own"),
                         "scale_dm_only": _mean_scale(preds, f"{m}_rs", "dm_only")})
        rows.append({"panel": panel, "block": label, "model": "Static portfolio", "variant": "",
                     "sr_own": port.loc["static_ew", "sharpe_net"]})
        rows.append({"panel": panel, "block": label, "model": "Shrinkage-mean portfolio", "variant": "",
                     "sr_own": port.loc["shrink_mean:rule", "sharpe_net"]})
    base, with_macro = _load(Path(a.no_macro)), _load(Path(a.macro))
    for m, name in MODELS:
        rows.append({"panel": "B", "block": "From 1990", "model": name, "variant": "Without state variables",
                     **_cells(base[0], base[1], m)})
        rows.append({"panel": "B", "block": "From 1990", "model": name, "variant": "With state variables",
                     **_cells(with_macro[0], with_macro[1], m)})
    rows.append({"panel": "B", "block": "From 1990", "model": "Static portfolio", "variant": "",
                 "sr_own": base[1].loc["static_ew", "sharpe_net"]})
    rows.append({"panel": "B", "block": "From 1990", "model": "Shrinkage-mean portfolio", "variant": "",
                 "sr_own": base[1].loc["shrink_mean:rule", "sharpe_net"]})
    df = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)

    lines = [r"\begin{table}[!ht]", r"\centering\footnotesize\setlength{\tabcolsep}{4pt}",
             r"\caption{Exploratory extensions}", r"\label{tab:extensions}",
             r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & \multicolumn{3}{c}{EM-trained} & \multicolumn{3}{c}{DM-trained} \\",
             r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
             r"Model & Forecast & $R^2_{OS}$ (\%) & CW $t$ & SR net & $R^2_{OS}$ (\%) & CW $t$ & SR net \\"]
    titles = {"A": "Panel A: real-time forecast shrinkage, out of sample 2000--2025",
              "B": "Panel B: U.S. state variables, feature months from 1990, out of sample 2001--2025"}
    for panel in ("A", "B"):
        lines += [r"\midrule", rf"\multicolumn{{8}}{{l}}{{\textit{{{titles[panel]}}}}} \\"]
        for block, g in df[df["panel"] == panel].groupby("block", sort=False):
            if panel == "A":
                lines.append(rf"\multicolumn{{8}}{{l}}{{{block}}} \\")
            prev = None
            for _, r in g.iterrows():
                if r["variant"] == "":
                    lines.append(f"{r['model']} & & & & {_f(r['sr_own'])} & & & \\\\")
                    continue
                name = "" if r["model"] == prev else r["model"]
                prev = r["model"]
                lines.append(f"{name} & {r['variant']} & " + " & ".join(
                    [_f(r[f'r2_{s}'], 3) + " & " + _f(r[f't_{s}']) + " & " + _f(r[f'sr_{s}']) for s in SCOPES]) + r" \\")
            lines.append(r"\addlinespace")
    sc = df[df["variant"] == "Real-time shrinkage"][["scale_own", "scale_dm_only"]].to_numpy()
    lines += [r"\bottomrule", r"\end{tabular}", "", r"\vspace{4pt}",
              r"\begin{minipage}{0.97\linewidth}\footnotesize",
              r"\textit{Notes:} $R^2_{OS}$ and Clark--West $t$ against the shrinkage mean; SR net is the net Sharpe "
              r"ratio of the timing portfolio at 20 basis points per unit of turnover (for the static and "
              r"shrinkage-mean rows, of those portfolios). Real-time shrinkage multiplies each forecast's "
              r"deviation from the shrinkage mean by a slope in $[0,1]$ estimated inside the training window: "
              r"the model is fitted on labels before the window's last 36 months and the slope of realized on "
              r"forecast deviations over those months is the scale; the model is then refitted on the whole "
              rf"window. Average yearly scales range from {np.nanmin(sc):.2f} to {np.nanmax(sc):.2f}. "
              r"State variables: log VIX, the U.S. 10-year minus 3-month Treasury spread and the 12-month log "
              r"change of the broad trade-weighted dollar (FRED), dated at the end of the feature month; both "
              r"rows of Panel B use the same sample. Both extensions were chosen after seeing the baseline "
              r"results and are exploratory.",
              r"\end{minipage}", r"\end{table}"]
    Path(a.tex).write_text("\n".join(lines) + "\n")
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(df.drop(columns=["panel"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
