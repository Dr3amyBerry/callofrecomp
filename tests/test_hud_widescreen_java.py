"""Compile and run the no-game-assets Java HUD aspect/PK3 unit test."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA = shutil.which("java")
JAVAC = shutil.which("javac")


@unittest.skipUnless(JAVA and JAVAC, "JDK not available in this environment")
class HudWidescreenJavaTest(unittest.TestCase):
    def test_private_overlay_and_square_icons(self):
        with tempfile.TemporaryDirectory() as directory:
            compiler = subprocess.run([
                JAVAC, "-encoding", "UTF-8", "-source", "8", "-target", "8",
                "-d", directory,
                str(ROOT / "android/java/org/callofrecomp/HudWidescreen.java"),
                str(ROOT / "tests/HudWidescreenSmoke.java"),
            ], capture_output=True, text=True, timeout=70)
            self.assertEqual(compiler.returncode, 0, compiler.stderr)
            execution = subprocess.run([
                JAVA, "-cp", directory, "org.callofrecomp.HudWidescreenSmoke",
            ], capture_output=True, text=True, timeout=70)
            self.assertEqual(execution.returncode, 0, execution.stderr + execution.stdout)
            self.assertIn("PASS", execution.stdout)


if __name__ == "__main__":
    unittest.main()
