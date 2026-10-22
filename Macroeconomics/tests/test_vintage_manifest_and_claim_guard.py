"""Verify Macroeconomics 10-series vintage manifest and out-of-sample predictive claim boundary."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT.parent / "packages" / "oeq-core" / "src"
if CORE_SRC.exists() and str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from oeq_core import ClaimBoundary, EvidenceGrade, validate_claim_boundary  # noqa: E402


class TestMacroeconomicsVintageManifest(unittest.TestCase):
    def test_vintage_manifest_and_claim_guard(self) -> None:
        manifest_path = ROOT / "data" / "fixtures" / "synthetic_payroll" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(int(manifest["observation_rows"]), 5261)
        self.assertEqual(len(manifest["series"]), 10)
        self.assertIn("PAYEMS", manifest["series"])
        self.assertIn("UNRATE", manifest["series"])

        boundary = ClaimBoundary(
            project_slug="macroeconomics",
            grade=EvidenceGrade.OOS_PREDICTIVE_COMPARISON,
            allows_causal_language=False,
            allows_live_profitability_claim=False,
        )
        self.assertEqual(validate_claim_boundary(boundary), [])


if __name__ == "__main__":
    unittest.main()
