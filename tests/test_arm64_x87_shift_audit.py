"""An auditor must not report success with Python assertions disabled."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ARM64ShiftAuditTests(unittest.TestCase):
    def test_optimized_python_is_rejected_before_any_compilation_or_output(self):
        for module in ('verify_arm64_x87_shifts','verify_arm64_dispatch'):
            with self.subTest(module=module):
                code=('from pathlib import Path; '
                      f'from tools.recomp.diagnostics.{module} import verify; '
                      'verify(Path("unused-compiler"),Path("unused-output"),4)')
                proc=subprocess.run([sys.executable,'-O','-c',code],cwd=ROOT,
                                    capture_output=True,text=True,timeout=10)
                self.assertNotEqual(proc.returncode,0)
                self.assertIn('optimized Python',proc.stderr)


if __name__=='__main__':unittest.main()
