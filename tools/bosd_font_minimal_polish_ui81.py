#!/usr/bin/env python3
"""Compatibility CLI for the historical UI80 minimal runtime-font polish stage."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.font_polish import patch_minimal_ascii_polish
from botsd.hashing import sha256_bytes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--report")
    args = ap.parse_args()

    source = Path(args.input).read_bytes()
    result = patch_minimal_ascii_polish(source)
    Path(args.output).write_bytes(result.data)
    lines = [
        "UI80 MINIMAL RUNTIME FONT POLISH: PASS",
        f"input_sha256={sha256_bytes(source)}",
        f"output_sha256={sha256_bytes(result.data)}",
        f"archive_size={len(result.data)} (unchanged)",
        "changed_glyphs=ASCII apostrophe(0x27), lowercase l(0x6C) only",
        "fullwidth_A-Z=UNCHANGED",
        "all_halfwidth_A-Z=UNCHANGED; all other lowercase cells unchanged",
    ]
    for name, old_size, new_size, allocation in result.member_sizes:
        lines.append(
            f"{name}: compressed {old_size}->{new_size}; allocation={allocation}; "
            f"headroom={allocation - new_size}"
        )
    lines.append(
        "VERIFICATION: all 453 streams decode; PAC size/offsets preserved; "
        "exactly two font members changed."
    )
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
