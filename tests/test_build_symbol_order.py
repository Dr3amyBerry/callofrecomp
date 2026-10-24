import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/recomp/diagnostics'))
from build_symbol_order import build_order

class T(unittest.TestCase):
    def test_rank_dedup_limit(self):
        self.assertEqual(build_order(['1.0% b', '5.5% a', '0.5% b', '# c', '3% c']), ['a', 'c', 'b'])
        self.assertEqual(build_order(['10 a', '20 b', '5 c'], limit=2), ['b', 'a'])
        self.assertEqual(build_order(['x', 'y']), ['x', 'y'])
        self.assertEqual(build_order(['99 a', '1 b'], min_share=0.05), ['a'])
if __name__ == '__main__':
    unittest.main()
