#!/usr/bin/env python3
"""Compatibility CLI for the shared PPF3 implementation in :mod:`botsd.ppf`."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.hashing import sha256_path
from botsd.ppf import build, verify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--description", default="Duel Masters BOTSD English patch")
    args = parser.parse_args()
    for path in (args.source, args.target):
        if not path.is_file():
            parser.error(f"file not found: {path}")
    stats, changed = build(args.source, args.target, args.output, description=args.description)
    parsed = verify(args.output)
    if parsed != stats:
        raise RuntimeError("PPF verification mismatch")
    print("Source SHA-256:", sha256_path(args.source))
    print("Target SHA-256:", sha256_path(args.target))
    print("PPF SHA-256:   ", sha256_path(args.output))
    print("PPF size:      ", args.output.stat().st_size, "bytes")
    print("Records:       ", stats.records)
    print("Changed bytes: ", changed)
    print("Verification: PASS")


if __name__ == "__main__":
    main()
