"""Offline safety/metadata tests; no game assets, ADB, or file changes in WSA."""
from __future__ import annotations
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/recomp/diagnostics"))
import wsa_save_guard as guard


class SaveGuardTests(unittest.TestCase):
    def test_only_known_save_directory(self):
        self.assertEqual(guard.valid_save_path(
            "files/profile/main/save/autosave/training.svg"), "autosave/training.svg")
        for invalid in ("", "files/profile/main/config.cfg",
                        "files/profile/main/save/../main/hack.svg",
                        "/files/profile/main/save/foo.svg",
                        "files/profile/main/save/.secrets",
                        "files/profile/main/save/a\nB",
                        "files/profile/main/save//two"):
            with self.subTest(invalid=invalid), self.assertRaises(guard.SaveGuardError):
                guard.valid_save_path(invalid)

    def test_manifest_is_deterministic_and_does_not_include_file_content(self):
        m = guard.manifest({"quicksave.svg": b"test content"})
        self.assertEqual(m["files"]["quicksave.svg"]["sha256"],
                         hashlib.sha256(b"test content").hexdigest())
        self.assertEqual(m["files"]["quicksave.svg"]["bytes"], 12)
        self.assertNotIn("test content", str(m))

    def test_refuse_paths_outside_private_folder(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(guard.SaveGuardError):
                guard.private_output_dir(Path(d))
        with self.assertRaises(guard.SaveGuardError):
            guard.private_output_dir(Path.cwd())

    def test_refuse_blank_snapshot(self):
        responses = [b"x86_64\n", b"windows_x86_64\n", b""]
        with patch.object(guard, "adb_bytes", side_effect=responses):
            with self.assertRaisesRegex(guard.SaveGuardError, "No existing saves"):
                guard.collect_saves()

    def test_inventory_rejects_non_wsa(self):
        with patch.object(guard, "adb_bytes", side_effect=[b"arm64-v8a\n", b"tecno\n"]) as adb:
            with self.assertRaises(guard.SaveGuardError):
                guard.collect_saves()
        self.assertEqual(adb.call_count, 2)

    def test_compare_expected_and_current_fingerprint(self):
        expected = guard.manifest({"quicksave.svg": b"a"})
        modified = guard.manifest({"quicksave.svg": b"b"})
        self.assertNotEqual(expected, modified)


if __name__ == "__main__":
    unittest.main()
