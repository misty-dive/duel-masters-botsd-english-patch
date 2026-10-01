#!/usr/bin/env python3
"""Compatibility wrapper for the UI75 677-card face/thumbnail builder.

The maintained renderer and streaming UNPACK writer now live in :mod:`botsd.cardfaces`.
Historical archive/font/compressor path arguments are accepted for old build recipes but are no
longer dynamically imported.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.archive import parse_archive_bytes
from botsd.cardfaces import build_card_faces, load_spec
from botsd.indexed_tga import IndexedTGA
from botsd.sda import OuterSDA


def _write_report(path: Path, rows) -> None:
    fields = [
        "seq", "resource_key", "internal_id", "english_name", "large_chunk", "small_chunk",
        "compression", "compressed_headroom", "title_scale", "type_scale", "rules_scale",
        "rules_lines", "flavor_scale", "flavor_lines", "large_changed_pixels",
        "small_changed_pixels",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            m = row.metrics
            writer.writerow({
                "seq": row.sequence,
                "resource_key": row.resource_key,
                "internal_id": row.internal_id,
                "english_name": row.english_name,
                "large_chunk": row.large_chunk,
                "small_chunk": row.small_chunk,
                "compression": m.compression,
                "compressed_headroom": m.compressed_headroom,
                "title_scale": f"{m.title_scale:.4f}",
                "type_scale": f"{m.type_scale:.4f}",
                "rules_scale": f"{m.rules_scale:.4f}",
                "rules_lines": m.rules_lines,
                "flavor_scale": f"{m.flavor_scale:.4f}",
                "flavor_lines": m.flavor_lines,
                "large_changed_pixels": m.large_changed_pixels,
                "small_changed_pixels": m.small_changed_pixels,
            })


def _write_previews(output: Path, preview_dir: Path, rows) -> None:
    preview_dir.mkdir(parents=True, exist_ok=True)
    wanted = {0, 5, 16, 27, 34, 100, 200, 300, 400, 500, 600, 676}
    sda = OuterSDA(output)
    for row in rows:
        if row.sequence not in wanted:
            continue
        chunk = sda.read_chunk(row.large_chunk)
        inner_size = int.from_bytes(chunk[:4], "little")
        archive = parse_archive_bytes(chunk[:inner_size], decompress=True)
        raw = archive.members[0].raw
        if raw is None:
            continue
        IndexedTGA(raw).to_rgba_image().crop((0, 0, 384, 512)).save(
            preview_dir / f"{row.sequence:03d}_{row.resource_key}.png"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unpack", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("fontlink", type=Path)
    parser.add_argument("archive_tool", type=Path, help="legacy compatibility argument; ignored")
    parser.add_argument("font_tool", type=Path, help="legacy compatibility argument; ignored")
    parser.add_argument("strong_tool", type=Path, help="legacy compatibility argument; ignored")
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument("--master", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=677)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--allow-nonretail", action="store_true")
    args = parser.parse_args()

    rows = build_card_faces(
        args.unpack,
        args.inventory,
        args.fontlink,
        args.output,
        master_csv=args.master,
        spec=load_spec(args.spec) if args.spec else None,
        start=args.start,
        end=args.end,
        verify_retail=not args.allow_nonretail,
    )
    report = args.report or args.output.with_suffix(".csv")
    _write_report(report, rows)
    if args.preview_dir:
        _write_previews(args.output, args.preview_dir, rows)
    print(f"wrote {args.output}")
    print(f"report {report}")
    if rows:
        print(f"min headroom {min(row.metrics.compressed_headroom for row in rows)}")
        print(f"optimal {sum(row.metrics.compression == 'optimal' for row in rows)}")
        print(f"min title {min(row.metrics.title_scale for row in rows):.4f}")
        print(f"min rules {min(row.metrics.rules_scale for row in rows):.4f}")


if __name__ == "__main__":
    main()
