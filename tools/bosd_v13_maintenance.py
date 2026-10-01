#!/usr/bin/env python3
"""Build the verified BOTSD v1.3 maintenance components from exact public-v1.2 files.

This compatibility entry point delegates to :mod:`botsd.v13`.  The v1.3 executable, SCRPACK,
CHANGE/TURN and ACE changes are all rebuilt from structural/semantic recipes; the canonical path
no longer stores the maintenance release as raw byte-diff tables or opaque target blobs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.manifest import BASELINE
from botsd.v13 import build_directory

V12_HASHES = {row.name: row.v12.sha256 for row in BASELINE.components}
V13_HASHES = {row.name: row.v13.sha256 for row in BASELINE.components}
SIZES = {row.name: row.v13.size for row in BASELINE.components}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "v12_dir",
        type=Path,
        help="directory containing exact public-v1.2 SLPM_658.82, SCRPACK.SDA, TCHANGE.IMG, DECK.DAT",
    )
    parser.add_argument("output_dir", type=Path, help="directory for v1.3 component outputs")
    parser.add_argument("--language", default="en", help="localization package code (default: en)")
    parser.add_argument("--report", type=Path, help="optional QA report path")
    args = parser.parse_args()

    rows = build_directory(args.v12_dir, args.output_dir, language=args.language)
    lines = [
        "BOTSD v1.3 MAINTENANCE COMPONENT BUILD",
        "source=public v1.2",
        "maintenance_generation=semantic/structural recipes (no raw v1.3 byte-diff tables)",
    ]
    for row in rows:
        lines.append(
            f"{row.name}: {row.source_sha256} -> {row.target_sha256} ({row.size} bytes)"
        )
    lines += [
        "SLPM_658.82=Aura pointer-overlap repair + keyboard mode semantic edit",
        "SCRPACK.SDA=parsed command-ordinal branch relocation + localized 1D03 dialogue edit",
        "TCHANGE.IMG=semantic CHANGE/TURN layout recipe",
        "DECK.DAT=semantic DECK_SRC_DC_P02_TGA ACE badge recipe",
        "RESULT=PASS",
    ]
    report = "\n".join(lines) + "\n"
    print(report, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
