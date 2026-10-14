"""Synthetic, offline checks for ANGLE readiness logic."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"/"recomp"/"diagnostics"))
from angle_readiness import classify,parse_package_path,parse_settings

class AngleReadinessTests(unittest.TestCase):
    def test_missing_angle_prevents_a_claim_of_running_vulkan(self):
        r=classify(True,33,True,True,False,None,None,None)
        self.assertTrue(r["architecture_candidate"])
        self.assertFalse(r["settings_point_to_angle"])
        self.assertFalse(r["vulkan_angle_execution_verified"])
        self.assertFalse(r["gameplay_fps_measured"])
        self.assertIn("Official AngleLibraries.apk is not installed",
                      r["blockers_for_current_test"])
    def test_configured_debuggable_app_still_not_proof_of_execution(self):
        r=classify(True,33,True,True,True,"org.callofrecomp","angle","org.chromium.angle")
        self.assertTrue(r["settings_point_to_angle"])
        self.assertFalse(r["vulkan_angle_execution_verified"])
    def test_old_android_blocked(self):
        r=classify(True,28,True,True,True,"org.callofrecomp","angle","org.chromium.angle")
        self.assertFalse(r["settings_point_to_angle"])
    def test_non_debug_app_blocked(self):
        r=classify(True,33,False,True,True,"org.callofrecomp","angle","org.chromium.angle")
        self.assertFalse(r["settings_point_to_angle"])
    def test_package_settings_and_selection(self):
        r=classify(True,33,True,True,True,
                   "com.other,org.callofrecomp","native,angle","org.chromium.angle")
        self.assertEqual(r["app_selection"],"angle")
        self.assertTrue(r["settings_point_to_angle"])
    def test_inconsistent_driver_setting_lists_are_not_accepted(self):
        r=classify(True,33,True,True,True,
                   "org.callofrecomp,com.other","angle","org.chromium.angle")
        self.assertEqual(r["app_selection"],"unspecified")
        self.assertFalse(r["settings_point_to_angle"])
    def test_package_path_requires_real_package(self):
        self.assertFalse(parse_package_path(1,""))
        self.assertFalse(parse_package_path(0,"null"))
        self.assertTrue(parse_package_path(0,"package:/data/app/sample/base.apk"))
    def test_null_settings_do_not_become_driver_ids(self):
        self.assertIsNone(parse_settings("null\n"))
        self.assertIsNone(parse_settings(""))
        self.assertEqual(parse_settings("angle\n"),"angle")
if __name__=="__main__":
    unittest.main()
