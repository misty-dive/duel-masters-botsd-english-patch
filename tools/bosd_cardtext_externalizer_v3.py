#!/usr/bin/env python3
"""Compatibility CLI for BOTSD card-text externalization.

The parser, combined-LIST builder, CP932 rules and executable patch now live in
:mod:`botsd.cardtext` so they can be tested/reused without importing another command script.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.cardtext import (
    CARD_TEXT_OBJECT_GLOBAL_GP_OFF,
    CODE_CAVE_VA,
    DISPLAY_COUNT,
    LOAD_VA_DELTA,
    LOOP_COUNT_VA,
    MASTER_COUNT,
    MASTER_POINTER_BYTE_OFFSET,
    MASTER_TABLE_VA,
    TEXT_RESOURCE_GLOBAL_GP_OFF,
    TOTAL_POINTERS,
    build_combined_list,
    build_externalized,
    check_patch_sites,
    decode_game_text,
    encode_cp932,
    encode_i,
    encode_j,
    encode_r,
    load_translation_csv,
    parse_combined_relative,
    parse_master_text,
    parse_retail_list,
    patch_executable,
    read_cstr,
    va_to_off,
)
from botsd.hashing import sha256_bytes

# Preserve the historical helper name for downstream notes/imports.
sha256 = sha256_bytes


def _check(exe: Path, list1: Path) -> None:
    executable = exe.read_bytes()
    print(f"Executable SHA-256: {sha256_bytes(executable)}")
    print(f"LIST_1 SHA-256:     {sha256_bytes(list1.read_bytes())}")
    parse_retail_list(list1)
    parse_master_text(executable)
    check_patch_sites(executable)
    print(f"Retail LIST meaningful entries: {DISPLAY_COUNT}")
    print(f"Embedded master text entries:   {MASTER_COUNT}")
    print(f"Combined relocation count:      {TOTAL_POINTERS} (0x{TOTAL_POINTERS:X})")
    print(f"Appended master table offset:   0x{MASTER_POINTER_BYTE_OFFSET:X}")
    print("Source/patch-site validation: OK")


def _build(args: argparse.Namespace) -> None:
    result = build_externalized(
        args.exe.read_bytes(),
        args.list1.read_bytes(),
        args.master_csv,
        args.display_csv,
    )
    args.out_exe.parent.mkdir(parents=True, exist_ok=True)
    args.out_list1.parent.mkdir(parents=True, exist_ok=True)
    args.out_exe.write_bytes(result.executable)
    args.out_list1.write_bytes(result.combined_list)
    print(f"Patched executable: {args.out_exe}")
    print(f"  size: {len(result.executable)} bytes (unchanged)")
    print(f"  SHA-256: {sha256_bytes(result.executable)}")
    print(f"Combined LIST_1: {args.out_list1}")
    print(f"  pointers: {TOTAL_POINTERS} ({DISPLAY_COUNT} display + {MASTER_COUNT} master)")
    print(f"  size: {len(result.combined_list)} bytes")
    print(f"  SHA-256: {sha256_bytes(result.combined_list)}")
    print("Offline pointer/text validation: OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("exe", type=Path)
    check.add_argument("list1", type=Path)
    build = sub.add_parser("build")
    build.add_argument("exe", type=Path)
    build.add_argument("list1", type=Path)
    build.add_argument("master_csv", type=Path)
    build.add_argument("display_csv", type=Path)
    build.add_argument("out_exe", type=Path)
    build.add_argument("out_list1", type=Path)
    args = parser.parse_args()
    if args.cmd == "check":
        _check(args.exe, args.list1)
    else:
        _build(args)


if __name__ == "__main__":
    main()
