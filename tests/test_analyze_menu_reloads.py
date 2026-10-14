"""Pure synthetic fixtures: no proprietary game resources or logs are needed."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "recomp"))
from analyze_menu_reloads import analyze_menu_reloads


LOG = """----- R_Init -----
Parsing menu file:ui/main.menu
Parsing menu file:ui/options.menu
UI menu load time = 1099 milli seconds
Parsing menu file:ui/pregame.menu
UI menu load time = 397 milli seconds
--- Common Initialization Complete ---
RE_Shutdown( 0 )
------ Server Initialization ------
Hunk_Clear: reset the hunk ok
----- R_Init -----
Parsing menu file:ui/main.menu
Parsing menu file:ui/options.menu
UI menu load time = 1102 milli seconds
Parsing menu file:ui/pregame.menu
UI menu load time = 414 milli seconds
UI menu load time = 33 milli seconds
CL_InitCGame:  7.89 seconds
"""


class MenuReloadsTest(unittest.TestCase):
    def test_reports_cross_cycle_reloads_and_ignores_orphan_timer(self):
        report = analyze_menu_reloads(LOG)
        self.assertEqual(report["renderer_initializations_observed"], 2)
        self.assertFalse(report["menu_cycles"][0]["after_hunk_clear"])
        self.assertTrue(report["menu_cycles"][1]["after_hunk_clear"])
        self.assertEqual(report["menu_parse_cycles_observed"], 2)
        self.assertEqual([c["observed_menu_load_ms"] for c in report["menu_cycles"]],
                         [1496, 1516])
        self.assertEqual([c["parse_events"] for c in report["menu_cycles"]], [3, 3])
        self.assertEqual(report["observed_menu_load_ms_total"], 3012)
        self.assertEqual(report["adjacent_cycle_reloads"], [{
            "previous_renderer_cycle": 1, "current_renderer_cycle": 2,
            "repeated_unique_files": 3, "current_after_hunk_clear": True,
        }])

    def test_single_menu_load_is_not_a_duplicate(self):
        report = analyze_menu_reloads(LOG.split("RE_Shutdown")[0])
        self.assertEqual(len(report["adjacent_cycle_reloads"]), 0)
        self.assertEqual(report["menu_parse_cycles_observed"], 1)

    def test_incomplete_log_does_not_invent_renderer(self):
        report = analyze_menu_reloads("Parsing menu file:UI\\Main.menu\n"
                                      "UI menu load time = 5 milli seconds\n")
        self.assertEqual(report["renderer_initializations_observed"], 0)
        self.assertEqual(report["menu_cycles"][0]["renderer_cycle"], 0)
        self.assertEqual(report["observed_menu_load_ms_total"], 5)

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.log"
            path.write_text(LOG, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "recomp" /
                                     "analyze_menu_reloads.py"), str(path), "--json"],
                check=True, text=True, capture_output=True,
            )
            report = json.loads(result.stdout)
            self.assertEqual(report["menu_parse_cycles_observed"], 2)
            self.assertEqual(report["adjacent_cycle_reloads"][0]["repeated_unique_files"], 3)


if __name__ == "__main__":
    unittest.main()
