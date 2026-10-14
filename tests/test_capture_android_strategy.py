import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/recomp'))
from capture_android_strategy import safe_prefix,parse_build_id,base_apk_path
class CaptureStrategyTests(unittest.TestCase):
    def test_build_id_unique(self):
        self.assertEqual(parse_build_id('Build ID: 012345Abcdef'), '012345abcdef')
        with self.assertRaises(ValueError):parse_build_id('no build ID here')
        with self.assertRaises(ValueError):parse_build_id('Build ID: abc\nBuild ID: def')
    def test_only_base_apk(self):
        self.assertEqual(base_apk_path('package:/data/app/a/base.apk\npackage:/data/app/split_config.apk\n'),
                         '/data/app/a/base.apk')
        for s in ('', 'package:/data/app/z/split_config.apk\n'):
            with self.assertRaises(ValueError):base_apk_path(s)
    def test_no_output_path_traversal(self):
        for s in ('../escape','nested/test','C:\\unsafe','áé',''):
            self.assertFalse(safe_prefix(s))
        self.assertTrue(safe_prefix('tecno_spawn_A1-2026'))
if __name__=='__main__':unittest.main()
