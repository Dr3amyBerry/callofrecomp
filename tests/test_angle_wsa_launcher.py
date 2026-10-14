"""Offline, no-ADB tests for optional UI entry into the real game."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from angle_wsa_launcher import UILocatorError, game_activity_resumed, play_button_center

NODE = ('<node text="Jugar" package="org.callofrecomp" '
        'class="android.widget.Button" enabled="true" clickable="true" '
        'bounds="[10,40][110,80]"/>')

class AngleWSALauncherTests(unittest.TestCase):
    def test_finds_unique_enabled_button(self):
        self.assertEqual(play_button_center(f"<hierarchy>{NODE}</hierarchy>"), (60,60))
    def test_rejects_no_or_duplicate_buttons(self):
        with self.assertRaises(UILocatorError):
            play_button_center("<hierarchy/>")
        with self.assertRaises(UILocatorError):
            play_button_center(f"<hierarchy>{NODE}{NODE}</hierarchy>")
    def test_does_not_click_on_another_package(self):
        with self.assertRaises(UILocatorError):
            play_button_center("<hierarchy>" + NODE.replace(
                "org.callofrecomp", "com.attacker.app") + "</hierarchy>")
    def test_disabled_button_and_invalid_coordinates(self):
        for changed in [NODE.replace('enabled="true"','enabled="false"'),
                        NODE.replace('clickable="true"','clickable="false"'),
                        NODE.replace('[10,40][110,80]','[110,40][10,80]'),
                        NODE.replace('[10,40][110,80]','[10,40][99999,80]')]:
            with self.assertRaises(UILocatorError):
                play_button_center(f"<hierarchy>{changed}</hierarchy>")
    def test_malformed_xml_fail_closed(self):
        with self.assertRaises(UILocatorError):
            play_button_center("<hierarchy><node")
    def test_game_activity_must_be_in_resumed_record(self):
        self.assertTrue(game_activity_resumed(
            "topResumedActivity=ActivityRecord{p org.callofrecomp/.GameActivity t2}"))
        self.assertFalse(game_activity_resumed(
            "mResumedActivity: ActivityRecord{p org.callofrecomp/.LauncherActivity t2}\n"
            "ActivityRecord{p org.callofrecomp/.GameActivity t1}"))


if __name__ == "__main__":
    unittest.main()
