#!/usr/bin/env python3
"""
screenpack-updater.py

Usage:
  screenpack-updater.py <path>

This Python script reads an INI file, parses each line, and applies:

1) key-deletion rules (keys_to_delete),
2) value-modification rules (value_modifications),
3) existing key-transformation rules (transformations),
4) append-if-missing rules (append_if_missing).

If a key matches an entry in keys_to_delete, the line is removed entirely.
If a key matches a rule in value_modifications, its value is updated accordingly.
Then the (possibly modified) key and value are passed through the transformations.

Platform-specific behavior:
  - Windows: if started without arguments, a file selection dialog is shown so
    you can pick the screenpack file (.def or .ini) to patch. Drag & drop also works.
  - macOS / Linux: if started without arguments, usage information is printed.
"""

import sys
import re
import argparse
import io
import shutil
import os
import math

# Target ikemen version for this patcher. Only files with a lower version
# (or missing version) will be patched.
TARGET_IKEMEN_VERSION_STR = "1.0"
TARGET_IKEMEN_VERSION = 1.0

def _parse_ikemen_version_to_float(value: str):
    """
    Parse version string using only the first two numeric components (major.minor).
    Returns None if parsing fails.
    """
    value_body, _ = _split_value_comment(value)
    value_body = value_body.strip().strip('"')
    if not value_body:
        return None
    parts = value_body.split(".")
    if not parts:
        return None
    if len(parts) == 1:
        core = parts[0]
    else:
        core = parts[0] + "." + parts[1]
    try:
        return float(core)
    except ValueError:
        return None

def _detect_ikemen_version(ini_path: str):
    """
    Scan file for [Info] / ikemenversion and return:
      (has_info_section: bool, raw_value: str|None, parsed_float: float|None)
    Only active (non-commented) ikemenversion lines are considered.
    """
    has_info = False
    raw_version = None
    parsed = None
    current_section = ""

    try:
        with open(ini_path, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                m_sec = SECTION_REGEX.match(line)
                if m_sec:
                    current_section = m_sec.group(1).strip().lower()
                    if current_section == "info":
                        has_info = True
                    continue

                m_kv = KEY_VALUE_REGEX.match(line)
                if not m_kv:
                    continue

                semicolon = m_kv.group(1)
                if semicolon == ";":
                    # Entire line commented out.
                    continue

                if current_section == "info":
                    key = m_kv.group(2).strip().lower()
                    if key == "ikemenversion":
                        raw_version = m_kv.group(3)
                        parsed = _parse_ikemen_version_to_float(raw_version)
                        break
    except OSError as e:
        print(f"WARNING: Failed to read '{ini_path}' to detect ikemenversion: {e}", file=sys.stderr)

    return has_info, raw_version, parsed

if sys.platform == "win32":
    # Only used when launched without arguments on Windows.
    import tkinter as tk
    from tkinter import filedialog

# Section renames for Ikemen 1.0 screenpacks
SECTION_RENAMES = {
    "menu info": "pause menu",
    "menubgdef": "pausebgdef",
    "training info": "training pause menu",
    "trainingbgdef": "trainingpausebgdef",
}

# Canonical output casing for renamed sections
SECTION_CANONICAL_CASE = {
    "pause menu": "Pause Menu",
    "pausebgdef": "PauseBGdef",
    "training pause menu": "Training Pause Menu",
    "trainingpausebgdef": "TrainingPauseBGdef",
}

append_if_missing = {
    "option info": {
        "keymenu.pos": "0, 0",
        "keymenu.window.margins.y": "0, 0",
        "keymenu.window.visibleitems": "0",
    },
}

keys_to_delete = {
    "languages": [
        re.compile(r"^languages$", re.IGNORECASE),
    ],
    "vs screen": [
        re.compile(r"^p2\.accept\.key$", re.IGNORECASE),
        re.compile(r"^p2\.skip\.key$", re.IGNORECASE),
    ],
    "victory screen": [
        re.compile(r"^winquote\.time$", re.IGNORECASE),
    ],
    "attract mode": [
        re.compile(r"^credits\.key$", re.IGNORECASE),
        re.compile(r"^options\.key$", re.IGNORECASE),
    ],
    "option info": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
        re.compile(r"^keymenu\.itemname\.playerno$", re.IGNORECASE),
    ],
    "replay info": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
    ],
    "pause menu": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
    ],
    "training pause menu": [
        re.compile(r"^menu\.uselocalcoord$", re.IGNORECASE),
    ],
}

value_modifications = {
    "victory screen": [
        (re.compile(r"^winquote\.spacing$", re.IGNORECASE), re.compile(r"^([^,]*),([^,]*)$"), r"\2"),
    ],
    "dialogue info": [
        (re.compile(r"^p[12]\.text\.spacing$", re.IGNORECASE), re.compile(r"^([^,]*),([^,]*)$"), r"\2"),
    ],
    "hiscore info": [
        (re.compile(r"^item\.name\.text$", re.IGNORECASE), re.compile(r"^.*$"), r"%s"),
        (re.compile(r"^item\.rank\.?[0-9]*\.text$", re.IGNORECASE), re.compile(r"%0?([0-9]+)[si]"), r"%0\1d"),
        (re.compile(r"^item\.rank\.?[0-9]*\.text$", re.IGNORECASE), re.compile(r"%[si]"), r"%d"),
        (re.compile(r"^item\.data\.(?!time\.).*text$", re.IGNORECASE), re.compile(r"%0?([0-9]+)[si]"), r"%0\1d"),
        (re.compile(r"^item\.data\.(?!time\.).*text$", re.IGNORECASE), re.compile(r"%[si]"), r"%d"),

        (re.compile(r"^item\.data\.text\.win$", re.IGNORECASE), re.compile(r"%s"), "%d"),
        (re.compile(r"^item\.rank\.text\.default$", re.IGNORECASE), re.compile(r"%s"), "%d"),
        (re.compile(r"^item\.rank\.text\.[0-9]+$", re.IGNORECASE), re.compile(r"%s"), "%d"),
    ],
    "continue screen": [
        (re.compile(r"^credits\.text$", re.IGNORECASE), re.compile(r"%0?([0-9]+)[si]"), r"%0\1d"),
        (re.compile(r"^credits\.text$", re.IGNORECASE), re.compile(r"%[si]"), r"%d"),
    ],
    "attract mode": [
        (re.compile(r"^credits\.text$", re.IGNORECASE), re.compile(r"%0?([0-9]+)[si]"), r"%0\1d"),
        (re.compile(r"^credits\.text$", re.IGNORECASE), re.compile(r"%[si]"), r"%d"),
    ],
}

