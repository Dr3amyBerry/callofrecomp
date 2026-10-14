"""Offline contract checks for the MANUAL ANGLE build; never invoke network or ADB."""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REV = "43140711d13063716fd32a15de829885d0bce469"

class AngleBuildPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = (ROOT / "tools/recomp/diagnostics/build_angle_android_linux.sh").read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github/workflows/angle-manual-build.yml").read_text(encoding="utf-8")
    def test_build_pinned_to_verified_upstream_commit(self):
        self.assertIn(f'ANGLE_COMMIT="{REV}"', self.build)
        self.assertIn("chromium.googlesource.com/angle/angle.git", self.build)
        self.assertIn('gclient sync --revision "angle@$ANGLE_COMMIT"', self.build)
        self.assertIn('git -C angle rev-parse HEAD', self.build)
    def test_gn_android_wsa_vulkan_target(self):
        for arg in ('target_os = "android"', 'target_cpu = "x64"',
                    'angle_enable_vulkan = true', "angle_apks",
                    "AngleLibraries.apk.sha256"):
            self.assertIn(arg, self.build)
    def test_workflow_manual_only_and_readonly_github_permissions(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)
        self.assertNotIn("\n  pull_request:", self.workflow)
        self.assertRegex(self.workflow, r"permissions:\s+contents: read")
        self.assertIn("upload-artifact@v4", self.workflow)
    def test_linux_build_cannot_change_wsa_or_game(self):
        for word in ("adb install", "settings put", "git push", "org.callofrecomp"):
            self.assertNotIn(word, self.build)
        self.assertIn("Refusing to overwrite a nonempty workspace", self.build)
    def test_shell_syntax_if_native_bash_is_available(self):
        import os
        import shutil
        import subprocess
        if os.name == "nt":
            candidates = [Path("C:/Program Files/Git/bin/bash.exe"),
                          Path("C:/wit/bin/bash.exe")]
            bash = next((str(p) for p in candidates if p.is_file()), None)
        else:
            bash = shutil.which("bash")
        if not bash:
            self.skipTest("No Linux/Git Bash shell available to check -n syntax")
        run = subprocess.run([bash, "-n", str(ROOT / "tools/recomp/diagnostics/build_angle_android_linux.sh")],
                             capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
    def test_workflow_yaml_structure_when_yaml_is_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("Optional PyYAML not installed")
        obj = yaml.safe_load(self.workflow)
        triggers = obj.get("on", obj.get(True))
        self.assertEqual(triggers, {"workflow_dispatch": None})
        self.assertEqual(obj["permissions"], {"contents": "read"})
        self.assertEqual(len(obj["jobs"]), 1)

if __name__ == "__main__":
    unittest.main()
