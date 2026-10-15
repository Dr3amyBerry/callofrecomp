"""Read-only artifact audit tests using temporary private trees."""
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

from tools import verify_local_artifacts as v


class ArtifactVerifierTests(unittest.TestCase):
    def setUp(self):
        self.t = TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        r = Path(self.t.name)
        local = r / ".local"
        profiles = local / "profiles"
        catalog = local / "catalog"
        catalog.mkdir(parents=True)
        profiles.mkdir(parents=True)
        self.r = r
        self.profile = profiles
        self.catalog = catalog
        for key, value in {"ROOT": r, "LOCAL": local, "PROFILES": profiles,
                           "CATALOG": catalog}.items():
            context = patch.object(v, key, value)
            context.start()
            self.addCleanup(context.stop)

    def test_manifest_verifies_hash_and_missing_old_source(self):
        dest = self.profile / "history" / "scripts" / "x.py"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"print(1)\n")
        record = {"old": ".local/profiles/x.py",
                  "new": ".local/profiles/history/scripts/x.py",
                  "bytes": dest.stat().st_size,
                  "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}
        manifest = self.catalog / "archived_legacy_scripts_2026-10-15.json"
        manifest.write_text(json.dumps({"moves": [record]}), encoding="utf8")
        result, errors = v.verify_move_manifest(manifest, "moves")
        self.assertEqual(result["verified"], 1)
        self.assertFalse(errors)
        dest.write_bytes(b"changed")
        result, errors = v.verify_move_manifest(manifest, "moves")
        self.assertTrue(errors)
        self.assertEqual(result["verified"], 0)

    def test_manifest_does_not_hash_archived_build_directory(self):
        dst = self.r / ".local" / "builds" / "history" / "a"
        dst.mkdir(parents=True)
        manifest = self.catalog / "archived_builds_2026-10-15.json"
        manifest.write_text(json.dumps({"moves": [["build-a", ".local/builds/history/a"]]}),
                            encoding="utf8")
        result, errors = v.verify_move_manifest(manifest, "moves")
        self.assertEqual(result["verified"], 1)
        self.assertFalse(errors)

    def test_session_layout_requires_all_subfolders(self):
        run = self.profile / "runs" / "shared" / "date" / "study" / "id"
        run.mkdir(parents=True)
        (run / "session.json").write_text(json.dumps({
            "created_utc": "2026-10-15T18:00:00Z", "target": "shared", "study": "test"
        }), encoding="utf8")
        result, errors = v.verify_runs()
        self.assertEqual(result["runs"], 1)
        self.assertEqual(len(errors), len(v.EXPECTED))
        for folder in v.EXPECTED:
            (run / folder).mkdir()
        result, errors = v.verify_runs()
        self.assertFalse(errors)

    def test_index_rejects_stale_old_path(self):
        indexed = self.catalog / "profiles_index.json"
        indexed.write_text(json.dumps({"count": 1, "indexed_utc": "2026-10-15",
                                       "files": [{"path": ".local/profiles/x.py"}]}), encoding="utf8")
        archived = self.catalog / "archived_legacy_scripts_2026-10-15.json"
        archived.write_text(json.dumps({"moves": [{"old": ".local/profiles/x.py",
                                                  "new": ".local/profiles/history/scripts/x.py"}]}),
                            encoding="utf8")
        result, errors = v.verify_index()
        self.assertEqual(len(errors), 2)

    def test_legacy_syntax_failure_is_reported_not_executed(self):
        good = self.profile / "ok.py"
        broken = self.profile / "broken.py"
        good.write_text("VALUE=1\n", encoding="utf8")
        broken.write_text("def not-valid\n", encoding="utf8")
        result, errors = v.verify_scripts()
        self.assertEqual(result["inspected"], 2)
        self.assertEqual(result["valid_ast"], 1)
        self.assertEqual(result["legacy_parse_errors"][0]["path"], ".local/profiles/broken.py")
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
