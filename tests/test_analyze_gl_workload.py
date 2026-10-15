"""GL windows need frame-weighted accounting, never GPU/FPS inference."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/recomp/diagnostics'))
from analyze_gl_workload import analyze

def window(frames,draws,indices,draw_us):
    return (f'gl profile: frames={frames} arrays=0 elements=0 ranges={draws} array_verts=0 indices={indices} tex_bind=0 tex_image=0 tex_sub=0 buf_bind=0 buf_data_bytes=0 buf_sub_bytes=0 lock=0 unlock=0 active_tex=0\n'
            f'gl cpu: frames={frames} draw_calls={draws} draw_us={draw_us} tex_bind_calls=0 tex_bind_us=0 tex_upload_calls=0 tex_upload_us=0 array_calls=0 array_us=0 lock_calls=0 lock_us=0 state_calls=0 state_us=0 buffer_calls=0 buffer_us=0\n')

class GLWorkloadTest(unittest.TestCase):
    def test_weight_by_frames_and_select_only_tail_windows(self):
        result=analyze(window(1,999,999,999)+window(10,20,100,1000)+window(30,30,300,3000),last=2)
        self.assertEqual(result['profile_frames'],40)
        self.assertEqual(result['guest_counters_per_frame']['ranges'],1.25)
        self.assertEqual(result['guest_counters_per_frame']['indices'],10)
        self.assertEqual(result['thread_cpu_ms_per_frame']['draw'],0.1)
        self.assertIn('not GPU',result['limitations'])

    def test_reject_missing_zero_or_incomplete_windows(self):
        for text,last in (('',1),(window(0,0,0,0),1),(window(1,1,1,1),2),
                          (window(1,1,1,1).replace('indices=1','indices=-1'),1)):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):analyze(text,last=last)

if __name__=='__main__':unittest.main()
