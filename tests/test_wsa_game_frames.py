import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from capture_wsa_game_frames import isolate_fresh_windows

def line(fps=55,cpu=17):
    return f"frame stats: fps={fps}.0 ms avg=18.18 min=17.4 max=19.1 cpu={cpu}.0 swap=0.8 pace=0.9\n"

class WsaFrameCaptureTests(unittest.TestCase):
    def test_extract_after_only_and_validate_gameplay(self):
        earlier=line()*5
        fresh=line()*60
        raw,stats=isolate_fresh_windows(earlier,earlier+fresh,60)
        self.assertEqual(raw,fresh)
        self.assertEqual(stats["median_fps"],55)
        self.assertEqual(stats["count"],60)
    def test_rotated_log_not_compared(self):
        with self.assertRaises(ValueError):isolate_fresh_windows(line()*10,line()*4,3)
    def test_menu_not_accepted(self):
        with self.assertRaises(ValueError):isolate_fresh_windows("","".join(line(cpu=2) for _ in range(60)),60)
    def test_incomplete_capture_not_accepted(self):
        with self.assertRaises(ValueError):isolate_fresh_windows("","".join(line() for _ in range(58)),60)
if __name__=='__main__':unittest.main()
