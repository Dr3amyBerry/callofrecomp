#!/usr/bin/env python3
"""Audit owned PK3 campaign metadata without copying proprietary source.

This is lexical static evidence, never proof of mission completion. Output is
private by default under ignored analysis/local. Archive priority is a declared
model: plain archives ascending, then the selected locale ascending, last wins.
Native startup ordering and loose-file overrides must be checked separately.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile


def uncomment(source: str) -> str:
    # Preserve strings and line numbers, including comment markers in strings.
    pattern = r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"')
                  else ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)


def key(name: str) -> str:
    return name.replace('\\', '/').lower()


def mask_strings(source: str) -> str:
    """Keep offsets/newlines while hiding literal content from code searches."""
    return re.sub(r'"(?:\\.|[^"\\])*"',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source)


def code_matches(pattern: str, source: str):
    """Match real code names with original string arguments still available."""
    code = mask_strings(source)
    for match in re.finditer(pattern, source, re.I):
        if not code[match.start()].isspace():
            yield match


def analyze(main: Path, language: str = 'spanish', start: str = 'training') -> dict:
    with ExitStack() as stack:
        providers: dict[str, list[dict]] = {}
        selected = []
        excluded = []
        paths = sorted(main.glob('*.pk3'), key=lambda p: p.name.lower())
        plain, localized = [], []
        for path in paths:
            match = re.match(r'localized_([a-z]+)_', path.name.lower())
            if not match:
                plain.append(path)
            elif match[1] == language.lower():
                localized.append(path)
            else:
                excluded.append(path.name)
        for path in plain + localized:
            archive = stack.enter_context(zipfile.ZipFile(path))
            selected.append(path.name)
            for info in archive.infolist():
                if info.is_dir():
                    continue
                logical = key(info.filename)
                if logical.startswith('/') or '..' in logical.split('/') or ':' in logical:
                    raise ValueError(f'unsafe archive member in {path.name}')
                providers.setdefault(logical, []).append({
                    'archive': path.name, 'member': info.filename,
                    'bytes': info.file_size, 'crc32': f'{info.CRC:08x}',
                    '_archive': archive, '_info': info,
                })

        def metadata(logical):
            found = providers.get(logical, [])
            if not found:
                return None
            return {k: v for k, v in found[-1].items() if not k.startswith('_')}

        scripts = {}
        read_errors = {}
        for logical, found in providers.items():
            if logical.endswith('.gsc'):
                winner = found[-1]
                try:
                    raw = winner['_archive'].read(winner['_info'])
                    scripts[logical] = uncomment(raw.decode('latin1'))
                except (OSError, zipfile.BadZipFile, RuntimeError) as error:
                    read_errors[logical] = str(error)

        def dependencies(logical):
            source = mask_strings(scripts.get(logical, ''))
            refs = re.findall(r'\b([a-z_][\w]*(?:[\\/][\w]+)+)\s*::', source, re.I)
            refs += re.findall(r'#include\s+([a-z_][\w]*(?:[\\/][\w]+)+)', source, re.I)
            return sorted({key(r) + '.gsc' for r in refs})

        maps = {}
        for logical in providers:
            match = re.fullmatch(r'maps/([^/_][^/]*)\.(?:bsp|gsc)', logical)
            if match and (logical.endswith('.bsp') or 'maps/' + match[1] + '.bsp' in providers):
                maps[match[1]] = None
        maps[start.lower()] = None
        records = {}

        def record(name):
            script_path = f'maps/{name}.gsc'
            bsp_path = f'maps/{name}.bsp'
            source = scripts.get(script_path, '')
            transitions = []
            for match in code_matches(r'\b(missionsuccess|changelevel)\s*\(\s*"([\w]+)"\s*,\s*(true|false)\s*\)', source):
                transitions.append({'kind': match[1].lower(), 'target': match[2].lower(),
                                    'persistent': match[3].lower() == 'true',
                                    'line': source.count('\n', 0, match.start()) + 1})
            cvars = []
            for match in code_matches(r'\bsetcvar\s*\(\s*"([^"\n]+)"\s*,\s*"([^"\n]*)"\s*\)', source):
                cvars.append({'name': match[1], 'value': match[2],
                              'line': source.count('\n', 0, match.start()) + 1})
                if match[1].lower() == 'nextmap':
                    target = re.fullmatch(r'map\s+([\w]+)', match[2], re.I)
                    if target:
                        transitions.append({'kind': 'nextmap_cvar', 'target': target[1].lower(),
                                            'line': cvars[-1]['line']})
            visited, missing = set(), set()
            pending = [script_path]
            while pending:
                dep = pending.pop()
                if dep in visited:
                    continue
                visited.add(dep)
                if dep not in scripts:
                    missing.add(dep)
                else:
                    pending.extend(dependencies(dep))
            bsp = metadata(bsp_path)
            bsp_valid = False
            if bsp:
                winner = providers[bsp_path][-1]
                try:
                    # Full read validates ZIP decompression and CRC, no extraction.
                    raw = winner['_archive'].read(winner['_info'])
                    bsp['sha256'] = hashlib.sha256(raw).hexdigest()
                    bsp['magic'] = raw[:4].decode('ascii', errors='replace')
                    bsp['version'] = struct.unpack('<I', raw[4:8])[0] if len(raw) >= 8 else None
                    bsp_valid = bsp['magic'] == 'IBSP' and bsp['version'] == 59
                except (OSError, zipfile.BadZipFile, RuntimeError) as error:
                    read_errors[bsp_path] = str(error)
            has_main = bool(re.search(r'\bmain\s*\(\s*\)\s*\{', mask_strings(source), re.I))
            return {'name': name, 'bsp': bsp, 'script': metadata(script_path),
                    'has_main': has_main,
                    'transitions': transitions, 'cvar_writes': cvars,
                    'script_dependency_count': len(visited),
                    'missing_script_dependencies': sorted(missing),
                    'static_status': 'static_verified' if bsp_valid and has_main and not missing and transitions else 'static_issues',
                    'completion_status': 'requires_playthrough'}

        pending = list(maps)
        while pending:
            name = pending.pop()
            if name in records:
                continue
            records[name] = record(name)
            pending.extend(t['target'] for t in records[name]['transitions'])
        reachable, pending = [], [start.lower()]
        while pending:
            name = pending.pop(0)
            if name in reachable:
                continue
            reachable.append(name)
            pending.extend(t['target'] for t in records[name]['transitions'])
        ui_evidence = []
        for logical in ('ui/main.menu', 'ui/victoryscreen.menu'):
            if logical not in providers:
                continue
            winner = providers[logical][-1]
            source = uncomment(winner['_archive'].read(winner['_info']).decode('latin1'))
            tokens = []
            for match in code_matches(r'\b(setcvar|cvartest|exec)\s+(?:"([^"\n]*)"|([\w]+))(?:\s+"([^"\n]*)")?', source):
                tokens.append({'kind': match[1].lower(), 'argument': match[2] or match[3],
                               'value': match[4], 'line': source.count('\n', 0, match.start()) + 1})
            ui_evidence.append({'path': logical, 'provider': metadata(logical), 'tokens': tokens,
                                'scope': 'lexical tokens; menu condition/action grouping is not interpreted'})
        return {
            'schema_version': 1, 'language': language, 'start': start,
            'priority_model': 'plain ascending then selected locale ascending; last member wins',
            'priority_model_verified_against_native_startup': False,
            'archives_low_to_high': selected, 'excluded_language_archives': excluded,
            'reachable_maps': reachable, 'maps': [records[n] for n in sorted(records)],
            'script_overrides': [{'path': n, 'providers': [p['archive'] for p in ps],
                                  'winner': ps[-1]['archive']} for n, ps in sorted(providers.items())
                                 if n.startswith('maps/') and n.endswith('.gsc') and len(ps) > 1],
            'read_errors': read_errors,
            'progression_ui': ui_evidence,
            'all_maps_completable_verified': False,
            'limitations': [
                'Static_verified means BSP header/CRC, script, literal transition and script dependency presence only.',
                'No objectives, AI behavior, trigger reachability, saves, death/retry, unlock persistence or playthrough verified.',
                'Branches are lexical possibilities; unreachable functions and conditions are not evaluated.',
                'Dynamic script references, sound/model/image aliases and engine callbacks are not resolved.',
                'Loose files and exact native localization/archive priority are not modeled.',
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('main_directory', type=Path)
    parser.add_argument('--language', default='spanish')
    parser.add_argument('--start', default='training')
    parser.add_argument('--output', type=Path, default=Path('analysis/local/campaign_audit.json'))
    args = parser.parse_args()
    try:
        report = analyze(args.main_directory, args.language, args.start)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Private report: {args.output}; {len(report["reachable_maps"])} reachable maps; completion requires playthrough')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
