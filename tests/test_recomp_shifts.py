"""Compile both logical-shift paths against an independent byte oracle."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LogicalShiftTests(unittest.TestCase):
    def test_byte_oracle_with_and_without_specialization(self):
        compiler = os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not compiler:
            self.skipTest('CTest supplies a C compiler')
        with tempfile.TemporaryDirectory() as directory:
            for optimization in ('0', '1', '2'):
                for enabled in (False, True):
                    with self.subTest(optimization=optimization, enabled=enabled):
                        binary = Path(directory) / 'shifts.exe'
                        command = [compiler, '-O' + optimization,
                                   '-I' + str(ROOT / 'tools/recomp'),
                                   str(ROOT / 'tests/recomp_shift_smoke.c'), '-o', str(binary)]
                        if enabled:
                            command.append('-DCODRECOMP_ARM64_NARROW_RIGHT_SHIFT')
                        subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
                        subprocess.run([str(binary)], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