transformations = {
    "music": [
        (re.compile(r"^continue\.end\.(.+)$", re.IGNORECASE), ["continueend.\\1"]),
        (re.compile(r"^results\.lose\.(.+)$", re.IGNORECASE), ["resultslose.\\1"]),
    ],
    "title info": [
        (re.compile(r"^menu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^menu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.bg.\\1.\\2"]),

        (re.compile(r"^cursor\.(?!done\.)(.+)\.snd$", re.IGNORECASE), ["cursor.done.\\1.snd"]),

        (re.compile(r"^menu\.accept\.key$", re.IGNORECASE), ["menu.done.key"]),

        (re.compile(r"^footer1\.(font|offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE), ["footer.title.\\1"]),
        (re.compile(r"^footer2\.(font|offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE), ["footer.info.\\1"]),
        (re.compile(r"^footer3\.(font|offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE), ["footer.version.\\1"]),
    ],
    "select info": [
        # cell.* and cursor.* remap (and 1-based -> 0-based) is handled in apply_key_transformations()

        (re.compile(r"^p([12])\.teammenu\.accept\.key$", re.IGNORECASE), ["p\\1.teammenu.done.key"]),

        (re.compile(r"^p([12])\.palmenu\.accept\.key$", re.IGNORECASE), ["p\\1.palmenu.done.key"]),

        (re.compile(r"^p[12]\.palmenu\.random\.applypal$", re.IGNORECASE), ["palmenu.random.applypal"]),

        (re.compile(r"^stage\.active\.font$", re.IGNORECASE), ["stage.font", "stage.active.font"]),
        (re.compile(r"^stage\.active\.(offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE), ["stage.\\1"]),

        (re.compile(r"^p([12])\.face\.slide\.speed$", re.IGNORECASE), ["p\\1.face.velocity"]),
        (re.compile(r"^p([12])\.face2\.slide\.speed$", re.IGNORECASE), ["p\\1.face2.velocity"]),
        (re.compile(r"^p([12])\.face\.slide\.dist$", re.IGNORECASE), ["p\\1.face.maxdist"]),
        (re.compile(r"^p([12])\.face2\.slide\.dist$", re.IGNORECASE), ["p\\1.face2.maxdist"]),
    ],
    "vs screen": [
        (re.compile(r"^p1\.accept\.key$", re.IGNORECASE), ["done.key"]),
        (re.compile(r"^p1\.skip\.key$", re.IGNORECASE), ["skip.key"]),

        (re.compile(r"^p([1-8])\.icon\.(offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["p\\1.icon.\\2", "p\\1.icon.done.\\2"]),

        (re.compile(r"^p([12])\.slide\.speed$", re.IGNORECASE), ["p\\1.velocity"]),
        (re.compile(r"^p([12])\.face2\.slide\.speed$", re.IGNORECASE), ["p\\1.face2.velocity"]),
        (re.compile(r"^p([12])\.slide\.dist$", re.IGNORECASE), ["p\\1.maxdist"]),
        (re.compile(r"^p([12])\.face2\.slide\.dist$", re.IGNORECASE), ["p\\1.face2.maxdist"]),
    ],
    "victory screen": [
        (re.compile(r"^winquote\.spacing$", re.IGNORECASE), ["winquote.textspacing"]),
        (re.compile(r"^winquote\.delay$", re.IGNORECASE), ["winquote.textdelay"]),

        (re.compile(r"^p([12])\.slide\.speed$", re.IGNORECASE), ["p\\1.velocity"]),
        (re.compile(r"^p([12])\.face2\.slide\.speed$", re.IGNORECASE), ["p\\1.face2.velocity"]),
        (re.compile(r"^p([12])\.slide\.dist$", re.IGNORECASE), ["p\\1.maxdist"]),
        (re.compile(r"^p([12])\.face2\.slide\.dist$", re.IGNORECASE), ["p\\1.face2.maxdist"]),
    ],
    "option info": [
        (re.compile(r"^menu\.itemname\.menugame\.stunbar$", re.IGNORECASE), ["menu.itemname.menugame.dizzy"]),
        (re.compile(r"^menu\.itemname\.menugame\.guardbar$", re.IGNORECASE), ["menu.itemname.menugame.guardbreak"]),
        (re.compile(r"^menu\.itemname\.menugame\.redlifebar$", re.IGNORECASE), ["menu.itemname.menugame.redlife"]),
        (re.compile(r"^menu\.itemname\.menuvideo\.vretrace$", re.IGNORECASE), ["menu.itemname.menuvideo.vsync"]),

        (re.compile(r"^menu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^menu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.bg.\\1.\\2"]),
        (re.compile(r"^keymenu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["keymenu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^keymenu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["keymenu.item.bg.\\1.\\2"]),
        (re.compile(r"^keymenu\.p([12])\.pos$", re.IGNORECASE), ["keymenu.p\\1.menuoffset"]),
        (re.compile(r"^keymenu\.item\.p([12])\.(font|offset|scale|xshear|angle|text|layerno|window|localcoord)$", re.IGNORECASE), ["keymenu.p\\1.playerno.\\2"]),
    ],
    "replay info": [
        (re.compile(r"^menu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^menu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.bg.\\1.\\2"]),
    ],
    "pause menu": [
        (re.compile(r"^menu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^menu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.bg.\\1.\\2"]),
    ],
    "training pause menu": [
        (re.compile(r"^menu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^menu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.bg.\\1.\\2"]),

        (re.compile(r"^menu\.valuename\.dummycontrol\.(cooperative|ai|manual)$", re.IGNORECASE), ["menu.valuename.dummycontrol_\\1"]),
        (re.compile(r"^menu\.valuename\.ailevel\.([1-8])$", re.IGNORECASE), ["menu.valuename.ailevel_\\1"]),
        (re.compile(r"^menu\.valuename\.guardmode\.(none|auto)$", re.IGNORECASE), ["menu.valuename.guardmode_\\1"]),
        (re.compile(r"^menu\.valuename\.dummymode\.(stand|crouch|jump|wjump)$", re.IGNORECASE), ["menu.valuename.dummymode_\\1"]),
        (re.compile(r"^menu\.valuename\.distance\.(any|close|medium|far)$", re.IGNORECASE), ["menu.valuename.distance_\\1"]),
        (re.compile(r"^menu\.valuename\.buttonjam\.(none|a|b|c|x|y|z|s|d|w)$", re.IGNORECASE), ["menu.valuename.buttonjam_\\1"]),
    ],
    "attract mode": [
        (re.compile(r"^menu\.bg\.active\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.active.bg.\\1.\\2"]),
        (re.compile(r"^menu\.bg\.(.+)\.(anim|spr|offset|facing|scale|xshear|angle|layerno|window|localcoord)$", re.IGNORECASE), ["menu.item.bg.\\1.\\2"]),

        (re.compile(r"^menu\.accept\.key$", re.IGNORECASE), ["menu.done.key"]),
        (re.compile(r"^options\.key$", re.IGNORECASE), ["options.keycode"]),
    ],
    "challenger info": [
        (re.compile(r"^text$", re.IGNORECASE), ["text.text"]),
    ],
    "continue screen": [
        (re.compile(r"^accept\.key$", re.IGNORECASE), ["done.key"]),
    ],
    "dialogue info": [
        (re.compile(r"^p([12])\.text\.spacing$", re.IGNORECASE), ["p\\1.text.textspacing"]),
        (re.compile(r"^p([12])\.text\.delay$", re.IGNORECASE), ["p\\1.text.textdelay"]),
    ],
    "hiscore info": [
        (re.compile(r"^item\.data\.(.+)$", re.IGNORECASE), ["item.result.\\1"]),
        (re.compile(r"^title\.data\.(.+)$", re.IGNORECASE), ["title.result.\\1"]),

        (re.compile(r"^accept\.key$", re.IGNORECASE), ["done.key"]),
    ],
}

_member_offset_params = {}
_member_scale_params = {}
_facing_params = {}
_velocity_params = {}
_PLAYER_MEMBER_MAP = {1: [1, 3, 5, 7], 2: [2, 4, 6, 8]}

class _AnchorToken:
    """
    Internal placeholder used to mark where section-flush generated lines
    (aggregated offsets/scales/velocities) should be inserted.
    """
    __slots__ = ("id",)
    def __init__(self, id_: int):
        self.id = id_

_anchor_counter = 0
def _new_anchor_token() -> _AnchorToken:
    global _anchor_counter
    _anchor_counter += 1
    return _AnchorToken(_anchor_counter)

def _is_trailing_comment_or_blank_line(item) -> bool:
    """
    True for items that are plain strings which are blank or ';' comments.
    Used to insert append_if_missing lines before "tail comments" that often
    belong to the next section header.
    """
    if isinstance(item, _AnchorToken):
        return False
    s = str(item)
    st = s.strip()
    return st == "" or st.startswith(";")

def _parse_xy_pair(value_str: str):
    """
    Parse 'x, y' into a tuple of floats (x, y). Missing or invalid components
    are treated as 0.0.
    """
    parts = [p.strip() for p in str(value_str).split(",")]
    x_str = parts[0] if len(parts) > 0 and parts[0] != "" else "0"
    y_str = parts[1] if len(parts) > 1 and parts[1] != "" else "0"
    try:
        x = float(x_str)
    except (TypeError, ValueError):
        x = 0.0
    try:
        y = float(y_str)
    except (TypeError, ValueError):
        y = 0.0
    return x, y


def _parse_scale_pair(value_str: str):
    """
    Parse 'x, y' into a tuple of floats (x, y) for scale values.
    Missing or invalid components are treated as 1.0 (scale default).
    """
    parts = [p.strip() for p in str(value_str).split(",")]
    x_str = parts[0] if len(parts) > 0 and parts[0] != "" else "1"
    y_str = parts[1] if len(parts) > 1 and parts[1] != "" else "1"
    try:
        x = float(x_str)
    except (TypeError, ValueError):
        x = 1.0
    try:
        y = float(y_str)
    except (TypeError, ValueError):
        y = 1.0
    return x, y

def _record_facing_param(section: str, orig_key: str, value: str) -> None:
    """
    Record facing values (pX.facing, pX.face.facing, pX.face2.facing) so that
    slide.speed can later be converted into velocity with the correct sign.
    """
    sec = (section or "").lower()
    if sec not in ("select info", "vs screen", "victory screen"):
        return

    base_player = None
    kind = None  # "face", "face2", "plain"

    m = re.match(r"^p([0-9]+)\.face\.facing$", orig_key, flags=re.IGNORECASE)
    if m:
        base_player = int(m.group(1))
        kind = "face"
    else:
        m = re.match(r"^p([0-9]+)\.face2\.facing$", orig_key, flags=re.IGNORECASE)
        if m:
            base_player = int(m.group(1))
            kind = "face2"
        else:
            m = re.match(r"^p([0-9]+)\.facing$", orig_key, flags=re.IGNORECASE)
            if m:
                base_player = int(m.group(1))
                kind = "plain"

    if base_player is None or kind is None:
        return

    first = str(value).split(",")[0].strip()
    try:
        facing = float(first) if first != "" else 1.0
    except ValueError:
        facing = 1.0

    key = (sec, base_player, kind)
    _facing_params[key] = facing
    print(
        f"[{section}] Recorded facing for {orig_key}: {facing}",
        file=sys.stderr,
    )

def _record_member_offset_param(section: str, orig_key: str, value: str):
    """
    Record base/member offsets so they can be aggregated later.

    Handles three kinds of offsets (for p1 / p2 only):
      - pX.face.offset     with pX.memberY.face.offset
      - pX.face2.offset    with pX.memberY.face2.offset
      - pX.offset          with pX.memberY.offset

    The mapping of members is the same as in _remap_member_key:
      p1.member1 -> p1, member2 -> p3, member3 -> p5, member4 -> p7
      p2.member1 -> p2, member2 -> p4, member3 -> p6, member4 -> p8

    The original lines are DROPPED from output; final aggregated offsets
    are emitted by _flush_member_offsets_for_section().
    """
    sec = (section or "").lower()

    # Only aggregate member offsets in sections that support member mapping.
    if sec not in ("select info", "vs screen", "victory screen"):
        return (False, None)

    base_player = None
    member_index = None
    kind = None  # "face", "face2", "plain"

    # Base offsets ----------------------------------------------------------
    m = re.match(r"^p([12])\.face\.offset$", orig_key, flags=re.IGNORECASE)
    if m:
        base_player = int(m.group(1))
        kind = "face"
    else:
        m = re.match(r"^p([12])\.face2\.offset$", orig_key, flags=re.IGNORECASE)
        if m:
            base_player = int(m.group(1))
            kind = "face2"
        else:
            m = re.match(r"^p([12])\.offset$", orig_key, flags=re.IGNORECASE)
            if m:
                base_player = int(m.group(1))
                kind = "plain"

    # Member offsets --------------------------------------------------------
    if base_player is None:
        m = re.match(
            r"^p([12])\.member([1-4])\.face\.offset$",
            orig_key,
            flags=re.IGNORECASE,
        )
        if m:
            base_player = int(m.group(1))
            member_index = int(m.group(2))
            kind = "face"
        else:
            m = re.match(
                r"^p([12])\.member([1-4])\.face2\.offset$",
                orig_key,
                flags=re.IGNORECASE,
            )
            if m:
                base_player = int(m.group(1))
                member_index = int(m.group(2))
                kind = "face2"
            else:
                m = re.match(
                    r"^p([12])\.member([1-4])\.offset$",
                    orig_key,
                    flags=re.IGNORECASE,
                )
                if m:
                    base_player = int(m.group(1))
                    member_index = int(m.group(2))
                    kind = "plain"

    if base_player is None or kind is None:
        return (False, None)

    x, y = _parse_xy_pair(value)
    key = (sec, base_player, kind)
    slot = _member_offset_params.setdefault(
        key, {"base": None, "members": {}, "anchor": None}
    )

    if member_index is None:
        slot["base"] = (x, y)
    else:
        slot["members"][member_index] = (x, y)

    anchor = None
    if slot.get("anchor") is None:
        slot["anchor"] = _new_anchor_token()
        anchor = slot["anchor"]

    print(
        f"[{section}] Recorded offset for {orig_key}: ({x}, {y})",
        file=sys.stderr,
    )
    return (True, anchor)


def _flush_member_offsets_for_section(section: str):
    """
    When finishing a section, emit any pending aggregated offsets.

    For each (section, base_player, kind) group we output at most one
    offset per *final* player index:
      - member1 -> p1/p2
      - member2 -> p3/p4
      - member3 -> p5/p6
      - member4 -> p7/p8

    The final offset is: base_offset + member_offset (with 0,0 defaults).
    """
    if not section:
        return ({}, [])
    sec = section.lower()

    # Only aggregate offsets in these sections
    if sec not in ("select info", "vs screen", "victory screen"):
        return ({}, [])

    anchor_map = {}
    append_lines = []

    for (s, base_player, kind), data in list(_member_offset_params.items()):
        if s != sec:
            continue

        base_off = data.get("base")
        members = data.get("members", {})

        # Decide which members need final lines.
        member_indices = set(members.keys())
        # Always keep a pX.*.offset for member1 if there was either a base
        # value or an explicit member1 override.
        if base_off is not None or 1 in member_indices:
            member_indices.add(1)

        if not member_indices:
            del _member_offset_params[(s, base_player, kind)]
            continue

        for member_idx in sorted(member_indices):
            target_players = _PLAYER_MEMBER_MAP[base_player]
            new_player = target_players[member_idx - 1]

            bx, by = base_off if base_off is not None else (0.0, 0.0)
            mx, my = members.get(member_idx, (0.0, 0.0))
            fx = bx + mx
            fy = by + my

            if kind == "face":
                base_key = f"p{new_player}.face"
            elif kind == "face2":
                base_key = f"p{new_player}.face2"
            else:
                base_key = f"p{new_player}"

            off_str = f"{fx:g}, {fy:g}"
            lines = []
            if sec in ("select info", "vs screen"):
                print(
                    f"[{section}] Aggregated offset: base p{base_player} "
                    f"{kind} member{member_idx} -> {base_key}.offset/.done.offset = {off_str}",
                    file=sys.stderr,
                )
                lines.append(f"{base_key}.offset = {off_str}")
                lines.append(f"{base_key}.done.offset = {off_str}")
            else:
                # Victory Screen: no .done variants
                print(
                    f"[{section}] Aggregated offset: base p{base_player} "
                    f"{kind} member{member_idx} -> {base_key}.offset = {off_str}",
                    file=sys.stderr,
                )
                lines.append(f"{base_key}.offset = {off_str}")

            anchor = data.get("anchor")
            if anchor is not None:
                anchor_map.setdefault(anchor, []).extend(lines)
            else:
                append_lines.extend(lines)

        # Remove so we don't flush twice if the same section name repeats.
        del _member_offset_params[(s, base_player, kind)]
    return (anchor_map, append_lines)

def _record_member_scale_param(section: str, orig_key: str, value: str):
    """
    Record base/member scales so they can be aggregated later.

    Handles three kinds of scales (for p1 / p2 only):
      - pX.face.scale     with pX.memberY.face.scale
      - pX.face2.scale    with pX.memberY.face2.scale
      - pX.scale          with pX.memberY.scale

    The mapping of members is the same as in _remap_member_key:
      p1.member1 -> p1, member2 -> p3, member3 -> p5, member4 -> p7
      p2.member1 -> p2, member2 -> p4, member3 -> p6, member4 -> p8

    The original lines are DROPPED from output; final aggregated scales
    are emitted by _flush_member_scales_for_section().
    """
    sec = (section or "").lower()

    # Only aggregate member scales in sections that support member mapping.
    if sec not in ("select info", "vs screen", "victory screen"):
        return (False, None)

    base_player = None
    member_index = None
    kind = None  # "face", "face2", "plain"

    # Base scales -----------------------------------------------------------
    m = re.match(r"^p([12])\.face\.scale$", orig_key, flags=re.IGNORECASE)
    if m:
        base_player = int(m.group(1))
        kind = "face"
    else:
        m = re.match(r"^p([12])\.face2\.scale$", orig_key, flags=re.IGNORECASE)
        if m:
            base_player = int(m.group(1))
            kind = "face2"
        else:
            m = re.match(r"^p([12])\.scale$", orig_key, flags=re.IGNORECASE)
            if m:
                base_player = int(m.group(1))
                kind = "plain"

    # Member scales ---------------------------------------------------------
    if base_player is None:
        m = re.match(
            r"^p([12])\.member([1-4])\.face\.scale$",
            orig_key,
            flags=re.IGNORECASE,
        )
        if m:
            base_player = int(m.group(1))
            member_index = int(m.group(2))
            kind = "face"
        else:
            m = re.match(
                r"^p([12])\.member([1-4])\.face2\.scale$",
                orig_key,
                flags=re.IGNORECASE,
            )
            if m:
                base_player = int(m.group(1))
                member_index = int(m.group(2))
                kind = "face2"
            else:
                m = re.match(
                    r"^p([12])\.member([1-4])\.scale$",
                    orig_key,
                    flags=re.IGNORECASE,
                )
                if m:
                    base_player = int(m.group(1))
                    member_index = int(m.group(2))
                    kind = "plain"

    if base_player is None or kind is None:
        return (False, None)

    x, y = _parse_scale_pair(value)
    key = (sec, base_player, kind)
    slot = _member_scale_params.setdefault(
        key, {"base": None, "members": {}, "anchor": None}
    )

    if member_index is None:
        slot["base"] = (x, y)
    else:
        slot["members"][member_index] = (x, y)

    anchor = None
    if slot.get("anchor") is None:
        slot["anchor"] = _new_anchor_token()
        anchor = slot["anchor"]

    print(
        f"[{section}] Recorded scale for {orig_key}: ({x}, {y})",
        file=sys.stderr,
    )
    return (True, anchor)


def _flush_member_scales_for_section(section: str):
    """
    When finishing a section, emit any pending aggregated scales.

    For each (section, base_player, kind) group we output at most one
    scale per *final* player index:
      - member1 -> p1/p2
      - member2 -> p3/p4
      - member3 -> p5/p6
      - member4 -> p7/p8

    The final scale is: base_scale * member_scale (with 1,1 defaults).
    """
    if not section:
        return ({}, [])
    sec = section.lower()

    # Only aggregate scales in these sections
    if sec not in ("select info", "vs screen", "victory screen"):
        return ({}, [])

    anchor_map = {}
    append_lines = []

    for (s, base_player, kind), data in list(_member_scale_params.items()):
        if s != sec:
            continue

        base_scale = data.get("base")
        members = data.get("members", {})

        # Decide which members need final lines.
        member_indices = set(members.keys())
        # Always keep a pX.*.scale for member1 if there was either a base
        # value or an explicit member1 override.
        if base_scale is not None or 1 in member_indices:
            member_indices.add(1)

        if not member_indices:
            del _member_scale_params[(s, base_player, kind)]
            continue

        for member_idx in sorted(member_indices):
            target_players = _PLAYER_MEMBER_MAP[base_player]
            new_player = target_players[member_idx - 1]

            bx, by = base_scale if base_scale is not None else (1.0, 1.0)
            mx, my = members.get(member_idx, (1.0, 1.0))
            fx = bx * mx
            fy = by * my

            if kind == "face":
                base_key = f"p{new_player}.face"
            elif kind == "face2":
                base_key = f"p{new_player}.face2"
            else:
                base_key = f"p{new_player}"

            scale_str = f"{fx:g}, {fy:g}"
            lines = []
            if sec in ("select info", "vs screen"):
                print(
                    f"[{section}] Aggregated scale: base p{base_player} "
                    f"{kind} member{member_idx} -> {base_key}.scale/.done.scale = {scale_str}",
                    file=sys.stderr,
                )
                lines.append(f"{base_key}.scale = {scale_str}")
                lines.append(f"{base_key}.done.scale = {scale_str}")
            else:
                # Victory Screen: no .done variants
                print(
                    f"[{section}] Aggregated scale: base p{base_player} "
                    f"{kind} member{member_idx} -> {base_key}.scale = {scale_str}",
                    file=sys.stderr,
                )
                lines.append(f"{base_key}.scale = {scale_str}")

            anchor = data.get("anchor")
            if anchor is not None:
                anchor_map.setdefault(anchor, []).extend(lines)
            else:
                append_lines.extend(lines)

        # Remove so we don't flush twice if the same section name repeats.
        del _member_scale_params[(s, base_player, kind)]
    return (anchor_map, append_lines)

def _record_velocity_param(section: str, orig_key: str, value: str):
    """
    Record slide.speed entries so they can be converted into velocity at
    section flush time, after we know the relevant facing.

    Supported:
      - [Select Info]:       pX.face.slide.speed / pX.face2.slide.speed
      - [VS Screen],
        [Victory Screen]:    pX.slide.speed / pX.face2.slide.speed

    The original lines are DROPPED from output; final velocities are
    emitted by _flush_velocity_for_section().
    """
    sec = (section or "").lower()
    if sec not in ("select info", "vs screen", "victory screen"):
        return (False, None)

    base_player = None
    kind = None  # "face", "face2", "plain"

    if sec == "select info":
        m = re.match(r"^p([0-9]+)\.face\.slide\.speed$", orig_key, flags=re.IGNORECASE)
        if m:
            base_player = int(m.group(1))
            kind = "face"
        else:
            m = re.match(r"^p([0-9]+)\.face2\.slide\.speed$", orig_key, flags=re.IGNORECASE)
            if m:
                base_player = int(m.group(1))
                kind = "face2"
    else:
        m = re.match(r"^p([0-9]+)\.slide\.speed$", orig_key, flags=re.IGNORECASE)
        if m:
            base_player = int(m.group(1))
            kind = "plain"
        else:
            m = re.match(r"^p([0-9]+)\.face2\.slide\.speed$", orig_key, flags=re.IGNORECASE)
            if m:
                base_player = int(m.group(1))
                kind = "face2"

    if base_player is None or kind is None:
        return (False, None)

    vx, vy = _parse_xy_pair(value)
    key = (sec, base_player, kind)
    slot = _velocity_params.setdefault(key, {"v": None, "anchor": None})
    slot["v"] = (vx, vy)

    anchor = None
    if slot.get("anchor") is None:
        slot["anchor"] = _new_anchor_token()
        anchor = slot["anchor"]

    print(
        f"[{section}] Recorded slide.speed for {orig_key}: ({vx}, {vy})",
        file=sys.stderr,
    )
    return (True, anchor)


def _flush_velocity_for_section(section: str):
    """
    Emit any pending velocity lines for the given section.
    X component is multiplied by the corresponding facing:
      velocity.x = slide_speed.x * facing
    """
    if not section:
        return ({}, [])
    sec = section.lower()
    if sec not in ("select info", "vs screen", "victory screen"):
        return ({}, [])

    anchor_map = {}
    append_lines = []

    # First, flush velocities for this section.
    for (s, base_player, kind), slot in list(_velocity_params.items()):
        if s != sec:
            continue
        (vx, vy) = slot.get("v") if slot else (0.0, 0.0)

        # Try to get a facing value for this player/kind.
        facing = _facing_params.get((sec, base_player, kind))
        if facing is None:
            if kind == "plain":
                # plain -> try face as fallback
                facing = _facing_params.get((sec, base_player, "face"), 1.0)
            else:
                # face/face2 -> try plain as fallback
                facing = _facing_params.get((sec, base_player, "plain"), 1.0)

        fx = vx * facing
        vel_str = f"{fx:g}, {vy:g}"

        if sec == "select info":
            if kind == "face":
                new_key = f"p{base_player}.face.velocity"
            elif kind == "face2":
                new_key = f"p{base_player}.face2.velocity"
            else:
                new_key = f"p{base_player}.velocity"
        else:  # vs screen / victory screen
            if kind == "plain":
                new_key = f"p{base_player}.velocity"
            elif kind == "face2":
                new_key = f"p{base_player}.face2.velocity"
            else:
                new_key = f"p{base_player}.face.velocity"

        print(
            f"[{section}] Aggregated velocity: p{base_player} {kind} "
            f"slide.speed * facing={facing:g} -> {new_key} = {vel_str}",
            file=sys.stderr,
        )
        line = f"{new_key} = {vel_str}"

        anchor = slot.get("anchor") if slot else None
        if anchor is not None:
            anchor_map.setdefault(anchor, []).append(line)
        else:
            append_lines.append(line)

        del _velocity_params[(s, base_player, kind)]

    # Then clear any stored facing for this section so repeated sections
    # don't accidentally reuse old data.
    for key in list(_facing_params.keys()):
        s, _, _ = key
        if s == sec:
            del _facing_params[key]
    return (anchor_map, append_lines)

SECTION_REGEX = re.compile(r'^[ \t]*\[([^]]+)\][ \t]*(?:;.*)?$')
KEY_VALUE_REGEX = re.compile(r'^[ \t]*(;?)[ \t]*([^=]+)=[ \t]*(.*)$')

def _ensure_utf8_stdio():
    """
    Force UTF-8 output on Windows consoles / redirection to avoid
    UnicodeEncodeError (e.g., when encountering U+FEFF BOM).
    """
    try:
        # Python 3.7+ supports reconfigure on text I/O wrappers.
        sys.stdout.reconfigure(encoding='utf-8', errors='strict')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        # If reconfigure isn't available, continue — input handling
        # below still strips a BOM via 'utf-8-sig'.
        pass

def _remap_member_key(orig_key: str):
    """
    Global mapping for any key that starts with p1./p2. and contains a ".memberX"
    segment anywhere in the key path. The mapping is:
      p1.member1 -> p1 (member segment removed)
      p1.member2 -> p3
      p1.member3 -> p5
      p1.member4 -> p7
      p2.member1 -> p2 (member segment removed)
      p2.member2 -> p4
      p2.member3 -> p6
      p2.member4 -> p8

    Examples:
      p1.member3.icon.offset            -> p5.icon.offset
      p1.value.empty.icon.member4.spr   -> p7.value.empty.icon.spr
      p2.member2.icon.spr               -> p4.icon.spr
    """
    m = re.match(r'^(p)([12])(\..*)$', orig_key, flags=re.IGNORECASE)
    if not m:
        return orig_key, False

    p_letter, base_str, rest = m.group(1), m.group(2), m.group(3)
    mm = re.search(r'\.member([1-4])', rest, flags=re.IGNORECASE)
    if not mm:
        return orig_key, False

    base = int(base_str)
    member = int(mm.group(1))
    target_map = {1: [1, 3, 5, 7], 2: [2, 4, 6, 8]}
    new_p = target_map[base][member - 1]
    new_rest = rest[:mm.start()] + rest[mm.end():]  # remove ".memberX" only
    return f"{p_letter}{new_p}{new_rest}", True

def _remap_boxcursor_alpharange(orig_key: str):
    """
    If key name ends with 'boxcursor.alpharange' the mapping changes the key to
    'boxcursor.pulse'. Values set to '30, 20, 30'.
    """
    m = re.match(r'^(.*\bboxcursor)\.alpharange$', orig_key, flags=re.IGNORECASE)
    if not m:
        return orig_key, False
    return f"{m.group(1)}.pulse", True

def _split_value_comment(s: str):
    """
    Split a 'value[  ;comment]' into ('value', '[  ;comment]'), preserving any
    original spacing before the semicolon. If there is no inline comment, the
    second element is an empty string.
    """
    m = re.match(r'^(.*?)([ \t]*;.*)?$', s)
    return (m.group(1), m.group(2) or '') if m else (s, '')

def _should_strip_all_quotes_for_key(orig_key: str) -> bool:
    """
    Only strip ALL quote characters for:
      - keys suffixed with ".key" (case-insensitive)
      - the key named exactly "glyphs" (case-insensitive)
    """
    k = (orig_key or "").strip()
    return k.lower() == "glyphs" or k.lower().endswith(".key")

def _unwrap_wrapping_quotes(value_body: str):
    """
    If the entire value is wrapped in double-quotes (ignoring outer whitespace),
    return (True, inner_without_outer_quotes). Otherwise return (False, original).

    NOTE: This only removes ONE outer pair; it does NOT remove interior quotes.
    """
    s = value_body if value_body is not None else ""
    m = re.match(r'^\s*"(.*)"\s*$', s, flags=re.DOTALL)
    if m:
        return True, m.group(1)
    return False, s

def _normalize_key_value_if_needed(orig_key: str, value: str) -> str:
    """If key name ends with '.key' (case-insensitive), turn 'a&b&c' into 'a, b, c'."""
    if re.search(r'\.key$', orig_key, flags=re.IGNORECASE):
        parts = [p.strip() for p in value.split('&') if p.strip() != '']
        new_value = ', '.join(parts) if parts else value.strip()
        return new_value
    return value

def _pause_before_exit():
    """
    On interactive consoles, wait for user confirmation before exiting
    so that messages are visible when the script is launched by double-click.
    """
    try:
        if sys.stdin.isatty():
            input("Press Enter to exit...")
    except Exception:
        # If stdin is not available or something goes wrong, just ignore.
        pass

def _select_ini_via_dialog():
    """
    Windows-only helper: open a file selection dialog (defaulting to .def) and
    return the chosen path, or an empty string/None if the user cancels.
    """
    root = tk.Tk()
    root.withdraw()
    root.update()
    file_path = filedialog.askopenfilename(
        title="Select screenpack file to patch",
        defaultextension=".def",
        filetypes=[
            ("Screenpack files", "*.def"),
            ("INI files", "*.ini"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return file_path

def process_ini(ini_path, output_stream, has_info=None, raw_version=None, parsed_version=None):
    """
    Core processing: read an INI file, apply all rules, and write the resulting
    lines to `output_stream` (a file-like object such as sys.stdout or
    an io.StringIO instance).
    """
    current_section = ""
    info_section_seen = False
    # True once we have written an active ikemenversion line in [Info].
    ikemenversion_written = False
    # Track active (non-commented) keys we've seen per section (case-insensitive).
    seen_keys_by_section = {}

    # Buffer lines within a section so we can insert generated lines
    # (aggregations) at the point where their triggering line occurred
    section_buffer = []

    def _resolve_anchors(buf, anchor_to_lines, trailing_lines):
        out = []
        for item in buf:
            if isinstance(item, _AnchorToken):
                lines = anchor_to_lines.pop(item, [])
                if lines:
                    out.extend(lines)
                # If no lines mapped, drop the placeholder entirely.
            else:
                out.append(item)
        # Any leftovers (should be rare) preserve previous behavior by appending.
        for lines in anchor_to_lines.values():
            out.extend(lines)
        if trailing_lines:
            out.extend(trailing_lines)
        return out

    def _finalize_section(section_name: str, buf):
        """
        - Insert append_if_missing lines *before* trailing blank/comment tail.
        - Flush aggregation helpers, inserting their generated lines at the
          AnchorToken location (the line that first initiated that aggregation).
        """
        if not section_name:
            # Still allow velocity/scale/offset buffers for empty section names to clear,
            # but there should be none in practice.
            return buf

        # 1) Append-if-missing (but *before* trailing comments/blanks)
        section_map = append_if_missing.get(section_name, {})
        missing_items = []
        if section_map:
            seen = seen_keys_by_section.get(section_name, set())
            for k, v in section_map.items():
                key_norm = str(k).strip().lower()
                if key_norm not in seen:
                    print(f"[{section_name}] Appending missing key: {k}", file=sys.stderr)
                    new_items = handle_line(
                        section=section_name,
                        orig_key=str(k),
                        value=str(v),
                        comment=""
                    )
                    if new_items:
                        missing_items.extend(new_items)

        if missing_items:
            # Insert right before the trailing blank/comment tail to avoid separating
            # "header comments" intended for the next section.
            i = len(buf) - 1
            while i >= 0 and _is_trailing_comment_or_blank_line(buf[i]):
                i -= 1
            insert_at = i + 1
            buf = buf[:insert_at] + missing_items + buf[insert_at:]

        # 2) Flush aggregations for this section and insert at their anchors
        anchor_map = {}
        trailing_lines = []

        a1, t1 = _flush_member_offsets_for_section(section_name)
        anchor_map.update(a1)
        trailing_lines.extend(t1)

        a2, t2 = _flush_member_scales_for_section(section_name)
        for k, v in a2.items():
            anchor_map.setdefault(k, []).extend(v)
        trailing_lines.extend(t2)

        a3, t3 = _flush_velocity_for_section(section_name)
        for k, v in a3.items():
            anchor_map.setdefault(k, []).extend(v)
        trailing_lines.extend(t3)

        # Replace AnchorTokens with their generated lines.
        return _resolve_anchors(buf, anchor_map, trailing_lines)

    # If caller indicated that there is no [Info] section at all, create one
    # at the very top of the output with the target ikemenversion.
    if has_info is False:
        print("[Info]", file=output_stream)
        print(f"ikemenversion = {TARGET_IKEMEN_VERSION_STR}", file=output_stream)
        print("", file=output_stream)
        info_section_seen = True
        ikemenversion_written = True

    with open(ini_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            raw_line = line.rstrip('\n')

            if raw_line.lstrip().startswith(";"):
                section_buffer.append(raw_line)
                continue

            # 1) Check if it's a [Section] line
            section_match = SECTION_REGEX.match(raw_line)
            if section_match:
                # Before switching sections, finalize & emit the previous buffer.
                finalized = _finalize_section(current_section, section_buffer)
                for item in finalized:
                    print(item, file=output_stream)
                section_buffer = []
                orig_section_name = section_match.group(1).strip()
                sec_lower = orig_section_name.lower()
                sec_lower = SECTION_RENAMES.get(sec_lower, sec_lower)
                current_section = sec_lower
                if current_section == "info":
                    info_section_seen = True
                # Rewrite section header (preserve leading whitespace and trailing comments)
                lb = raw_line.find("[")
                rb = raw_line.rfind("]")
                prefix = raw_line[:lb] if lb != -1 else ""
                suffix = raw_line[rb+1:] if rb != -1 else ""
                out_name = SECTION_CANONICAL_CASE.get(current_section, orig_section_name)
                print(f"{prefix}[{out_name}]{suffix}", file=output_stream)
                # If [Info] exists but has no active ikemenversion entry, insert it
                # immediately after the section header (only once).
                if current_section == "info" and raw_version is None and not ikemenversion_written:
                    section_buffer.append(f"ikemenversion = {TARGET_IKEMEN_VERSION_STR}")
                    ikemenversion_written = True
                continue

            # 2) Check if it's a key=value line with optional comment
            kv_match = KEY_VALUE_REGEX.match(raw_line)
            if kv_match:
                semicolon = kv_match.group(1)  # ";" or ""
                raw_key = kv_match.group(2)
                raw_value = kv_match.group(3)

                raw_value_original = raw_value
                preserve_original_line = True

                comment_marker = ";" if semicolon == ";" else ""
                clean_key = raw_key.strip()
                # Record only active (non-commented) keys as "present" in this section.
                if comment_marker != ";":
                    seen_keys_by_section.setdefault(current_section, set()).add(clean_key.lower())

                # If we are in [Info] and see ikemenversion, force it to the
                # target version while preserving any inline comment.
                if current_section == "info" and comment_marker != ";" and clean_key.lower() == "ikemenversion":
                    body, inline_comment = _split_value_comment(raw_value)
                    raw_value = f"{TARGET_IKEMEN_VERSION_STR}{inline_comment}"
                    preserve_original_line = False
                    ikemenversion_written = True
                    print(
                        f"[info] Updating ikemenversion to {TARGET_IKEMEN_VERSION_STR}",
                        file=sys.stderr,
                    )

                new_items = handle_line(
                    section=current_section,
                    orig_key=clean_key,
                    value=raw_value,
                    comment=comment_marker,
                    # Only preserve the original raw line if we didn't already force a semantic change before handle_line() runs.
                    raw_line=(raw_line if preserve_original_line and raw_value == raw_value_original else None),
                )

                # Write whatever lines we got back (unless empty => deleted)
                if new_items:
                    section_buffer.extend(new_items)
            else:
                # 3) Not a key-value line => pass it unchanged
                section_buffer.append(raw_line)

    # End of file: flush appends for the final section.
    finalized = _finalize_section(current_section, section_buffer)
    for item in finalized:
        print(item, file=output_stream)

    # For callers that didn't provide has_info/raw_version (legacy usage),
    # fall back to adding [Info] at the end if it was never seen.
    if has_info is None and not info_section_seen:
        print(f"[info] Adding missing [Info] section with ikemenversion = {TARGET_IKEMEN_VERSION_STR}", file=sys.stderr)
        print("", file=output_stream)
        print("[Info]", file=output_stream)
        print(f"ikemenversion = {TARGET_IKEMEN_VERSION_STR}", file=output_stream)


def main(argv=None):
    """
    CLI entry point.

    Default: patch the INI file in place.
    Optional: --stdout to write patched contents to stdout (like the original script).
    """
    _ensure_utf8_stdio()

    parser = argparse.ArgumentParser(
        description=(
            "Update / patch an INI file in-place (default) or write to stdout.\n\n"
            "Windows: if started without arguments, a file picker dialog will open.\n"
            "macOS/Linux: run with a path argument, e.g. screenpack-updater path/to/system.def"
        )
    )
    parser.add_argument(
        "ini_path",
        nargs="?",
        help="Path to the INI file to process.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write patched INI to stdout instead of modifying the file in place.",
    )

    args = parser.parse_args(argv)

    ini_path = args.ini_path

    # If no path was passed on the command line, decide behavior by platform.
    if ini_path is None:
        if sys.platform == "win32":
            # Show a file picker dialog so users can choose an INI file.
            try:
                ini_path = _select_ini_via_dialog()
            except Exception as e:
                print(f"Error opening file dialog: {e}", file=sys.stderr)
                _pause_before_exit()
                return

            if not ini_path:
                print("No file selected. Exiting.", file=sys.stderr)
                _pause_before_exit()
                return
        else:
            # On macOS/Linux, just show help and exit if no args.
            parser.print_help(sys.stderr)
            print("\nExample:", file=sys.stderr)
            print("  screenpack-updater path/to/system.def", file=sys.stderr)
            sys.exit(1)

    # Detect existing ikemenversion to decide if patching is needed.
    has_info, raw_version, parsed_version = _detect_ikemen_version(ini_path)

    patch_needed = False
    reason = ""
    if not has_info:
        patch_needed = True
        reason = "no [Info] section present"
    elif raw_version is None:
        patch_needed = True
        reason = "no active ikemenversion entry in [Info]"
    elif parsed_version is None:
        patch_needed = True
        reason = f"unable to parse ikemenversion '{raw_version.strip()}'"
    elif parsed_version < TARGET_IKEMEN_VERSION:
        patch_needed = True
        reason = f"ikemenversion {parsed_version} < target {TARGET_IKEMEN_VERSION}"
    else:
        patch_needed = False
        reason = (
            f"ikemenversion {parsed_version} >= target {TARGET_IKEMEN_VERSION} "
            "- patching not needed"
        )

    if not patch_needed:
        print(f"[info] {reason}", file=sys.stderr)
        if args.stdout:
            # For --stdout, still output the original file so the behavior is predictable.
            with open(ini_path, "r", encoding="utf-8-sig", errors="replace") as f:
                sys.stdout.write(f.read())
        _pause_before_exit()
        return

    print(f"[info] Patching required: {reason}", file=sys.stderr)

    if args.stdout:
        # write updated content to stdout.
        process_ini(ini_path, sys.stdout, has_info=has_info, raw_version=raw_version, parsed_version=parsed_version)
        # Inform user which ikemenversion the file was updated to.
        if raw_version is None:
           from_str = "missing/invalid"
        else:
            from_str = raw_version.strip()
        print(
            f"[info] ikemenversion updated to {TARGET_IKEMEN_VERSION_STR} (was {from_str})",
            file=sys.stderr,
        )
        _pause_before_exit()
    else:
        # patch in place, creating a .bak backup first.
        backup_path = ini_path + ".bak"
        try:
            shutil.copy2(ini_path, backup_path)
            print(f"Backup created: {backup_path}", file=sys.stderr)
        except Exception as e:
            print(
                f"WARNING: Failed to create backup '{backup_path}': {e}",
                file=sys.stderr,
            )

        buf = io.StringIO()
        process_ini(ini_path, buf, has_info=has_info, raw_version=raw_version, parsed_version=parsed_version)
        new_content = buf.getvalue()
        with open(ini_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(new_content)

        # Inform user which ikemenversion the file was updated to.
        if raw_version is None:
            from_str = "missing/invalid"
        else:
            from_str = raw_version.strip()
        print(
            f"[info] ikemenversion updated to {TARGET_IKEMEN_VERSION_STR} (was {from_str})",
            file=sys.stderr,
        )
        _pause_before_exit()

def handle_line(section, orig_key, value, comment, raw_line=None):
    """
    1) Check if key should be deleted (keys_to_delete).
    2) If not deleted, apply value modifications (value_modifications).
    3) Quote handling:
       - For *.key and glyphs: remove ALL double-quote characters from values.
       - For all other keys: preserve quotes (including full-value wrapping quotes).
    4) Apply transformations on the key (transformations).
    Return a list of lines to print. If empty => line is removed entirely.
    """
    changed = False
    # Check for key deletion
    for pattern in keys_to_delete.get(section, []):
        if pattern.match(orig_key):
            print(f"[{section}] Deleting line for key: {orig_key}", file=sys.stderr)
            return []

    # Work only on the part before an inline comment; keep the comment to reattach later.
    value_body, inline_comment = _split_value_comment(value)

    # Preserve full-value wrapping quotes for non-target keys, but do all processing
    # on the unwrapped inner value so numeric parsing/regex rules keep working.
    was_wrapped, inner_value = _unwrap_wrapping_quotes(value_body)
    strip_all_quotes = _should_strip_all_quotes_for_key(orig_key)

    if strip_all_quotes and was_wrapped:
        changed = True

    # Value modifications
    new_value = inner_value
    for (key_rx, val_rx, repl) in value_modifications.get(section, []):
        if key_rx.match(orig_key):
            old_value = new_value
            new_value = val_rx.sub(repl, new_value)
            if new_value != old_value:
                changed = True
                print(
                    f"[{section}] Value modified for key {orig_key}: "
                    f"'{old_value}' => '{new_value}'",
                    file=sys.stderr
                )

    # Quote handling:
    # - For *.key and glyphs: strip ALL quote chars.
    # - Otherwise: keep exactly whether the original was wrapped.
    if strip_all_quotes:
        stripped = new_value.replace('"', '')
        if stripped != new_value:
            changed = True
        new_value = stripped

    # Value for parsing/aggregation checks should never include wrapping quotes.
    # (And for strip_all_quotes keys, it also won't include interior quotes.)
    value_for_logic = new_value

    # Globally normalize any "*.key" value: a&b&c -> a, b, c
    if re.search(r'\.key$', orig_key, re.IGNORECASE):
        old_v = new_value
        new_value = _normalize_key_value_if_needed(orig_key, new_value)
        if new_value != old_v:
            changed = True
            print(
                f"[global] Normalized .key list for {orig_key}: '{old_v}' => '{new_value}'",
                file=sys.stderr
            )
        value_for_logic = new_value

    # Only active (non-commented) lines participate in aggregation helpers.
    # Commented lines (starting with ';') should remain comments and must not
    # produce new active entries.
    if comment != ";":
        # Record facing first so it's available when we later turn slide.speed
        # into velocity with the correct direction.
        _record_facing_param(section, orig_key, value_for_logic)

        # Then, see if this is a base/member offset that should be aggregated
        # into a single pX[.face|.face2].offset per final player.
        handled, anchor = _record_member_offset_param(section, orig_key, value_for_logic)
        if handled:
            return [anchor] if anchor is not None else []

        # Next, see if this is a base/member scale that should be aggregated.
        handled, anchor = _record_member_scale_param(section, orig_key, value_for_logic)
        if handled:
            return [anchor] if anchor is not None else []

    # Convert p1/p2 + ".memberX" segments into p1/p3/p5/p7 or p2/p4/p6/p8,
    # and drop the ".memberX" segment from the key path.
    remapped_key, did_remap = _remap_member_key(orig_key)
    if did_remap:
        changed = True
        print(f"[global] Member key remapped: {orig_key} => {remapped_key}", file=sys.stderr)
        orig_key = remapped_key

    # Convert any '<prefix>boxcursor.alpharange' into '<prefix>boxcursor.pulse'
    remapped_key2, did_remap2 = _remap_boxcursor_alpharange(orig_key)
    if did_remap2:
        changed = True
        print(
            f"[global] Boxcursor alpharange remapped: {orig_key} => {remapped_key2}; "
            f"value forced to '30, 20, 30'",
            file=sys.stderr,
        )
        orig_key, new_value = remapped_key2, "30, 20, 30"

    # In menu-related sections, convert any *.itemname.*empty with an empty value
    # into *.itemname.*spacer = -
    #
    # Example:
    #   menu.itemname.foo.empty =
    # becomes:
    #   menu.itemname.foo.spacer = -
    if comment != ";" and section in (
        "title info",
        "select info",
        "option info",
        "attract mode",
        "pause menu",
        "training pause menu",
        "replay info",
    ):
        m = re.match(r"^(.+\.itemname\..*)empty$", orig_key, flags=re.IGNORECASE)
        if m and value_for_logic.strip() == "":
            new_key = m.group(1) + "spacer"
            print(
                f"[{section}] Converting empty itemname: {orig_key} => {new_key} = -",
                file=sys.stderr,
            )
            return [f"{comment}{new_key} = -{inline_comment}"]

    # Expand [Hiscore Info] title.text into six fixed lines
    if section == "hiscore info" and re.match(r"^title\.text$", orig_key, re.IGNORECASE):
        changed = True
        # Preserve wrapping quotes ONLY if the original value was wrapped and this
        # key is not one of the quote-stripping targets.
        q = '"' if (was_wrapped and not strip_all_quotes) else ""
        out_lines = [
            f"{comment}title.text.arcade = {q}Ranking Arcade{q}",
            f"{comment}title.text.teamarcade = {q}Ranking Team Arcade{q}",
            f"{comment}title.text.teamcoop = {q}Ranking Team Cooperative{q}",
            f"{comment}title.text.timeattack = {q}Ranking Time Attack{q}",
            f"{comment}title.text.survival = {q}Ranking Survival{q}",
            f"{comment}title.text.survivalcoop = {q}Ranking Survival Cooperative{q}",
        ]
        print(
            f"[{section}] Expanded {orig_key} into 6 title.text.* lines",
            file=sys.stderr
        )
        return out_lines

    # After member remapping and other adjustments, capture slide.speed so we
    # can convert it into velocity (with facing applied) when the section ends.
    if comment != ";":
        handled, anchor = _record_velocity_param(section, orig_key, value_for_logic)
        if handled:
            return [anchor] if anchor is not None else []

    # Prepare output value with preserved wrapping quotes for non-target keys.
    if (not strip_all_quotes) and was_wrapped:
        value_for_output = f"\"{new_value}\""
    else:
        value_for_output = new_value

    # Key transformations
    transformed_lines = apply_key_transformations(section, orig_key, value_for_output + inline_comment, comment)
    if transformed_lines:
        return transformed_lines

    # No semantic changes: preserve original formatting exactly to avoid whitespace-only "linting"
    if raw_line is not None and not changed:
        return [raw_line]

    # Keep as is
    return [f"{comment}{orig_key} = {value_for_output}{inline_comment}"]

def apply_key_transformations(section, orig_key, value, comment):
    # Special-case [Select Info] where we now want 0-based indices instead of 1-based.
    # This keeps the param rename (row.col -> row-col) but also shifts indices by -1.
    if section == "select info":
        # cell.<row>.<col>.(offset|facing|skip) -> cell.<row-1>-<col-1>.(...)
        m = re.match(
            r"^cell\.([0-9]+)\.([0-9]+)\.(offset|facing|skip)$",
            orig_key,
            flags=re.IGNORECASE,
        )
        if m:
            row = int(m.group(1)) - 1
            col = int(m.group(2)) - 1
            suffix = m.group(3).lower()
            new_key = f"cell.{row}-{col}.{suffix}"
            print(
                f"[{section}] Key modified (1-based -> 0-based): {orig_key} => {new_key}",
                file=sys.stderr,
            )
            return [f"{comment}{new_key} = {value}"]

        # p<1|2>.cursor.(active|done).<row>.<col>.(anim|spr|offset|facing|scale) ->
        # p<1|2>.cursor.(active|done).<row-1>-<col-1>.(...)
        m = re.match(
           r"^p([12])\.cursor\.(active|done)\.([0-9]+)\.([0-9]+)\."
            r"(anim|spr|offset|facing|scale)$",
            orig_key,
            flags=re.IGNORECASE,
        )
        if m:
            player = m.group(1)
            cursor_state = m.group(2).lower()   # active / done
            row = int(m.group(3)) - 1
            col = int(m.group(4)) - 1
            suffix = m.group(5).lower()
            new_key = f"p{player}.cursor.{cursor_state}.{row}-{col}.{suffix}"
            print(
                f"[{section}] Key modified (1-based -> 0-based): {orig_key} => {new_key}",
                file=sys.stderr,
            )
            return [f"{comment}{new_key} = {value}"]

    section_rules = transformations.get(section, [])
    for (pattern, replacements) in section_rules:
        m = pattern.match(orig_key)
        if m:
            out_lines = []
            for rep in replacements:
                new_key = m.expand(rep)
                val_out = value
                out_lines.append(f"{comment}{new_key} = {val_out}")
                print(f"[{section}] Key modified: {orig_key} => {new_key}", file=sys.stderr)
            # Stop after the first matching rule to avoid duplicate transformations.
            return out_lines
    return None


if __name__ == "__main__":
    main()
