import unittest,sys
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from capture_wsa_game_frames import isolate_fresh_windows, verify_renderer

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
class WsaRendererIdentityTests(unittest.TestCase):
    def _api(self, angle=True, expected_log=True, global_override=False):
        def fake(serial,*args,**kwargs):
            if args[:4]==('shell','settings','get','global'):
                values={
                    'angle_debug_package':'org.chromium.angle' if angle else 'null',
                    'angle_gl_driver_selection_pkgs':'org.callofrecomp' if angle else 'null',
                    'angle_gl_driver_selection_values':'angle' if angle else 'null',
                    'angle_gl_driver_all_angle':'1' if global_override else 'null',
                }
                return values[args[4]].encode()
            if args[:3]==('shell','pm','path'):
                return b'package:/data/app/org.chromium.angle/base.apk'
            if args[:2]==('shell','date'):
                return b'1791995000'
            if args[:3]==('logcat','-d','-v'):
                if not expected_log:return b''
                return (
                   b'1791994999.1  9657  9657 I GraphicsEnvironment: ANGLE debug package enabled: org.chromium.angle\n'
                   b'1791994999.4  9657  9675 I ANGLE   : Version (2.1), Renderer (Vulkan 1.3.0)\n')
            raise AssertionError(args)
        return fake

    def test_gl4es_requires_clean_global_settings(self):
        with patch('capture_wsa_game_frames.android',side_effect=self._api(angle=False)):
            self.assertTrue(verify_renderer('127.0.0.1:58526','9657','gl4es')['driver_settings_clear'])
        with patch('capture_wsa_game_frames.android',side_effect=self._api(angle=True)):
            with self.assertRaises(ValueError):
                verify_renderer('127.0.0.1:58526','9657','gl4es')

    def test_angle_requires_live_vulkan_same_pid(self):
        with patch('capture_wsa_game_frames.android',side_effect=self._api()):
            self.assertTrue(verify_renderer('127.0.0.1:58526','9657','angle')['vulkan_verified'])
            with self.assertRaises(ValueError):
                verify_renderer('127.0.0.1:58526','9325','angle')

    def test_angle_rejects_missing_log_or_global_override(self):
        for opts in ({'expected_log':False},{'global_override':True},{'angle':False}):
            with self.subTest(opts=opts),patch('capture_wsa_game_frames.android',
                                               side_effect=self._api(**opts)):
                with self.assertRaises(ValueError):
                    verify_renderer('127.0.0.1:58526','9657','angle')

if __name__=='__main__':unittest.main()
