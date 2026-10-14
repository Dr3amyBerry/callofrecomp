import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from summarize_wsa_vk_surface import parse_one

class WsaVkSurfaceTests(unittest.TestCase):
    def test_cannot_confuse_native_clear_with_game_fps(self):
        ready="VK_READY width=1280 height=720 gpu=AMD Radeon Graphics image_count=5 fifo=2 immediate_available=0 present_mode=2"
        prefix="VK_INIT NativeActivity created; waiting for Android surface\n"+ready+"\n"
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=1.9000\n"
        result="VK_RESULT fps=75.000 frames=1275 seconds=17.000 thread_cpu_ms_per_frame=1.90000 acquire_wall_ms_per_frame=11.55000 present_wall_ms_per_frame=0.03000 present_mode=FIFO resolution=1280x720"
        sample=prefix+window*16+result
        d=parse_one(sample)
        self.assertEqual(d["average_fps"],75)
        self.assertFalse(d["gameplay_fps_comparable"])
        self.assertFalse(d["immediate_available"])
        self.assertEqual(d["one_second_windows"],16)
    def test_indexed_mesh_pipeline_is_reported_separately_from_clear_and_game(self):
        prefix=("VK_INIT NativeActivity created; waiting for Android surface\n"
                "VK_MESH_READY vertices=4 indices=6 draws_per_frame=1 procedural_checker=1\n"
                "VK_SCENE name=mesh, integration=standalone, gameplay=0\n"
                "VK_READY width=1280 height=720 gpu=AMD image_count=5 fifo=2 immediate_available=0 present_mode=2\n")
        window="VK_WINDOW fps=75.000 frames=75 elapsed=1.000 thread_cpu_ms_per_frame=1.9100\n"
        result=("VK_RESULT fps=75.000 frames=1275 seconds=17.000 thread_cpu_ms_per_frame=1.91000 "
                "acquire_wall_ms_per_frame=11.54000 present_wall_ms_per_frame=0.03100 "
                "present_mode=FIFO resolution=1280x720")
        data=parse_one(prefix+window*16+result)
        self.assertEqual(data['scene'],'mesh')
        self.assertEqual(data['mesh']['vertices'],4)
        self.assertEqual(data['mesh']['indices'],6)
        self.assertTrue(data['mesh']['procedural_checker'])
        self.assertFalse(data['gameplay_fps_comparable'])
        self.assertIn('indexed quad',data['workload'])

    def test_mesh_without_successful_pipeline_must_fail(self):
        text=("VK_INIT NativeActivity created; waiting for Android surface\n"
              "VK_SCENE name=mesh, integration=standalone, gameplay=0\n")
        with self.assertRaisesRegex(ValueError,'pipeline'):
            parse_one(text)

    def test_fails_closed_on_missing_swapchain_presentation(self):
        with self.assertRaises(ValueError): parse_one("vkCreateInstance=0\nvkCreateSurface=0")
        with self.assertRaises(ValueError): parse_one("VK_INIT NativeActivity created; waiting for Android surface")
    def test_mismatch_frames_rejected(self):
        ready="VK_READY width=1280 height=720 gpu=AMD image_count=5 fifo=2 immediate_available=1 present_mode=0"
        s="VK_INIT NativeActivity created; waiting for Android surface\n"+ready+"\n"+"VK_WINDOW fps=10 frames=10 elapsed=1.0 thread_cpu_ms_per_frame=1.0\n"*12
        s+="VK_RESULT fps=150.000 frames=10 seconds=16.000 thread_cpu_ms_per_frame=1 acquire_wall_ms_per_frame=1 present_wall_ms_per_frame=1 present_mode=IMMEDIATE resolution=1280x720"
        with self.assertRaises(ValueError):parse_one(s)
if __name__=='__main__':unittest.main()
