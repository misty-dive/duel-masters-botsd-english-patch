#!/usr/bin/env python3
"""Compatibility wrapper for the v1.1 Records/Options/Deck Builder/Deck Stats cleanup."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.ui_polish_v11 import build_all

FONT_DEFAULT = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("opt", type=Path)
    parser.add_argument("deck", type=Path)
    parser.add_argument("exe", type=Path)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--font", type=Path, default=Path(FONT_DEFAULT))
    parser.add_argument("--strings", type=Path, default=ROOT / "localization/en/ui_polish_v11.json")
    parser.add_argument("--spec", type=Path)
    args = parser.parse_args()
    result = build_all(
        args.opt.read_bytes(),
        args.deck.read_bytes(),
        args.exe.read_bytes(),
        args.font,
        args.strings,
        spec_path=args.spec,
    )
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "OPT_UI11_POLISH.DAT").write_bytes(result.opt)
    (args.outdir / "DECK_UI11_POLISH.DAT").write_bytes(result.deck)
    (args.outdir / "SLPM_658.82_UI11_POLISH").write_bytes(result.executable)
    print("\n".join(result.report_lines))


if __name__ == "__main__":
    main()
