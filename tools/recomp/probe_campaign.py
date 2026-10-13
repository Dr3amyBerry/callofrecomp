#!/usr/bin/env python3
"""Probe native campaign startup using owned assets; never certify completion.

Each map gets an isolated writable profile. Logs/reports stay private by default.
Generate the input graph with audit_campaign.py before running this probe.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def classify_startup(name, code, log):
    fatal = bool(re.search(r'^FATAL\b|script runtime error|script compile error', log,
                           re.IGNORECASE | re.MULTILINE))
    server = bool(re.search(r'^Server: ' + re.escape(name) + r'\s*$', log, re.MULTILINE))
    client = 'CL_InitCGame:' in log
    return {'server_started': server, 'cgame_initialized': client,
            'fatal_detected': fatal,
            'startup_verified': code == 0 and server and client and not fatal,
            'completion_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', type=Path)
    parser.add_argument('install', type=Path)
    parser.add_argument('audit', type=Path)
    parser.add_argument('--output', type=Path, default=Path('analysis/local/campaign_runtime'))
    parser.add_argument('--frames', type=int, default=90)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--maps', nargs='+', help='Optional subset of the audited graph')
    parser.add_argument('--language', type=int, default=4, help='Original engine language cvar')
    args = parser.parse_args()
    if args.frames < 1 or args.timeout <= 0:
        parser.error('frames and timeout must be positive')
    engine, install, output = args.engine.resolve(), args.install.resolve(), args.output.resolve()
    if not engine.is_file() or not (install / 'CoDSP.exe').is_file():
        parser.error('engine and owned CoDSP.exe must exist')
    names = json.loads(args.audit.read_text())['reachable_maps']
    if args.maps:
        if any(name not in names for name in args.maps): parser.error('map outside audited graph')
        names = args.maps
    output.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'server/client startup only; briefing, objectives and exits require playthrough',
              'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'all_maps_completable_verified': False, 'results': []}
    env = os.environ.copy(); env['CODRECOMP_FRAME_STATS'] = '1'
    for name in names:
        # Map names from external reports cannot choose arbitrary output paths.
        if not re.fullmatch(r'[a-zA-Z0-9_]+', name): parser.error('invalid map name')
        profile = output / 'profiles' / name; profile.mkdir(parents=True, exist_ok=True)
        log_path = output / (name + '.log'); started = time.monotonic()
        with log_path.open('wb') as stream:
            try:
                code = subprocess.run([str(engine), str(install), str(profile),
                    '+set', 'com_introplayed', '1', '+set', 'cg_nopredict', '0',
                    '+set', 'cl_language', str(args.language), '+spmap', name,
                    '+wait', str(args.frames), '+quit'], env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=args.timeout).returncode
            except subprocess.TimeoutExpired:
                code = 'timeout'
        result = {'map': name, 'exit': code, 'seconds': round(time.monotonic() - started, 2),
                  **classify_startup(name, code, log_path.read_text(errors='replace'))}
        report['results'].append(result)
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    return 0 if all(r['startup_verified'] for r in report['results']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
