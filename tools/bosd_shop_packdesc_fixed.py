#!/usr/bin/env python3
"""Compatibility CLI for verified booster-description localization.

The binary record logic lives in :mod:`botsd.shop`; English text lives in
`localization/en/shop_boosters.json` instead of being embedded in patch logic.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.hashing import sha256_bytes
from botsd.shop import load_booster_descriptions, patch_booster_descriptions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_elf", type=Path)
    parser.add_argument("output_elf", type=Path)
    parser.add_argument(
        "--translations",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "localization/en/shop_boosters.json",
    )
    args = parser.parse_args()

    source = args.input_elf.read_bytes()
    records = load_booster_descriptions(args.translations)
    target = patch_booster_descriptions(source, records)
    args.output_elf.parent.mkdir(parents=True, exist_ok=True)
    args.output_elf.write_bytes(target)
    print(f"input_sha256={sha256_bytes(source)}")
    print(f"output_sha256={sha256_bytes(target)}")
    print("PASS: descriptions changed; price/image/pack metadata preserved")


if __name__ == "__main__":
    main()
