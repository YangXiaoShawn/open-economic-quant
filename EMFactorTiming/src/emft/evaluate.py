"""Statistical and economic evaluation of out-of-sample forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def newey_west_t(x: np.ndarray, lags: int = 3) -> tuple[float, float]:
    """t-statistic and one-sided p-value (mean > 0) with Newey-West standard errors."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 10:
        return np.nan, np.nan
    d = x - x.mean()
    s = d @ d / n
    for k in range(1, min(lags, n - 1) + 1):
        w = 1 - k / (lags + 1)
        s += 2 * w * (d[k:] @ d[:-k]) / n
    se = np.sqrt(s / n)
    t = x.mean() / se if se > 0 else np.nan
    return t, 1 - stats.norm.cdf(t)


def r2_table(preds: pd.DataFrame, lags: int = 3) -> pd.DataFrame:
    """Pooled out-of-sample R^2 against two benchmarks.

    R2_OS = 1 - sum (y - yhat)^2 / sum (y - bench)^2   (Campbell and Thompson 2008)

    hist  = the factor's own expanding mean (the standard benchmark)
    shrink = that mean shrunk toward the regional mean of the same factor. A model
             can beat `hist` merely by pooling noisy means across countries; only
             beating `shrink` is evidence of time variation being forecast.

    Significance: Clark-West (2007) adjusted MSPE difference, 2 (y - b)(yhat - b),
    averaged across the cross-section each month; the monthly series is tested
    with Newey-West errors, so correlation within a month does not inflate t.
    """
    rows = []
    for (model, scope), g in preds.groupby(["model", "scope"]):
        y, p = g["target"].to_numpy(), g["pred"].to_numpy()
        row = {"model": model, "scope": scope}
        for tag, col in (("hist", "hist_mean"), ("shrink", "shrink_mean")):
            b = g[col].to_numpy()
            row[f"r2_vs_{tag}_pct"] = 100 * (1 - np.sum((y - p) ** 2) / np.sum((y - b) ** 2))
            cw = 2 * (y - b) * (p - b)
            monthly = pd.Series(cw).groupby(g["target_month"].to_numpy()).mean().to_numpy()
            row[f"cw_t_{tag}"] = newey_west_t(monthly, lags)[0] if np.any(p != b) else np.nan
        row["obs"], row["months"] = len(g), g["target_month"].nunique()
        rows.append(row)
    return pd.DataFrame(rows).sort_values("r2_vs_shrink_pct", ascending=False).reset_index(drop=True)


def r2_by_country(preds: pd.DataFrame, model: str, scope: str) -> pd.DataFrame:
    g = preds[(preds["model"] == model) & (preds["scope"] == scope)]
    rows = []
    for c, h in g.groupby("country"):
        y, p = h["target"].to_numpy(), h["pred"].to_numpy()
        r2 = {f"r2_vs_{t}_pct": 100 * (1 - np.sum((y - p) ** 2) / np.sum((y - h[c2].to_numpy()) ** 2))
              for t, c2 in (("hist", "hist_mean"), ("shrink", "shrink_mean"))}
        rows.append({"country": c, **r2, "obs": len(h)})
    return pd.DataFrame(rows).sort_values("r2_vs_shrink_pct", ascending=False).reset_index(drop=True)


def timing_weights(g: pd.DataFrame, how: str) -> np.ndarray:
    """Weights across factors within one country-month; gross exposure sums to 1."""
    n = len(g)
    if how == "static":
        return np.full(n, 1.0 / n)
    if how == "sign":
        s = np.sign(g["pred"].to_numpy())
        return s / max(np.abs(s).sum(), 1)
    p = g["pred"].to_numpy()
    tot = np.abs(p).sum()
    return p / tot if tot > 0 else np.full(n, 1.0 / n)


def portfolio_returns(preds: pd.DataFrame, cost_bps: float = 0.0) -> pd.DataFrame:
    """Monthly returns of timing portfolios, averaged equally across countries.

    For each model/scope the country portfolio holds each factor in proportion to
    its forecast (gross exposure 1). The static benchmark holds every factor
    equally. Turnover is sum |w_t - w_{t-1}| within a country; the cost applies
    only to these timing trades -- the factor returns themselves are gross of the
    costs of their own monthly rebalancing.
    """
    out = []
    static_done = False
    for (model, scope), g in preds.groupby(["model", "scope"]):
        variants = [("proportional", "prop")]
        if model == "fmom":
            variants = [("sign", "sign")]
        if not static_done:
            variants.append(("static", "static"))
        for label, how in variants:
            recs = []
            for (country, tm), h in g.groupby(["country", "target_month"], sort=True):
                w = timing_weights(h, how)
                recs.append((country, tm, h["factor"].to_numpy(), w, float(w @ h["target"].to_numpy())))
            df = pd.DataFrame(recs, columns=["country", "target_month", "factors", "w", "gross"])
            df["turnover"] = 0.0
            for country, h in df.groupby("country"):
                prev = None
                for i, row in h.iterrows():
                    cur = pd.Series(row["w"], index=row["factors"])
                    if prev is not None:
                        df.at[i, "turnover"] = cur.sub(prev, fill_value=0).abs().sum()
                    prev = cur
            df["net"] = df["gross"] - cost_bps / 1e4 * df["turnover"]
            monthly = df.groupby("target_month")[["gross", "net", "turnover"]].mean().reset_index()
            name = "static_ew" if how == "static" else f"{model}:{scope}"
            monthly["strategy"] = name
            out.append(monthly)
            if how == "static":
                static_done = True
    return pd.concat(out, ignore_index=True)


def portfolio_table(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s, g in monthly.groupby("strategy"):
        gr, nt = g["gross"].to_numpy(), g["net"].to_numpy()
        rows.append(
            {
                "strategy": s,
                "mean_ann_pct": 1200 * gr.mean(),
                "vol_ann_pct": 100 * np.sqrt(12) * gr.std(ddof=1),
                "sharpe_gross": np.sqrt(12) * gr.mean() / gr.std(ddof=1),
                "sharpe_net": np.sqrt(12) * nt.mean() / nt.std(ddof=1),
                "turnover_monthly": g["turnover"].mean(),
                "months": len(g),
            }
        )
    return pd.DataFrame(rows).sort_values("sharpe_net", ascending=False).reset_index(drop=True)
