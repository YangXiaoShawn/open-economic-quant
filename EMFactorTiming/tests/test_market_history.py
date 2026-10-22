"""Time-varying market classification: region lookup, equivalence with the static path, no leakage."""

import numpy as np
import pandas as pd

from emft.data import Markets, apply_market_history, load_markets, synthetic_panel
from emft.features import FEATURES, _regional_terms, build_features


def _month(s: str) -> pd.Period:
    return pd.Period(s, freq="M")


def test_regions_follow_msci_events():
    months = pd.period_range("1995-01", "2025-12", freq="M")
    panel = pd.DataFrame([(c, m) for c in ("grc", "qat", "rus", "bra") for m in months], columns=["country", "month"])
    panel["region"] = panel["country"].map(load_markets().region)
    out = apply_market_history(panel).set_index(["country", "month"])["region"]
    assert out[("grc", _month("2001-05"))] == "EM" and out[("grc", _month("2001-06"))] == "DM"
    assert out[("grc", _month("2013-11"))] == "DM" and out[("grc", _month("2013-12"))] == "EM"
    assert out[("qat", _month("2014-05"))] == "OTHER" and out[("qat", _month("2014-06"))] == "EM"
    assert out[("rus", _month("2022-03"))] == "EM" and out[("rus", _month("2022-04"))] == "OTHER"
    assert (out.loc["bra"] == "EM").all()  # no event: static class throughout


def test_general_path_matches_static_path_when_regions_are_constant():
    panel, _ = synthetic_panel(n_dm=3, n_em=3, n_factors=4, n_months=120, seed=2)
    static = build_features(panel).set_index(["month", "country", "factor"])
    wide = panel.pivot_table(index="month", columns=["country", "factor"], values="ret")
    R = wide.reindex(pd.period_range(wide.index.min(), wide.index.max(), freq="M", name="month"))
    m12 = R.rolling(12, min_periods=12).mean()
    region = panel.drop_duplicates("country").set_index("country")["region"]
    reg = pd.DataFrame({c: [region[c[0]]] * len(R) for c in R.columns}, index=R.index)
    reg.columns = R.columns
    dm_m12, pooled = _regional_terms(R, m12, reg)
    got = dm_m12.stack(["country", "factor"], future_stack=True)
    want = static["dm_m12"].reorder_levels(got.index.names)
    np.testing.assert_allclose(got.reindex(want.index).to_numpy(), want.to_numpy(), rtol=1e-12, equal_nan=True)
    n_own = R.notna().cumsum()
    hist = R.expanding(min_periods=24).mean()
    shrink = ((n_own * hist + 120 * pooled) / (n_own + 120)).where(hist.notna())
    got_s = shrink.stack(["country", "factor"], future_stack=True).reindex(want.index)
    np.testing.assert_allclose(got_s.to_numpy(), static["shrink_mean"].to_numpy(), rtol=1e-12, equal_nan=True)


def test_time_varying_features_do_not_use_future_returns():
    panel, _ = synthetic_panel(n_dm=3, n_em=3, n_factors=4, n_months=120, seed=1)
    # e00 moves from EM to DM in 1995-01, d00 from DM to EM in 1996-01
    panel.loc[(panel["country"] == "e00") & (panel["month"] >= _month("1995-01")), "region"] = "DM"
    panel.loc[(panel["country"] == "d00") & (panel["month"] >= _month("1996-01")), "region"] = "EM"
    cut = _month("1998-06")
    base = build_features(panel).set_index(["month", "country", "factor"])
    assert set(base.loc[(_month("1994-12"), "e00"), "region"]) == {"EM"}
    assert set(base.loc[(_month("1995-01"), "e00"), "region"]) == {"DM"}

    shocked = panel.copy()
    after = shocked["month"] > cut
    shocked.loc[after, "ret"] += np.random.default_rng(9).normal(0, 0.5, after.sum())
    moved = build_features(shocked).set_index(["month", "country", "factor"])
    past = base.index.get_level_values("month") <= cut
    cols = FEATURES + ["hist_mean", "shrink_mean"]
    pd.testing.assert_frame_equal(base.loc[past, cols], moved.loc[past, cols])


def test_history_must_end_in_the_static_class(tmp_path):
    bad = tmp_path / "h.yaml"
    bad.write_text("events:\n  - {country: bra, from_month: 2000-01, was: EM, region: DM}\n")
    panel = pd.DataFrame({"country": ["bra"], "month": [_month("2001-01")], "region": ["EM"]})
    try:
        apply_market_history(panel, Markets(frozenset(), frozenset({"bra"})), bad)
    except ValueError as e:
        assert "differs from markets.yaml" in str(e)
    else:
        raise AssertionError("inconsistent history accepted")
