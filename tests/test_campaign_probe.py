import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('campaign_probe',
    Path(__file__).parents[1] / 'tools/recomp/probe_campaign.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)


class StartupClassificationTests(unittest.TestCase):
    def test_loading_does_not_certify_completion(self):
        result = probe.classify_startup('training', 0,
            'Server: training\r\nWARNING: this will become a script error in a few days!\nCL_InitCGame: 3 seconds\n')
        self.assertTrue(result['startup_verified'])
        self.assertFalse(result['completion_verified'])

    def test_script_error_wrong_map_crash_and_timeout_cannot_pass(self):
        good = 'Server: training\nCL_InitCGame: 3 seconds\n'
        for code, log in [(5, good), ('timeout', good), (0, good + 'script runtime error'),
                          (0, good + 'FATAL pc=1234'), (0, good.replace('training', 'credits')),
                          (0, 'Server: training\n')]:
            self.assertFalse(probe.classify_startup('training', code, log)['startup_verified'])
