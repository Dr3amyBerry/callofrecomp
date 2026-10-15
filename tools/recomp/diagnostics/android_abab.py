#!/usr/bin/env python3
"""Prepare offline, then explicitly run the existing TECNO checkpoint A/B/A/B.

Navigation comes from the fixed-scene October 15 procedure. No device is
accessed by prepare/help/import. Running requires a separately authorized
physical session; this tool does not certify arbitrary APK mathematics.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.local_capture import capture_path, write_png
from tools.recomp.analyze_frame_stats import parse_frames
from tools.recomp.diagnostics.android_perf_environment import parse_battery, snapshot
from tools.recomp.diagnostics.scene_fingerprint import _fingerprint, compare_scene
from tools.recomp.diagnostics.stable_frame_gate import LABELS, analyze_abab, capture_gate

RUNS = ROOT / '.local/profiles/runs'
PACKAGE = 'org.callofrecomp'
LOG = 'files/profile/codrecomp.log'
SOURCES = (Path(__file__).resolve(), ROOT / 'tools/local_capture.py',
           ROOT / 'tools/recomp/analyze_frame_stats.py',
           ROOT / 'tools/recomp/diagnostics/stable_frame_gate.py',
           ROOT / 'tools/recomp/diagnostics/scene_fingerprint.py',
           ROOT / 'tools/recomp/diagnostics/android_perf_environment.py')


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def write_text(path: Path, value: str) -> None:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(value)


def validate_run(run: Path) -> Path:
    run = run.resolve()
    if not run.is_relative_to((RUNS / 'tecno').resolve()) or run == (RUNS / 'tecno').resolve():
        raise ValueError('Use a canonical private TECNO run')
    if json.loads((run / 'session.json').read_text())['target'] != 'tecno':
        raise ValueError('Run must target TECNO')
    for name in ('reports', 'metrics', 'logs', 'captures'):
        path = run / name
        if not path.is_dir() or not path.resolve().is_relative_to(run):
            raise ValueError('Unsafe or missing run output directory')
    return run


def apk_identity(path: Path) -> dict:
    path = path.resolve(strict=True)
    with zipfile.ZipFile(path) as archive:
        libraries = [name for name in archive.namelist() if name.startswith('lib/') and name.endswith('.so')]
        if not libraries or any(not name.startswith('lib/arm64-v8a/') for name in libraries):
            raise ValueError('Require an ARM64-only APK')
        for name in libraries:
            with archive.open(name) as stream:
                header = stream.read(64)
            if (len(header) < 64 or header[:6] != b'\x7fELF\x02\x01' or
                    struct.unpack_from('<H', header, 18)[0] != 183):
                raise ValueError('Require little-endian AArch64 ELF libraries')
        if 'lib/arm64-v8a/libmain.so' not in libraries:
            raise ValueError('APK lacks libmain.so')
        try:
            manifest_hash = hashlib.sha256(archive.read('AndroidManifest.xml')).hexdigest()
        except KeyError as exc:
            raise ValueError('APK manifest missing') from exc
    return {'path': str(path), 'sha256': sha(path), 'manifest_sha256': manifest_hash}


def validate_saves(saves: dict) -> None:
    if not isinstance(saves, dict) or not saves:
        raise ValueError('Nonempty protected save manifest required')
    for path, digest in saves.items():
        parts = PurePosixPath(path).parts
        if (not path.startswith('files/') or '/save/' not in path or
                '..' in parts or '\\' in path or not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or
                not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest)):
            raise ValueError('Unsafe save path or invalid save hash')


def prepare_plan(*, run: Path, baseline: Path, candidate: Path, restore: Path,
                 protected_files: Path, scene_reference: Path, serial: str,
                 reference_fps: float) -> Path:
    if not __debug__:
        raise RuntimeError('Do not use optimized Python')
    run = validate_run(run)
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', serial):
        raise ValueError('Explicit device serial required')
    if not math.isfinite(reference_fps) or reference_fps <= 0:
        raise ValueError('Positive finite reference FPS required')
    protected = json.loads(protected_files.read_text(encoding='utf-8'))
    if not isinstance(protected, dict):
        raise ValueError('Protected file manifest must be an object')
    saves = {k: v for k, v in protected.items() if '/save/' in k}
    validate_saves(saves)
    artifacts = {name: apk_identity(path) for name, path in
                 (('A', baseline), ('B', candidate), ('restore', restore))}
    if artifacts['A']['sha256'] == artifacts['B']['sha256']:
        raise ValueError('A and B must be different APKs')
    if len({item['manifest_sha256'] for item in artifacts.values()}) != 1:
        raise ValueError('APK manifests differ from the pinned restoration package')
    scene_reference = scene_reference.resolve(strict=True)
    scene = {'path': str(scene_reference), 'sha256': sha(scene_reference),
             'fingerprint': _fingerprint(scene_reference.read_bytes())}
    plan = {'schema': 1, 'run': str(run), 'serial': serial, 'package': PACKAGE,
            'order': list(LABELS), 'artifacts': artifacts, 'protected_saves': saves,
            'scene': scene, 'reference_fps': reference_fps,
            'navigation': 'tecno-release024-training-checkpoint-2026-10-15',
            'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in SOURCES},
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'state': 'prepared_offline_not_executed'}
    path = run / 'reports/abab-plan.json'
    write_json(path, plan)
    return path


def load_plan(path: Path) -> dict:
    if not __debug__:
        raise RuntimeError('Do not use optimized Python')
    plan = json.loads(path.read_text(encoding='utf-8'))
    run = validate_run(Path(plan['run']))
    if path.resolve() != run / 'reports/abab-plan.json':
        raise ValueError('Plan must be stored in its own run')
    if (plan['schema'] != 1 or plan['package'] != PACKAGE or plan['order'] != list(LABELS) or
            plan['navigation'] != 'tecno-release024-training-checkpoint-2026-10-15' or
            not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', plan['serial']) or
            not math.isfinite(plan['reference_fps']) or plan['reference_fps'] <= 0):
        raise ValueError('Unsupported or invalid plan')
    validate_saves(plan['protected_saves'])
    if plan['source_sha256'] != {p.relative_to(ROOT).as_posix(): sha(p) for p in SOURCES}:
        raise ValueError('Procedure/helper source hash changed; prepare a new run')
    if set(plan['artifacts']) != {'A', 'B', 'restore'}:
        raise ValueError('Require A, B and restoration APK pins')
    for item in plan['artifacts'].values():
        current = apk_identity(Path(item['path']))
        if current != item:
            raise ValueError('Pinned APK hash/identity mismatch: ' + item['path'])
    if len({item['manifest_sha256'] for item in plan['artifacts'].values()}) != 1:
        raise ValueError('APK manifests differ from the pinned restoration package')
    for item in (plan['scene'],):
        if sha(Path(item['path'])) != item['sha256']:
            raise ValueError('Pinned input hash mismatch: ' + item['path'])
    # Recompute the reference; never trust an independently edited fingerprint.
    plan['scene']['fingerprint'] = _fingerprint(Path(plan['scene']['path']).read_bytes())
    return plan


def install_sessions(text: str) -> dict:
    """Recognize AOSP session dumps; unknown OEM formats fail closed.

    A nonzero historical mFinalStatus is completion evidence. An active
    session, mDestroyed alone, or absence from the dump is not evidence.
    """
    if 'Active install sessions:' not in text or 'Historical install sessions:' not in text:
        raise RuntimeError('Unknown Package Installer session dump format')
    sessions, section, current = {}, None, None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith('install sessions:'):
            section, current = stripped.split()[0], None
        match = re.fullmatch(r'(?:(?:Active|Finalized|Orphaned|Child)\s+)*Session (\d+):', stripped)
        if match:
            current = int(match[1])
            if current in sessions:
                raise RuntimeError('Ambiguous install session ID')
            sessions[current] = {'section': section, 'final_status': None}
        status = re.search(r'\bmFinalStatus=(-?\d+)\b', line)
        if current is not None and status:
            sessions[current]['final_status'] = int(status[1])
    return sessions


class Runner:
    def __init__(self, plan: dict):
        self.plan = plan
        self.run = Path(plan['run'])
        self.pending_install = None

    def adb(self, *args: str, timeout: int = 150) -> bytes:
        command = ['adb', '-s', self.plan['serial'], *args]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            # Reap the local client before querying the separately tracked remote
            # install session. Client termination alone does not settle that session.
            process.kill()
            process.communicate()
            raise
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        return stdout

    def log(self) -> str:
        return self.adb('exec-out', 'run-as', PACKAGE, 'cat', LOG).decode(errors='replace')

    def savecheck(self) -> None:
        for path, expected in self.plan['protected_saves'].items():
            actual = hashlib.sha256(self.adb('exec-out', 'run-as', PACKAGE, 'cat', path)).hexdigest()
            if actual != expected:
                raise RuntimeError('Protected save changed: ' + path)

    def installed_hash(self) -> str:
        paths = self.adb('shell', 'pm', 'path', PACKAGE).decode().splitlines()
        if len(paths) != 1 or not re.fullmatch(r'package:/[A-Za-z0-9_./=+~-]+\.apk', paths[0]):
            raise RuntimeError('Require one installed base APK, no splits')
        return self.adb('shell', 'sha256sum', paths[0][8:]).decode().split()[0]

    def battery(self, minimum_level: int = 25) -> dict:
        data = parse_battery(self.adb('shell', 'dumpsys', 'battery').decode())
        level, temperature = data['battery_level_pct'], data['battery_temperature_c']
        if level is None or temperature is None or level < minimum_level or temperature > 40:
            raise RuntimeError('Battery/temperature missing or outside measurement conditions')
        return data

    def preflight(self) -> None:
        if self.adb('get-serialno').decode().strip() != self.plan['serial']:
            raise RuntimeError('Wrong serial')
        model = self.adb('shell', 'getprop', 'ro.product.model').decode().upper()
        abi = self.adb('shell', 'getprop', 'ro.product.cpu.abi').decode().strip()
        if 'TECNO' not in model or 'CK6N' not in model or abi != 'arm64-v8a':
            raise RuntimeError('Require physical TECNO CK6n ARM64 for this navigation profile')
        if self.adb('shell', 'am', 'get-current-user').strip() != b'0':
            raise RuntimeError('This checkpoint profile requires Android user 0')
        sessions = self.sessions()
        if any(row['section'] == 'Active' for row in sessions.values()):
            raise RuntimeError('Another Package Installer session is active')
        if self.installed_hash() != self.plan['artifacts']['restore']['sha256']:
            raise RuntimeError('Installed APK does not match the pinned restoration APK')
        self.savecheck()
        self.battery(minimum_level=30)

    def sessions(self) -> dict:
        return install_sessions(self.adb('shell', 'dumpsys', 'package', 'installs', timeout=20).decode())

    def settle_pending(self, *, cancel: bool = False, timeout: int = 240) -> int | None:
        if self.pending_install is None:
            return None
        session = self.pending_install
        if cancel:
            # AOSP may defer abandonment while verification is using stageDir.
            # Requesting it is not completion: wait for the historical record.
            try:
                self.adb('shell', 'pm', 'install-abandon', str(session), timeout=30)
            except (subprocess.SubprocessError, RuntimeError):
                pass
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            state = self.sessions().get(session)
            if state and state['section'] == 'Historical' and state['final_status'] not in (None, 0):
                write_json(self.run / 'reports' / f'install-{session}-terminal.json', state)
                self.pending_install = None
                return state['final_status']
            time.sleep(2)
        raise RuntimeError(f'Install session {session} is not proven terminal; refuse another installation')

    def install(self, artifact: dict) -> None:
        self.settle_pending()
        if sha(Path(artifact['path'])) != artifact['sha256']:
            raise RuntimeError('APK hash changed before install')
        remote = '/data/local/tmp/codrecomp-abab-' + uuid.uuid4().hex + '.apk'
        session = None
        try:
            self.adb('push', artifact['path'], remote, timeout=180)
            if self.adb('shell', 'sha256sum', remote).decode().split()[0] != artifact['sha256']:
                raise RuntimeError('Transferred APK hash mismatch')
            size = str(Path(artifact['path']).stat().st_size)
            created = self.adb('shell', 'pm', 'install-create', '-r', '--user', '0', '-S', size).decode()
            match = re.fullmatch(r'Success: created install session \[(\d+)\]\s*', created)
            if not match:
                raise RuntimeError('Install session ID unavailable; no commit issued')
            session = self.pending_install = int(match[1])
            write_json(self.run / 'reports' / f'install-{session}-created.json',
                       {'session': session, 'artifact_sha256': artifact['sha256'], 'remote': remote})
            self.adb('shell', 'pm', 'install-write', '-S', size, str(session), 'base.apk', remote, timeout=180)
            write_json(self.run / 'reports' / f'install-{session}-commit-requested.json', {'session': session})
            result = self.adb('shell', 'pm', 'install-commit', str(session), timeout=180)
            status = self.settle_pending()
            if b'Success' not in result or status != 1 or self.installed_hash() != artifact['sha256']:
                raise RuntimeError('APK installation identity check failed')
        except BaseException:
            if self.pending_install is not None:
                self.settle_pending(cancel=True)
            raise
        finally:
            # Never remove a file while its tracked installer might still use it.
            if self.pending_install is None:
                try:
                    self.adb('shell', 'rm', '-f', remote, timeout=20)
                except subprocess.SubprocessError:
                    pass

    def wait_log(self, predicate, timeout: int = 150) -> str:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                text = self.log()
            except subprocess.CalledProcessError:
                time.sleep(2)
                continue
            if predicate(text):
                return text
            time.sleep(2)
        raise RuntimeError('Timed out waiting for initialization or stable gameplay')

    def tap(self, x: int, y: int) -> None:
        self.adb('shell', 'input', 'tap', str(x), str(y))

    def stage(self, label: str) -> str:
        self.savecheck()
        self.battery()
        self.adb('shell', 'am', 'force-stop', PACKAGE)
        write_text(self.run / 'logs' / (label + '-previous.log'), self.log())
        self.install(self.plan['artifacts'][label[0]])
        # Only this disposable log is removed; no saves/configuration are written.
        self.adb('shell', 'run-as', PACKAGE, 'rm', '-f', LOG)
        self.adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/.LauncherActivity')
        time.sleep(3)
        self.tap(540, 1140)
        self.wait_log(lambda text: '--- Common Initialization Complete ---' in text)
        self.wait_log(lambda text: len(rows := parse_frames(text)) >= 5 and
                      all(r['fps'] > 40 and r['cpu_ms'] < 15 for r in rows[-5:]), timeout=120)
        self.tap(1690, 420)
        time.sleep(3)
        self.tap(1040, 536)
        self.wait_log(lambda text: 'G_loadGame:' in text and 'CL_InitCGame:' in text)
        time.sleep(4)
        self.tap(1190, 1010)

        def warmed(text):
            gate = capture_gate(text.rsplit('CL_InitCGame:', 1)[-1], last=20, edge=5,
                                reference_fps=self.plan['reference_fps'] if label[0] == 'A' else None)
            if gate['reason_codes'] == ['reference_mismatch']:
                raise RuntimeError('Non-comparable baseline; stop before B')
            return gate['stable']

        self.wait_log(warmed, timeout=180)
        # Exactly one image per stage; script comparison, no repeated UI inspection.
        raw = self.adb('exec-out', 'screencap', '-p', timeout=30)
        write_png(capture_path(self.run, label.lower() + '-scene'), raw)
        scene = compare_scene(self.plan['scene']['fingerprint'], _fingerprint(raw))
        write_json(self.run / 'metrics' / (label + '-scene.json'), scene)
        if not scene['comparable']:
            raise RuntimeError('Scene differs from the pinned known reference: ' + label)
        before_environment = snapshot(self.plan['serial'])
        self.battery()
        before = self.log()
        pid = self.adb('shell', 'pidof', PACKAGE).strip()
        if not re.fullmatch(rb'[0-9]+', pid):
            raise RuntimeError('No unique live game PID')
        # Log reads and environment monitoring stay outside the measurement window.
        for _ in range(11):
            time.sleep(5)
        after = self.log()
        if not after.startswith(before) or self.adb('shell', 'pidof', PACKAGE).strip() != pid:
            raise RuntimeError('Process/log changed during capture')
        fresh = after[len(before):]
        if 'G_loadGame:' in fresh or 'CL_InitCGame:' in fresh:
            raise RuntimeError('Scene reloaded during capture')
        after_environment = snapshot(self.plan['serial'])
        self.battery()
        self.savecheck()
        write_json(self.run / 'metrics' / (label + '-environment.json'),
                   {'before': before_environment, 'after': after_environment})
        return fresh

    def restore(self) -> None:
        self.settle_pending(cancel=True)
        self.adb('shell', 'am', 'force-stop', PACKAGE)
        self.install(self.plan['artifacts']['restore'])
        self.savecheck()

    def execute(self) -> dict:
        if not __debug__:
            raise RuntimeError('Do not use optimized Python')
        # Validate pins again before any device access, including direct API use.
        self.plan = load_plan(self.run / 'reports/abab-plan.json')
        for folder in ('logs', 'metrics', 'captures'):
            # A prepared run can contain plan/build reports, but no previous capture.
            for path in (self.run / folder).iterdir():
                if any(path.name.lower().startswith(label.lower()) for label in LABELS):
                    raise FileExistsError('Refuse to overwrite stage evidence: ' + str(path))
        write_json(self.run / 'reports/execution-started.json',
                   {'started_utc': datetime.now(timezone.utc).isoformat()})
        result = {'status': 'failed', 'restored': False, 'completed_stages': []}
        started = False
        try:
            self.preflight()
            started = True
            captures = {}
            for label in LABELS:
                text = self.stage(label)
                write_text(self.run / 'logs' / (label + '.log'), text)
                gate = capture_gate(text, reference_fps=self.plan['reference_fps'] if label[0] == 'A' else None)
                write_json(self.run / 'metrics' / (label + '-stability.json'), gate)
                if not gate['stable']:
                    raise RuntimeError(label + ' stability gate failed: ' + str(gate['reason_codes']))
                captures[label] = text
                result['completed_stages'].append(label)
            result['analysis'] = analyze_abab(captures, expected_baseline_fps=self.plan['reference_fps'])
            result['status'] = 'completed_abab'
            result['limitation'] = 'Coarse scene and temporal checks; no automatic proof of full fidelity or sustained FPS'
            return result
        except BaseException as exc:
            result['error'] = str(exc)
            raise
        finally:
            try:
                if started:
                    self.restore()
                    result['restored'] = True
            except BaseException as exc:
                result['status'] = 'critical_restore_failure'
                result['restore_error'] = str(exc)
                raise
            finally:
                write_json(self.run / 'reports/abab-result.json', result)


def main():
    if not __debug__:
        raise RuntimeError('Do not use optimized Python')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Offline only; never invokes ADB')
    for name in ('run', 'baseline', 'candidate', 'restore', 'protected-files', 'scene-reference'):
        prepare.add_argument('--' + name, type=Path, required=True)
    prepare.add_argument('--serial', required=True)
    prepare.add_argument('--reference-fps', type=float, required=True)
    execute = commands.add_parser('run', help='Connect/install/measure/restore on the specified physical device')
    execute.add_argument('--plan', type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    if command == 'prepare':
        print(prepare_plan(**args))
    else:
        print(json.dumps(Runner(load_plan(args['plan'])).execute(), indent=2))


if __name__ == '__main__':
    main()
