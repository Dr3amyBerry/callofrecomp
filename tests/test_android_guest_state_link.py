"""Local guest data must not hide JNI/SDL or change owned ELF behavior."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
MAP=ROOT/'android/guest_state.map'

class GuestStateLinkTests(unittest.TestCase):
    def test_android_option_is_explicit_and_wsa_only(self):
        cmake=(ROOT/'android/CMakeLists.txt').read_text()
        self.assertIn('option(CODRECOMP_LOCAL_GUEST_STATE "WSA experiment: bind guest data within libmain" OFF)',cmake)
        result=subprocess.run([sys.executable,str(ROOT/'tools/recomp/build_android.py'),
                               '--abi','arm64-v8a','--local-guest-state'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--local-guest-state requires --abi x86_64',result.stderr)

    def test_only_internal_state_is_local(self):
        text=MAP.read_text()
        self.assertEqual(text.split('local:')[1].split('}')[0].split(),['R;','MEM;','U;','PC;'])
        self.assertIn('global: *;',text)

    @unittest.skipUnless(os.name=='posix' and os.environ.get('RECOMP_TEST_CC'),'ELF host compiler')
    def test_owned_elf_exports_and_state_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'owned.c';library=folder/'owned.so'
            source.write_text('''#include <stdint.h>
uint8_t R[32],*MEM; unsigned U[32],PC;
int SDL_main(int a,char **b){(void)b;R[3]=(uint8_t)a;PC+=R[3];return PC;}
int Java_org_callofrecomp_GameActivity_nativeInput(void){return R[3];}
''')
            subprocess.run([os.environ['RECOMP_TEST_CC'],'-shared','-fPIC','-O1',str(source),
                            '-Wl,--version-script='+str(MAP),'-o',str(library)],check=True,capture_output=True)
            lib=ctypes.CDLL(str(library))
            self.assertEqual(lib.SDL_main(7,None),7)
            self.assertEqual(lib.SDL_main(5,None),12)
            self.assertEqual(lib.Java_org_callofrecomp_GameActivity_nativeInput(),5)
            for symbol in ('R','MEM','U','PC'):
                with self.assertRaises(AttributeError):getattr(lib,symbol)

if __name__=='__main__':unittest.main()
