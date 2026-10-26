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
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

MONO = Path(__file__).resolve().parents[1]
SCRATCH = MONO.parent
PORTAL_CANDIDATES = sorted(SCRATCH.glob("YangXiaoShawn.github.io*"))
PORTAL = PORTAL_CANDIDATES[0] if PORTAL_CANDIDATES else SCRATCH / "YangXiaoShawn.github.io"

EXCLUDED = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data_binance",
    "data_perp",
    "data_okx",
}

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


# Never published to the Hugging Face dataset, whatever the project's data license says.
HF_NEVER_UPLOAD = ("Microstructure/artifacts/", "Microstructure/data/raw/")
UNKNOWN_LICENSE_MARKER = "RIGHTS_UNKNOWN"
# Gitignored paths that are nevertheless published to the dataset (aggregated result
# tables and data-access notes); every other gitignored file stays local by default.
HF_PUBLISH_IGNORED: dict[str, tuple[str, ...]] = {
    "CryptoFactors": ("data/DATA_ACCESS.md", "data/results/"),
    "PolymarketFactors": ("data/DATA_ACCESS.md",),
}


def git_ls_files(repo: Path, subdir: str | None = None, ignored: bool = False) -> set[str] | None:
    """Return paths in the git index of ``repo`` (relative to ``subdir`` when given).

    With ``ignored``, return the untracked files git ignores instead. Returns None when
    ``repo`` is not the root of a git checkout, so callers never act on the index of an
    enclosing repository by accident.
    """
    if not (repo / ".git").exists():
        return None
    cmd = ["git", "-C", str(repo), "ls-files", "-z"]
    if ignored:
        cmd += ["--others", "--ignored", "--exclude-standard"]
    if subdir:
        cmd += ["--", subdir]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = [p for p in out.split("\0") if p]
    if not subdir:
        return set(paths)
    prefix = f"{subdir}/"
    return {p[len(prefix):] for p in paths if p.startswith(prefix)}


def _prune_empty_dirs(directory: Path, stop: Path) -> None:
    while directory != stop and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def mirror_project(src_dir: Path, dst_dir: Path, delete: bool = True) -> list[str]:
    """Copy ``src_dir`` over ``dst_dir`` and return the stale paths removed from ``dst_dir``.

    With ``delete``, files the destination checkout tracks in git but the source no longer
    has are removed, so deletions in the monorepo reach the split repository. Only tracked
    paths inside ``dst_dir`` are candidates: ``.git``, EXCLUDED paths and local untracked or
    gitignored files (caches, downloaded data) are never touched.
    """
    removed: list[str] = []
    if delete:
        dst_root = dst_dir.resolve()
        for rel in sorted(git_ls_files(dst_dir) or ()):
            parts = rel.split("/")
            if parts[0] == ".git" or any(part in EXCLUDED for part in parts):
                continue
            if (src_dir / rel).is_file():
                continue
            target = dst_dir / rel
            if not target.resolve().is_relative_to(dst_root):
                continue
            if target.is_file() or target.is_symlink():
                target.unlink()
                removed.append(rel)
                _prune_empty_dirs(target.parent, dst_dir)

    for p in src_dir.rglob("*"):
        rel = p.relative_to(src_dir)
        if any(part in EXCLUDED for part in rel.parts):
            continue
        target = dst_dir / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    return removed


def project_data_license(proj_dir: Path) -> str:
    yaml_path = proj_dir / "project.yaml"
    if not yaml_path.is_file():
        return ""
    match = re.search(r"^data_license:[ \t]*(.*)$", yaml_path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def hf_upload_plan(proj: str, allow_unknown_license: bool = False, root: Path = MONO) -> tuple[list[str], list[str]]:
    """Split a project's files into (published, withheld) paths for the Hugging Face dataset.

    Gitignored files (raw downloads, registered or licensed extracts, local caches) are
    withheld unless listed in HF_PUBLISH_IGNORED. A project whose project.yaml declares
    ``data_license: RIGHTS_UNKNOWN`` additionally publishes only files tracked in git and
    nothing under a ``raw/`` directory. ``allow_unknown_license`` lifts both restrictions.
    """
    src_dir = root / proj
    guarded = not allow_unknown_license
    unknown_rights = UNKNOWN_LICENSE_MARKER in project_data_license(src_dir)
    tracked = git_ls_files(root, proj) if guarded else set()
    ignored = git_ls_files(root, proj, ignored=True) if guarded else set()
    published: list[str] = []
    withheld: list[str] = []
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src_dir).as_posix()
        if any(part in EXCLUDED for part in rel.split("/")) or f"{proj}/{rel}".startswith(HF_NEVER_UPLOAD):
            continue
        if guarded and (
            tracked is None
            or ignored is None
            or (rel in ignored and not rel.startswith(HF_PUBLISH_IGNORED.get(proj, ())))
            or (unknown_rights and (rel not in tracked or "raw" in rel.split("/")[:-1]))
        ):
            withheld.append(rel)
        else:
            published.append(rel)
    return published, withheld


