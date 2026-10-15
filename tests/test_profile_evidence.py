"""Contracts for the reusable profile evidence verifier.

Temporary toy files only: no TECNO device, ADB, real ELF, perf.data or APK.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import os
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.recomp.diagnostics import profile_evidence as ep


class ProfileEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "runs" / "shared" / "study" / "metrics").mkdir(parents=True)

    def make(self, name: str, data: bytes):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_hash_correct_for_multiple_files(self):
        self.make("cpu/a.perf.data", b"one")
        self.make("cpu/b.json", b"two")
        result = ep.hash_files(self.root, ["cpu/a.perf.data", "cpu/b.json"])
        self.assertEqual(result["kind"], "profile_evidence_hashes")
        self.assertEqual(result["files"][0]["sha256"],
                         hashlib.sha256(b"one").hexdigest())
        self.assertEqual(result["files"][1]["size_bytes"], 3)

    def test_manifest_saves_once_then_rejects_overwrite(self):
        self.make("cpu/a.perf.data", b"one")
        doc = ep.hash_files(self.root, ["cpu/a.perf.data"])
        name = "runs/shared/study/metrics/sha.json"
        ep.save_hashes(self.root, name, doc)
        result = ep.verify_hashes(self.root, name)
        self.assertEqual(result["verified"], 1)
        self.assertEqual(result["status"], "pass")
        with self.assertRaises(FileExistsError):
            ep.save_hashes(self.root, name, doc)

    def test_refuses_tampered_evidence(self):
        src = self.make("cpu/a.perf.data", b"one")
        name = "runs/shared/study/metrics/sha.json"
        ep.save_hashes(self.root, name, ep.hash_files(self.root, ["cpu/a.perf.data"]))
        src.write_bytes(b"two")
        result = ep.verify_hashes(self.root, name)
        self.assertEqual(result["verified"], 0)
        self.assertEqual(result["status"], "fail")

    def test_rejects_duplicate_and_missing_files(self):
        self.make("a.data", b"data")
        with self.assertRaises(ep.EvidenceError):
            ep.hash_files(self.root, ["a.data", "a.data"])
        with self.assertRaises(ep.EvidenceError):
            ep.hash_files(self.root, ["missing"])

    def test_rejects_traversal_and_absolute_paths(self):
        self.make("a.data", b"data")
        for name in ("../outside.data", "..\\outside.data" if os.name == "nt" else "../x",
                     str(self.root / "a.data")):
            with self.subTest(name=name):
                with self.assertRaises(ep.EvidenceError):
                    ep.safe_file(self.root, name)

    def test_rejects_symlink_outside_tree_when_supported(self):
        outside = self.root.parent / "does-not-exist"
        link = self.root / "external.json"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Windows symlink not available")
        with self.assertRaises(ep.EvidenceError):
            ep.safe_file(self.root, "external.json")

    def test_metadata_compares_build_ids_and_requires_complete(self):
        for n in ("a", "b"):
            self.make(n + ".json", json.dumps({
                "status": "complete", "installed_unstripped_build_id": "1234abcd1234abcd",
                "resolved_guest": {"native_samples_total": 42},
                "utc": "2026-10-15T00:00:00Z"
            }).encode())
        result = ep.metadata(self.root, ["a.json", "b.json"],
                             require_same_build=True, require_complete=True)
        self.assertEqual(result["same_build_id"], "1234abcd1234abcd")
        self.assertEqual(result["metadata"][0]["fields"]["resolved_native_samples_total"], 42)
        self.make("b.json", json.dumps({
            "status": "complete", "installed_unstripped_build_id": "aaaaaaaabbbbbbbb"
        }).encode())
        with self.assertRaisesRegex(ep.EvidenceError, "differ"):
            ep.metadata(self.root, ["a.json", "b.json"], require_same_build=True)

    def test_missing_identity_cannot_pass_same_build_gate(self):
        self.make("a.json", b'{"status":"complete"}')
        with self.assertRaisesRegex(ep.EvidenceError, "Build ID missing"):
            ep.metadata(self.root, ["a.json"], require_same_build=True)
        self.make("a.json", b'{"status":"partial","installed_unstripped_build_id":"1234abcd"}')
        with self.assertRaisesRegex(ep.EvidenceError, "incomplete"):
            ep.metadata(self.root, ["a.json"], require_complete=True)

    def test_inventory_is_bounded_and_filtered(self):
        self.make("tecno_cpu.json", b"{}")
        self.make("simpleperf_run.data", b"123")
        self.make("generic-unrelated.json", b"{}")
        result = ep.inventory(self.root, limit=1)
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["results"]), 1)
        self.assertTrue(result["truncated"])
        self.assertEqual(ep.inventory(self.root, token="tecno")["count"], 1)

    def test_output_only_in_existing_metrics_directory(self):
        self.make("cpu.json", b"{}")
        doc = ep.hash_files(self.root, ["cpu.json"])
        for invalid in ("output.json", "../output.json", "runs/unknown/metrics/a.json",
                        "runs/shared/study/logs/a.json"):
            with self.subTest(path=invalid):
                with self.assertRaises(ep.EvidenceError):
                    ep.save_hashes(self.root, invalid, doc)

    def test_metadata_cannot_expose_unexpected_json_keys(self):
        self.make("a.json", json.dumps({
            "status": "complete", "password": "private", "api_key": "abc"
        }).encode())
        output = ep.metadata(self.root, ["a.json"])
        self.assertEqual(output["metadata"][0]["fields"], {"status": "complete"})
        self.assertNotIn("password", json.dumps(output))
        self.assertNotIn("api_key", json.dumps(output))


if __name__ == "__main__":
    unittest.main()
