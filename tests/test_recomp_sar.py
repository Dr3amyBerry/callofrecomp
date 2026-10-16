"""Independent portable byte oracle for ARM64 narrow signed SAR."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SignedSARTests(unittest.TestCase):
    def test_host_byte_oracle_with_and_without_specialization(self):
        cc = os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not cc:
            self.skipTest('No C compiler installed')
        with tempfile.TemporaryDirectory() as directory:
            for level in ('0','1','2'):
                for enabled in (False,True):
                    with self.subTest(level=level,enabled=enabled):
                        exe = Path(directory) / 'sar.exe'
                        command = [cc,'-O'+level,'-I',str(ROOT/'tools/recomp'),
                                   str(ROOT/'tests/recomp_sar_smoke.c'),'-o',str(exe)]
                        if enabled:command.append('-DCODRECOMP_ARM64_NARROW_SAR')
                        subprocess.run(command,capture_output=True,text=True,check=True,timeout=60)
                        subprocess.run([str(exe)],check=True,timeout=35)

    def test_only_arm64_optin_uses_new_sar(self):
        rt = (ROOT/'tools/recomp/recomp_rt.h').read_text(encoding='utf8')
        cm = (ROOT/'android/CMakeLists.txt').read_text(encoding='utf8')
        self.assertIn('#ifdef CODRECOMP_ARM64_NARROW_SAR',rt)
        self.assertIn('option(CODRECOMP_ARM64_NARROW_SAR',cm)
        block=cm.split('option(CODRECOMP_ARM64_NARROW_SAR',1)[1].split('# Dispatch last-hit',1)[0]
        self.assertIn('OFF)',block)
        self.assertIn('if(NOT ANDROID_ABI STREQUAL "arm64-v8a")',block)
        self.assertIn('target_compile_definitions(main PRIVATE CODRECOMP_ARM64_NARROW_SAR)',block)

if __name__=='__main__':
    unittest.main()
