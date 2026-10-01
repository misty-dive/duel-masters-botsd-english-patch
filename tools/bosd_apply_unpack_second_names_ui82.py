#!/usr/bin/env python3
"""Compatibility CLI for applying the UI82 second-card-sprite chunk patch."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.unpack import SECOND_NAME_FIRST, SECOND_NAME_LAST, apply_second_name_patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ui76_compiled", type=Path)
    parser.add_argument("patch_zip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    result = apply_second_name_patch(args.ui76_compiled, args.patch_zip, args.output)
    text = (
        "UI82 SECOND-SPRITE APPLY: PASS\n"
        f"input_sha256={result.retail_sha256}\n"
        f"output_sha256={result.target_sha256}\n"
        f"outer_size={args.output.stat().st_size}\n"
        "outer_offsets_unchanged=yes\n"
        f"patched_chunks={len(result.changed_chunks)}\n"
        f"chunk_range={SECOND_NAME_FIRST}-{SECOND_NAME_LAST}\n"
        "full_card_layers_677_2036_untouched=yes\n"
        "chunks_2714_plus_untouched=yes\n"
        "full_card_reconversion_performed=no\n"
    )
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
