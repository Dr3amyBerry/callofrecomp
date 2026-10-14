"""Pure comparison validation; no ADB, game files or proprietary screenshots."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from summarize_wsa_driver_ab import summarize, InvalidTrial


def row(backend, fps=55, p10=50, cpu=17.5):
    row={"device":"127.0.0.1:58526","profile":"Equilibrado",
         "scene":"Camp Toccoa training, static spawn","uncapped_diagnostic":False,
         "frame_summary_windows":30,"analyzed_last_windows":20,"pid":"123",
         "stats":{"count":20,"median_fps":fps,"p10_window_fps":p10,
                  "median_cpu_ms":cpu,"likely_mixed_loading_or_menu":False}}
    if backend=="angle":
        row["backend"]="angle"
        row["backend_before"]={"backend":"angle","vulkan_verified":True,
                               "log_evidence":{"angle_vulkan_execution_verified":True,
                                               "game_pid_checked":"123"}}
        row["backend_after"]=copy.deepcopy(row["backend_before"])
    else:
        row["backend"]="gl4es"
        row["backend_before"]={"driver_settings_clear":True}
        row["backend_after"]={"driver_settings_clear":True}
    return row


class TestWSADriverAB(unittest.TestCase):
    def test_near_identical_b_is_not_a_speedup(self):
        summary=summarize(row("gl4es",54.75,50.2,17.54),
                          row("angle",55.15,47.6,17.8),
                          row("gl4es",55.2,54.6,17.43))
        self.assertTrue(summary["comparison"]["b_median_between_a_controls"])
        self.assertTrue(summary["comparison"]["b_p10_lower_than_both_controls"])
        self.assertAlmostEqual(summary["comparison"]["b_vs_mean_a_fps_delta"],.175)
        self.assertIn("Do not replace GL4ES",summary["decision"])

    def test_refuses_missing_angle_vulkan_identity(self):
        a,b,c=row("gl4es"),row("angle"),row("gl4es")
        b["backend_after"]["log_evidence"]["angle_vulkan_execution_verified"]=False
        with self.assertRaises(InvalidTrial):summarize(a,b,c)
    def test_refuses_cross_pid_angle(self):
        a,b,c=row("gl4es"),row("angle"),row("gl4es")
        b["backend_before"]["log_evidence"]["game_pid_checked"]="999"
        with self.assertRaises(InvalidTrial):summarize(a,b,c)
    def test_refuses_mixed_loading_or_menu(self):
        a,b,c=row("gl4es"),row("angle"),row("gl4es")
        b["stats"]["likely_mixed_loading_or_menu"]=True
        with self.assertRaises(InvalidTrial):summarize(a,b,c)
    def test_refuses_mismatched_scene_or_profile(self):
        a,b,c=row("gl4es"),row("angle"),row("gl4es")
        c["scene"]="Main menu"
        with self.assertRaises(InvalidTrial):summarize(a,b,c)
    def test_refuses_gl4es_with_configured_angle(self):
        a,b,c=row("gl4es"),row("angle"),row("gl4es")
        a["backend_before"]["driver_settings_clear"]=False
        with self.assertRaises(InvalidTrial):summarize(a,b,c)
    def test_accepts_a1_legacy_reference_only_with_stage(self):
        a,b,c=row("gl4es"),row("angle"),row("gl4es")
        del a["backend"]
        a["stage"]="GL4ES gameplay baseline/control, NOT Vulkan renderer"
        self.assertIn("comparison", summarize(a,b,c))
        a["stage"]="Unknown"
        with self.assertRaises(InvalidTrial):summarize(a,b,c)


if __name__=="__main__":
    unittest.main()
