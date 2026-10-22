"""Verify NYC HVFHV 10,000-trip sample diagnostics and CasualLab claim boundary."""
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


class TestRealNycSampleDiagnostics(unittest.TestCase):
    def test_nyc_hvfhv_10000_trip_diagnostics(self) -> None:
        diag = json.loads((ROOT / "data" / "nyc_sample" / "diagnostics.json").read_text(encoding="utf-8"))
        self.assertEqual(int(diag["row_count"]), 10000)
        self.assertEqual(diag["sources"], ["nyc_hvfhv"])
        self.assertEqual(int(diag["validity"]["duplicate_trip_id_count"]), 0)
        self.assertEqual(int(diag["validity"]["missing_trip_id_count"]), 0)
        self.assertEqual(int(diag["validity"]["negative_trip_miles_count"]), 0)
        self.assertEqual(int(diag["validity"]["nonpositive_trip_seconds_count"]), 0)
        self.assertEqual(diag["suppression_or_nonreporting"]["pickup_indicator_status"], "unavailable")

        boundary = ClaimBoundary(
            project_slug="casuallab",
            grade=EvidenceGrade.SYNTHETIC_SMOKE,
            allows_causal_language=False,
            allows_live_profitability_claim=False,
        )
        self.assertEqual(validate_claim_boundary(boundary), [])


if __name__ == "__main__":
    unittest.main()
