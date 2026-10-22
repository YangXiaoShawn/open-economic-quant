"""Pure-Python and NumPy-compatible cross-sectional factor evaluation primitives."""
from __future__ import annotations

import math
from typing import Sequence


def _ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def cross_sectional_rank_ic(scores: Sequence[float], forward_returns: Sequence[float]) -> float:
    if len(scores) != len(forward_returns) or len(scores) < 2:
        raise ValueError("scores and forward_returns must have matching length >= 2")
    rx = _ranks(scores)
    ry = _ranks(forward_returns)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0.0 or deny == 0.0:
        return 0.0
    return num / (denx * deny)


def residualize_quadratic(y: Sequence[float], p: Sequence[float]) -> list[float]:
    """Residualize forward return y on [1, p, p^2] via ordinary least squares."""
    n = len(y)
    if n != len(p) or n < 4:
        raise ValueError("y and p must have matching length >= 4")
    x_rows = [(1.0, float(pi), float(pi) ** 2) for pi in p]
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    for row, yi in zip(x_rows, y):
        for r in range(3):
            xty[r] += row[r] * float(yi)
            for c in range(3):
                xtx[r][c] += row[r] * row[c]
    aug = [xtx[r][:] + [xty[r]] for r in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        if abs(div) < 1e-12:
            return [float(yi) for yi in y]
        for j in range(col, 4):
            aug[col][j] /= div
        for r in range(3):
            if r != col:
                factor = aug[r][col]
                for j in range(col, 4):
                    aug[r][j] -= factor * aug[col][j]
    b0, b1, b2 = aug[0][3], aug[1][3], aug[2][3]
    return [float(yi) - (b0 + b1 * float(pi) + b2 * (float(pi) ** 2)) for yi, pi in zip(y, p)]


def newey_west_tstat(series: Sequence[float], max_lag: int = 6) -> float:
    n = len(series)
    if n < 3:
        return 0.0
    mean = sum(series) / n
    centered = [float(x) - mean for x in series]
    gamma0 = sum(c * c for c in centered) / n
    var_hat = gamma0
    for lag in range(1, min(max_lag, n - 1) + 1):
        weight = 1.0 - lag / (max_lag + 1.0)
        cov = sum(centered[t] * centered[t - lag] for t in range(lag, n)) / n
        var_hat += 2.0 * weight * cov
    if var_hat <= 0.0:
        return 0.0
    se = math.sqrt(var_hat / n)
    return mean / se


def turnover_penalized_net_return(gross_return: float, turnover: float, cost_bps: float) -> float:
    return float(gross_return) - float(turnover) * (float(cost_bps) / 10_000.0)


def quantile_long_short_spread(
    scores: Sequence[float],
    forward_returns: Sequence[float],
    n_quantiles: int = 5,
) -> float:
    """Compute top-quantile minus bottom-quantile mean forward return."""
    n = len(scores)
    if n != len(forward_returns) or n < n_quantiles or n_quantiles < 2:
        raise ValueError("Invalid inputs for quantile_long_short_spread")
    paired = sorted(zip(scores, forward_returns), key=lambda item: item[0])
    bucket_size = max(1, n // n_quantiles)
    bottom = [r for _, r in paired[:bucket_size]]
    top = [r for _, r in paired[-bucket_size:]]
    return (sum(top) / len(top)) - (sum(bottom) / len(bottom))


def benjamini_hochberg_fdr(p_values: Sequence[float]) -> list[float]:
    """Compute Benjamini-Hochberg FDR-adjusted q-values preserving input order."""
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda item: float(item[1]))
    q_values = [0.0] * m
    prev_q = 1.0
    for rank_rev in range(m - 1, -1, -1):
        orig_idx, p_val = indexed[rank_rev]
        rank = rank_rev + 1
        raw_q = min(1.0, float(p_val) * m / rank)
        prev_q = min(prev_q, raw_q)
        q_values[orig_idx] = prev_q
    return q_values


def volatility_target_weights(
    returns: Sequence[float],
    target_vol: float = 0.15,
    lookback: int = 20,
    max_leverage: float = 1.5,
    annualization: float = 365.0,
) -> list[float]:
    """Compute causal (lagged) volatility-targeted position weights."""
    weights: list[float] = []
    for t in range(len(returns)):
        if t < 2:
            weights.append(1.0)
            continue
        start = max(0, t - lookback)
        window = [float(x) for x in returns[start:t]]
        mean = sum(window) / len(window)
        var = sum((x - mean) ** 2 for x in window) / max(1, len(window) - 1)
        realized_ann_vol = math.sqrt(max(var, 1e-12) * annualization)
        raw_weight = float(target_vol) / realized_ann_vol
        weights.append(min(float(max_leverage), max(0.1, raw_weight)))
    return weights


def expanding_ic_ir_weights(ic_history: dict[str, Sequence[float]], min_periods: int = 5) -> dict[str, float]:
    """Compute out-of-sample factor weights proportional to signed IC Information Ratio."""
    raw_scores: dict[str, float] = {}
    for factor, series in ic_history.items():
        vals = [float(x) for x in series]
        if len(vals) < min_periods:
            raw_scores[factor] = 0.0
            continue
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / max(1, len(vals) - 1)
        std = math.sqrt(max(var, 1e-12))
        raw_scores[factor] = mean / std
    denom = sum(abs(v) for v in raw_scores.values())
    if denom <= 1e-12:
        n = max(1, len(ic_history))
        return {k: 1.0 / n for k in ic_history}
    return {k: v / denom for k, v in raw_scores.items()}


def empirical_bayes_shrinkage_weight(
    own_variance: float,
    cross_sectional_variance: float,
    n_obs: int,
) -> float:
    """Compute Empirical Bayes / James-Stein shrinkage intensity toward regional pooled mean.

    Returns lambda in [0, 1] where 1.0 = full shrinkage to regional pooled mean.
    """
    if n_obs <= 0 or own_variance <= 0.0:
        return 1.0
    if cross_sectional_variance <= 0.0:
        return 1.0
    sampling_var = float(own_variance) / float(n_obs)
    return sampling_var / (sampling_var + float(cross_sectional_variance))
