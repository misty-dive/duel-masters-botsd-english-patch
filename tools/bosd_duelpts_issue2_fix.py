#!/usr/bin/env python3
"""Compatibility CLI for the verified v1.2 Issue #2 DUELPTS digit repair."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.duelpts import build_issue2_fix, load_spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean_duelpts", type=Path)
    parser.add_argument("v11_duelpts", type=Path)
    parser.add_argument("output_duelpts", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--allow-nonretail", action="store_true")
    args = parser.parse_args()

    result = build_issue2_fix(
        args.clean_duelpts.read_bytes(),
        args.v11_duelpts.read_bytes(),
        spec=load_spec(args.spec) if args.spec else None,
        verify_hashes=not args.allow_nonretail,
    )
    args.output_duelpts.parent.mkdir(parents=True, exist_ok=True)
    args.output_duelpts.write_bytes(result.data)
    text = "\n".join(result.report_lines) + "\n"
    print(text, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
