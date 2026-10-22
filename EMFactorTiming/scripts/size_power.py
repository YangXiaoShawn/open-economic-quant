"""Size and power of the out-of-sample tests on known-truth synthetic panels.

Writes reports/validation/size_power.csv and .md. This is software validation:
every number here comes from simulated data with a known data-generating process.

    python scripts/size_power.py --reps 40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emft.backtest import run_backtest  # noqa: E402
from emft.data import synthetic_panel  # noqa: E402
from emft.evaluate import r2_table  # noqa: E402
from emft.features import build_features, model_ready  # noqa: E402

CRIT = 1.645  # one-sided 5%


def one(signal_sd: float, seed: int) -> dict:
    panel, _ = synthetic_panel(n_dm=6, n_em=6, n_factors=12, n_months=300, signal_sd=signal_sd, seed=seed)
    d = model_ready(build_features(panel))
    t = r2_table(run_backtest(d, models=("ols",), scopes=("own",), oos_start=2005)).iloc[0]
    return {"signal_sd": signal_sd, "seed": seed, **{k: t[k] for k in
            ("r2_vs_hist_pct", "cw_t_hist", "r2_vs_shrink_pct", "cw_t_shrink")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=40)
    ap.add_argument("--out", default="reports/validation")
    a = ap.parse_args()
    rows = [one(s, seed) for s in (0.0, 0.004, 0.008) for seed in range(100, 100 + a.reps)]
    df = pd.DataFrame(rows)
    summ = df.groupby("signal_sd").agg(
        reps=("seed", "size"),
        mean_r2_vs_hist=("r2_vs_hist_pct", "mean"),
        reject_vs_hist=("cw_t_hist", lambda t: (t > CRIT).mean()),
        mean_r2_vs_shrink=("r2_vs_shrink_pct", "mean"),
        reject_vs_shrink=("cw_t_shrink", lambda t: (t > CRIT).mean()),
    ).reset_index()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "size_power_draws.csv", index=False)
    summ.to_csv(out / "size_power.csv", index=False)
    lines = [
        "# Size and power on synthetic panels (software validation, not a finding)",
        "",
        "6 DM + 6 EM countries, 12 factors, 300 months, OOS from 2005, pooled OLS.",
        "Rejection = Clark-West t > 1.645 (one-sided 5%). Row signal_sd = 0 is the null.",
        "",
        summ.round(3).to_markdown(index=False) if hasattr(summ, "to_markdown") else summ.round(3).to_string(index=False),
    ]
    (out / "size_power.md").write_text("\n".join(lines) + "\n")
    print(summ.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
