#!/usr/bin/env python3
"""Summarize repeated original UI menu parsing without modifying the game.

Only reads an existing engine log. Menu load timings belong to initialization,
not GPU rendering or the steady-state cost of a game frame.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MENU_TIME = re.compile(r"UI menu load time =\s*(\d+)\s*milli seconds")
MENU_PREFIX = "Parsing menu file:"
R_INIT = "----- R_Init -----"


@dataclass
class MenuCycle:
    renderer_cycle: int
    after_hunk_clear: bool
    parsed_files: list[str] = field(default_factory=list)
    menu_load_ms: list[int] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "renderer_cycle": self.renderer_cycle,
            "after_hunk_clear": self.after_hunk_clear,
            "parse_events": len(self.parsed_files),
            "unique_menu_files": len(set(self.parsed_files)),
            "timed_parse_groups": len(self.menu_load_ms),
            "observed_menu_load_ms": sum(self.menu_load_ms),
        }


def analyze_menu_reloads(text: str) -> dict:
    cycles: list[MenuCycle] = []
    current: MenuCycle | None = None
    after_hunk_clear = False
    waiting_for_group_time = False
    renderer_reinitializations = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "Hunk_Clear:" in line:
            after_hunk_clear = True
        if R_INIT in line:
            renderer_reinitializations += 1
            current = MenuCycle(renderer_reinitializations, after_hunk_clear and renderer_reinitializations > 1)
            cycles.append(current)
            after_hunk_clear = False
            waiting_for_group_time = False
        elif line.startswith(MENU_PREFIX):
            if current is None:
                # Logs may begin mid-initialization; never invent an R_Init event.
                current = MenuCycle(0, False)
                cycles.append(current)
            path = line[len(MENU_PREFIX):].strip().replace("\\", "/").lower()
            if path:
                current.parsed_files.append(path)
                waiting_for_group_time = True
        else:
            match = MENU_TIME.search(line)
            if match and current is not None and waiting_for_group_time:
                current.menu_load_ms.append(int(match.group(1)))
                waiting_for_group_time = False

    menu_cycles = [cycle for cycle in cycles if cycle.parsed_files]
    overlaps = []
    for previous, current_cycle in zip(menu_cycles, menu_cycles[1:]):
        repeats = set(previous.parsed_files) & set(current_cycle.parsed_files)
        overlaps.append({
            "previous_renderer_cycle": previous.renderer_cycle,
            "current_renderer_cycle": current_cycle.renderer_cycle,
            "repeated_unique_files": len(repeats),
            "current_after_hunk_clear": current_cycle.after_hunk_clear,
        })
    return {
        "renderer_initializations_observed": renderer_reinitializations,
        "menu_parse_cycles_observed": len(menu_cycles),
        "menu_cycles": [cycle.summary() for cycle in menu_cycles],
        "adjacent_cycle_reloads": overlaps,
        "observed_menu_load_ms_total": sum(sum(c.menu_load_ms) for c in menu_cycles),
        "interpretation": (
            "Repeated parsing after Hunk_Clear is observed, but is not proven "
            "unnecessary: parsed objects or GL resources may have been invalidated. "
            "These timings do not measure per-frame duplicate rendering or FPS."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Existing codrecomp.log (local/private)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary")
    args = parser.parse_args()
    report = analyze_menu_reloads(args.log.read_text(encoding="utf-8", errors="replace"))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("R_Init cycles: %d; menu parse cycles: %d" % (
            report["renderer_initializations_observed"],
            report["menu_parse_cycles_observed"],
        ))
        for cycle in report["menu_cycles"]:
            print("cycle %d: %d menu parse events, %d unique, %d ms reported, after Hunk_Clear=%s" % (
                cycle["renderer_cycle"], cycle["parse_events"],
                cycle["unique_menu_files"], cycle["observed_menu_load_ms"],
                cycle["after_hunk_clear"],
            ))
        for overlap in report["adjacent_cycle_reloads"]:
            print("cycles %d -> %d: %d repeated files (after Hunk_Clear=%s)" % (
                overlap["previous_renderer_cycle"],
                overlap["current_renderer_cycle"],
                overlap["repeated_unique_files"],
                overlap["current_after_hunk_clear"],
            ))
        print(report["interpretation"])


if __name__ == "__main__":
    main()
