"""Expanding-window, annually refitted out-of-sample backtest.

For each test year Y, models are trained on rows whose TARGET month falls before
January of Y (so every training label was already realised) and evaluated on rows
whose target month falls in Y.

Training scopes, all evaluated on the same test region:
  own       train on the test region only (EM -> EM)
  dm_only   train on developed markets only, test on EM (the transfer test)
  pooled    train on DM and EM together
"""

from __future__ import annotations

import logging

import pandas as pd

from .features import FEATURES
from .models import LEARNED, RULES, Forecaster

log = logging.getLogger(__name__)

SCOPES = ("own", "dm_only", "pooled")


def run_backtest(
    data: pd.DataFrame,
    test_region: str = "EM",
    models: tuple[str, ...] = LEARNED + RULES,
    scopes: tuple[str, ...] = SCOPES,
    oos_start: int = 2000,
    min_train_months: int = 120,
    seed: int = 0,
    features: tuple[str, ...] = tuple(FEATURES),
) -> pd.DataFrame:
    """Return one row per (test observation, model, scope) with the forecast."""
    last_year = int(data["target_month"].max().year)
    out: list[pd.DataFrame] = []
    first_month = data["target_month"].min()

    for year in range(oos_start, last_year + 1):
        cutoff = pd.Period(f"{year}-01", freq="M")
        if (cutoff - first_month).n < min_train_months:
            continue
        test = data[(data["target_month"].dt.year == year) & (data["region"] == test_region)]
        if test.empty:
            continue
        past = data[data["target_month"] < cutoff]
        train_sets = {
            "own": past[past["region"] == test_region],
            "dm_only": past[past["region"] == "DM"],
            "pooled": past[past["region"].isin(["DM", "EM"])],
        }
        for scope in scopes:
            train = train_sets[scope]
            if train.empty:
                continue
            for name in models:
                if name in RULES and scope != "own":
                    continue  # rules do not train, one copy is enough
                f = Forecaster(name, seed=seed, features=features).fit(train)
                pred = test[["month", "target_month", "country", "factor", "region", "target", "hist_mean", "shrink_mean", "own_m12"]].copy()
                pred["model"] = name
                pred["scope"] = scope if name not in RULES else "rule"
                pred["pred"] = f.predict(test)
                pred["scale"] = f.scale
                out.append(pred)
        log.info("year %d: trained on %d rows, tested on %d", year, len(train_sets["own"]), len(test))

    if not out:
        raise ValueError("No out-of-sample years: check oos_start and sample length")
    return pd.concat(out, ignore_index=True)
