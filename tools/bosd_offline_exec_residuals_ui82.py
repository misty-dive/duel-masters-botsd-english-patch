#!/usr/bin/env python3
"""Compatibility CLI for the final UI82 offline executable string residuals."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.exec_strings import load_asset_spec, load_strings, patch_fixed_slots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_elf", type=Path)
    parser.add_argument("output_elf", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    spec = load_asset_spec(repo / "botsd" / "assets" / "offline_exec_residuals_ui82.json")
    strings = load_strings(repo / "localization" / "en" / "offline_exec_residuals_ui82.json")
    result = patch_fixed_slots(args.input_elf.read_bytes(), spec, strings)
    args.output_elf.write_bytes(result.data)
    lines = ["UI82 OFFLINE EXECUTABLE RESIDUAL PATCH", *result.report_lines, "RESULT=PASS"]
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.report:
        args.report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
