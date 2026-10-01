#!/usr/bin/env python3
"""Compatibility CLI for the UI82 WAIT and TITLE graphical fixes."""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.archive import parse_archive
from botsd.gamefont import GameFont
from botsd.indexed_tga import IndexedTGA
from botsd.wait_title import build_title, build_wait, load_spec, load_strings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-in", type=Path, required=True)
    parser.add_argument("--wait-out", type=Path, required=True)
    parser.add_argument("--title-in", type=Path, required=True)
    parser.add_argument("--title-out", type=Path, required=True)
    parser.add_argument("--fontlink", type=Path, required=True)
    parser.add_argument("--tools-dir", type=Path, required=True, help="retained for historical CLI compatibility")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    spec = load_spec(repo / "botsd" / "assets" / "wait_title_ui82.json")
    strings = load_strings(repo / "localization" / "en" / "wait_title_ui82.json")
    font = GameFont(args.fontlink)

    wait = build_wait(args.wait_in.read_bytes(), font, spec["wait"], strings)
    title = build_title(args.title_in.read_bytes(), spec["title"])
    args.wait_out.parent.mkdir(parents=True, exist_ok=True)
    args.title_out.parent.mkdir(parents=True, exist_ok=True)
    args.wait_out.write_bytes(wait.data)
    args.title_out.write_bytes(title.data)

    lines = ["UI82 WAIT + TITLE TARGETED STATIC PATCH", "[WAIT]", *wait.report_lines, "[TITLE]", *title.report_lines, "RESULT=PASS"]
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.report:
        args.report.write_text(text, encoding="utf-8")

    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
        wait_image = IndexedTGA(wait.data).to_rgba_image()
        title_archive = parse_archive(args.title_out, decompress=True)
        member_name = spec["title"]["member"]
        raw = next(row.raw for row in title_archive.members if row.name == member_name)
        if raw is None:
            raise RuntimeError(f"{member_name} was not decompressed")
        title_image = IndexedTGA(raw).to_rgba_image()
        for name, image in (("WAIT_UI82", wait_image), ("TITLE_UI82", title_image)):
            from PIL import Image

            background = Image.new("RGBA", image.size, (80, 80, 80, 255))
            background.alpha_composite(image)
            background.convert("RGB").save(args.preview_dir / f"{name}.png")


if __name__ == "__main__":
    main()
