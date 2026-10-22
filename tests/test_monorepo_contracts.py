"""Monorepo-level contract tests across all 8 Open Economic & Quant projects."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from verify_monorepo import (  # noqa: E402
    CF_SRC,
    PM_SRC,
    PROJECTS,
    check_no_bare_sibling_imports,
    verify_all,
)


class TestMonorepoContracts(unittest.TestCase):
    def test_all_eight_projects_verify(self) -> None:
        summary = verify_all()
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["projects_verified"], 8)
        for proj in PROJECTS:
            self.assertEqual(summary["manifest_files_per_project"][proj], 6)

    def test_zero_bare_sibling_imports(self) -> None:
        self.assertEqual(check_no_bare_sibling_imports(PM_SRC / "polymarket_factors"), [])
        self.assertEqual(check_no_bare_sibling_imports(CF_SRC / "crypto_factors"), [])

    def test_published_reports_exist_across_all_eight_projects(self) -> None:
        expected_reports = {
            "CasualLab": "reports/technical_report.md",
            "Macroeconomics": "reports/technical_report.md",
            "RealEstate": "reports/loan_hazard_analysis.md",
            "TariffIncidence": "reports/tariff_incidence_results.md",
            "Microstructure": "reports/technical_report.md",
            "EMFactorTiming": "reports/jkp_em/r2_oos.csv",
            "PolymarketFactors": "reports/artifact_funnel.csv",
            "CryptoFactors": "reports/factor_transfer_summary.csv",
        }
        for proj, rel_path in expected_reports.items():
            full_path = ROOT / proj / rel_path
            self.assertTrue(full_path.is_file(), f"Missing report {proj}/{rel_path}")


if __name__ == "__main__":
    unittest.main()
