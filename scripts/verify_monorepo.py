#!/usr/bin/env python3
"""Comprehensive monorepo verification suite across oeq-core and all 8 research projects."""
from __future__ import annotations

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

PROJECTS: dict[str, tuple[str, EvidenceGrade, bool]] = {
    "CasualLab": ("casuallab", EvidenceGrade.SYNTHETIC_SMOKE, False),
    "Macroeconomics": ("macroeconomics", EvidenceGrade.OOS_PREDICTIVE_COMPARISON, False),
    "RealEstate": ("realestate", EvidenceGrade.CAUSAL_IDENTIFIED, False),  # auto-demoted due to pre-trend p=0.0046
    "TariffIncidence": ("tariff-incidence", EvidenceGrade.CAUSAL_IDENTIFIED, True),
    "Microstructure": ("microstructure", EvidenceGrade.OOS_PREDICTIVE_COMPARISON, False),
    "EMFactorTiming": ("em-factor-timing", EvidenceGrade.BACKTEST_ASSOCIATION, False),
    "PolymarketFactors": ("polymarket-factors", EvidenceGrade.BACKTEST_ASSOCIATION, False),
    "CryptoFactors": ("crypto-factors", EvidenceGrade.BACKTEST_ASSOCIATION, False),
}

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


def verify_all() -> dict[str, object]:
    errors: list[str] = []
    manifest_counts: dict[str, int] = {}

    for proj_dir_name, (slug, grade, passed_pretrend) in PROJECTS.items():
        proj_dir = ROOT / proj_dir_name
        if not proj_dir.is_dir():
            errors.append(f"Missing project directory: {proj_dir_name}")
            continue
        tracked: list[Path] = []
        for req in REQUIRED_FILES:
            fp = proj_dir / req
            if not fp.is_file():
                errors.append(f"Missing required file: {proj_dir_name}/{req}")
            else:
                tracked.append(fp)

        yaml_path = proj_dir / "project.yaml"
        if yaml_path.is_file():
            text = yaml_path.read_text(encoding="utf-8")
            keys = set(re.findall(r"^([a-zA-Z][a-zA-Z0-9_]*):", text, flags=re.MULTILINE))
            missing = REQUIRED_YAML_KEYS - keys
            if missing:
                errors.append(f"{proj_dir_name}/project.yaml missing keys: {sorted(missing)}")

        raw_boundary = ClaimBoundary(
            project_slug=slug,
            grade=grade,
            allows_causal_language=(grade == EvidenceGrade.CAUSAL_IDENTIFIED),
            allows_live_profitability_claim=False,
            passed_pretrend_or_placebo=passed_pretrend,
        )
        boundary = auto_demote_claim(raw_boundary)
        violations = validate_claim_boundary(boundary)
        if violations:
            errors.append(f"ClaimBoundary violation for {proj_dir_name}: {violations}")

        manifest = build_run_manifest(
            project_slug=slug,
            root=proj_dir,
            files=tracked,
            evidence_grade=boundary.grade.value,
        )
        chk_errors = verify_manifest_checksums(proj_dir, manifest)
        if chk_errors:
            errors.append(f"Manifest checksum error in {proj_dir_name}: {chk_errors}")
        manifest_counts[proj_dir_name] = manifest["file_count"]

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
        "polymarket_walkforward_net_spread": pm_summary["sample_walkforward_net_spread"],
        "crypto_vol_targeted_mean_net": cf_summary["sample_vol_targeted_mean_net"],
    }


if __name__ == "__main__":
    summary = verify_all()
    print(f"monorepo-verify-ok projects={summary['projects_verified']} status={summary['status']}")
    print(json.dumps(summary, indent=2))
