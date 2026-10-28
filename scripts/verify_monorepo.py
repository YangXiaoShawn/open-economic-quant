#!/usr/bin/env python3
"""Comprehensive monorepo verification suite across oeq-core and all 8 research projects.

Checksums of each project's required files are compared against the committed
scripts/monorepo_manifest.json; after intentionally editing those files, regenerate it
with ``python scripts/verify_monorepo.py --update-manifest`` (``make update-manifest``).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "packages" / "oeq-core" / "src"
PM_SRC = ROOT / "PolymarketFactors" / "src"
CF_SRC = ROOT / "CryptoFactors" / "src"

for p in (CORE_SRC, PM_SRC, CF_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from oeq_core import (  # noqa: E402
    ClaimBoundary,
    EvidenceGrade,
    auto_demote_claim,
    build_run_manifest,
    validate_claim_boundary,
    verify_manifest_checksums,
)
from crypto_factors.pipeline import run_sample_pipeline as run_cf_sample  # noqa: E402
from polymarket_factors.pipeline import run_sample_pipeline as run_pm_sample  # noqa: E402

MANIFEST_PATH = ROOT / "scripts" / "monorepo_manifest.json"

# Claims each project makes publicly: (evidence grade, uses causal language), per outcome
# where outcomes carry different identification status ("project" otherwise). These are
# declarations; the pre-trend/placebo evidence a causal claim needs is read from the
# project's result files (see outcome_gates), so a declaration the data does not support
# fails verification instead of being silently demoted.
PROJECTS: dict[str, dict[str, tuple[EvidenceGrade, bool]]] = {
    "CasualLab": {"project": (EvidenceGrade.SYNTHETIC_SMOKE, False)},
    "Macroeconomics": {"project": (EvidenceGrade.OOS_PREDICTIVE_COMPARISON, False)},
    # Loan-level hazard estimates are associations; the market-level event-study
    # pre-trend test fails (p = 0.004), see reports/local_market_event_study.md.
    "RealEstate": {"project": (EvidenceGrade.ASSOCIATIONAL_ONLY, False)},
    "TariffIncidence": {
        "log_landed_unit_value": (EvidenceGrade.CAUSAL_IDENTIFIED, True),
        "log_customs_unit_value": (EvidenceGrade.CAUSAL_IDENTIFIED, True),
        # Noisy pre-period and a failed date placebo: qualified reading only.
        "log_quantity": (EvidenceGrade.ASSOCIATIONAL_ONLY, False),
    },
    "Microstructure": {"project": (EvidenceGrade.OOS_PREDICTIVE_COMPARISON, False)},
    "EMFactorTiming": {"project": (EvidenceGrade.BACKTEST_ASSOCIATION, False)},
    "PolymarketFactors": {"project": (EvidenceGrade.BACKTEST_ASSOCIATION, False)},
    "CryptoFactors": {"project": (EvidenceGrade.BACKTEST_ASSOCIATION, False)},
}

# Pre-trend verdicts (TariffIncidence econ.designs.pretrend_test) that do not
# undermine identification; a bounded near-zero effect is a finding, not a failure.
PASSING_PRETREND_VERDICTS = frozenset({"CLEAN", "PRECISE_NULL_EFFECT_BOUNDED"})

REQUIRED_FILES = ("project.yaml", "pyproject.toml", "Makefile", "README.md", "STATUS.md", "AGENTS.md")
REQUIRED_YAML_KEYS = {
    "title",
    "slug",
    "summary",
    "research_question",
    "research_fields",
    "project_type",
    "status",
    "data_sources",
    "reproduction_command",
    "github_url",
    "site_url",
    "dataset_url",
    "space_url",
    "last_updated",
    "limitations",
}


def check_no_bare_sibling_imports(pkg_dir: Path) -> list[str]:
    """Ensure every module inside pkg_dir uses package-qualified or relative imports."""
    modules = {p.stem for p in pkg_dir.glob("*.py") if p.stem != "__init__"}
    violations: list[str] = []
    for py_file in sorted(pkg_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in modules:
                violations.append(f"{py_file.relative_to(ROOT)}:{node.lineno} bare import from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in modules:
                        violations.append(f"{py_file.relative_to(ROOT)}:{node.lineno} bare import {alias.name}")
    return violations


def project_slug(proj_dir: Path) -> str:
    yaml_path = proj_dir / "project.yaml"
    if not yaml_path.is_file():
        return ""
    match = re.search(r"^slug:[ \t]*(\S+)", yaml_path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return match.group(1).strip("'\"") if match else ""


def tariff_outcome_gates(checks_path: Path) -> dict[str, bool]:
    """Per-outcome identification gate from TariffIncidence identification_checks.json.

    An outcome passes when both reference-period pre-trend tests have a passing verdict
    and the 12-month treatment-date placebo has status PASS.
    """
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    pretrend = checks.get("pretrend_tests", {})
    gates: dict[str, bool] = {}
    for check in checks.get("checks", []):
        if check.get("check") != "placebo_treatment_date_minus_12m" or "outcome" not in check:
            continue
        outcome = check["outcome"]
        verdicts = [pretrend.get(f"pretrend_{outcome}_ref{ref}", {}).get("verdict") for ref in (1, 3)]
        gates[outcome] = check.get("status") == "PASS" and all(v in PASSING_PRETREND_VERDICTS for v in verdicts)
    return gates


def outcome_gates(proj_dir_name: str, root: Path = ROOT) -> dict[str, bool]:
    """Pre-trend/placebo gate per outcome, derived from result files where a project has them."""
    if proj_dir_name == "TariffIncidence":
        checks_path = root / "TariffIncidence" / "data" / "results" / "identification_checks.json"
        return tariff_outcome_gates(checks_path) if checks_path.is_file() else {}
    return {}


def claim_violations(
    slug: str,
    claims: dict[str, tuple[EvidenceGrade, bool]],
    gates: dict[str, bool],
) -> tuple[list[str], dict[str, str]]:
    """Validate declared claims against derived gates; also return the grade each claim supports."""
    violations: list[str] = []
    supported: dict[str, str] = {}
    for outcome, (grade, causal_language) in claims.items():
        boundary = ClaimBoundary(
            project_slug=slug if outcome == "project" else f"{slug}:{outcome}",
            grade=grade,
            allows_causal_language=causal_language,
            allows_live_profitability_claim=False,
            passed_pretrend_or_placebo=gates.get(outcome, False),
        )
        violations.extend(validate_claim_boundary(boundary))
        supported[outcome] = auto_demote_claim(boundary).grade.value
    return violations, supported


def required_files_manifest(proj_dir: Path, slug: str) -> dict[str, object]:
    files = [proj_dir / req for req in REQUIRED_FILES if (proj_dir / req).is_file()]
    manifest = build_run_manifest(project_slug=slug, root=proj_dir, files=files, evidence_grade="")
    # Keep the committed file deterministic: only what the checksums depend on.
    return {"project": slug, "file_count": manifest["file_count"], "files": manifest["files"]}


def write_manifest(path: Path = MANIFEST_PATH) -> dict[str, object]:
    projects = {
        name: required_files_manifest(ROOT / name, project_slug(ROOT / name))
        for name in PROJECTS
        if (ROOT / name).is_dir()
    }
    payload = {"algorithm": "sha256", "regenerate": "make update-manifest", "projects": projects}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def manifest_errors(proj_dir: Path, committed: dict[str, object] | None) -> list[str]:
    """Compare a project's required files against its entry in the committed manifest."""
    if committed is None:
        return [f"no committed manifest entry for {proj_dir.name}"]
    errors = verify_manifest_checksums(proj_dir, committed)
    expected = {str(item["path"]) for item in committed.get("files", [])}  # type: ignore[union-attr]
    present = {req for req in REQUIRED_FILES if (proj_dir / req).is_file()}
    errors.extend(f"unrecorded:{rel}" for rel in sorted(present - expected))
    return errors


