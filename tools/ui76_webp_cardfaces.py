#!/usr/bin/env python3
"""Compatibility CLI for the accepted UI76 whole-card English image pipeline.

The source mapping/provenance logic and streaming converter now live in
:mod:`botsd.card_sources` and :mod:`botsd.fullcard`. Historical renderer/archive/compressor
path arguments are accepted for existing build recipes but ignored.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.fullcard import build_full_card_images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_unpack", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("crosswalk", type=Path)
    parser.add_argument("renderer_module", type=Path, help="legacy compatibility argument; ignored")
    parser.add_argument("archive_tool", type=Path, help="legacy compatibility argument; ignored")
    parser.add_argument("strong_tool", type=Path, help="legacy compatibility argument; ignored")
    parser.add_argument("out_unpack", type=Path)
    parser.add_argument("qa_dir", type=Path)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--exception-dir", type=Path, required=True)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--jobs", type=int, default=1, help="accepted for compatibility; conversion is streamed deterministically")
    parser.add_argument("--allow-unpinned-db", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--allow-nonretail", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be >= 1")

    report = build_full_card_images(
        args.base_unpack,
        args.inventory,
        args.crosswalk,
        args.out_unpack,
        args.qa_dir,
        cache_dir=args.cache_dir,
        exception_dir=args.exception_dir,
        database=args.db,
        offline=args.offline,
        allow_unpinned_db=args.allow_unpinned_db,
        verify_retail=not args.allow_nonretail,
    )
    print("UI76 FULL-CARD VERIFICATION: PASS")
    print(f"output_sha256={report.output_sha256}")
    print(f"full_card_resources={report.resources}")
    print(f"changed_outer_chunks={report.changed_chunks}")
    print(f"min_compressed_headroom={report.min_compressed_headroom}")
    print(f"min_source_colors={report.min_source_colors}")


if __name__ == "__main__":
    main()
