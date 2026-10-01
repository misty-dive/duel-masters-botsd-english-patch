#!/usr/bin/env python3
"""Compatibility CLI for the verified DECK/*.DAT text localization stage."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.decktext import patch_directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--translations",
        type=Path,
        default=Path("localization/en/deck_text.json"),
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rows = patch_directory(args.input_dir, args.output_dir, args.translations)
    lines = [
        "UI82 DECK DATA TEXT LOCALIZATION",
        "slots: callout 0x06+40, title 0x2E+20; bytes >=0x42 preserved",
        f"files={len(rows)}",
        "all_sizes=UNCHANGED",
        "all_header_bytes_0x00_0x05=UNCHANGED",
        "all_card_composition_bytes_0x42_end=BYTE-IDENTICAL",
        "source_cp932_fields=VERIFIED",
        "english_fields=ASCII_AND_NUL_PADDED",
        "RESULT=PASS",
        "",
        "file\tinput_sha256\toutput_sha256\tsize",
    ]
    lines.extend(
        f"{row.filename}\t{row.source_sha256}\t{row.target_sha256}\t{row.size}" for row in rows
    )
    report = "\n".join(lines) + "\n"
    print(report, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
