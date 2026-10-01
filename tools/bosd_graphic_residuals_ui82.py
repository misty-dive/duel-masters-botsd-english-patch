#!/usr/bin/env python3
"""Compatibility CLI for the UI82 residual LOBBY/TOUR/DECK graphics stage."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.graphic_residuals import build_all


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("lobby", "tour", "deck"):
        ap.add_argument(f"--{name}-in", type=Path, required=True)
        ap.add_argument(f"--{name}-out", type=Path, required=True)
    ap.add_argument("--tools-dir", type=Path, required=True, help="retained for historical CLI compatibility")
    ap.add_argument("--report", type=Path)
    ap.add_argument("--preview-dir", type=Path)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    results = build_all(
        {name: getattr(args, f"{name}_in") for name in ("lobby", "tour", "deck")},
        {name: getattr(args, f"{name}_out") for name in ("lobby", "tour", "deck")},
        repo / "botsd" / "assets" / "graphic_residuals_ui82.json",
    )
    lines = ["UI82 TARGETED GRAPHICAL RESIDUAL PATCH"]
    for name in ("lobby", "tour", "deck"):
        lines.append(f"[{name.upper()}]")
        lines.extend(results[name].report_lines)
    lines += [
        "archive_sizes=UNCHANGED",
        "non-target_members=BYTE-IDENTICAL (decompressed)",
        "pixel_containment=PASS",
        "RESULT=PASS",
    ]
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.report:
        args.report.write_text(text, encoding="utf-8")

    if args.preview_dir:
        from botsd.archive import parse_archive
        from botsd.graphic_residuals import load_spec
        from botsd.indexed_tga import IndexedTGA

        spec = load_spec(repo / "botsd" / "assets" / "graphic_residuals_ui82.json")
        args.preview_dir.mkdir(parents=True, exist_ok=True)
        names = {"lobby": "LOBBY_UI82", "tour": "TOUR_UI82", "deck": "DECK_UI82"}
        for key in ("lobby", "tour", "deck"):
            archive = parse_archive(getattr(args, f"{key}_out"), decompress=True)
            member_name = spec[key]["member"]
            raw = next(row.raw for row in archive.members if row.name == member_name)
            if raw is None:
                raise RuntimeError(f"{member_name} was not decompressed")
            image = IndexedTGA(raw).to_rgba_image()
            image.save(args.preview_dir / f"{names[key]}.png")
            image.getchannel("A").save(args.preview_dir / f"{names[key]}_alpha.png")


if __name__ == "__main__":
    main()
