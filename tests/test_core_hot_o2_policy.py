"""Phase13 profile-guided whole-core compiler policy, OFF by default."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
CMAKE=ROOT/"android/CMakeLists.txt"

class HotCoreCompilePolicyTests(unittest.TestCase):
    def policy_block(self):
        text=CMAKE.read_text(encoding="utf-8")
        begin=text.index("option(CODRECOMP_CORE_HOT_O2")
        end=text.index("option(CODRECOMP_HOT_X87_FASTPATH",begin)
        return text[begin:end]

    def test_coDSP_hot_windows_only_not_visibility(self):
        block=self.policy_block()
        self.assertIn("foreach(part p0 p1 p4)",block)
        self.assertNotIn("foreach(part p0 p1 p4 p8)",block)
        self.assertIn('COMPILE_OPTIONS "-O2;-ffp-contract=off"',block)
        self.assertIn('if(NOT ANDROID_ABI STREQUAL "arm64-v8a")',block)
        self.assertIn('if(NOT RECOMP_OPTIMIZATION STREQUAL "1")',block)

    def test_exact_private_binary_guard_and_off_default(self):
        block=self.policy_block()
        self.assertRegex(block,r'option\(CODRECOMP_CORE_HOT_O2\s+.+OFF\)')
        self.assertIn('file(SHA256 "${profile_pcode}" profile_pcode_hash)',block)
        self.assertIn('36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e',block)

if __name__=="__main__":
    unittest.main()
