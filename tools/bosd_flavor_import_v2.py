#!/usr/bin/env python3
"""Compatibility CLI for the historical printing-specific English flavor importer."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.flavor import import_flavor, load_json_cards, read_csv, write_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--master-in", type=Path, required=True)
    parser.add_argument("--display-in", type=Path, required=True)
    parser.add_argument("--master-out", type=Path, required=True)
    parser.add_argument("--display-out", type=Path, required=True)
    parser.add_argument("--qa-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--unique-reprint-fallback", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    master = read_csv(args.master_in)
    display = read_csv(args.display_in)
    qa, report = import_flavor(
        load_json_cards(args.json),
        read_csv(args.crosswalk),
        master,
        display,
        unique_reprint_fallback=args.unique_reprint_fallback,
    )
    write_csv(args.master_out, master)
    write_csv(args.display_out, display)
    write_csv(args.qa_out, qa)

    lines = ["BOTSD flavor import v2"] + [
        f"{key.replace('_', ' ').title()}: {value}" for key, value in report.__dict__.items()
    ]
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.summary_out:
        args.summary_out.write_text(text, encoding="utf-8")
    return 2 if args.strict and report.remaining_untranslated_source_flavor else 0


if __name__ == "__main__":
    raise SystemExit(main())
