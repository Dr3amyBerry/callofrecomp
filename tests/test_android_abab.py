"""Offline planning and recovery tests: no ADB process may be started."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.recomp.diagnostics import android_abab as abab


def frames(fps=22.0, cpu=43.0):
    return ('frame stats: fps=%.3f ms avg=45.0 min=40.0 max=60.0 cpu=%.3f swap=2.0 pace=0.0\n' % (fps, cpu)) * 60


class ABABTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / 'runs/tecno/session'
        self.run.mkdir(parents=True)
        for name in ('reports', 'logs', 'metrics', 'captures', 'builds'):
            (self.run / name).mkdir()
        (self.run / 'session.json').write_text('{"target":"tecno"}')
        self.patch = patch.object(abab, 'RUNS', self.root / 'runs')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.no_adb = patch('subprocess.run', side_effect=AssertionError('Unexpected process/ADB'))
        self.no_adb.start()
        self.addCleanup(self.no_adb.stop)
        self.no_popen = patch('subprocess.Popen', side_effect=AssertionError('Unexpected process/ADB'))
        self.no_popen.start()
        self.addCleanup(self.no_popen.stop)
        self.a, self.b, self.restore = [self.root / (n + '.apk') for n in ('a', 'b', 'restore')]
        for path in (self.a, self.b, self.restore):
            self.apk(path)
        self.protected = self.root / 'saves.json'
        self.protected.write_text(json.dumps({'files/profile/main/save/autosave/training.svg':
                                             hashlib.sha256(b'original-save').hexdigest()}))
        self.scene = self.root / 'scene.png'
        Image.new('RGB', (240, 135), (30, 50, 70)).save(self.scene)

    def apk(self, path, machine=183):
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', header, 18, machine)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('lib/arm64-v8a/libmain.so', header)
            archive.writestr('AndroidManifest.xml', b'same synthetic manifest')
            archive.comment = path.name.encode()

    def prepare(self, **kwargs):
        options = dict(run=self.run, baseline=self.a, candidate=self.b, restore=self.restore,
                       protected_files=self.protected, scene_reference=self.scene,
                       serial='test-tecno', reference_fps=22.0)
        options.update(kwargs)
        return abab.prepare_plan(**options)

    def test_prepare_offline_pins_all_identities_and_existing_scene(self):
        path = self.prepare()
        plan = abab.load_plan(path)
        self.assertEqual(plan['order'], ['A1', 'B1', 'A2', 'B2'])
        self.assertEqual(plan['artifacts']['A']['sha256'], hashlib.sha256(self.a.read_bytes()).hexdigest())
        self.assertEqual(plan['artifacts']['restore']['sha256'], hashlib.sha256(self.restore.read_bytes()).hexdigest())
        self.assertEqual(plan['scene']['sha256'], hashlib.sha256(self.scene.read_bytes()).hexdigest())
        self.assertFalse((self.run / 'reports/execution-started.json').exists())

    def test_wrong_abi_is_rejected_offline(self):
        self.apk(self.b, machine=62)
        with self.assertRaisesRegex(ValueError, 'AArch64'):
            self.prepare()

    def test_other_package_or_version_manifest_is_rejected_offline(self):
        with zipfile.ZipFile(self.b, 'a') as archive:
            # Replace instead of duplicate the XML entry.
            entries = {name: archive.read(name) for name in archive.namelist()}
        entries['AndroidManifest.xml'] = b'other package'
        with zipfile.ZipFile(self.b, 'w') as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        with self.assertRaisesRegex(ValueError, 'manifests differ'):
            self.prepare()

    def test_noncanonical_run_is_rejected(self):
        with self.assertRaises(ValueError):
            self.prepare(run=self.root)

    def test_empty_or_unsafe_save_manifest_is_rejected(self):
        for data in ({}, {'../../save/foo': 'a' * 64}, {'files/profile/main/save/foo': 'bad'}):
            self.protected.write_text(json.dumps(data))
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.prepare()

    def test_plan_cannot_overwrite_existing_evidence(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_execution_refuses_existing_stage_log_before_device_access(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        (self.run / 'logs/A1.log').write_text('keep evidence')
        with self.assertRaises(FileExistsError):
            runner.execute()
        self.assertEqual((self.run / 'logs/A1.log').read_text(), 'keep evidence')

    def test_tampered_apk_or_scene_is_rejected_before_device_access(self):
        path = self.prepare()
        for artifact in (self.b, self.scene):
            original = artifact.read_bytes()
            artifact.write_bytes(original + b'tampered')
            with self.assertRaisesRegex(ValueError, 'hash'):
                abab.load_plan(path)
            artifact.write_bytes(original)

    def test_changed_procedure_hash_requires_new_plan(self):
        path = self.prepare()
        plan = json.loads(path.read_text())
        plan['source_sha256'] = {}
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            abab.load_plan(path)

    def fake_runner(self, **options):
        events = []

        class Fake(abab.Runner):
            def preflight(self):
                events.append('preflight')
                if options.get('preflight_error'):
                    raise RuntimeError('preflight failed')

            def stage(self, label):
                events.append(label)
                if label == options.get('fail_at'):
                    raise RuntimeError('stage failed')
                return frames(16 if label == options.get('unstable_at') else 22)

            def restore(self):
                events.append('restore')
                if options.get('restore_error'):
                    raise RuntimeError('restore failed')

        return Fake(abab.load_plan(self.prepare())), events

    def test_success_runs_exact_order_and_restores_initial_apk(self):
        runner, events = self.fake_runner()
        result = runner.execute()
        self.assertEqual(events, ['preflight', 'A1', 'B1', 'A2', 'B2', 'restore'])
        self.assertTrue(result['restored'])
        self.assertEqual(len(list((self.run / 'logs').glob('A*.log'))), 2)

    def test_partial_failure_restores_and_preserves_error(self):
        runner, events = self.fake_runner(fail_at='B1')
        with self.assertRaisesRegex(RuntimeError, 'stage failed'):
            runner.execute()
        self.assertEqual(events, ['preflight', 'A1', 'B1', 'restore'])
        report = json.loads((self.run / 'reports/abab-result.json').read_text())
        self.assertTrue(report['restored'])
        self.assertEqual(report['status'], 'failed')

    def test_bad_baseline_stops_before_b_and_restores(self):
        runner, events = self.fake_runner(unstable_at='A1')
        with self.assertRaisesRegex(RuntimeError, 'stability'):
            runner.execute()
        self.assertEqual(events, ['preflight', 'A1', 'restore'])

    def test_preflight_failure_does_not_install_or_restore(self):
        runner, events = self.fake_runner(preflight_error=True)
        with self.assertRaisesRegex(RuntimeError, 'preflight failed'):
            runner.execute()
        self.assertEqual(events, ['preflight'])

    def test_restore_failure_remains_critical(self):
        runner, events = self.fake_runner(fail_at='B1', restore_error=True)
        with self.assertRaisesRegex(RuntimeError, 'restore failed'):
            runner.execute()
        result = json.loads((self.run / 'reports/abab-result.json').read_text())
        self.assertEqual(result['status'], 'critical_restore_failure')
        self.assertIn('stage failed', result['error'])
        self.assertFalse(result['restored'])

    def test_wrong_device_preflight_has_no_mutations(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        calls = []
        def adb(*args, **kwargs):
            calls.append(args)
            return b'test-tecno' if args == ('get-serialno',) else b'WSA'
        runner.adb = adb
        with self.assertRaisesRegex(RuntimeError, 'TECNO'):
            runner.preflight()
        self.assertFalse(any('install' in args or 'force-stop' in args for args in calls))

    def device(self, runner, *, interrupt_first_commit=False, pending_polls=0):
        """Deterministic device double; subprocess.run remains forbidden."""
        events = []
        installed = runner.plan['artifacts']['restore']['sha256']
        logs = iter(['previous log', 'warmup\n', 'warmup\n' + frames()])
        pushed, sessions, next_session = {}, {}, 1
        def adb(*args, **kwargs):
            nonlocal installed, next_session, pending_polls
            events.append(args)
            if args == ('get-serialno',):
                return b'test-tecno'
            if args[:2] == ('shell', 'getprop'):
                return b'TECNO CK6n' if args[-1] == 'ro.product.model' else b'arm64-v8a'
            if args == ('shell', 'am', 'get-current-user'):
                return b'0'
            if args[0] == 'push':
                pushed[args[2]] = args[1]
                return b'copied'
            if args[:3] == ('shell', 'pm', 'path'):
                return b'package:/data/app/base.apk\n'
            if args[:2] == ('shell', 'sha256sum'):
                if args[-1] in pushed:
                    return hashlib.sha256(Path(pushed[args[-1]]).read_bytes()).hexdigest().encode()
                return installed.encode() + b'  /data/app/base.apk'
            if args[:3] == ('shell', 'pm', 'install-create'):
                session = next_session
                next_session += 1
                sessions[session] = {'status': 0, 'artifact': None, 'abandoned': False}
                return f'Success: created install session [{session}]'.encode()
            if args[:3] == ('shell', 'pm', 'install-write'):
                sessions[int(args[5])]['artifact'] = pushed[args[-1]]
                return b'Success'
            if args[:3] == ('shell', 'pm', 'install-commit'):
                session = int(args[-1])
                if interrupt_first_commit and session == 1:
                    raise subprocess.TimeoutExpired('simulated remote commit', 180)
                installed = hashlib.sha256(Path(sessions[session]['artifact']).read_bytes()).hexdigest()
                sessions[session]['status'] = 1
                return b'Success'
            if args[:3] == ('shell', 'pm', 'install-abandon'):
                sessions[int(args[-1])]['abandoned'] = True
                return b'Success'
            if args == ('shell', 'dumpsys', 'package', 'installs'):
                for session, state in sessions.items():
                    if state['abandoned'] and not state['status']:
                        if pending_polls:
                            pending_polls -= 1
                        else:
                            state['status'] = -115
                active = ''.join(f'  Active Session {s}:\n    mFinalStatus=0\n'
                                 for s, v in sessions.items() if not v['status'])
                historical = ''.join(f'  Session {s}:\n    mFinalStatus={v["status"]}\n'
                                     for s, v in sessions.items() if v['status'])
                events.append(('session-status', {s: v['status'] for s, v in sessions.items()}))
                return ('Active install sessions:\n' + active + 'Historical install sessions:\n' + historical).encode()
            if args[:3] == ('shell', 'dumpsys', 'battery'):
                return b'temperature: 390\nlevel: 80\n'
            if args[:2] == ('shell', 'pidof'):
                return b'1234\n'
            if args[:2] == ('exec-out', 'screencap'):
                return self.scene.read_bytes()
            if args[:4] == ('exec-out', 'run-as', abab.PACKAGE, 'cat'):
                return next(logs).encode() if args[-1] == abab.LOG else b'original-save'
            if args[:3] in (('shell', 'am', 'force-stop'), ('shell', 'am', 'start'),
                             ('shell', 'input', 'tap'), ('shell', 'run-as', abab.PACKAGE)) or args[:2] == ('shell', 'rm'):
                return b''
            raise AssertionError('Unexpected mocked command: ' + str(args))
        runner.adb = adb
        return events

    def test_real_preflight_and_restore_validate_original_apk_and_save(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        events = self.device(runner)
        runner.preflight()
        runner.restore()
        pushes = [event for event in events if event[0] == 'push']
        self.assertEqual(len(pushes), 1)
        self.assertEqual(pushes[0][1], str(self.restore.resolve()))
        self.assertFalse(any('uninstall' in event for event in events))

    def test_real_stage_uses_existing_navigation_one_image_and_fresh_logs(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        events = self.device(runner)
        initialization = iter(['--- Common Initialization Complete ---', frames(60, 10),
                               'G_loadGame:\nCL_InitCGame:\n', 'CL_InitCGame:\n' + frames()])
        def wait(predicate, **kwargs):
            text = next(initialization)
            self.assertTrue(predicate(text))
            return text
        runner.wait_log = wait
        with patch.object(abab.time, 'sleep'), patch.object(abab, 'snapshot', return_value={}), \
             patch.object(abab, 'capture_path', side_effect=lambda r, n: r / 'captures' / (n + '.png')):
            text = runner.stage('A1')
        self.assertEqual(text, frames())
        self.assertEqual(sum(event[:2] == ('exec-out', 'screencap') for event in events), 1)
        removals = [event for event in events if event[:3] == ('shell', 'run-as', abab.PACKAGE) and 'rm' in event]
        self.assertEqual(removals, [('shell', 'run-as', abab.PACKAGE, 'rm', '-f', abab.LOG)])
        self.assertTrue((self.run / 'captures/a1-scene.png').exists())

    def test_timed_out_commit_is_proven_terminal_before_restoration_install(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        events = self.device(runner, interrupt_first_commit=True, pending_polls=2)
        runner.stage = lambda label: runner.install(runner.plan['artifacts']['A'])
        with patch.object(abab.time, 'sleep'), self.assertRaises(subprocess.TimeoutExpired):
            runner.execute()
        creates = [i for i, event in enumerate(events) if event[:3] == ('shell', 'pm', 'install-create')]
        terminal = next(i for i, event in enumerate(events)
                        if event[0] == 'session-status' and event[1].get(1) == -115)
        self.assertEqual(len(creates), 2)
        self.assertLess(creates[0], terminal)
        self.assertLess(terminal, creates[1])
        result = json.loads((self.run / 'reports/abab-result.json').read_text())
        self.assertTrue(result['restored'])

    def test_missing_terminal_evidence_prevents_restore_install(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        events = self.device(runner, interrupt_first_commit=True, pending_polls=999)
        runner.stage = lambda label: runner.install(runner.plan['artifacts']['A'])
        import itertools
        clock = itertools.count(step=300)
        with patch.object(abab.time, 'monotonic', side_effect=lambda: next(clock)), \
             self.assertRaisesRegex(RuntimeError, 'not proven terminal'):
            runner.execute()
        self.assertEqual(sum(e[:3] == ('shell', 'pm', 'install-create') for e in events), 1)
        result = json.loads((self.run / 'reports/abab-result.json').read_text())
        self.assertEqual(result['status'], 'critical_restore_failure')
        self.assertFalse(result['restored'])

    def test_unknown_battery_state_is_rejected(self):
        runner = abab.Runner(abab.load_plan(self.prepare()))
        runner.adb = lambda *args, **kwargs: b'level: 80\n'
        with self.assertRaisesRegex(RuntimeError, 'Battery'):
            runner.battery()

    def test_local_adb_client_is_reaped_on_timeout_and_interrupt(self):
        from unittest.mock import Mock
        for error in (subprocess.TimeoutExpired('adb', 1), KeyboardInterrupt()):
            runner = abab.Runner({'run': str(self.run), 'serial': 'test-tecno'})
            process = Mock()
            process.communicate.side_effect = [error, (b'', b'')]
            with patch.object(abab.subprocess, 'Popen', return_value=process), \
                 self.assertRaises(type(error)):
                runner.adb('shell', 'pm', 'install-commit', '123')
            process.kill.assert_called_once()
            self.assertEqual(process.communicate.call_count, 2)

    def test_unknown_session_dump_is_not_completion_evidence(self):
        with self.assertRaisesRegex(RuntimeError, 'Unknown Package Installer'):
            abab.install_sessions('unrecognized OEM output')


class OptimizedPythonTest(unittest.TestCase):
    def test_optimized_mode_is_rejected_without_device_access(self):
        script = Path(abab.__file__)
        result = subprocess.run([sys.executable, '-O', str(script), 'run', '--plan', 'nonexistent'],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('optimized Python', result.stderr)
