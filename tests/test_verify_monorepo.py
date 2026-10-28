"""verify_monorepo.py must be able to fail: checksum drift and unsupported claims are errors."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from verify_monorepo import (  # noqa: E402
    MANIFEST_PATH,
    PROJECTS,
    REQUIRED_FILES,
    EvidenceGrade,
    claim_violations,
    manifest_errors,
    outcome_gates,
    tariff_outcome_gates,
    verify_all,
)

TARIFF_CHECKS = ROOT / "TariffIncidence" / "data" / "results" / "identification_checks.json"


class TestVerifyMonorepo(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tariff_gates_follow_identification_checks(self) -> None:
        gates = outcome_gates("TariffIncidence")
        self.assertEqual(
            gates,
            {"log_customs_unit_value": True, "log_landed_unit_value": True, "log_quantity": False},
        )

    def test_declared_claims_match_the_evidence(self) -> None:
        violations, supported = claim_violations(
            "tariff-incidence", PROJECTS["TariffIncidence"], outcome_gates("TariffIncidence")
        )
        self.assertEqual(violations, [])
        self.assertEqual(supported["log_quantity"], "ASSOCIATIONAL_ONLY")

    def test_causal_claim_on_quantity_is_rejected(self) -> None:
        claims = {"log_quantity": (EvidenceGrade.CAUSAL_IDENTIFIED, True)}
        violations, supported = claim_violations("tariff-incidence", claims, outcome_gates("TariffIncidence"))
        self.assertTrue(any("CAUSAL_IDENTIFIED requires" in v for v in violations), violations)
        self.assertEqual(supported["log_quantity"], "ASSOCIATIONAL_ONLY")

    def test_failed_placebo_in_results_invalidates_the_headline_claim(self) -> None:
        checks = json.loads(TARIFF_CHECKS.read_text(encoding="utf-8"))
        for check in checks["checks"]:
            if check.get("outcome") == "log_landed_unit_value":
                check["status"] = "FAIL"
        tampered = self.tmp / "identification_checks.json"
        tampered.write_text(json.dumps(checks), encoding="utf-8")
        gates = tariff_outcome_gates(tampered)
        self.assertFalse(gates["log_landed_unit_value"])
        violations, _ = claim_violations("tariff-incidence", PROJECTS["TariffIncidence"], gates)
        self.assertTrue(any("log_landed_unit_value" in v for v in violations), violations)

    def test_causal_language_without_causal_grade_is_rejected(self) -> None:
        claims = {"project": (EvidenceGrade.ASSOCIATIONAL_ONLY, True)}
        violations, _ = claim_violations("realestate", claims, {})
        self.assertEqual(violations, ["realestate: causal language requires CAUSAL_IDENTIFIED grade"])

    def test_checksum_drift_is_reported(self) -> None:
        committed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["projects"]["CasualLab"]
        self.assertEqual(manifest_errors(ROOT / "CasualLab", committed), [])
        proj = self.tmp / "CasualLab"
        proj.mkdir()
        for req in REQUIRED_FILES:
            shutil.copy2(ROOT / "CasualLab" / req, proj / req)
        with (proj / "STATUS.md").open("a", encoding="utf-8") as fh:
            fh.write("\nunreviewed edit\n")
        self.assertEqual(manifest_errors(proj, committed), ["checksum_mismatch:STATUS.md"])
        self.assertEqual(manifest_errors(proj, None), ["no committed manifest entry for CasualLab"])

    def test_verify_all_fails_against_a_stale_manifest(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["projects"]["RealEstate"]["files"][0]["sha256"] = "0" * 64
        stale = self.tmp / "monorepo_manifest.json"
        stale.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            verify_all(manifest_path=stale)
        self.assertIn("Manifest checksum error in RealEstate", str(ctx.exception))

    def test_verify_all_fails_without_a_manifest(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            verify_all(manifest_path=self.tmp / "missing.json")
        self.assertIn("Missing checksum manifest", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
