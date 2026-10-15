"""Non-device unit tests for the private artifact workflow."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import local_workspace as ws
from tools import local_capture as capture


class LocalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.local = self.root / ".local"
        self.profiles = self.local / "profiles"
        self.profiles.mkdir(parents=True)
        self.patchers = (
            patch.object(ws, "ROOT", self.root),
            patch.object(ws, "LOCAL", self.local),
            patch.object(ws, "PROFILES", self.profiles),
            patch.object(ws, "INDEX", self.local / "catalog" / "profiles_index.json"),
            patch.object(capture, "ROOT", self.root),
            patch.object(capture, "PROFILES", self.profiles),
        )
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_unique_runs_and_layout(self):
        clock = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
        a = ws.create_run("wsa", "renderer-gl", now=clock)
        b = ws.create_run("wsa", "renderer-gl", now=clock)
        self.assertNotEqual(a, b)
        for run in (a, b):
            self.assertTrue(all((run / item).is_dir() for item in ws.DIRS))
            data = json.loads((run / "session.json").read_text(encoding="utf8"))
            self.assertEqual(data["target"], "wsa")
            self.assertEqual(data["study"], "renderer-gl")

    def test_path_traversal_and_bad_names_fail(self):
        for name in ("../bad", "C:\\bad", "bad name", "", ".hidden", "CAPS"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    ws.check_slug(name)
        with self.assertRaises(ValueError):
            ws.create_run("invalid", "test")
        with self.assertRaises(ValueError):
            capture.capture_path(self.profiles / ".." / "elsewhere", "screen")

    def test_capture_png_exclusive_no_overwrites(self):
        run = ws.create_run("tecno", "training")
        dest = capture.capture_path(run, "scene-a")
        raw = b"\x89PNG\r\n\x1a\n" + b"data"
        capture.write_png(dest, raw)
        self.assertEqual(dest.read_bytes(), raw)
        with self.assertRaises(FileExistsError):
            capture.write_png(dest, raw)
        with self.assertRaises(ValueError):
            capture.write_png(capture.capture_path(run, "scene-b"), b"NO PNG")

    def test_find_prefers_canonical_tools(self):
        data = {"files": [
            {"path": ".local/profiles/run_capture_android_old.py", "kind": "script"},
            {"path": "tools/recomp/capture_android_strategy.py", "kind": "script"},
            {"path": ".local/profiles/blah.png", "kind": "capture"}
        ]}
        out = ws.candidates("capture android", data, "script")
        self.assertEqual(out[0]["path"], "tools/recomp/capture_android_strategy.py")
        self.assertEqual(len(out), 2)

    def test_index_excludes_third_party_and_follows_no_symlinks(self):
        (self.profiles / "phase14_test.py").write_text("pass", encoding="utf8")
        third = self.profiles / "angle-research"
        third.mkdir()
        (third / "external.py").write_text("pass", encoding="utf8")
        data = ws.index_files()
        paths = [x["path"] for x in data["files"]]
        self.assertIn(".local/profiles/phase14_test.py", paths)
        self.assertFalse(any("external.py" in x for x in paths))
        ws.save_index(data)
        stored = json.loads(ws.INDEX.read_text(encoding="utf8"))
        self.assertEqual(stored["count"], data["count"])

    def test_adb_capture_requires_explicit_serial(self):
        with self.assertRaises(ValueError):
            capture.capture_android("")
        with self.assertRaises(ValueError):
            capture.capture_android("bad serial; rm")


if __name__ == "__main__":
    unittest.main()
