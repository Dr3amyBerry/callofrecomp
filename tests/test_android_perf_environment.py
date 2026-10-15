"""Android read-only environment sampling and thermal/frequency parsing."""
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.recomp.diagnostics import android_perf_environment as probe


BATTERY = """Current Battery Service state:
 USB powered: true
 level: 98
 temperature: 410
"""
THERMAL = """Thermal Status: 0
Cached temperatures:
  Temperature{mValue=79.0, mType=0, mName=CPU, mStatus=0}
Current temperatures from HAL:
  Temperature{mValue=56.4, mType=0, mName=CPU, mStatus=0}
  Temperature{mValue=54.4, mType=1, mName=GPU, mStatus=0}
  Temperature{mValue=40.0, mType=3, mName=SKIN, mStatus=0}
Current cooling devices from HAL:
 CoolingDevice{mValue=0, mType=2, mName=cpu_adaptive_0}
"""

class AndroidPerformanceEnvironmentTests(unittest.TestCase):
    def test_battery_parsing(self):
        r=probe.parse_battery(BATTERY)
        self.assertEqual(r["battery_temperature_c"],41.0)
        self.assertEqual(r["battery_level_pct"],98)
        self.assertTrue(r["usb_powered"])

    def test_missing_battery_remains_null(self):
        self.assertIsNone(probe.parse_battery(None)["battery_temperature_c"])
        self.assertIsNone(probe.parse_battery("n/a")["usb_powered"])

    def test_thermal_parses_current_not_stale_cache(self):
        r=probe.parse_thermal(THERMAL)
        self.assertEqual(r["thermal_status"],0)
        self.assertEqual(r["hal_cpu_temp_c"],56.4)
        self.assertEqual(r["hal_gpu_temp_c"],54.4)
        self.assertEqual(r["hal_skin_temp_c"],40.0)

    def test_thermal_missing_is_null(self):
        r=probe.parse_thermal("ThermalEventListeners: none")
        self.assertIsNone(r["thermal_status"])
        self.assertIsNone(r["hal_cpu_temp_c"])

    def test_snapshot_missing_cpu_freq_does_not_fake_value(self):
        def simulated(serial,*args,timeout=12):
            if args==("dumpsys","battery"):return BATTERY
            if args==("dumpsys","thermalservice"):return THERMAL
            if "cpu7" in args[-1]:return None
            if "cpu0" in args[-1]:return "1450000"
            return None
        with patch.object(probe,"adb_read",side_effect=simulated):
            r=probe.snapshot("CK6N01",cpu_ids=(0,7))
        self.assertEqual(r["freq_readable_cores"],1)
        self.assertEqual(r["cpu_freq_khz"]["0"],1450000)
        self.assertIsNone(r["cpu_freq_khz"]["7"])

    def test_validate_cpu_ids(self):
        with self.assertRaises(ValueError):
            probe.snapshot("CK6N01",cpu_ids=())
        with self.assertRaises(ValueError):
            probe.snapshot("CK6N01",cpu_ids=(64,))

    def test_shell_args_use_list_not_interpolation(self):
        with patch.object(probe.subprocess,"run") as mocked:
            mocked.return_value.returncode=0
            mocked.return_value.stdout="1450000\n"
            got=probe.adb_read("101202538N103635","cat",
                               "/sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq")
        self.assertEqual(got,"1450000")
        self.assertEqual(mocked.call_args.args[0][0:4],
                         ["adb","-s","101202538N103635","shell"])
        with self.assertRaises(ValueError):
            probe.adb_read("serial; rm", "cat", "/x")

    def test_collection_can_stop_cleanly_with_one_sample(self):
        stop=threading.Event()
        def fake_snapshot(serial):
            stop.set()
            return {"utc":"2026-10-15","cpu_freq_khz":{"7":2000000}}
        with patch.object(probe,"snapshot",side_effect=fake_snapshot):
            r=probe.collect("TEST_SERIAL",duration_sec=20,interval_sec=3,stop=stop)
        self.assertEqual(len(r["samples"]),1)
        self.assertTrue(r["read_only"])

    def test_duration_and_interval_limits(self):
        with self.assertRaises(ValueError):
            probe.collect("CK6N01",duration_sec=0.1)
        with self.assertRaises(ValueError):
            probe.collect("CK6N01",duration_sec=60,interval_sec=0.01)


if __name__=="__main__":
    unittest.main()
