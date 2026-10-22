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
    build_run_manifest,
    cross_sectional_rank_ic,
    newey_west_tstat,
    residualize_quadratic,
    turnover_penalized_net_return,
    validate_claim_boundary,
    verify_manifest_checksums,
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

    def test_claim_guard_blocks_prohibited_claims(self) -> None:
        valid = ClaimBoundary("realestate", EvidenceGrade.ASSOCIATIONAL_ONLY)
        self.assertEqual(validate_claim_boundary(valid), [])
        invalid = ClaimBoundary(
            "microstructure",
            EvidenceGrade.BACKTEST_ASSOCIATION,
            allows_live_profitability_claim=True,
        )
        self.assertEqual(len(validate_claim_boundary(invalid)), 1)

    def test_factor_primitives(self) -> None:
        ic = cross_sectional_rank_ic([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0])
        self.assertAlmostEqual(ic, -1.0, places=6)
        p = [0.1, 0.3, 0.5, 0.7, 0.9]
        y = [0.2 + 0.5 * x - 0.3 * (x ** 2) for x in p]
        res = residualize_quadratic(y, p)
        for val in res:
            self.assertAlmostEqual(val, 0.0, places=6)
        self.assertAlmostEqual(turnover_penalized_net_return(0.01, 0.5, 20.0), 0.009, places=6)
        self.assertGreater(newey_west_tstat([0.02, 0.03, 0.025, 0.028, 0.022, 0.031], max_lag=2), 5.0)


if __name__ == "__main__":
    unittest.main()
