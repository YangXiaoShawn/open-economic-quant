"""Verify published JKP emerging-market R2_OS and portfolio tables."""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


if __name__ == "__main__":
    unittest.main()