def verify_all(manifest_path: Path = MANIFEST_PATH) -> dict[str, object]:
    errors: list[str] = []
    manifest_counts: dict[str, int] = {}
    supported_grades: dict[str, dict[str, str]] = {}

    if manifest_path.is_file():
        committed = json.loads(manifest_path.read_text(encoding="utf-8")).get("projects", {})
    else:
        committed = {}
        errors.append(f"Missing checksum manifest {manifest_path.name}; run `make update-manifest`")

    for proj_dir_name, claims in PROJECTS.items():
        proj_dir = ROOT / proj_dir_name
        if not proj_dir.is_dir():
            errors.append(f"Missing project directory: {proj_dir_name}")
            continue
        for req in REQUIRED_FILES:
            if not (proj_dir / req).is_file():
                errors.append(f"Missing required file: {proj_dir_name}/{req}")

        yaml_path = proj_dir / "project.yaml"
        if yaml_path.is_file():
            text = yaml_path.read_text(encoding="utf-8")
            keys = set(re.findall(r"^([a-zA-Z][a-zA-Z0-9_]*):", text, flags=re.MULTILINE))
            missing = REQUIRED_YAML_KEYS - keys
            if missing:
                errors.append(f"{proj_dir_name}/project.yaml missing keys: {sorted(missing)}")
        slug = project_slug(proj_dir) or proj_dir_name

        violations, supported_grades[proj_dir_name] = claim_violations(slug, claims, outcome_gates(proj_dir_name))
        if violations:
            errors.append(f"ClaimBoundary violation for {proj_dir_name}: {violations}")

        entry = committed.get(proj_dir_name)
        chk_errors = manifest_errors(proj_dir, entry)
        if chk_errors:
            errors.append(
                f"Manifest checksum error in {proj_dir_name}: {chk_errors} "
                "(run `make update-manifest` if the change is intended)"
            )
        manifest_counts[proj_dir_name] = int(entry["file_count"]) if entry else 0

    # Check AST import hygiene
    errors.extend(check_no_bare_sibling_imports(PM_SRC / "polymarket_factors"))
    errors.extend(check_no_bare_sibling_imports(CF_SRC / "crypto_factors"))

    # Run sample pipelines
    pm_summary = run_pm_sample()
    cf_summary = run_cf_sample()
    if pm_summary["sample_fixture_periods"] < 8:
        errors.append("PolymarketFactors sample fixture periods < 8")
    if cf_summary["sample_fixture_dates"] < 10:
        errors.append("CryptoFactors sample fixture dates < 10")

    if errors:
        raise SystemExit("Monorepo verification failed:\n- " + "\n- ".join(errors))

    return {
        "status": "ok",
        "projects_verified": len(PROJECTS),
        "manifest_files_per_project": manifest_counts,
        "supported_evidence_grades": supported_grades,
        "polymarket_walkforward_net_spread": pm_summary["sample_walkforward_net_spread"],
        "crypto_vol_targeted_mean_net": cf_summary["sample_vol_targeted_mean_net"],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--update-manifest",
        action="store_true",
        help=f"Regenerate {MANIFEST_PATH.relative_to(ROOT)} from the current files before verifying",
    )
    if ap.parse_args().update_manifest:
        write_manifest()
        print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    summary = verify_all()
    print(f"monorepo-verify-ok projects={summary['projects_verified']} status={summary['status']}")
    print(json.dumps(summary, indent=2))
