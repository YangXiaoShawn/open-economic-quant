"""The pipeline must find predictability that exists and not invent it where it does not."""

from emft.backtest import run_backtest
from emft.data import synthetic_panel
from emft.evaluate import r2_table
from emft.features import build_features, model_ready


def _table(signal_sd, scopes=("own",), seed=3, models=("ols", "hist_mean", "shrink_mean")):
    panel, _ = synthetic_panel(n_dm=6, n_em=6, n_factors=12, n_months=300,
                               signal_sd=signal_sd, seed=seed)
    data = model_ready(build_features(panel))
    preds = run_backtest(data, models=models, scopes=scopes, oos_start=2005)
    return r2_table(preds).set_index(["model", "scope"])


def test_detects_injected_predictability():
    ols = _table(signal_sd=0.008).loc[("ols", "own")]
    assert ols["r2_vs_shrink_pct"] > 0.3
    assert ols["cw_t_shrink"] > 2.0


def test_no_false_discovery_without_signal():
    t = _table(signal_sd=0.0)
    assert t.loc[("ols", "own"), "r2_vs_shrink_pct"] < 0.3
    # each benchmark compared with itself is exactly zero by construction
    assert abs(t.loc[("hist_mean", "rule"), "r2_vs_hist_pct"]) < 1e-9
    assert abs(t.loc[("shrink_mean", "rule"), "r2_vs_shrink_pct"]) < 1e-9


def test_real_time_forecast_shrinkage_is_bounded_and_anchored():
    panel, _ = synthetic_panel(n_dm=4, n_em=4, n_factors=8, n_months=240, signal_sd=0.004, seed=5)
    data = model_ready(build_features(panel))
    preds = run_backtest(data, models=("ols", "ols_rs"), scopes=("own",), oos_start=2005)
    rs, base = preds[preds["model"] == "ols_rs"], preds[preds["model"] == "ols"]
    assert rs["scale"].between(0, 1).all() and (base["scale"] == 1).all()
    # same fitted model, deviation scaled by the year's slope estimated inside the training window
    dev_rs = (rs["pred"] - rs["shrink_mean"]).to_numpy()
    dev = (base["pred"] - base["shrink_mean"]).to_numpy()
    assert abs(dev_rs - rs["scale"].to_numpy() * dev).max() < 1e-12


def test_developed_market_training_transfers_when_premia_are_shared():
    t = _table(signal_sd=0.008, scopes=("dm_only",), models=("ols",))
    assert t.loc[("ols", "dm_only"), "r2_vs_shrink_pct"] > 0.3
