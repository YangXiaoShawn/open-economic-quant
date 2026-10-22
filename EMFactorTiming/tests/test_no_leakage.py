"""Features dated t must not change when returns after t change."""

import numpy as np
import pandas as pd

from emft.data import synthetic_panel
from emft.features import FEATURES, build_features


def test_future_returns_do_not_move_past_features():
    panel, _ = synthetic_panel(n_dm=3, n_em=3, n_factors=4, n_months=120, seed=1)
    cut = pd.Period("1998-06", freq="M")
    base = build_features(panel).set_index(["month", "country", "factor"])

    shocked = panel.copy()
    after = shocked["month"] > cut
    shocked.loc[after, "ret"] = shocked.loc[after, "ret"] + np.random.default_rng(9).normal(0, 0.5, after.sum())
    moved = build_features(shocked).set_index(["month", "country", "factor"])

    past = base.index.get_level_values("month") <= cut
    cols = FEATURES + ["hist_mean"]
    pd.testing.assert_frame_equal(base.loc[past, cols], moved.loc[past, cols])

    # Targets are next-month returns: those dated before the cut stay fixed,
    # the target dated exactly at the cut is the first shocked month.
    before = base.index.get_level_values("month") < cut
    pd.testing.assert_series_equal(base.loc[before, "target"], moved.loc[before, "target"])
    at_cut = base.index.get_level_values("month") == cut
    assert not np.allclose(base.loc[at_cut, "target"], moved.loc[at_cut, "target"])
