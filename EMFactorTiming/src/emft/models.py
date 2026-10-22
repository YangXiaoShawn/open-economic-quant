"""Forecasting models.

Learned models share one interface (fit on a training panel, predict on a test
panel) and fold-local preprocessing: feature scaling and target winsorisation use
training rows only. Hyperparameters are fixed in advance rather than tuned on the
evaluation sample.

Three non-learned rules serve as benchmarks:
  hist_mean    expanding mean of the factor's own history (Campbell-Thompson benchmark)
  shrink_mean  own expanding mean shrunk toward the regional mean of the same factor
  fmom         trailing 12-month mean, i.e. factor momentum
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import ElasticNet, LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURES

LEARNED = ("ols", "enet", "gbrt", "nn")
RULES = ("hist_mean", "shrink_mean", "fmom")
# Real-time forecast shrinkage: "<model>_rs" scales the model's forecast deviation from
# the shrinkage mean by a slope estimated inside the training window (see Forecaster.fit).
SCALED = tuple(f"{m}_rs" for m in LEARNED)
RS_VALIDATION_MONTHS = 36


def _winsorise(y: np.ndarray, lo: float = 0.005, hi: float = 0.995) -> np.ndarray:
    a, b = np.quantile(y, [lo, hi])
    return np.clip(y, a, b)


@dataclass
class Forecaster:
    name: str
    seed: int = 0
    max_train_rows: int = 400_000  # subsample very large panels for the tree/NN fits
    scale: float = 1.0  # multiplies the forecast deviation; estimated in fit for "_rs" models
    features: tuple[str, ...] = tuple(FEATURES)
    _models: list = field(default_factory=list, repr=False)

    def fit(self, train: pd.DataFrame) -> "Forecaster":
        if self.name in RULES:
            return self
        if self.name in SCALED:
            return self._fit_scaled(train)
        rng = np.random.default_rng(self.seed)
        cap = self.max_train_rows if self.name == "gbrt" else self.max_train_rows // 3
        if len(train) > cap and self.name in ("gbrt", "nn"):
            train = train.iloc[rng.choice(len(train), cap, replace=False)]
        X = train[list(self.features)].to_numpy()
        y = _winsorise(train["target"].to_numpy())
        # Learn only the deviation from the shrunk historical mean, so a learned
        # model is credited for forecasting time variation, not for re-estimating
        # the unconditional premium. The anchor is added back at prediction time.
        y = y - train["shrink_mean"].to_numpy()
        self._models = [self._make(s).fit(X, y) for s in self._seeds()]
        return self

    def _fit_scaled(self, train: pd.DataFrame) -> "Forecaster":
        """Fit the base model, then shrink its forecasts by a slope estimated without future data.

        The base model is fitted on training rows whose target month precedes the last
        RS_VALIDATION_MONTHS months of the window and predicts those months; the slope of
        the realised deviation from the shrinkage mean on the forecast deviation, clipped
        to [0, 1], is the scale. The base model is then refitted on the whole window.
        With no usable validation split the scale stays 1 (no shrinkage).
        """
        base = self.name[: -len("_rs")]
        cut = train["target_month"].max() - (RS_VALIDATION_MONTHS - 1)
        inner, val = train[train["target_month"] < cut], train[train["target_month"] >= cut]
        self.scale = 1.0
        if len(inner) and len(val):
            x = self._base(base).fit(inner).deviation(val)
            y = (val["target"] - val["shrink_mean"]).to_numpy()
            if x @ x > 0:
                self.scale = float(np.clip(x @ y / (x @ x), 0.0, 1.0))
        self._models = self._base(base).fit(train)._models
        return self

    def _base(self, name: str) -> "Forecaster":
        return Forecaster(name, self.seed, self.max_train_rows, features=self.features)

    def deviation(self, test: pd.DataFrame) -> np.ndarray:
        """Forecast of the return in excess of the shrinkage mean (learned models only)."""
        X = test[list(self.features)].to_numpy()
        return np.mean([m.predict(X) for m in self._models], axis=0)

    def predict(self, test: pd.DataFrame) -> np.ndarray:
        if self.name == "hist_mean":
            return test["hist_mean"].to_numpy()
        if self.name == "shrink_mean":
            return test["shrink_mean"].to_numpy()
        if self.name == "fmom":
            return test["own_m12"].to_numpy()
        return test["shrink_mean"].to_numpy() + self.scale * self.deviation(test)

    def _seeds(self) -> list[int]:
        # The neural net is an ensemble over initialisations (as in Gu, Kelly and Xiu 2020).
        return [self.seed + k for k in range(3)] if self.name == "nn" else [self.seed]

    def _make(self, seed: int):
        if self.name == "ols":
            return make_pipeline(StandardScaler(), LinearRegression())
        if self.name == "enet":
            return make_pipeline(StandardScaler(), ElasticNet(alpha=1e-4, l1_ratio=0.5, max_iter=5000))
        if self.name == "gbrt":
            return HistGradientBoostingRegressor(
                max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                min_samples_leaf=200, early_stopping=False, random_state=seed,
            )
        if self.name == "nn":
            return make_pipeline(
                StandardScaler(),
                MLPRegressor(
                    hidden_layer_sizes=(32, 16), alpha=1e-3, learning_rate_init=1e-3,
                    max_iter=200, early_stopping=True, n_iter_no_change=10, random_state=seed,
                ),
            )
        raise ValueError(f"Unknown model {self.name!r}")
