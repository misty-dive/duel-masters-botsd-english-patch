#!/usr/bin/env python3
"""Compatibility CLI for hash-gated fixed-size DATAPACK chunk patches."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.datapack import apply_chunk_patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    target, result = apply_chunk_patch(args.retail.read_bytes(), args.patch)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    print(f"Patched {len(result.changed_chunks)} DATAPACK chunks: {list(result.changed_chunks)}")
    print(f"Output SHA-256: {result.sha256}")


if __name__ == "__main__":
    main()
