#!/usr/bin/env python3
"""Compatibility wrapper for the UI76 embedded-English Card Info build.

The maintained implementation lives in :mod:`botsd.cardinfo`.  This historical
filename is kept so old build notes remain usable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.cardinfo import build_embedded_cardinfo, load_spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_elf", type=Path)
    parser.add_argument("master_csv", type=Path)
    parser.add_argument("output_elf", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--spec", type=Path)
    args = parser.parse_args()

    result = build_embedded_cardinfo(
        args.input_elf.read_bytes(),
        args.master_csv,
        spec=load_spec(args.spec) if args.spec else None,
    )
    args.output_elf.parent.mkdir(parents=True, exist_ok=True)
    args.output_elf.write_bytes(result.data)
    text = "\n".join(result.report_lines) + "\n"
    print(text, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
