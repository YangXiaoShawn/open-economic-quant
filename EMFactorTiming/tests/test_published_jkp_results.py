"""Verify published JKP emerging-market R2_OS, portfolio tables, and 312-month real-data shrinkage/ML benchmarks."""
from __future__ import annotations

import csv
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT.parent / "packages" / "oeq-core" / "src"
if CORE_SRC.exists() and str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from oeq_core import empirical_bayes_shrinkage_weight, newey_west_tstat  # noqa: E402


def _load_monthly(folder: str, strategy: str) -> list[dict[str, str]]:
    path = ROOT / "reports" / folder / "portfolio_monthly.csv"
    with path.open("r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["strategy"] == strategy]
    rows.sort(key=lambda r: r["target_month"])
    return rows


class TestEMFactorTimingPublishedTables(unittest.TestCase):
    def test_r2_oos_table(self) -> None:
        path = ROOT / "reports" / "jkp_em" / "r2_oos.csv"
        with path.open("r", encoding="utf-8") as fh:
            rows = {(r["model"], r["scope"]): r for r in csv.DictReader(fh)}
        self.assertAlmostEqual(float(rows[("shrink_mean", "rule")]["r2_vs_hist_pct"]), 1.2025, places=3)
        for (model, scope), r in rows.items():
            if scope in ("own", "pooled", "dm_only"):
                self.assertLess(float(r["r2_vs_shrink_pct"]), 0.0)
                self.assertGreater(float(r["cw_t_shrink"]), 1.5)

    def test_portfolios_table(self) -> None:
        path = ROOT / "reports" / "jkp_em" / "portfolios.csv"
        with path.open("r", encoding="utf-8") as fh:
            rows = {r["strategy"]: r for r in csv.DictReader(fh)}
        self.assertAlmostEqual(float(rows["shrink_mean:rule"]["sharpe_net"]), 1.9054, places=3)
        self.assertAlmostEqual(float(rows["static_ew"]["sharpe_net"]), 1.4774, places=3)
        self.assertAlmostEqual(float(rows["gbrt:own"]["sharpe_net"]), 1.2648, places=3)

    def test_eb_and_long_only_real_312m_verification(self) -> None:
        path = ROOT / "reports" / "jkp_em" / "eb_and_long_only_summary.csv"
        with path.open("r", encoding="utf-8") as fh:
            rows = {r["specification"]: r for r in csv.DictReader(fh)}

        k60 = _load_monthly("jkp_em_kappa60", "shrink_mean:rule")
        k120 = _load_monthly("jkp_em", "shrink_mean:rule")
        k240 = _load_monthly("jkp_em_kappa240", "shrink_mean:rule")
        gbrt_rs = _load_monthly("jkp_em_rs", "gbrt_rs:own")
        self.assertEqual(len(k120), 312)
        self.assertEqual(len(k240), 312)
        self.assertEqual(len(gbrt_rs), 312)

        blend_gross = [0.75 * float(k240[t]["gross"]) + 0.25 * float(gbrt_rs[t]["gross"]) for t in range(312)]
        blend_net = [0.75 * float(k240[t]["net"]) + 0.25 * float(gbrt_rs[t]["net"]) for t in range(312)]
        mg = sum(blend_gross) / 312.0
        sg = math.sqrt(sum((x - mg) ** 2 for x in blend_gross) / 311.0)
        mn = sum(blend_net) / 312.0
        sn = math.sqrt(sum((x - mn) ** 2 for x in blend_net) / 311.0)
        sh_gross = round((mg / sg) * math.sqrt(12.0), 4)
        sh_net = round((mn / sn) * math.sqrt(12.0), 4)
        nw_t = round(newey_west_tstat(blend_net, max_lag=6), 2)

        self.assertAlmostEqual(sh_gross, float(rows["turnover_damped_blend:75_k240_25_gbrt_rs"]["sharpe_gross"]), places=4)
        self.assertAlmostEqual(sh_net, float(rows["turnover_damped_blend:75_k240_25_gbrt_rs"]["sharpe_net_20bp"]), places=4)
        self.assertAlmostEqual(nw_t, float(rows["turnover_damped_blend:75_k240_25_gbrt_rs"]["nw_t_net"]), places=2)
        self.assertGreater(
            float(rows["eb_shrink_mean:rule"]["sharpe_net_20bp"]),
            float(rows["shrink_mean:rule"]["sharpe_net_20bp"]),
        )
        self.assertGreater(
            float(rows["turnover_damped_blend:75_k240_25_gbrt_rs"]["sharpe_gross"]),
            float(rows["shrink_mean:rule_kappa240"]["sharpe_gross"]),
        )
        w = empirical_bayes_shrinkage_weight(own_variance=0.0025, cross_sectional_variance=0.00002, n_obs=120)
        self.assertTrue(0.45 < w < 0.55)


if __name__ == "__main__":
    unittest.main()
