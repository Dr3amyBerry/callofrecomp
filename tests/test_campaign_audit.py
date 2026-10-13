"""Synthetic campaign fixtures; no original game data is required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).parents[1] / 'tools/recomp/audit_campaign.py'
spec = importlib.util.spec_from_file_location('campaign_audit', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CampaignAuditTests(unittest.TestCase):
    def test_strings_cannot_supply_main_or_script_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(root / 'pak0.pk3', 'w') as archive:
                archive.writestr('maps/training.bsp', b'IBSP\x3b\0\0\0')
                archive.writestr('maps/training.gsc', r'''other() {
print("main() {");
print("maps\\missing::main(); #include maps\\missing_include");
missionSuccess("training",true);
}''')
            record = audit.analyze(root)['maps'][0]
            self.assertFalse(record['has_main'])
            self.assertEqual(record['missing_script_dependencies'], [])
            self.assertEqual(record['static_status'], 'static_issues')

    def test_fake_transitions_in_strings_keep_real_arguments_and_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(root / 'pak0.pk3', 'w') as archive:
                archive.writestr('maps/training.bsp', b'IBSP\x3b\0\0\0')
                archive.writestr('maps/training.gsc', r'''main() {
print("missionSuccess(\"ghost\",false); changelevel(\"ghost\",true)");
print("setcvar(\"nextmap\",\"map ghost\")");
missionSuccess("training",true);
setcvar("nextmap", "map training");
}''')
            report = audit.analyze(root)
            record = report['maps'][0]
            self.assertEqual(report['reachable_maps'], ['training'])
            self.assertEqual(record['transitions'], [
                {'kind': 'missionsuccess', 'target': 'training', 'persistent': True, 'line': 4},
                {'kind': 'nextmap_cvar', 'target': 'training', 'line': 5},
            ])
            self.assertEqual(record['cvar_writes'], [{'name': 'nextmap', 'value': 'map training', 'line': 5}])

    def test_patch_case_locale_comments_dependencies_and_incomplete_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = {
                'pak0.pk3': {'Maps/Alpha.BSP': b'IBSP\x3b\0\0\0',
                             'maps/alpha.gsc': 'main() { missionSuccess("obsolete",false); }',
                             'maps/beta.bsp': b'IBSP\x3b\0\0\0',
                             'maps/beta.gsc': 'main() { setcvar("nextmap", "map alpha"); }'},
                'pak1.pk3': {'maps/ALPHA.gsc': '''// missionSuccess("ghost",false);
/* changelevel("ghost",false); */
main() { maps\\missing::main(); missionSuccess("beta",true); }
''',
                            'maps/unrelated.gsc': 'main() { }'},
                'localized_french_pak0.pk3': {'maps/alpha.gsc': 'main() { changelevel("wrong", false); }'},
            }
            for name, members in assets.items():
                with zipfile.ZipFile(root / name, 'w') as archive:
                    for member, data in members.items():
                        archive.writestr(member, data)
            report = audit.analyze(root, language='spanish', start='alpha')
            self.assertEqual(report['reachable_maps'], ['alpha', 'beta'])
            alpha = next(m for m in report['maps'] if m['name'] == 'alpha')
            self.assertEqual(alpha['script']['archive'], 'pak1.pk3')
            self.assertEqual(alpha['transitions'][0]['target'], 'beta')
            self.assertEqual(alpha['transitions'][0]['persistent'], True)
            self.assertEqual(alpha['missing_script_dependencies'], ['maps/missing.gsc'])
            self.assertEqual(alpha['completion_status'], 'requires_playthrough')
            self.assertNotIn('ghost', json.dumps(report))
            self.assertFalse(report['all_maps_completable_verified'])

    def test_missing_target_bsp_and_script_are_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(root / 'pak0.pk3', 'w') as archive:
                archive.writestr('maps/training.gsc', 'main() { changelevel("lost",false); }')
            report = audit.analyze(root)
            lost = next(m for m in report['maps'] if m['name'] == 'lost')
            self.assertIsNone(lost['bsp'])
            self.assertIsNone(lost['script'])
            self.assertEqual(lost['static_status'], 'static_issues')
            self.assertEqual(report['reachable_maps'], ['training', 'lost'])


if __name__ == '__main__':
    unittest.main()
