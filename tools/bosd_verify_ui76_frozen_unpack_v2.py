#!/usr/bin/env python3
"""Compatibility CLI for the frozen UI76 677-card UNPACK verification."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.unpack import verify_ui76


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path)
    parser.add_argument("compiled", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify_ui76(args.retail, args.compiled, args.inventory)
    text = (
        "UI76 FROZEN 677-CARD CHECKPOINT V2: PASS\n"
        f"retail_sha256={result.retail_sha256}\n"
        f"compiled_sha256={result.target_sha256}\n"
        f"outer_size={args.compiled.stat().st_size}\n"
        f"outer_chunks={result.chunk_count}\n"
        "outer_offsets_unchanged=yes\n"
        f"changed_card_chunks={len(result.changed_chunks)}\n"
        "non_card_chunks_byte_identical=yes\n"
        "large_resources=677\n"
        "printed_thumbnail_resources=677\n"
        "final_chunk_checked_through_eof=yes\n"
        "reconversion_performed=no\n"
    )
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
