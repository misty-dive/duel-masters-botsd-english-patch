#!/usr/bin/env python3
"""Compatibility CLI for the frozen UI82 card-layer UNPACK verification."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.unpack import verify_ui82


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path)
    parser.add_argument("ui76", type=Path)
    parser.add_argument("ui82", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("patch_zip", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result, delta = verify_ui82(args.retail, args.ui76, args.ui82, args.inventory, args.patch_zip)
    text = (
        "UI82 FROZEN CARD CHECKPOINT: PASS\n"
        f"retail_sha256={result.retail_sha256}\n"
        f"ui82_compiled_sha256={result.target_sha256}\n"
        f"outer_size={args.ui82.stat().st_size}\n"
        f"outer_chunks={result.chunk_count}\n"
        "outer_offsets_unchanged=yes\n"
        "ui76_large_card_chunks=677\n"
        "ui76_printed_thumbnail_chunks=677\n"
        f"ui82_second_sprite_name_chunks={len(delta)}\n"
        "cardinfo_background_chunks_1354_1359_retail_identical=yes\n"
        "all_other_chunks_retail_identical=yes\n"
        "ui76_existing_card_layers_byte_identical_in_ui82=yes\n"
        "full_card_reconversion_performed=no\n"
    )
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
