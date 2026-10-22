"""Verify published JKP emerging-market R2_OS, portfolio tables, and Empirical Bayes / Long-Only benchmarks."""
from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT.parent / "packages" / "oeq-core" / "src"
if CORE_SRC.exists() and str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from oeq_core import empirical_bayes_shrinkage_weight  # noqa: E402


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

    def test_eb_and_long_only_summary(self) -> None:
        path = ROOT / "reports" / "jkp_em" / "eb_and_long_only_summary.csv"
        with path.open("r", encoding="utf-8") as fh:
            rows = {r["specification"]: r for r in csv.DictReader(fh)}
        self.assertGreater(
            float(rows["eb_shrink_mean:rule"]["r2_vs_hist_pct"]),
            float(rows["shrink_mean:rule"]["r2_vs_hist_pct"]),
        )
        self.assertGreater(
            float(rows["eb_shrink_mean:rule:long_only"]["sharpe_net_20bp"]),
            float(rows["enet:pooled:long_only"]["sharpe_net_20bp"]),
        )
        w = empirical_bayes_shrinkage_weight(own_variance=0.0025, cross_sectional_variance=0.00002, n_obs=120)
        self.assertTrue(0.45 < w < 0.55)


if __name__ == "__main__":
    unittest.main()
