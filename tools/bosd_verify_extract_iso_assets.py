#!/usr/bin/env python3
"""Compatibility CLI for streaming ISO asset verification/extraction.

Historical syntax is preserved:

    bosd_verify_extract_iso_assets.py ISO HASHES.tsv --extract BASENAME=OUTPUT

The implementation now delegates to :mod:`botsd.extract` and never reads a multi-gigabyte ISO into
one Python bytes object.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.extract import verify_hash_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("hashes", type=Path)
    parser.add_argument("--extract", action="append", default=[], help="BASENAME=OUTPUT")
    args = parser.parse_args()

    extracts: dict[str, Path] = {}
    for item in args.extract:
        if "=" not in item:
            parser.error(f"invalid --extract {item!r}; expected BASENAME=OUTPUT")
        name, output = item.split("=", 1)
        extracts[name] = Path(output)

    rows = verify_hash_manifest(args.iso, args.hashes, extracts)
    for row in rows:
        print(f"OK {row.iso_path} {row.size} bytes {row.sha256}")
        if row.output is not None:
            print(f"Extracted {row.iso_path} -> {row.output}")


if __name__ == "__main__":
    main()
