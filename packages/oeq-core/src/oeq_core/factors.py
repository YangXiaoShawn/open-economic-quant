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
    # Solve 3x3 normal equations (X^T X) beta = X^T y for X = [1, p, p^2]
    x_rows = [(1.0, float(pi), float(pi) ** 2) for pi in p]
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    for row, yi in zip(x_rows, y):
        for r in range(3):
            xty[r] += row[r] * float(yi)
            for c in range(3):
                xtx[r][c] += row[r] * row[c]
    # Gaussian elimination
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
