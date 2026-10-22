"""Deterministic SHA-256 file hashing and run-manifest verification."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_manifest(
    project_slug: str,
    root: Path,
    files: Iterable[Path],
    evidence_grade: str,
) -> dict[str, object]:
    entries = []
    for file_path in sorted(files):
        rel = file_path.relative_to(root).as_posix()
        entries.append(
            {
                "path": rel,
                "size_bytes": file_path.stat().st_size,
                "sha256": compute_sha256(file_path),
            }
        )
    return {
        "project": project_slug,
        "evidence_grade": evidence_grade,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": len(entries),
        "files": entries,
    }


def verify_manifest_checksums(root: Path, manifest: dict[str, object]) -> list[str]:
    failures: list[str] = []
    for item in manifest.get("files", []):  # type: ignore[union-attr]
        rel = str(item["path"])
        target = root / rel
        if not target.exists():
            failures.append(f"missing:{rel}")
            continue
        observed = compute_sha256(target)
        if observed != item["sha256"]:
            failures.append(f"checksum_mismatch:{rel}")
    return failures
