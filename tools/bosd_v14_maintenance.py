#!/usr/bin/env python3
"""Build the exact BOTSD v1.4 maintenance components from public-v1.3 inputs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.hashing import sha256_bytes
from botsd.v14 import build_v14


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "v13_dir",
        type=Path,
        help="directory containing exact public-v1.3 SLPM_658.82 and SCRPACK.SDA",
    )
    parser.add_argument("retail_scrpack", type=Path, help="exact retail SCRPACK.SDA")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    exe = (args.v13_dir / "SLPM_658.82").read_bytes()
    scr = (args.v13_dir / "SCRPACK.SDA").read_bytes()
    retail = args.retail_scrpack.read_bytes()

    result = build_v14(exe, scr, retail, language=args.language)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "SLPM_658.82").write_bytes(result.executable)
    (args.output_dir / "SCRPACK.SDA").write_bytes(result.scrpack)

    print("BOTSD v1.4 maintenance component build: PASS")
    print(
        "SLPM_658.82: "
        f"sha256={sha256_bytes(result.executable)} "
        f"differing_bytes={result.executable_differing_bytes}"
    )
    print(
        "SCRPACK.SDA: "
        f"sha256={sha256_bytes(result.scrpack)} "
        f"differing_bytes={result.scrpack_differing_bytes}"
    )


if __name__ == "__main__":
    main()
