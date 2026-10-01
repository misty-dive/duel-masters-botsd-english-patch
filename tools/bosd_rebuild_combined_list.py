#!/usr/bin/env python3
"""Compatibility CLI for rebuilding the 4,058-pointer externalized LIST_1.BIN."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.cardtext import (
    DISPLAY_COUNT,
    MASTER_COUNT,
    TOTAL_POINTERS,
    build_combined_list,
    materialize_translation_rows,
    parse_combined_relative,
    read_csv_rows,
)
from botsd.hashing import sha256_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    display_rows = read_csv_rows(args.display)
    master_rows = read_csv_rows(args.master)
    if len(display_rows) != DISPLAY_COUNT or len(master_rows) != MASTER_COUNT:
        raise ValueError(
            f"wrong row counts: display={len(display_rows)} master={len(master_rows)}"
        )
    display = materialize_translation_rows(display_rows, "list_index", DISPLAY_COUNT)
    master = materialize_translation_rows(master_rows, "master_text_id", MASTER_COUNT)
    raw = build_combined_list(display, master)
    dcheck, mcheck = parse_combined_relative(raw)
    if dcheck != display or mcheck != master:
        raise RuntimeError("combined LIST round-trip self-check failed")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    print(f"Wrote {args.out}")
    print(f"Pointers: {TOTAL_POINTERS} = {DISPLAY_COUNT} display + {MASTER_COUNT} master")
    print(f"Size: {len(raw)} bytes")
    print(f"SHA-256: {sha256_bytes(raw)}")


if __name__ == "__main__":
    main()