def report_withheld(proj: str, withheld: list[str], root: Path = MONO) -> None:
    if not withheld:
        return
    size = sum((root / proj / rel).stat().st_size for rel in withheld)
    reason = "gitignored" if UNKNOWN_LICENSE_MARKER not in project_data_license(root / proj) else (
        f"gitignored, untracked or raw/ data of a {UNKNOWN_LICENSE_MARKER} project"
    )
    print(
        f"hf-skip {proj}: withholding {len(withheld)} files ({size / 1e6:.1f} MB): {reason}; "
        "pass --allow-unknown-license once redistribution rights are confirmed"
    )
    groups = Counter("/".join(rel.split("/")[:2]) if "/" in rel else rel for rel in withheld)
    for group, count in sorted(groups.items()):
        print(f"  {proj}/{group}: {count} file(s)")


def sync_local_files(projects: list[str], delete: bool = True, allow_unknown_license: bool = False) -> dict[str, int]:
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
        for rel in mirror_project(src_dir, dst_dir, delete=delete):
            print(f"sync-delete {proj}/{rel}")

    manifest_path = PORTAL / "build" / "hf-dataset" / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prefixes = tuple(f"{p}/" for p in projects)
    files = [f for f in manifest["files"] if not f["path"].startswith(prefixes)]

    for proj in projects:
        published, _ = hf_upload_plan(proj, allow_unknown_license)
        for rel in published:
            files.append({"path": f"{proj}/{rel}", "size_bytes": (MONO / proj / rel).stat().st_size})

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


def push_all(projects: list[str], message: str, allow_unknown_license: bool = False) -> dict[str, str]:
    from huggingface_hub import HfApi

    # Decide what may be published before the commits below start tracking new files.
    upload_plan = {proj: hf_upload_plan(proj, allow_unknown_license) for proj in projects}
    for proj, (_, withheld) in upload_plan.items():
        report_withheld(proj, withheld)

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
            published, _ = upload_plan[proj]
            for rel in published:
                target = stage / proj / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(MONO / proj / rel, target)
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


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Synchronize Open Economic & Quant ecosystem")
    ap.add_argument(
        "--projects",
        default=",".join(SYNC_PROJECTS),
        help="Comma-separated list of project directories to sync (default: all eight)",
    )
    ap.add_argument("--verify-only", action="store_true", help="Run monorepo verification only")
    ap.add_argument("--sync-local", action="store_true", help="Sync local standalone checkouts and portal")
    ap.add_argument("--push-all", action="store_true", help="Push all changes to GitHub and Hugging Face")
    ap.add_argument("--message", default="Sync Open Economic & Quant ecosystem", help="Commit message for --push-all")
    ap.add_argument(
        "--no-delete",
        action="store_true",
        help="Do not remove files from standalone checkouts that no longer exist in the monorepo",
    )
    ap.add_argument(
        "--allow-unknown-license",
        action="store_true",
        help=(
            "Publish every file on disk to the HF dataset, including gitignored files and the untracked "
            "or raw/ files of projects whose data_license is RIGHTS_UNKNOWN"
        ),
    )
    return ap


def main() -> None:
    args = build_parser().parse_args()

    subprocess.run([sys.executable, str(MONO / "scripts" / "verify_monorepo.py")], check=True)
    if args.verify_only:
        return

    projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    if args.sync_local or args.push_all:
        sync_summary = sync_local_files(
            projects, delete=not args.no_delete, allow_unknown_license=args.allow_unknown_license
        )
        print("sync-local-ok", json.dumps(sync_summary))
    if args.push_all:
        push_summary = push_all(projects, args.message, allow_unknown_license=args.allow_unknown_license)
        print("push-all-ok", json.dumps(push_summary, indent=2))


if __name__ == "__main__":
    main()
