"""Write the paper's results tables from one run directory.

Every number in paper/tables/*.tex written by this script comes from the CSVs and
predictions of a single `python -m emft run`, so the paper can be regenerated
after any rerun instead of being edited by hand.

    python scripts/paper_tables.py --run reports/jkp_em --out paper/tables
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emft.evaluate import newey_west_t  # noqa: E402

MODEL_LABEL = {
    "ols": "OLS", "enet": "Elastic net", "gbrt": "Gradient-boosted trees", "nn": "Neural network",
    "hist_mean": "Own historical mean", "shrink_mean": "Shrinkage mean", "fmom": "Factor momentum",
}
SCOPE_LABEL = {"own": "EM", "dm_only": "DM only", "pooled": "Pooled", "rule": "--"}
COUNTRY = {
    "are": "United Arab Emirates", "bra": "Brazil", "chl": "Chile", "chn": "China", "col": "Colombia",
    "cze": "Czech Republic", "egy": "Egypt", "grc": "Greece", "hun": "Hungary", "idn": "Indonesia",
    "ind": "India", "kor": "Korea", "kwt": "Kuwait", "mex": "Mexico", "mys": "Malaysia", "per": "Peru",
    "phl": "Philippines", "pol": "Poland", "qat": "Qatar", "sau": "Saudi Arabia", "tha": "Thailand",
    "tur": "Turkey", "twn": "Taiwan", "zaf": "South Africa",
    "aus": "Australia", "aut": "Austria", "bel": "Belgium", "can": "Canada", "che": "Switzerland",
    "deu": "Germany", "dnk": "Denmark", "esp": "Spain", "fin": "Finland", "fra": "France",
    "gbr": "United Kingdom", "hkg": "Hong Kong", "irl": "Ireland", "isr": "Israel", "ita": "Italy",
    "jpn": "Japan", "nld": "Netherlands", "nor": "Norway", "nzl": "New Zealand", "prt": "Portugal",
    "sgp": "Singapore", "swe": "Sweden", "usa": "United States",
}
LEARNED_ORDER = ["ols", "enet", "gbrt", "nn"]
SCOPE_ORDER = ["own", "dm_only", "pooled"]


def _f(x: float, d: int = 2) -> str:
    return "--" if pd.isna(x) else f"{x:.{d}f}".replace("-", "$-$")


def _notes(text: str) -> list[str]:
    return ["", r"\vspace{4pt}", r"\begin{minipage}{0.95\linewidth}\footnotesize",
            r"\textit{Notes:} " + text, r"\end{minipage}"]


def coverage_table(cov: pd.DataFrame, manifest: dict) -> str:
    cov = cov[cov["region"].isin(["DM", "EM"])].copy()
    cov["name"] = cov["country"].map(COUNTRY)
    lines = [r"\begin{table}[!ht]", r"\centering\footnotesize\setlength{\tabcolsep}{4pt}",
             r"\caption{Coverage of the JKP factor returns by market}", r"\label{tab:coverage}",
             r"\begin{tabular}{lrllr@{\hspace{6pt}}lrllr}", r"\toprule"]
    half = r"Market & Factors & First & Last & Obs."
    lines += [half + " & " + half + r" \\", r"\midrule"]
    for reg, title in (("DM", "Developed markets"), ("EM", "Emerging markets")):
        g = cov[cov["region"] == reg].sort_values("name").reset_index(drop=True)
        lines.append(rf"\multicolumn{{10}}{{l}}{{\textit{{{title} ({len(g)})}}}} \\")
        k = (len(g) + 1) // 2
        for i in range(k):
            cells = []
            for j in (i, i + k):
                if j < len(g):
                    r = g.loc[j]
                    cells += [r["name"], str(int(r["factors"])), r["first"], r["last"], f"{int(r['obs']):,}"]
                else:
                    cells += [""] * 5
            lines.append(" & ".join(cells) + r" \\")
        lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    lines += _notes(
        "Monthly capped value-weighted factor returns of \\citet{jensen2023replication}, downloaded from "
        "jkpfactors.com. Country-factor-months in which a leg holds fewer than "
        f"{manifest['min_stocks']} stocks are dropped. ``Obs.'' counts country-factor-months after that "
        "filter. Markets are classified by the current MSCI classification.")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def forecast_slopes(preds: pd.DataFrame) -> pd.DataFrame:
    """Pooled slope of the realised deviation from the shrinkage mean on the forecast deviation.

    Descriptive only: estimated on the whole out-of-sample period, so rescaling forecasts by
    it would use future data. A slope between 0 and 1 means forecasts point the right way but
    are too large, which is how a positive Clark-West statistic can accompany a negative R2.
    """
    rows = []
    for (m, s), g in preds[preds["model"].isin(LEARNED_ORDER)].groupby(["model", "scope"]):
        x = (g["pred"] - g["shrink_mean"]).to_numpy()
        y = (g["target"] - g["shrink_mean"]).to_numpy()
        rows.append({"model": m, "scope": s, "slope": float(x @ y / (x @ x)),
                     "sd_forecast_dev_pct": 100 * float(x.std())})
    return pd.DataFrame(rows)


def r2_table(r2: pd.DataFrame, manifest: dict, slopes: pd.DataFrame) -> str:
    rows = []
    for m in LEARNED_ORDER:
        for s in SCOPE_ORDER:
            h = r2[(r2["model"] == m) & (r2["scope"] == s)]
            if not h.empty:
                rows.append(h.iloc[0])
    rules = [r2[(r2["model"] == m) & (r2["scope"] == "rule")] for m in ("fmom", "shrink_mean")]
    first, last = manifest["oos_start"], manifest.get("last_year", "")
    lines = [r"\begin{table}[!ht]", r"\centering\small\setlength{\tabcolsep}{4pt}",
             rf"\caption{{Out-of-sample $R^2$ for emerging-market factor returns, {first}--{last}}}",
             r"\label{tab:r2}", r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & \multicolumn{2}{c}{vs.\ own historical mean} & \multicolumn{2}{c}{vs.\ shrinkage mean} & & \\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}",
             r"Model & Training & $R^2_{OS}$ (\%) & CW $t$ & $R^2_{OS}$ (\%) & CW $t$ & Slope & Obs. \\", r"\midrule"]
    sl = slopes.set_index(["model", "scope"])["slope"]
    prev = None
    for r in rows:
        name = MODEL_LABEL[r["model"]] if r["model"] != prev else ""
        prev = r["model"]
        lines.append(f"{name} & {SCOPE_LABEL[r['scope']]} & {_f(r['r2_vs_hist_pct'], 3)} & {_f(r['cw_t_hist'])} & "
                     f"{_f(r['r2_vs_shrink_pct'], 3)} & {_f(r['cw_t_shrink'])} & "
                     f"{_f(sl.get((r['model'], r['scope']), np.nan))} & {int(r['obs']):,} \\\\")
    lines.append(r"\addlinespace")
    for h in rules:
        if h.empty:
            continue
        r = h.iloc[0]
        lines.append(f"{MODEL_LABEL[r['model']]} & -- & {_f(r['r2_vs_hist_pct'], 3)} & {_f(r['cw_t_hist'])} & "
                     f"{_f(r['r2_vs_shrink_pct'], 3)} & {_f(r['cw_t_shrink'])} & -- & {int(r['obs']):,} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    lines += _notes(
        "Pooled over all emerging-market country-factor-months. $R^2_{OS} = 1 - \\sum (r-\\hat r)^2 / "
        "\\sum (r-b)^2$ for benchmark $b$. CW $t$ is the Clark--West statistic: the adjusted MSPE "
        "difference is averaged across the cross-section each month and its mean tested with Newey--West "
        "standard errors (3 lags); one-sided 5\\% critical value 1.645. Training scope: EM = emerging markets "
        "only; DM only = developed markets only (the transfer test); Pooled = both. Learned models forecast "
        "the deviation from the shrinkage mean and are refitted every January. The shrinkage mean is the "
        "benchmark itself, so its own row against that benchmark is zero by construction. Slope: pooled "
        "regression slope, without intercept, of $r-\\tilde r$ on $\\hat r-\\tilde r$ over the whole "
        "out-of-sample period; a descriptive diagnostic that uses future data and is not a tradable rescaling.")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def country_table(preds: pd.DataFrame, model: str) -> tuple[str, pd.DataFrame]:
    """R^2 vs the shrinkage mean and CW t by country, EM-trained vs DM-trained, for one model."""
    out = []
    for c, g in preds[preds["model"] == model].groupby("country"):
        row = {"country": c}
        for s in ("own", "dm_only"):
            h = g[g["scope"] == s]
            y, p, b = h["target"].to_numpy(), h["pred"].to_numpy(), h["shrink_mean"].to_numpy()
            row[f"r2_{s}"] = 100 * (1 - np.sum((y - p) ** 2) / np.sum((y - b) ** 2))
            cw = pd.Series(2 * (y - b) * (p - b)).groupby(h["target_month"].to_numpy()).mean().to_numpy()
            row[f"t_{s}"] = newey_west_t(cw, 3)[0]
            row["obs"] = len(h)
        out.append(row)
    df = pd.DataFrame(out)
    df["name"] = df["country"].map(COUNTRY)
    df = df.sort_values("name").reset_index(drop=True)
    lines = [r"\begin{table}[!ht]", r"\centering\small",
             rf"\caption{{Transfer by country: {MODEL_LABEL[model].lower()} trained on emerging vs.\ developed markets}}",
             r"\label{tab:country}", r"\begin{tabular}{lrrrrr}", r"\toprule",
             r" & \multicolumn{2}{c}{EM-trained} & \multicolumn{2}{c}{DM-trained} & \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
             r"Market & $R^2_{OS}$ (\%) & CW $t$ & $R^2_{OS}$ (\%) & CW $t$ & Obs. \\", r"\midrule"]
    for _, r in df.iterrows():
        lines.append(f"{r['name']} & {_f(r['r2_own'], 3)} & {_f(r['t_own'])} & {_f(r['r2_dm_only'], 3)} & "
                     f"{_f(r['t_dm_only'])} & {int(r['obs']):,} \\\\")
    n_pos = {s: int((df[f"r2_{s}"] > 0).sum()) for s in ("own", "dm_only")}
    n_sig = {s: int((df[f"t_{s}"] > 1.645).sum()) for s in ("own", "dm_only")}
    lines += [r"\midrule",
              rf"Markets with $R^2_{{OS}}>0$ & \multicolumn{{2}}{{c}}{{{n_pos['own']} of {len(df)}}} & "
              rf"\multicolumn{{2}}{{c}}{{{n_pos['dm_only']} of {len(df)}}} & \\",
              rf"Markets with CW $t>1.645$ & \multicolumn{{2}}{{c}}{{{n_sig['own']} of {len(df)}}} & "
              rf"\multicolumn{{2}}{{c}}{{{n_sig['dm_only']} of {len(df)}}} & \\",
              r"\bottomrule", r"\end{tabular}"]
    lines += _notes(
        "$R^2_{OS}$ and Clark--West $t$ against the shrinkage mean, computed within each market on the same "
        "observations for both training scopes. Country-level tests are not adjusted for multiple comparisons.")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n", df


def portfolio_table(port: pd.DataFrame, manifest: dict) -> str:
    def label(s: str) -> str:
        if s == "static_ew":
            return "Static equal-weight", "--"
        m, sc = s.split(":")
        return MODEL_LABEL[m], SCOPE_LABEL[sc]

    order = ["static_ew"] + [f"{m}:{s}" for m in LEARNED_ORDER for s in SCOPE_ORDER] + \
            ["shrink_mean:rule", "hist_mean:rule", "fmom:rule"]
    port = port.set_index("strategy")
    lines = [r"\begin{table}[!ht]", r"\centering\small\setlength{\tabcolsep}{5pt}",
             r"\caption{Emerging-market factor-timing portfolios}", r"\label{tab:portfolios}",
             r"\begin{tabular}{llrrrrr}", r"\toprule",
             r"Strategy & Training & Mean (\%) & Vol.\ (\%) & SR gross & SR net & Turnover \\", r"\midrule"]
    prev = None
    for s in order:
        if s not in port.index:
            continue
        r = port.loc[s]
        name, sc = label(s)
        if s == "fmom:rule":
            name = "Factor momentum (sign)"
        if s == "shrink_mean:rule":
            lines.append(r"\addlinespace")
        if sc == "EM" and prev is not None:
            lines.append(r"\addlinespace[2pt]")
        shown = "" if (name == prev and sc != "--") else name
        prev = name
        name = shown
        lines.append(f"{name} & {sc} & {_f(r['mean_ann_pct'])} & {_f(r['vol_ann_pct'])} & "
                     f"{_f(r['sharpe_gross'])} & {_f(r['sharpe_net'])} & {_f(r['turnover_monthly'])} \\\\")
        if s == "static_ew":
            lines.append(r"\addlinespace")
            prev = None
    lines += [r"\bottomrule", r"\end{tabular}"]
    lines += _notes(
        "Within each emerging market and month, the timing portfolio holds each factor in proportion to its "
        "forecast, scaled to unit gross exposure; the static portfolio holds every available factor equally. "
        "Country portfolios are averaged with equal weights. Mean and volatility are annualized, gross of "
        f"timing costs. Net Sharpe ratios deduct {manifest['cost_bps']:.0f} basis points per unit of monthly "
        "turnover; factor returns are already gross of their own rebalancing costs. The factor-momentum rule "
        "holds each factor long or short by the sign of its trailing 12-month mean.")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


OTHER_NAMES = {"arg": "Argentina", "jor": "Jordan", "mar": "Morocco", "pak": "Pakistan", "rus": "Russia",
               "ven": "Venezuela"}


def classification_table(path: Path) -> str:
    """Appendix table of the reclassification events in config/market_history.yaml."""
    import yaml

    ev = pd.DataFrame(yaml.safe_load(path.read_text())["events"]).sort_values(["from_month", "country"])
    names = {**COUNTRY, **OTHER_NAMES}
    lab = {"DM": "Developed", "EM": "Emerging", "OTHER": "Frontier/standalone"}
    lines = [r"\begin{table}[!ht]", r"\centering\footnotesize\setlength{\tabcolsep}{4pt}",
             r"\caption{MSCI reclassifications used for the time-varying classification}",
             r"\label{tab:classification}", r"\begin{tabular}{llll}", r"\toprule",
             r"Market & In force from & New class & MSCI event \\", r"\midrule"]
    for _, e in ev.iterrows():
        note = e["note"].replace("->", r"$\to$")
        lines.append(f"{names[e['country']]} & {e['from_month']} & {lab[e['region']]} & {note} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    lines += _notes(
        "Each market takes the new class from the first full month after MSCI implemented the change; before "
        "its first event a market has its prior class, and markets without events keep their current class. "
        "First inclusion in the MSCI indexes and partial-inclusion steps are not modelled. Sources: MSCI's "
        "list of market reclassifications and MSCI announcements, cited in \\texttt{config/market\\_history.yaml}.")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def strategy_label(s: str) -> str:
    if s == "static_ew":
        return "Static equal-weight"
    m, sc = s.split(":")
    return MODEL_LABEL[m] if sc == "rule" else f"{MODEL_LABEL[m]} ({SCOPE_LABEL[sc]}-trained)"


def cumulative_figure(monthly: pd.DataFrame, port: pd.DataFrame, path: Path, cost_bps: float) -> None:
    """Same selection rule as the run report (static + the three best net Sharpe ratios), readable labels."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    best = port[port["strategy"] != "static_ew"].sort_values("sharpe_net", ascending=False)["strategy"].head(3)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for st in ["static_ew", *best]:
        g = monthly[monthly["strategy"] == st].sort_values("target_month")
        x = pd.PeriodIndex(g["target_month"].astype(str), freq="M").to_timestamp()
        ax.plot(x, 100 * np.cumsum(g["net"].to_numpy()), label=strategy_label(st), linewidth=1.4)
    ax.axhline(0, color="0.6", linewidth=0.8)
    ax.set_ylabel(f"Cumulative net return, % (net of {cost_bps:.0f} bp per unit turnover)", fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="reports/jkp_em")
    ap.add_argument("--out", default="paper/tables")
    ap.add_argument("--country-model", default=None,
                    help="default: the learned model with the highest R2 vs the shrinkage mean (same rule as the CLI)")
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((run / "run_manifest.json").read_text())
    if manifest.get("provenance") != "JKP":
        raise SystemExit(f"{run} is not a real-data run (provenance={manifest.get('provenance')})")
    preds = pd.read_parquet(run / "predictions.parquet")
    manifest["last_year"] = int(preds["target_month"].max().year) if hasattr(preds["target_month"].iloc[0], "year") \
        else int(str(preds["target_month"].max())[:4])

    (out / "coverage.tex").write_text(coverage_table(pd.read_csv(run / "coverage.csv"), manifest))
    slopes = forecast_slopes(preds)
    slopes.to_csv(run / "forecast_slopes.csv", index=False)
    (out / "r2_oos.tex").write_text(r2_table(pd.read_csv(run / "r2_oos.csv"), manifest, slopes))

    r2 = pd.read_csv(run / "r2_oos.csv")
    model = a.country_model or r2[r2["model"].isin(LEARNED_ORDER)].iloc[0]["model"]
    tex, by_country = country_table(preds, model)
    (out / "transfer_by_country.tex").write_text(tex)
    by_country.to_csv(run / f"transfer_by_country_{model}.csv", index=False)
    (out / "portfolios.tex").write_text(portfolio_table(pd.read_csv(run / "portfolios.csv"), manifest))
    (out / "market_history.tex").write_text(
        classification_table(Path(__file__).resolve().parents[1] / "config" / "market_history.yaml"))
    fig_dir = out.parent / "figures"
    fig_dir.mkdir(exist_ok=True)
    cumulative_figure(pd.read_csv(run / "portfolio_monthly.csv"), pd.read_csv(run / "portfolios.csv"),
                      fig_dir / "cumulative_net.png", manifest["cost_bps"])
    print(f"wrote tables to {out} and figure to {fig_dir}")


if __name__ == "__main__":
    main()
