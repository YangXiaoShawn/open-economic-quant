"""Unit tests for oeq-core shared research primitives."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from oeq_core import (
    ClaimBoundary,
    EvidenceGrade,
    auto_demote_claim,
    benjamini_hochberg_fdr,
    build_run_manifest,
    cross_sectional_rank_ic,
    empirical_bayes_shrinkage_weight,
    expanding_ic_ir_weights,
    newey_west_tstat,
    quantile_long_short_spread,
    residualize_quadratic,
    turnover_penalized_net_return,
    validate_claim_boundary,
    verify_manifest_checksums,
    volatility_target_weights,
)


class TestOeqCore(unittest.TestCase):
    def test_provenance_manifest_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "artifact.txt"
            sample.write_text("open-economic-quant", encoding="utf-8")
            manifest = build_run_manifest("demo", root, [sample], "SYNTHETIC_SMOKE")
            self.assertEqual(manifest["file_count"], 1)
            self.assertEqual(verify_manifest_checksums(root, manifest), [])

    def test_claim_guard_and_auto_demote(self) -> None:
        valid = ClaimBoundary("realestate", EvidenceGrade.ASSOCIATIONAL_ONLY)
        self.assertEqual(validate_claim_boundary(valid), [])
        invalid = ClaimBoundary(
            "tariff-incidence",
            EvidenceGrade.CAUSAL_IDENTIFIED,
            allows_causal_language=True,
            allows_live_profitability_claim=True,
            passed_pretrend_or_placebo=False,
        )
        self.assertGreaterEqual(len(validate_claim_boundary(invalid)), 2)
        demoted = auto_demote_claim(invalid)
        self.assertEqual(demoted.grade, EvidenceGrade.ASSOCIATIONAL_ONLY)
        self.assertFalse(demoted.allows_causal_language)
        self.assertFalse(demoted.allows_live_profitability_claim)
        self.assertEqual(validate_claim_boundary(demoted), [])

    def test_factor_primitives_and_fdr(self) -> None:
        ic = cross_sectional_rank_ic([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0])
        self.assertAlmostEqual(ic, -1.0, places=6)
        p = [0.1, 0.3, 0.5, 0.7, 0.9]
        y = [0.2 + 0.5 * x - 0.3 * (x ** 2) for x in p]
        res = residualize_quadratic(y, p)
        for val in res:
            self.assertAlmostEqual(val, 0.0, places=6)
        self.assertAlmostEqual(turnover_penalized_net_return(0.01, 0.5, 20.0), 0.009, places=6)
        self.assertGreater(newey_west_tstat([0.02, 0.03, 0.025, 0.028, 0.022, 0.031], max_lag=2), 5.0)
        spread = quantile_long_short_spread([1.0, 2.0, 3.0, 4.0, 5.0], [-0.02, -0.01, 0.0, 0.01, 0.03], n_quantiles=5)
        self.assertAlmostEqual(spread, 0.05, places=6)
        qvals = benjamini_hochberg_fdr([0.001, 0.02, 0.04, 0.50])
        self.assertEqual(len(qvals), 4)
        self.assertLess(qvals[0], 0.01)
        self.assertLessEqual(qvals[0], qvals[1])

    def test_vol_target_and_shrinkage(self) -> None:
        weights = volatility_target_weights([0.01, -0.01, 0.015, -0.012, 0.008, -0.009], target_vol=0.15, lookback=4)
        self.assertEqual(len(weights), 6)
        self.assertTrue(all(0.1 <= w <= 1.5 for w in weights))
        ic_w = expanding_ic_ir_weights({"PM-LIQ": [-0.07, -0.08, -0.06, -0.075, -0.072], "PM-VOL": [-0.06, -0.07, -0.065, -0.07, -0.068]})
        self.assertAlmostEqual(sum(abs(v) for v in ic_w.values()), 1.0, places=6)
        self.assertLess(ic_w["PM-LIQ"], 0.0)
        lam = empirical_bayes_shrinkage_weight(own_variance=0.04, cross_sectional_variance=0.001, n_obs=60)
        self.assertTrue(0.0 < lam < 1.0)


if __name__ == "__main__":
    unittest.main()
