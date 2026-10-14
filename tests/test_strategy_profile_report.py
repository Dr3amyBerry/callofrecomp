import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/recomp'))
from strategy_profile_report import make_report,sample_time_ms
class ProfileStrategyReportTests(unittest.TestCase):
    def test_task_clock_ms_math(self):
        self.assertAlmostEqual(sample_time_ms(350,hz=350,duration_s=20,fps=25),2.0)
        for kwargs in ({'hz':0,'duration_s':20,'fps':25},{'hz':350,'duration_s':0,'fps':25}):
            with self.assertRaises(ValueError):sample_time_ms(10,**kwargs)
    def test_report_keeps_diagnostic_counter_unmodified(self):
        analysis={
            'total_cpu_samples':1000,'libmain_cpu_samples':850,
            'by_dso':{'libmain.so':850,'libGLES_mali.so':80,'libGL.so':25},
            'by_thread':[{'tid':44,'samples':900}],
            'resolved_guest':{
                'top_body_function_samples':[
                    {'module':'codsp','entry_va':'0x0041b8f0','samples':120},
                    {'module':'codsp','entry_va':'0x004d94c0','samples':64}],
                'unresolved_source_samples':140,'unique_ghidra_body_samples':700
            }
        }
        frame='frame stats: fps=25.0 ms avg=40.0 min=30.0 max=50.0 cpu=38.0 swap=2.0 pace=0.0\n'
        report=make_report(analysis,frame*40,hz=350,duration_s=20)
        self.assertEqual(report['status'],'DIAGNOSTIC_ONLY_NOT_A_PERFORMANCE_ATTEMPT')
        self.assertAlmostEqual(report['profile']['dsos'][0]['indicative_cpu_ms_per_frame'],
                               round(sample_time_ms(850,hz=350,duration_s=20,fps=25),3))
        self.assertEqual(report['profile']['guest_functions'][0]['name'],'codsp/0x0041b8f0')
        self.assertEqual(report['profile']['unresolved_native_source_samples'],140)
        self.assertAlmostEqual(report['reference_cpu_budget_excess_ms'],21.333,places=2)
    def test_short_frame_capture_is_not_accepted(self):
        analysis={'total_cpu_samples':1,'libmain_cpu_samples':1,'by_dso':{},
                  'by_thread':[],'resolved_guest':{'top_body_function_samples':[]}}
        with self.assertRaises(ValueError):
            make_report(analysis,'frame stats: fps=25.0 ms avg=40.0 min=40.0 max=40.0 cpu=38.0 swap=2.0 pace=0.0',
                        hz=350,duration_s=20)
if __name__=='__main__': unittest.main()
