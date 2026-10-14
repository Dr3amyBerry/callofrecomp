import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/recomp'))
from strategy_analyze_perf import aggregate_sample_rows
class StrategyAnalyzeTests(unittest.TestCase):
    def test_samples_are_not_double_counted(self):
        rows=[('libmain.so',0x1234,6,1,10,'f'),
              ('libGL.so',0x3456,7,1,10,'g'),
              ('libmain.so',0x1234,6,1,11,'f'),
              ('libmain.so',0x5678,7,1,10,'h')]
        x=aggregate_sample_rows(rows)
        self.assertEqual(x['total_cpu_samples'],4)
        self.assertEqual(x['libmain_cpu_samples'],3)
        self.assertEqual(x['by_dso']['libGL.so'],1)
        self.assertEqual(x['_main_pcs'][0x1234],2)
        self.assertEqual(x['by_thread'][0]['samples'],3)
        self.assertEqual(x['by_cpu'][6],2)
    def test_empty_record_rejected(self):
        with self.assertRaises(ValueError):aggregate_sample_rows([])
if __name__=='__main__':unittest.main()
