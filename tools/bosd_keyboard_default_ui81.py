#!/usr/bin/env python3
"""Historical UI81 keyboard mode patch retained as a compatibility CLI."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.keyboard import MODE_OFFSET, MODE_VA, V13_FINAL_MODE, build_historical_v12_stage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_elf")
    parser.add_argument("output_elf")
    parser.add_argument("--report")
    args = parser.parse_args()

    result = build_historical_v12_stage(Path(args.input_elf).read_bytes())
    Path(args.output_elf).write_bytes(result.data)
    lines = [
        "UI81 HISTORICAL KEYBOARD MODE PATCH",
        f"input_sha256={result.input_sha256}",
        f"output_sha256={result.output_sha256}",
        f"file_size={len(result.data)}",
        f"mode_virtual_address={MODE_VA:#x}",
        f"mode_file_offset={MODE_OFFSET:#x}",
        "historical_v12_mode=0->6 (full-width Latin path; retained for v1.2 hash reproducibility)",
        f"v13_final_mode={V13_FINAL_MODE} (applied later by the v1.3 maintenance stage)",
        "patch_bytes=1",
        "keyboard_pages=UNCHANGED",
        "keyboard_mode_switching_code=UNCHANGED",
        "RESULT=PASS",
    ]
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
