"""Compare a synthetic Vulkan device census with a synthetic Zink profile."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"/"recomp"/"diagnostics"))
from analyze_zink_requirements import analyze

def profile():
    return {
        "profiles":{"VP_ZINK_gl21_baseline":{"api-version":"1.2.0"}},
        "capabilities":{
            "vulkan10requirements":{"features":{"VkPhysicalDeviceFeatures":
                {"robustBufferAccess":True}}},
            "gl21_baseline":{
                "extensions":{"VK_KHR_maintenance5":1,"VK_KHR_create_renderpass2":1},
                "features":{"VkPhysicalDeviceFeatures":
                    {"logicOp":True,"alphaToOne":True}}
            }
        }
    }
def log(alpha=0,maintenance=0,core=1):
    return ("ZINK_GPU index=0 name=Test GPU api=1.3.0 vendor=0x1234 device=0x4567\n"
            "ZINK_FEATURE name=robustBufferAccess supported=1\n"
            "ZINK_FEATURE name=logicOp supported=1\n"
            f"ZINK_FEATURE name=alphaToOne supported={alpha}\n"
            f"ZINK_EXTENSION name=VK_KHR_maintenance5 supported={maintenance} advertised={maintenance} core_promoted=0\n"
            f"ZINK_EXTENSION name=VK_KHR_create_renderpass2 supported={core} advertised=0 core_promoted={core}\n"
            "ZINK_SUMMARY gpu=0 conservative_missing=2 full_profile_checked=0")
class ZinkProfileTests(unittest.TestCase):
    def test_real_blockers_and_core_promotions_distinguished(self):
        r=analyze(profile(),log())
        self.assertEqual(r["missing_required_core_features"],["alphaToOne"])
        self.assertEqual(r["missing_required_extensions_after_core_promotion"],
                         ["VK_KHR_maintenance5"])
        self.assertFalse(r["checked_baseline_compatible"])
        self.assertFalse(r["full_profile_checked"])
    def test_supported_subset_does_not_claim_complete_profile(self):
        r=analyze(profile(),log(alpha=1,maintenance=1))
        self.assertTrue(r["checked_baseline_compatible"])
        self.assertFalse(r["full_profile_checked"])
    def test_missing_census_rejected(self):
        with self.assertRaisesRegex(ValueError,"Incomplete census"):
            analyze(profile(),log().replace("ZINK_FEATURE name=alphaToOne supported=0\n",""))
    def test_wrong_profile_rejected(self):
        with self.assertRaisesRegex(ValueError,"does not contain"):
            analyze({"profiles":{}},log())
    def test_missing_gpu_report_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing or conflicting"):
            analyze(profile(),"no Vulkan devices")
if __name__=="__main__":
    unittest.main()
