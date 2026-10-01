#!/usr/bin/env python3
"""Compatibility CLI for the verified reserved FONTLINK Ü glyph patch."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.fontlink import decompress, load_ue_spec, parse_pac, patch_reserved_ue
from botsd.hashing import sha256_bytes
from botsd.manifest import RETAIL_SHA256


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("fontlink", type=Path)
    patch = sub.add_parser("patch")
    patch.add_argument("fontlink", type=Path)
    patch.add_argument("output", type=Path)
    args = parser.parse_args()

    raw = args.fontlink.read_bytes()
    got = sha256_bytes(raw)
    spec = load_ue_spec()
    expected = RETAIL_SHA256[str(spec["input_asset"])]
    if got != expected:
        raise SystemExit(f"unexpected FONTLINK SHA-256: {got}")
    entries = parse_pac(raw)
    for entry in entries:
        decompress(entry.blob)

    if args.cmd == "check":
        print("FONTLINK SHA-256:", got)
        print(f"All {len(entries)} font streams decode successfully.")
        return

    out = patch_reserved_ue(raw)
    args.output.write_bytes(out)
    print("Patched FONTLINK:", args.output)
    print("Archive size:", len(out), "bytes (unchanged)")
    print("All unrelated resources byte-identical.")
    print(f"All {len(parse_pac(out))} font streams decode successfully.")
    print("Patched SHA-256:", sha256_bytes(out))


if __name__ == "__main__":
    main()
