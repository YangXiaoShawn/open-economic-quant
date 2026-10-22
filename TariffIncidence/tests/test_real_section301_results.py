"""Verify official Section 301 empirical outputs (395,468 HS10-country-month obs, 4,306 products, trade diversion)."""
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


class TestRealSection301Results(unittest.TestCase):
    def test_window_sensitivity_and_complete_passthrough(self) -> None:
        win_path = ROOT / "data" / "results" / "window_sensitivity.json"
        data = json.loads(win_path.read_text(encoding="utf-8"))
        full = data["full window to 2020-02"]
        self.assertEqual(int(full["log_landed_unit_value"]["n_obs"]), 395468)
        self.assertEqual(full["log_landed_unit_value"]["verdict"], "CLEAN")
        self.assertAlmostEqual(float(full["log_landed_unit_value"]["mean_post"]), 0.154435, places=5)
        self.assertEqual(full["log_customs_unit_value"]["verdict"], "PRECISE_NULL_EFFECT_BOUNDED")
        self.assertAlmostEqual(float(full["log_customs_unit_value"]["mean_post"]), 0.025288, places=5)
        self.assertAlmostEqual(float(full["log_quantity"]["mean_post"]), -0.379326, places=5)

    def test_structural_and_diversion_reconciliation(self) -> None:
        struct = json.loads((ROOT / "data" / "results" / "structural_summary.json").read_text(encoding="utf-8"))
        div = json.loads((ROOT / "data" / "results" / "diversion_interpretation.json").read_text(encoding="utf-8"))

        self.assertEqual(struct["run"]["data_provenance"], "OFFICIAL")
        self.assertEqual(int(struct["n_products"]), 4306)
        self.assertAlmostEqual(float(struct["sigma_routes"]["inverted_from_ppml_quantity_response"]), 9.3559, places=3)
        self.assertAlmostEqual(float(struct["sigma_routes"]["fitted_to_observed_reallocation"]), 4.25, places=2)

        csum = div["counterfactual_adjusted_summary"]
        treated_chg = float(csum["treated_country_excess_change"])
        alt_chg = float(csum["alternative_countries_excess_change"])
        net_chg = float(csum["net_excess_change"])
        rep_ratio = float(csum["adjusted_replacement_ratio"])
        self.assertAlmostEqual(treated_chg + alt_chg, net_chg, places=2)
        self.assertAlmostEqual(alt_chg / abs(treated_chg), rep_ratio, places=6)
        self.assertAlmostEqual(rep_ratio, 0.111577, places=5)

        boundary = ClaimBoundary(
            project_slug="tariff-incidence",
            grade=EvidenceGrade.CAUSAL_IDENTIFIED,
            allows_causal_language=True,
            allows_live_profitability_claim=False,
            passed_pretrend_or_placebo=True,
        )
        self.assertEqual(validate_claim_boundary(boundary), [])


if __name__ == "__main__":
    unittest.main()
