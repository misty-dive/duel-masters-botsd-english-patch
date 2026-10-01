#!/usr/bin/env python3
"""Compatibility CLI for the shared BOTSD v1.3 release builder."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.release import build_v13_release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "v12_dir",
        type=Path,
        help="directory containing exact public-v1.2 maintenance components",
    )
    parser.add_argument("v12_full_ppf", type=Path, help="official public v1.2 full PPF")
    parser.add_argument("output_dir", type=Path, help="release output directory")
    args = parser.parse_args()

    build = build_v13_release(args.v12_dir, args.v12_full_ppf, args.output_dir)
    print("BOTSD v1.3 release build: PASS")
    print(f"full={build.full.path}")
    print(f"full_sha256={build.full.sha256}")
    print(f"hotfix={build.hotfix.path}")
    print(f"hotfix_sha256={build.hotfix.sha256}")
    print(f"report={build.report}")


if __name__ == "__main__":
    main()
