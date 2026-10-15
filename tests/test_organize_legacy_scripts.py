"""Safety tests for reversible historic script archiving; no actual profiles touched."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import unittest
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import organize_legacy_scripts as org


class ArchiveLegacyScriptsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        profiles = root / ".local" / "profiles"
        catalog = root / ".local" / "catalog"
        profiles.mkdir(parents=True)
        catalog.mkdir(parents=True)
        self.root = root
        self.profiles = profiles
        self.catalog = catalog
        values = {"ROOT": root, "PROFILE": profiles, "CATALOG": catalog,
                  "PREFLIGHT": catalog / "script_move_preflight.json",
                  "DEEP": catalog / "script_move_preflight_deep.json",
                  "NESTED": catalog / "nested_script_references.json",
                  "MANIFEST": catalog / "archived_legacy_scripts_2026-10-15.json"}
        for key, value in values.items():
            p = patch.object(org, key, value)
            p.start()
            self.addCleanup(p.stop)

    def prepare(self, *, referenced=False, sha_bad=False):
        src = self.profiles / "phase14c_old_example.py"
        src.write_text("print('example')\n", encoding="utf8")
        rel = src.relative_to(self.root).as_posix()
        sha = org.digest(src)
        old = {"path": rel, "bytes": src.stat().st_size,
               "sha256": "bad" if sha_bad else sha}
        (self.catalog / "script_move_preflight.json").write_text(
            json.dumps({"scripts": [old]}), encoding="utf8")
        (self.catalog / "script_move_preflight_deep.json").write_text(
            json.dumps({"candidates": [[rel, src.stat().st_size]],
                        "references": {src.name: ["docs/status.md"] if referenced else []}}),
            encoding="utf8")
        (self.catalog / "nested_script_references.json").write_text("{}", encoding="utf8")
        return src

    def test_group_labels(self):
        self.assertEqual(org.label("phase14f_oracle.py"), "cfg-phase14")
        self.assertEqual(org.label("phase8_result.py"), "cpu-phases")
        self.assertEqual(org.label("tecno_screen_small.py"), "tecno")
        self.assertEqual(org.label("fix_notes.py"), "oneoff-edits")

    def test_plan_requires_matching_sha_and_age(self):
        src = self.prepare()
        now = src.stat().st_mtime + 15 * 3600
        self.assertEqual(len(org.proposed(5, now=now)), 1)
        self.assertEqual(org.proposed(5, now=src.stat().st_mtime + 1), [])
        self.prepare(sha_bad=True)
        self.assertEqual(org.proposed(5, now=now), [])

    def test_skip_referenced_script(self):
        src = self.prepare(referenced=True)
        self.assertEqual(org.proposed(5, now=src.stat().st_mtime + 15 * 3600), [])

    def test_archive_restore_preserves_exact_bytes(self):
        src = self.prepare()
        original = src.read_bytes()
        moves = org.proposed(5, now=src.stat().st_mtime + 15 * 3600)
        org.apply(moves)
        target = self.root / moves[0]["new"]
        self.assertFalse(src.exists())
        self.assertEqual(target.read_bytes(), original)
        with self.assertRaises(RuntimeError):
            org.apply(moves)
        org.restore()
        self.assertEqual(src.read_bytes(), original)
        self.assertFalse(target.exists())

    def test_restore_refuses_overwrite_or_changed_archive(self):
        src = self.prepare()
        moves = org.proposed(5, now=src.stat().st_mtime + 15 * 3600)
        org.apply(moves)
        target = self.root / moves[0]["new"]
        target.write_text("tampered", encoding="utf8")
        with self.assertRaises(RuntimeError):
            org.restore()
        self.assertFalse(src.exists())


if __name__ == "__main__":
    unittest.main()
