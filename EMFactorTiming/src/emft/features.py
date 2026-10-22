"""Point-in-time predictors for next-month factor returns.

Every feature dated month t is a function of returns observed in months <= t only.
The target is the return realised in month t+1. `tests/test_no_leakage.py` checks
this by perturbing future returns and confirming no feature changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = [
    "own_r1",   # last month's factor return
    "own_m3",   # trailing 3-month mean
    "own_m12",  # trailing 12-month mean (factor momentum)
    "own_m36",  # trailing 36-month mean (slow-moving premium proxy)
    "own_v12",  # trailing 12-month volatility
    "cty_m12",  # same country, average 12-month mean across all factors
    "dm_m12",   # same factor, average 12-month mean across developed markets
]


def _regional_terms(R: pd.DataFrame, m12: pd.DataFrame, reg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """dm_m12 and the pooled regional mean when region membership can change over time.

    reg has R's shape and holds each series' region in each month. The DM average at t
    uses the series classified DM at t; the pooled mean for region g at t averages every
    past country-month that was in g when it was observed, and a series uses the pooled
    mean of the region it belongs to at t.
    """
    factors = R.columns.get_level_values("factor")
    dm = m12.where(reg == "DM").T.groupby(level="factor").mean().T
    dm_m12 = dm.reindex(columns=factors).set_axis(R.columns, axis=1)
    pooled = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
    for g in pd.unique(reg.to_numpy().ravel()):
        if not isinstance(g, str):
            continue
        member = reg == g
        sub = R.where(member)
        s = sub.T.groupby(level="factor").sum(min_count=1).T.fillna(0).cumsum()
        n = sub.notna().T.groupby(level="factor").sum().T.cumsum()
        pm = (s / n.where(n > 0)).reindex(columns=factors).set_axis(R.columns, axis=1)
        pooled = pooled.where(~member, pm)
    return dm_m12, pooled


def build_features(panel: pd.DataFrame, hist_min: int = 24, kappa: float = 120.0) -> pd.DataFrame:
    """Long table: month, country, factor, region, FEATURES, hist_mean, shrink_mean, target, target_month."""
    wide = panel.pivot_table(index="month", columns=["country", "factor"], values="ret")
    full = pd.period_range(wide.index.min(), wide.index.max(), freq="M")
    R = wide.reindex(full)  # explicit gaps stay NaN; rolling windows do not skip them

    feats: dict[str, pd.DataFrame] = {
        "own_r1": R,
        "own_m3": R.rolling(3, min_periods=3).mean(),
        "own_m12": R.rolling(12, min_periods=12).mean(),
        "own_m36": R.rolling(36, min_periods=24).mean(),
        "own_v12": R.rolling(12, min_periods=12).std(),
    }

    m12 = feats["own_m12"]
    cty = m12.T.groupby(level="country").mean().T  # month x country
    feats["cty_m12"] = cty.reindex(columns=m12.columns.get_level_values("country")).set_axis(m12.columns, axis=1)

    hist_mean = R.expanding(min_periods=hist_min).mean()
    n_own = R.notna().cumsum()

    # Shrinkage benchmark: each series' own expanding mean pulled toward the
    # expanding mean of the same factor pooled over all countries in its region,
    # with weight n / (n + kappa). Beating the own historical mean can reflect
    # nothing more than this kind of cross-sectional pooling; beating the shrunk
    # mean is evidence of timing.
    region = panel.drop_duplicates("country").set_index("country")["region"]
    time_varying = bool((panel.groupby("country")["region"].nunique() > 1).any())
    reg = None
    if time_varying:
        # month x country region, carried across months without data, then spread to series
        reg_c = (panel.drop_duplicates(["month", "country"]).pivot(index="month", columns="country", values="region")
                 .reindex(full).ffill().bfill())
        reg = reg_c.reindex(columns=R.columns.get_level_values("country")).set_axis(R.columns, axis=1)
        feats["dm_m12"], pooled = _regional_terms(R, m12, reg)
    else:
        dm_cols = [c for c in m12.columns if region.get(c[0]) == "DM"]
        if dm_cols:
            dm = m12[dm_cols].T.groupby(level="factor").mean().T  # month x factor
            feats["dm_m12"] = dm.reindex(columns=m12.columns.get_level_values("factor")).set_axis(m12.columns, axis=1)
        else:
            feats["dm_m12"] = pd.DataFrame(np.nan, index=m12.index, columns=m12.columns)
        pooled = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
        for g in region.dropna().unique():
            cols = [c for c in R.columns if region.get(c[0]) == g]
            sub = R[cols]
            s = sub.T.groupby(level="factor").sum(min_count=1).T.fillna(0).cumsum()
            n = sub.notna().T.groupby(level="factor").sum().T.cumsum()
            pm = (s / n.where(n > 0)).reindex(columns=sub.columns.get_level_values("factor"))
            pooled[cols] = pm.to_numpy()
    shrink_mean = (n_own * hist_mean + kappa * pooled) / (n_own + kappa)
    shrink_mean = shrink_mean.where(hist_mean.notna())

    target = R.shift(-1)

    def stack(frame: pd.DataFrame, name: str) -> pd.Series:
        s = frame.stack(["country", "factor"], future_stack=True)
        s.name = name
        return s

    out = pd.concat(
        [stack(feats[k], k) for k in FEATURES]
        + [stack(hist_mean, "hist_mean"), stack(shrink_mean, "shrink_mean"), stack(target, "target")],
        axis=1,
    )
    out.index.names = ["month", "country", "factor"]
    out = out.reset_index()
    out["region"] = stack(reg, "region").to_numpy() if time_varying else out["country"].map(region)
    out["target_month"] = out["month"] + 1
    return out


def model_ready(features: pd.DataFrame, extra: tuple[str, ...] = ()) -> pd.DataFrame:
    """Rows with a realised target, a benchmark and every feature (and extra column) observed."""
    need = FEATURES + list(extra) + ["hist_mean", "shrink_mean", "target"]
    return features.dropna(subset=need).reset_index(drop=True)
