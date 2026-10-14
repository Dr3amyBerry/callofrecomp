"""Tests for GL state observer reports using synthetic inputs."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"/"recomp"/"diagnostics"))
from analyze_gl_vk_capture import analyze
class GLVulkanStateReportTests(unittest.TestCase):
    @staticmethod
    def line(tracked,unsupported,mask,ready=0):
        return (f"gl vkstate: tracked={tracked} unsupported={unsupported} mask=0x{mask:x} "
                f"state_ready={ready} mvproj_hash=5ee87785 depth=1 blend=1 "
                f"stencil=0 alpha=1 tex0=1201 tex1=1102 matrix_push=0 matrix_pop=0")
    def test_counters_cumulative_not_frame_rates(self):
        d=analyze(self.line(100,200,0x10)+"\n"+self.line(140,290,0x19))
        self.assertEqual(d["samples"],2)
        self.assertEqual(d["tracked_delta_first_to_last"],40)
        self.assertEqual(d["unsupported_delta_first_to_last"],90)
        self.assertEqual(d["unsupported_mask_union"],"0x19")
        self.assertIn("untranslated_legacy_gl",d["unsupported_categories"])
        self.assertFalse(d["vulkan_backend_present"])
        self.assertFalse(d["fps_comparable"])
        self.assertFalse(d["subset_ready_in_any_sample"])
    def test_new_capture_family_histogram_optional_backcompat(self):
        family=" legacy_tex=10 legacy_upload=4 legacy_matrix=5 legacy_vertex=2 legacy_light=3 legacy_buffer=1 legacy_other=7"
        more=" legacy_tex=20 legacy_upload=9 legacy_matrix=6 legacy_vertex=6 legacy_light=13 legacy_buffer=1 legacy_other=14"
        d=analyze(self.line(11,32,0x10)+family+"\n"+self.line(13,69,0x10)+more)
        self.assertEqual(d["legacy_family_deltas"]["texture_state"],10)
        self.assertEqual(d["legacy_family_deltas"]["lighting_fog"],10)
        self.assertEqual(d["legacy_family_totals_last"]["other"],14)
        self.assertEqual(d["unsupported_delta_first_to_last"],37)
    def test_no_real_markers_fails(self):
        with self.assertRaisesRegex(ValueError,"No GL->Vulkan"):
            analyze("gl frame stats: fps=60")
    def test_mixed_sessions_fails(self):
        with self.assertRaisesRegex(ValueError,"decreased"):
            analyze(self.line(100,300,0x10)+"\n"+self.line(20,10,0))
    def test_ready_some_not_all(self):
        d=analyze(self.line(0,0,0,1)+"\n"+self.line(5,1,0x10,0))
        self.assertTrue(d["subset_ready_in_any_sample"])
        self.assertFalse(d["subset_ready_in_all_samples"])
if __name__=="__main__":
    unittest.main()
