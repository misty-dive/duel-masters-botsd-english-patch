#!/usr/bin/env python3
"""Compatibility CLI for the recovered UI82 semantic second-name renderer.

The preserved historical source lives under ``tools/archaeology/``.  The maintained
implementation is :mod:`botsd.second_names`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.second_names import render_second_names


def _first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.is_file():
            return path
    raise FileNotFoundError("; expected one of: " + ", ".join(str(path) for path in paths))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail_unpack", type=Path)
    parser.add_argument(
        "project_root",
        type=Path,
        help="historical checkpoint/repository root containing inventory and FONTLINK",
    )
    parser.add_argument("output_zip", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--fontlink", type=Path)
    parser.add_argument("--qa-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--allow-nonretail", action="store_true")
    parser.add_argument("--allow-nonfrozen-output", action="store_true")
    args = parser.parse_args()

    inventory = args.inventory or _first_existing(
        args.project_root / "unpack_card_inventory.csv",
        args.project_root / "data" / "unpack_card_inventory.csv",
    )
    fontlink = args.fontlink or _first_existing(
        args.project_root / "FONTLINK_UI81_EN.PAC",
        args.project_root / "FONTLINK.PAC",
    )
    result = render_second_names(
        args.retail_unpack,
        inventory,
        fontlink,
        args.output_zip,
        qa_dir=args.qa_dir,
        report_csv=args.report,
        verify_retail=not args.allow_nonretail,
        verify_frozen_output=not args.allow_nonfrozen_output,
    )
    print("UI82 SECOND-SPRITE SEMANTIC RENDER: PASS")
    print(f"chunks={result.chunks}")
    print(f"payload_sha256={result.payload_sha256}")
    print(f"zip={args.output_zip}")
    print(f"zip_sha256={result.patch_zip_sha256}")
    print(f"fallback_title_detectors={result.fallback_title_detectors}")
    print(f"changed_pixels_total={result.changed_pixels_total}")
    print("full_card_reconversion_performed=no")


if __name__ == "__main__":
    main()
