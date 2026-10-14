"""Offline smoke tests for the non-destructive WSA ANGLE activation guard."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
import angle_wsa_trial as trial


def baseline():
    return {
        "api": 33, "abi": "x86_64", "device": "windows_x86_64",
        "game_installed": True, "game_debuggable": True,
        "angle_installed": False, "game_running": False,
        "settings": {k: None for k in trial.SETTINGS},
    }


class AngleWSATrialTests(unittest.TestCase):
    def test_clean_wsa_is_candidate(self):
        self.assertEqual(trial.safe_for_trial(baseline()), [])
    def test_refuses_running_game(self):
        x = baseline()
        x["game_running"] = True
        self.assertTrue(trial.safe_for_trial(x))
    def test_refuses_another_device_or_custom_settings(self):
        x = baseline()
        x["abi"] = "arm64-v8a"
        x["settings"]["angle_debug_package"] = "another.package"
        self.assertGreaterEqual(len(trial.safe_for_trial(x)), 2)
    def test_refuses_overwriting_angle_package(self):
        x = baseline()
        x["angle_installed"] = True
        self.assertTrue(trial.safe_for_trial(x))
    def test_restore_settings_after_partial_install(self):
        x = baseline()
        with patch.object(trial, "adb", return_value="") as cmd, patch.object(
            trial, "setting_value", return_value=None
        ):
            errs = trial.restore("127.0.0.1:58526", x, True, True)
        self.assertEqual(errs, [])
        commands = [c.args for c in cmd.call_args_list]
        for k in trial.SETTINGS:
            self.assertIn(("127.0.0.1:58526", "shell", "settings", "delete", "global", k),
                          commands)
        self.assertIn(("127.0.0.1:58526", "uninstall", trial.ANGLE), commands)
        self.assertIn(("127.0.0.1:58526", "shell", "am", "force-stop", trial.GAME),
                      commands)
    def test_logcat_requires_fresh_same_pid_and_vulkan(self):
        fresh = (
            "         1791993905.100   123   123 I GraphicsEnvironment: ANGLE package enabled: org.chromium.angle\n"
            "         1791993905.301   123   124 I ANGLE   : Version (2.1), Renderer (Vulkan 1.3)\n"
        )
        x = trial.logcat_verdict(fresh, 1791993904, "123")
        self.assertTrue(x["angle_vulkan_execution_verified"])
        self.assertFalse(x["gameplay_fps_measured"])
        self.assertFalse(trial.logcat_verdict(fresh, 1791993906, "123")[
            "angle_vulkan_execution_verified"])
        self.assertFalse(trial.logcat_verdict(fresh, 1791993904, "456")[
            "angle_vulkan_execution_verified"])
        self.assertFalse(trial.logcat_verdict(fresh, 1791993904, None)[
            "angle_vulkan_execution_verified"])

    def test_real_wsa_angle_debug_package_log_verifies_vulkan(self):
        # Exact message variant seen with the official ANGLE x86_64 APK.
        log = (
            "         1791994760.343  9325  9325 I GraphicsEnvironment: ANGLE debug package enabled: org.chromium.angle\n"
            "         1791994760.505  9325  9343 I ANGLE   : Version (2.1.29111 git hash: 43140711d130), Renderer (Vulkan 1.3.0 (AMD Radeon(TM) Graphics (0x00001638)))\n"
        )
        result = trial.logcat_verdict(log, 1791994760, "9325")
        self.assertTrue(result["android_angle_package_selected"])
        self.assertTrue(result["angle_vulkan_renderer_reported"])
        self.assertTrue(result["angle_vulkan_execution_verified"])
        self.assertFalse(trial.logcat_verdict(log, 1791994761, "9325")[
            "angle_vulkan_execution_verified"])
        self.assertFalse(trial.logcat_verdict(log, 1791994760, "1234")[
            "angle_vulkan_execution_verified"])

    def test_logcat_rejects_mismatched_pid_and_unstructured_lines(self):
        log = (
            "ANGLE: Renderer (Vulkan 1.3)\n"
            "         1791993905.100   100   100 I GraphicsEnvironment: ANGLE package enabled: org.chromium.angle\n"
            "         1791993905.301   200   200 I ANGLE   : Version (2.1), Renderer (Vulkan 1.3)\n"
        )
        x = trial.logcat_verdict(log, 1791993904, "100")
        self.assertTrue(x["android_angle_package_selected"])
        self.assertFalse(x["angle_vulkan_renderer_reported"])
        self.assertFalse(x["angle_vulkan_execution_verified"])

    def test_partial_failure_still_restores(self):
        x = baseline()
        def fake_adb(serial, *args, **kwargs):
            if args[:5] == ("shell", "settings", "put", "global", "angle_debug_package"):
                raise trial.TrialError("simulated settings failure")
            if args[:3] == ("shell", "pm", "path"):
                return "package:/data/app/debug/base.apk"
            return ""
        with patch.object(trial, "snapshot", return_value=x), patch.object(
            trial, "inspect", return_value={"ready_for_isolated_trial": True,
                                           "sha256": "1"*64}
        ), patch.object(trial, "adb", side_effect=fake_adb), patch.object(
            trial, "restore", return_value=[]
        ) as cleanup:
            with self.assertRaisesRegex(trial.TrialError, "rollback:"):
                trial.run_trial(trial.SERIAL, Path("test.apk"), "1"*64,
                                "aapt", "apksigner", 10)
        self.assertEqual(cleanup.call_count, 1)
        self.assertTrue(cleanup.call_args.args[2])

    def test_runner_declares_no_fps_even_on_angle_logs(self):
        x = baseline()
        def fake_adb(serial, *args, **kwargs):
            if args[:3] == ("shell", "pm", "path"):
                return "package:/data/app/debug/base.apk"
            if args[:2] == ("shell", "date"):
                return "1791993904"
            if args[:3] == ("shell", "pidof", trial.GAME):
                return "123"
            if args[:2] == ("logcat", "-d"):
                return (
                    "         1791993905.100   123   123 I GraphicsEnvironment: ANGLE package enabled: org.chromium.angle\n"
                    "         1791993905.301   123   123 I ANGLE   : Version (2.1), Renderer (Vulkan 1.3)\n"
                )
            return ""
        with patch.object(trial, "snapshot", return_value=x), patch.object(
            trial, "inspect", return_value={"ready_for_isolated_trial": True,
                                           "sha256": "1"*64}
        ), patch.object(trial, "adb", side_effect=fake_adb), patch.object(
            trial, "restore", return_value=[]
        ) as cleanup, patch.object(trial.time, "sleep"):
            outcome = trial.run_trial(trial.SERIAL, Path("test.apk"), "1"*64,
                                      "aapt", "apksigner", 10)
        self.assertTrue(outcome["configuration_restored"])
        self.assertTrue(outcome["angle_vulkan_renderer_reported"])
        self.assertTrue(outcome["angle_vulkan_execution_verified"])
        self.assertFalse(outcome["gameplay_fps_measured"])
        self.assertTrue(cleanup.called)

    def test_exact_play_button_clicked_then_gameactivity_checked(self):
        xml = ('<hierarchy><node text="Jugar" package="org.callofrecomp" '
               'class="android.widget.Button" enabled="true" clickable="true" '
               'bounds="[25,100][125,160]"/></hierarchy>')
        def fake_adb(serial, *args, **kwargs):
            if args[:3] == ("shell", "cat", trial.UI_DUMP):
                return xml
            if args[:3] == ("shell", "dumpsys", "activity"):
                return "topResumedActivity=ActivityRecord{p org.callofrecomp/.GameActivity t3}"
            return ""
        with patch.object(trial, "adb", side_effect=fake_adb) as cmd, patch.object(trial.time, "sleep"):
            outcome = trial.launch_game_via_accessibility(trial.SERIAL)
        self.assertTrue(outcome["game_activity_resumed"])
        commands = [c.args for c in cmd.call_args_list]
        self.assertIn((trial.SERIAL, "shell", "input", "tap", "75", "130"), commands)
        self.assertIn((trial.SERIAL, "shell", "rm", "-f", trial.UI_DUMP), commands)

    def test_bad_or_disabled_ui_never_taps(self):
        xml = ('<hierarchy><node text="Jugar" package="org.callofrecomp" '
               'class="android.widget.Button" enabled="false" clickable="true" '
               'bounds="[25,100][125,160]"/></hierarchy>')
        def fake_adb(serial, *args, **kwargs):
            if args[:3] == ("shell", "cat", trial.UI_DUMP):
                return xml
            return ""
        with patch.object(trial, "adb", side_effect=fake_adb) as cmd:
            with self.assertRaises(trial.UILocatorError):
                trial.launch_game_via_accessibility(trial.SERIAL)
        commands = [c.args for c in cmd.call_args_list]
        self.assertFalse(any(c[:3] == (trial.SERIAL, "shell", "input") for c in commands))
        self.assertIn((trial.SERIAL, "shell", "rm", "-f", trial.UI_DUMP), commands)

    def test_blocks_before_install_if_running(self):
        x = baseline()
        x["game_running"] = True
        with patch.object(trial, "snapshot", return_value=x), patch.object(
            trial, "adb"
        ) as cmd:
            with self.assertRaises(trial.TrialError):
                trial.run_trial(trial.SERIAL, Path("sample.apk"), "0"*64,
                                "aapt", "apksigner", 20)
        cmd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
