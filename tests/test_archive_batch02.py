"""Offline end-to-end tests of the next private-archive batch.

No ADB, old profiles, engine binaries or real history are touched.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_private_script_refs as audit
from tools import organize_legacy_scripts as archive
from tools import verify_local_artifacts as verify


class SecondArchiveBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / ".local"
        self.profiles = self.local / "profiles"
        self.catalog = self.local / "catalog"
        self.catalog.mkdir(parents=True)
        self.profiles.mkdir(parents=True)
        fields = (
            (audit, {"ROOT": self.root, "PRIVATE": self.local,
                     "PROFILE": self.profiles, "CATALOG": self.catalog}),
            (archive, {"ROOT": self.root, "PROFILE": self.profiles,
                       "CATALOG": self.catalog,
                       "MANIFEST": self.catalog / "archived_legacy_scripts_2026-10-15.json"}),
            (verify, {"ROOT": self.root, "LOCAL": self.local,
                      "PROFILES": self.profiles, "CATALOG": self.catalog}),
        )
        for module, attrs in fields:
            for attr, value in attrs.items():
                p = patch.object(module, attr, value)
                p.start()
                self.addCleanup(p.stop)
        self.time = time.time()
        self.old = self.time - 15 * 3600

    def script(self, name="phase14e_sample.py", content="x = 10\n"):
        path = self.profiles / name
        path.write_text(content, encoding="utf-8")
        os.utime(path, (self.old, self.old))
        return path

    def audit_to_disk(self):
        data = audit.analyze(2, now=self.time)
        dest = self.catalog / "script_preflight_batch02.json"
        dest.write_text(json.dumps(data), encoding="utf-8")
        return data

    def test_catalog_json_does_not_create_fake_dependency(self):
        self.script()
        (self.catalog / "old_catalog.json").write_text(
            json.dumps({"script": "phase14e_sample.py"}), encoding="utf-8")
        result = self.audit_to_disk()
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["path"],
                         ".local/profiles/phase14e_sample.py")

    def test_reference_in_an_archived_script_blocks_move(self):
        self.script()
        archived = self.profiles / "history" / "scripts" / "cfg-phase14"
        archived.mkdir(parents=True)
        (archived / "prior.py").write_text(
            "old = '.local/profiles/phase14e_sample.py'\n", encoding="utf-8")
        result = self.audit_to_disk()
        self.assertEqual(result["candidate_count"], 0)
        self.assertIn("named_reference", result["scripts"][0]["reasons"])

    def test_relative_file_or_sibling_import_blocks_move(self):
        self.script("phase14e_self.py", "print(__file__)\n")
        self.script("phase14e_dep.py", "import phase14e_self\n")
        result = self.audit_to_disk()
        self.assertEqual(result["candidate_count"], 0)
        reasons = {Path(x["path"]).name: x["reasons"] for x in result["scripts"]}
        self.assertIn("relative_to_script", reasons["phase14e_self.py"])
        self.assertIn("sibling_imports", reasons["phase14e_dep.py"])

    def test_batch02_archives_and_restores_without_touching_batch01(self):
        old = self.script()
        original = old.read_bytes()
        report = self.audit_to_disk()
        self.assertEqual(report["candidate_count"], 1)
        moves = archive.proposed(10, now=self.time, batch_id=2)
        self.assertEqual(len(moves), 1)
        self.assertNotEqual(archive.manifest_for(1), archive.manifest_for(2))
        old_manifest = archive.manifest_for(1)
        old_manifest.write_text("PRESERVE OLD", encoding="utf-8")
        new_manifest = archive.manifest_for(2)
        archive.apply(moves, new_manifest)
        target = self.root / moves[0]["new"]
        self.assertFalse(old.exists())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(old_manifest.read_text(encoding="utf-8"), "PRESERVE OLD")
        # The mock first manifest is not JSON; validate the second directly.
        self.assertEqual(verify.verify_move_manifest(new_manifest, "moves")[0]["verified"], 1)
        with self.assertRaises(RuntimeError):
            archive.apply(moves, new_manifest)
        archive.restore(new_manifest)
        self.assertEqual(old.read_bytes(), original)
        self.assertFalse(target.exists())
        self.assertEqual(old_manifest.read_text(encoding="utf-8"), "PRESERVE OLD")

    def test_preflight_must_be_recent_and_unchanged(self):
        old = self.script()
        self.audit_to_disk()
        old.write_text("altered\n", encoding="utf-8")
        os.utime(old, (self.old, self.old))
        self.assertEqual(archive.proposed(20, now=self.time, batch_id=2), [])
        with self.assertRaises(ValueError):
            archive.proposed(20, now=self.time + 7200, batch_id=2)

    def test_verifier_aggregates_two_independent_manifests(self):
        records = []
        for idx in (1, 2):
            name = f"phase14e_{idx}.py"
            target = self.profiles / "history" / "scripts" / "cfg-phase14" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"value={idx}\n", encoding="utf-8")
            item = {
                "old": f".local/profiles/{name}",
                "new": target.relative_to(self.root).as_posix(),
                "bytes": target.stat().st_size, "sha256": verify.sha256(target)
            }
            manifest = archive.manifest_for(idx)
            manifest.write_text(json.dumps({"moves": [item]}), encoding="utf-8")
            records.append(item)
        checks, errors = verify.verify_script_archives()
        self.assertFalse(errors)
        self.assertEqual(checks["count"], 2)
        self.assertEqual(checks["verified"], 2)
        self.assertEqual(len(checks["batches"]), 2)
        (self.catalog / "profiles_index.json").write_text(
            json.dumps({"count": 2, "indexed_utc": "now",
                        "files": [{"path": item["new"]} for item in records]}),
            encoding="utf-8")
        _, index_errors = verify.verify_index()
        self.assertFalse(index_errors)


if __name__ == "__main__":
    unittest.main()
