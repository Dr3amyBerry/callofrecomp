"""Diagnostic APK flags must be available without changing default builds."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'tools/recomp/build_android.py'

class ProfileBuildFlagsTest(unittest.TestCase):
    def test_help_offers_opt_in_cpu_and_gl_diagnostics(self):
        proc = subprocess.run([sys.executable, str(BUILDER), '--help'],
                              capture_output=True, text=True, check=True)
        self.assertIn('--cpu-profile', proc.stdout)
        self.assertIn('--gl-profile', proc.stdout)
        self.assertIn('--gl-time-profile', proc.stdout)
        self.assertIn('--gl-vk-state-capture', proc.stdout)
        self.assertIn('--wsa-uncap-bench', proc.stdout)
        self.assertIn('--render-o2', proc.stdout)
        self.assertIn('--hot-x87-transform', proc.stdout)
        self.assertIn('--fast-copy32', proc.stdout)
        self.assertIn('--visibility-o2', proc.stdout)
        self.assertIn('--x87-nan-bits', proc.stdout)
        self.assertIn('--x87-normal-f2d', proc.stdout)
        self.assertIn('--x87-fcom-fastpath', proc.stdout)

    def test_wsa_uncap_is_rejected_for_arm64(self):
        proc = subprocess.run(
            [sys.executable, str(BUILDER), '--abi', 'arm64-v8a',
             '--wsa-uncap-bench'],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('for --abi x86_64 WSA only', proc.stderr)

if __name__ == '__main__':
    unittest.main()
