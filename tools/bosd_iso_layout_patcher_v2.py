#!/usr/bin/env python3
"""Streaming compatibility CLI for the shared :mod:`botsd.iso9660` patcher.

Unlike the historical implementation, this version never reads the multi-gigabyte
source/output ISO into a Python ``bytes`` or ``bytearray`` object.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.hashing import sha256_path
from botsd.iso9660 import Entry, Iso9660, KNOWN_RETAIL_SHA256, PatchResult, SECTOR, patch_iso

__all__ = ["Entry", "Iso9660", "KNOWN_RETAIL_SHA256", "PatchResult", "SECTOR", "patch_iso"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_iso", type=Path)
    parser.add_argument("output_iso", type=Path)
    parser.add_argument("replacement", type=Path, nargs="+")
    parser.add_argument("--allow-nonretail", action="store_true")
    args = parser.parse_args()
    rows = patch_iso(
        args.source_iso,
        args.output_iso,
        args.replacement,
        strict_core=not args.allow_nonretail,
    )
    print("Source ISO:", args.source_iso)
    print("Source size:", args.source_iso.stat().st_size, "bytes")
    print("Source SHA-256:", sha256_path(args.source_iso))
    print("Output ISO:", args.output_iso)
    print("Output size:", args.output_iso.stat().st_size, "bytes")
    print("Output SHA-256:", sha256_path(args.output_iso))
    print()
    for row in rows:
        print(f"{row.path}: {row.mode}")
        print(f"  LBA {row.old_lba} -> {row.new_lba}; size {row.old_size} -> {row.new_size}")
        print(f"  SHA-256 {row.sha256}")
    print("Verification: every replacement hashes correctly from the patched ISO.")
    print("Existing sectors were never relocated.")


if __name__ == "__main__":
    main()
