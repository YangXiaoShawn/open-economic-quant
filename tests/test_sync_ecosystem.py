"""Tests for scripts/sync_ecosystem.py: default project set, stale-file deletion, and the HF license guard."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sync_ecosystem import (  # noqa: E402
    SYNC_PROJECTS,
    build_parser,
    hf_upload_plan,
    mirror_project,
    project_data_license,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestSyncEcosystem(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_projects_cover_all_eight(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.projects.split(","), list(SYNC_PROJECTS))
        self.assertEqual(len(SYNC_PROJECTS), 8)
        self.assertFalse(args.no_delete)
        self.assertFalse(args.allow_unknown_license)

    def _split_checkout(self) -> tuple[Path, Path]:
        src = self.tmp / "mono" / "Proj"
        dst = self.tmp / "Proj"
        _write(src / ".gitignore", "cache/\n")
        _write(src / "kept.py", "new\n")
        _write(src / "pkg" / "added.py")
        _git(self.tmp, "init", "-q", str(dst))
        _write(dst / ".gitignore", "cache/\n")
        _write(dst / "kept.py", "old\n")
        _write(dst / "stale.py")
        _write(dst / "old_dir" / "gone.py")
        _git(dst, "add", ".gitignore", "kept.py", "stale.py", "old_dir/gone.py")
        _write(dst / "local_notes.txt")  # untracked
        _write(dst / "cache" / "download.bin")  # gitignored
        return src, dst

    def test_mirror_removes_only_stale_tracked_files(self) -> None:
        src, dst = self._split_checkout()
        removed = mirror_project(src, dst)
        self.assertEqual(sorted(removed), ["old_dir/gone.py", "stale.py"])
        self.assertEqual((dst / "kept.py").read_text(encoding="utf-8"), "new\n")
        self.assertTrue((dst / "pkg" / "added.py").is_file())
        self.assertFalse((dst / "old_dir").exists())
        self.assertTrue((dst / "local_notes.txt").is_file())
        self.assertTrue((dst / "cache" / "download.bin").is_file())
        self.assertTrue((dst / ".git" / "HEAD").is_file())

    def test_mirror_no_delete_keeps_stale_files(self) -> None:
        src, dst = self._split_checkout()
        self.assertEqual(mirror_project(src, dst, delete=False), [])
        self.assertTrue((dst / "stale.py").is_file())
        self.assertTrue((dst / "pkg" / "added.py").is_file())

    def _workspace(self, data_license: str) -> Path:
        root = self.tmp / "ws"
        proj = root / "Proj"
        _git(self.tmp, "init", "-q", str(root))
        _write(root / ".gitignore", "Proj/data/raw/\nProj/artifacts/\n")
        _write(proj / "project.yaml", f"title: Proj\ndata_license: {data_license}\n")
        _write(proj / "src" / "code.py")
        _write(proj / "data" / "fixtures" / "sample.csv")
        _write(proj / "reports" / "raw" / "tracked_table.csv")
        _git(root, "add", ".gitignore", "Proj/project.yaml", "Proj/src/code.py", "Proj/data/fixtures/sample.csv",
             "Proj/reports/raw/tracked_table.csv")
        _write(proj / "data" / "raw" / "download.parquet")  # gitignored third-party snapshot
        _write(proj / "artifacts" / "full_month.csv")  # gitignored derived artifact
        _write(proj / "data" / "nyc_full" / "panel.parquet")  # untracked, not ignored
        return root

    def test_rights_unknown_project_withholds_untracked_ignored_and_raw(self) -> None:
        root = self._workspace("RIGHTS_UNKNOWN for raw third-party sources; fixtures are publishable.")
        published, withheld = hf_upload_plan("Proj", root=root)
        self.assertEqual(published, ["data/fixtures/sample.csv", "project.yaml", "src/code.py"])
        self.assertEqual(
            withheld,
            ["artifacts/full_month.csv", "data/nyc_full/panel.parquet", "data/raw/download.parquet",
             "reports/raw/tracked_table.csv"],
        )

    def test_allow_unknown_license_publishes_everything(self) -> None:
        root = self._workspace("RIGHTS_UNKNOWN")
        published, withheld = hf_upload_plan("Proj", allow_unknown_license=True, root=root)
        self.assertEqual(withheld, [])
        self.assertEqual(len(published), 7)

    def test_licensed_project_is_not_restricted(self) -> None:
        root = self._workspace("Source-specific terms apply.")
        published, withheld = hf_upload_plan("Proj", root=root)
        self.assertEqual(withheld, [])
        self.assertIn("data/raw/download.parquet", published)

    def test_rights_unknown_projects_in_this_repo_are_detected(self) -> None:
        for proj in ("CasualLab", "Macroeconomics"):
            self.assertIn("RIGHTS_UNKNOWN", project_data_license(ROOT / proj))
        for proj in ("RealEstate", "TariffIncidence", "Microstructure", "EMFactorTiming", "PolymarketFactors",
                     "CryptoFactors"):
            self.assertNotIn("RIGHTS_UNKNOWN", project_data_license(ROOT / proj))


if __name__ == "__main__":
    unittest.main()
