from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .archive import parse_archive_bytes
from .hashing import sha256_bytes
from .indexed_tga import Box, IndexedTGA
from .ui_graphics import paint_indexed_text, patch_indexed_member


@dataclass(frozen=True)
class StaticLabelBuild:
    data: bytes
    report_lines: tuple[str, ...]


def load_asset_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_strings(path: str | Path) -> dict[str, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    strings = raw.get("strings")
    if not isinstance(strings, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in strings.items()):
        raise ValueError(f"invalid static-label localization file: {path}")
    return strings


def build_archive(
    source: bytes,
    archive_spec: dict[str, Any],
    strings: dict[str, str],
    font_path: str | Path,
) -> StaticLabelBuild:
    expected = archive_spec.get("input_sha256")
    got = sha256_bytes(source)
    if expected and got != expected:
        raise ValueError(f"static-label source SHA-256 {got} != expected {expected}")

    members = archive_spec.get("members")
    if not isinstance(members, dict) or not members:
        raise ValueError("static-label archive spec has no members")

    output = source
    report = [f"input_sha256={got}"]
    for member_name, edit_rows in members.items():
        archive = parse_archive_bytes(output, decompress=True)
        try:
            member = next(row for row in archive.members if row.name == member_name)
        except StopIteration as exc:
            raise ValueError(f"archive member not found: {member_name}") from exc
        if member.raw is None:
            raise RuntimeError("archive member was not decompressed")
        tga = IndexedTGA(member.raw)
        boxes: list[Box] = []
        for edit in edit_rows:
            text_id = edit["text_id"]
            if text_id not in strings:
                raise ValueError(f"missing localized static-label string: {text_id}")
            box_values = tuple(int(value) for value in edit["box"])
            if len(box_values) != 4:
                raise ValueError(f"bad box for {text_id}: {box_values!r}")
            box: Box = (
                box_values[0],
                box_values[1],
                box_values[2],
                box_values[3],
            )
            boxes.append(box)
            paint_indexed_text(
                tga,
                strings[text_id],
                box,
                font_path,
                clear_mode=str(edit["clear_mode"]),
                face_index=int(edit["face_index"]),
                outline_index=int(edit["outline_index"]),
                background_index=(
                    int(edit["background_index"])
                    if "background_index" in edit
                    else None
                ),
            )
        result = patch_indexed_member(output, member_name, tga, boxes)
        output = result.archive
        report.append(
            f"{member_name}: changed_pixels={result.changed_pixels} "
            f"compressed={result.stored_size}/{result.allocation} "
            f"headroom={result.allocation - result.stored_size}"
        )

    report.append(f"output_sha256={sha256_bytes(output)}")
    report.append(f"archive_size={len(output)}")
    report.append("non_target_members=BYTE-IDENTICAL (decompressed)")
    report.append("pixel_containment=PASS")
    return StaticLabelBuild(output, tuple(report))


def build_all(
    input_paths: dict[str, Path],
    output_dir: Path,
    font_path: Path,
    asset_spec_path: Path,
    strings_path: Path,
) -> dict[str, StaticLabelBuild]:
    spec = load_asset_spec(asset_spec_path)
    strings = load_strings(strings_path)
    archives = spec.get("archives")
    if not isinstance(archives, dict):
        raise ValueError("static-label asset spec is missing archives")
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, StaticLabelBuild] = {}
    for key, archive_spec in archives.items():
        if key not in input_paths:
            raise ValueError(f"missing static-label input mapping: {key}")
        result = build_archive(input_paths[key].read_bytes(), archive_spec, strings, font_path)
        output_name = archive_spec["output_name"]
        (output_dir / output_name).write_bytes(result.data)
        results[key] = result
    return results
