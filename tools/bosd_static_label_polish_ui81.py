#!/usr/bin/env python3
"""Compatibility CLI for the historical UI81 static-label build stage.

Preferred implementation: :mod:`botsd.static_labels` with editable English strings in
``localization/en/static_labels_ui81.json`` and geometry/palette metadata in
``botsd/assets/static_labels_ui81.json``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.static_labels import build_all


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("adv")
    ap.add_argument("advscn")
    ap.add_argument("duelpts")
    ap.add_argument("outdir")
    ap.add_argument("--font", required=True)
    ap.add_argument("--report")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    results = build_all(
        {
            "adv": Path(args.adv),
            "advscn": Path(args.advscn),
            "duelpts": Path(args.duelpts),
        },
        Path(args.outdir),
        Path(args.font),
        repo / "botsd" / "assets" / "static_labels_ui81.json",
        repo / "localization" / "en" / "static_labels_ui81.json",
    )
    lines = [
        "UI81 TARGETED STATIC LABEL POLISH",
        "renderer=shared semantic indexed-TGA builder; runtime FONTLINK untouched",
    ]
    for key in ("advscn", "adv", "duelpts"):
        lines.append(f"[{key}]")
        lines.extend(results[key].report_lines)
    lines.append("RESULT=PASS")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
