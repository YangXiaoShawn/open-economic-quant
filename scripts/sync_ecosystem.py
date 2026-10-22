#!/usr/bin/env python3
"""Ecosystem synchronization tool for Open Economic & Quant Research.

Synchronizes subprojects from the unified `open-economic-quant` monorepo to:
1. Standalone project checkouts (`EMFactorTiming`, `PolymarketFactors`, `CryptoFactors`, etc.)
2. `YangXiaoShawn.github.io` (`build/hf-dataset/dataset_manifest.json`, `assets/data/evidence.json`,
   `apps/space/catalog/*.json`, and `index.html`)
3. Optionally pushes commits to GitHub and uploads to Hugging Face Dataset & Space (`--push-all`).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MONO = Path(__file__).resolve().parents[1]
SCRATCH = MONO.parent
PORTAL_CANDIDATES = sorted(SCRATCH.glob("YangXiaoShawn.github.io*"))
PORTAL = PORTAL_CANDIDATES[0] if PORTAL_CANDIDATES else SCRATCH / "YangXiaoShawn.github.io"

EXCLUDED = {".DS_Store", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}

SYNC_PROJECTS = (
    "CasualLab",
    "Macroeconomics",
    "RealEstate",
    "TariffIncidence",
    "Microstructure",
    "EMFactorTiming",
    "PolymarketFactors",
    "CryptoFactors",
)

STANDALONE_REMOTES = {
    "CasualLab": "git@github.com:YangXiaoShawn/open-economic-quant-casuallab.git",
    "Macroeconomics": "git@github.com:YangXiaoShawn/open-economic-quant-macroeconomics.git",
    "RealEstate": "git@github.com:YangXiaoShawn/open-economic-quant-realestate.git",
    "TariffIncidence": "git@github.com:YangXiaoShawn/open-economic-quant-tariff-incidence.git",
    "Microstructure": "git@github.com:YangXiaoShawn/open-economic-quant-microstructure.git",
    "EMFactorTiming": "git@github.com:YangXiaoShawn/open-economic-quant-em-factor-timing.git",
    "PolymarketFactors": "git@github.com:YangXiaoShawn/open-economic-quant-polymarket-factors.git",
    "CryptoFactors": "git@github.com:YangXiaoShawn/open-economic-quant-crypto-factors.git",
}


def sync_local_files(projects: list[str]) -> dict[str, int]:
    """Copy updated project files to standalone checkouts and refresh portal manifest & evidence."""
    if not PORTAL.exists():
        raise FileNotFoundError(f"Portal checkout not found at {PORTAL}")

    if str(PORTAL / "scripts") not in sys.path:
        sys.path.insert(0, str(PORTAL / "scripts"))
    from build_space_catalog import SLUGS, file_category  # type: ignore

    for proj in projects:
        src_dir = MONO / proj
        dst_dir = SCRATCH / proj
        dst_dir.mkdir(parents=True, exist_ok=True)
        if not (dst_dir / ".git").exists():
            subprocess.run(["git", "-C", str(dst_dir), "init", "-b", "main"], check=True)
            subprocess.run(["git", "-C", str(dst_dir), "remote", "add", "origin", STANDALONE_REMOTES[proj]], check=True)
        for p in src_dir.rglob("*"):
            if any(part in EXCLUDED for part in p.parts):
                continue
            rel = p.relative_to(src_dir)
            target = dst_dir / rel
            if p.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)

    manifest_path = PORTAL / "build" / "hf-dataset" / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prefixes = tuple(f"{p}/" for p in projects)
    files = [f for f in manifest["files"] if not f["path"].startswith(prefixes)]

    for proj in projects:
        src_dir = MONO / proj
        for p in sorted(src_dir.rglob("*")):
            if not p.is_file() or any(part in EXCLUDED for part in p.parts):
                continue
            rel = f"{proj}/{p.relative_to(src_dir).as_posix()}"
            files.append({"path": rel, "size_bytes": p.stat().st_size})

    manifest["files"] = files
    manifest["file_count"] = len(files)
    manifest["size_bytes"] = sum(f["size_bytes"] for f in files)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    evidence_path = PORTAL / "assets" / "data" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    for proj in projects:
        slug = SLUGS[proj]
        p_files = [f for f in files if f["path"].startswith(f"{proj}/")]
        evidence["portfolio"]["projects"][slug] = {
            "files": len(p_files),
            "bytes": sum(f["size_bytes"] for f in p_files),
            "code": sum(file_category(f["path"]) == "code" for f in p_files),
            "data": sum(file_category(f["path"]) == "data" for f in p_files),
            "reports": sum(file_category(f["path"]) == "reports" for f in p_files),
            "tests": sum(file_category(f["path"]) == "tests" for f in p_files),
        }

    projects_port = evidence["portfolio"]["projects"]
    evidence["portfolio"]["total_files"] = sum(v["files"] for v in projects_port.values())
    evidence["portfolio"]["total_bytes"] = sum(v["bytes"] for v in projects_port.values())
    for cat in ("code", "data", "reports", "tests"):
        evidence["portfolio"]["categories"][cat] = sum(v[cat] for v in projects_port.values())

    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    subprocess.run([sys.executable, str(PORTAL / "scripts" / "build_space_catalog.py")], check=True)
    subprocess.run([sys.executable, str(PORTAL / "scripts" / "build_research_portfolio.py")], check=True)
    subprocess.run([sys.executable, str(PORTAL / "scripts" / "validate_projects.py")], check=True)
    subprocess.run([sys.executable, str(PORTAL / "scripts" / "verify_deployment.py")], check=True)

    return {
        "manifest_file_count": manifest["file_count"],
        "portfolio_total_files": evidence["portfolio"]["total_files"],
    }


def fast_forward_and_push(repo_dir: Path, message: str) -> str:
    subprocess.run(["git", "-C", str(repo_dir), "fetch", "origin", "main"], check=True)
    parent = subprocess.check_output(["git", "-C", str(repo_dir), "rev-parse", "origin/main"], text=True).strip()
    subprocess.run(["git", "-C", str(repo_dir), "add", "-A"], check=True)
    tree = subprocess.check_output(["git", "-C", str(repo_dir), "write-tree"], text=True).strip()
    parent_tree = subprocess.check_output(["git", "-C", str(repo_dir), "rev-parse", "origin/main^{tree}"], text=True).strip()
    if tree == parent_tree:
        return parent
    commit = subprocess.check_output(
        ["git", "-C", str(repo_dir), "commit-tree", tree, "-p", parent, "-m", message],
        text=True,
    ).strip()
    subprocess.run(["git", "-C", str(repo_dir), "update-ref", "refs/heads/main", commit], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "push", "origin", "main"], check=True)
    return commit


def push_all(projects: list[str], message: str) -> dict[str, str]:
    from huggingface_hub import HfApi

    results: dict[str, str] = {}
    results["monorepo"] = fast_forward_and_push(MONO, message)

    for proj in projects:
        results[proj] = fast_forward_and_push(SCRATCH / proj, message)

    api = HfApi()
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copy2(PORTAL / "build" / "hf-dataset" / "README.md", stage / "README.md")
        shutil.copy2(PORTAL / "build" / "hf-dataset" / "dataset_manifest.json", stage / "dataset_manifest.json")
        for proj in projects:
            src = MONO / proj
            dst = stage / proj
            for p in src.rglob("*"):
                if any(part in EXCLUDED for part in p.parts):
                    continue
                rel = p.relative_to(src)
                target = dst / rel
                if p.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, target)
        ds_info = api.upload_folder(
            repo_id="ShawnChamberlain/open-economic-quant-research-data",
            repo_type="dataset",
            folder_path=str(stage),
            commit_message=message,
        )
        results["hf_dataset"] = ds_info.oid

    ev_path = PORTAL / "assets" / "data" / "evidence.json"
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    ev["dataset_revision"] = results["hf_dataset"]
    ev_path.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")

    subprocess.run([sys.executable, str(PORTAL / "scripts" / "build_space_catalog.py")], check=True)
    subprocess.run([sys.executable, str(PORTAL / "scripts" / "build_research_portfolio.py")], check=True)
    subprocess.run([sys.executable, str(PORTAL / "scripts" / "verify_deployment.py")], check=True)

    sp_info = api.upload_folder(
        repo_id="ShawnChamberlain/open-economic-quant-research-observatory",
        repo_type="space",
        folder_path=str(PORTAL / "apps" / "space"),
        commit_message=message,
        allow_patterns=[
            "README.md",
            "index.html",
            "styles.css",
            "portfolio.css",
            "app.js",
            "evidence.json",
            "microstructure_backtest_reference.json",
            "favicon.svg",
            "catalog/*.json",
            "figures/*.svg",
        ],
    )
    results["hf_space"] = sp_info.oid
    results["portal"] = fast_forward_and_push(PORTAL, message)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Synchronize Open Economic & Quant ecosystem")
    ap.add_argument(
        "--projects",
        default="EMFactorTiming,PolymarketFactors,CryptoFactors",
        help="Comma-separated list of project directories to sync",
    )
    ap.add_argument("--verify-only", action="store_true", help="Run monorepo verification only")
    ap.add_argument("--sync-local", action="store_true", help="Sync local standalone checkouts and portal")
    ap.add_argument("--push-all", action="store_true", help="Push all changes to GitHub and Hugging Face")
    ap.add_argument("--message", default="Sync Open Economic & Quant ecosystem", help="Commit message for --push-all")
    args = ap.parse_args()

    subprocess.run([sys.executable, str(MONO / "scripts" / "verify_monorepo.py")], check=True)
    if args.verify_only:
        return

    projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    if args.sync_local or args.push_all:
        sync_summary = sync_local_files(projects)
        print("sync-local-ok", json.dumps(sync_summary))
    if args.push_all:
        push_summary = push_all(projects, args.message)
        print("push-all-ok", json.dumps(push_summary, indent=2))


if __name__ == "__main__":
    main()
