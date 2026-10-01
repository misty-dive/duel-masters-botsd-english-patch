#!/usr/bin/env python3
"""Compatibility CLI for the historical UI76 card-rule word-wrap stage."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.hashing import sha256_path
from botsd.ruleswrap import MAX_CELLS, read_csv, wrap_rule_tables, write_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-in", type=Path, required=True)
    parser.add_argument("--display-in", type=Path, required=True)
    parser.add_argument("--master-out", type=Path, required=True)
    parser.add_argument("--display-out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    master_fields, master_rows = read_csv(args.master_in)
    display_fields, display_rows = read_csv(args.display_in)
    result = wrap_rule_tables(master_rows, display_rows)
    write_csv(args.master_out, master_fields, master_rows)
    write_csv(args.display_out, display_fields, display_rows)

    lines = [
        "UI76 R7 CARD RULE WORD-WRAP: PASS",
        f"max_cells={MAX_CELLS}",
        f"rules_verified={result.rules_verified}",
        f"rules_with_added_wraps={result.rules_with_added_wraps}",
        f"new_linebreaks_inserted={result.new_linebreaks_inserted}",
        f"display_rows_synchronized={result.display_rows_synchronized}",
        f"max_line_cells_before={result.max_line_cells_before}",
        f"max_line_cells_after={result.max_line_cells_after}",
        f"max_wrapped_lines_per_rule={result.max_wrapped_lines_per_rule}",
        f"master_out_sha256={sha256_path(args.master_out)}",
        f"display_out_sha256={sha256_path(args.display_out)}",
        "All inserted line breaks replace existing ASCII spaces; encoded rule byte lengths are unchanged.",
        "No non-rule master translation is modified.",
    ]
    text = "\n".join(lines) + "\n"
    print(text, end="")
    args.report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
