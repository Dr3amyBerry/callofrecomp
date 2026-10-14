#!/usr/bin/env python3
"""Opt-in, fail-closed WSA launcher UI locator for ANGLE experiments.

Parses an actual accessibility hierarchy; no coordinate guesses and no clicks
outside the exact enabled CallofRecomp 'Jugar' Android button.
"""
from __future__ import annotations

import re
from xml.etree import ElementTree

BOUNDS = re.compile(r"^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$")
PACKAGE = "org.callofrecomp"


class UILocatorError(ValueError):
    pass


def play_button_center(hierarchy_xml: str) -> tuple[int, int]:
    try:
        root = ElementTree.fromstring(hierarchy_xml)
    except ElementTree.ParseError as ex:
        raise UILocatorError("Invalid UI accessibility dump") from ex
    if root.tag != "hierarchy":
        raise UILocatorError("Unexpected UI hierarchy root")
    candidates = [
        node for node in root.iter("node")
        if node.get("text") == "Jugar" and node.get("package") == PACKAGE
        and node.get("class") == "android.widget.Button"
    ]
    if len(candidates) != 1:
        raise UILocatorError(f"Expected exactly one game 'Jugar' button; found {len(candidates)}")
    node = candidates[0]
    if node.get("enabled") != "true" or node.get("clickable") != "true":
        raise UILocatorError("Play button disabled or not clickable (game data not ready)")
    match = BOUNDS.fullmatch(node.get("bounds") or "")
    if not match:
        raise UILocatorError("Missing or invalid UI button bounds")
    x0, y0, x1, y1 = (int(v) for v in match.groups())
    if not (x0 < x1 and y0 < y1 and x0 >= 0 and y0 >= 0
            and x1 <= 10000 and y1 <= 10000):
        raise UILocatorError("Unsafe screen coordinates")
    return (x0 + x1) // 2, (y0 + y1) // 2


def game_activity_resumed(dumpsys: str) -> bool:
    """Avoid treating activities in Android's historical stack as foreground."""
    return any(
        "org.callofrecomp/.GameActivity" in line
        for line in dumpsys.splitlines()
        if "mResumedActivity" in line or "topResumedActivity" in line
    )
