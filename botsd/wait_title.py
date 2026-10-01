from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .archive import parse_archive_bytes, rebuild_archive_bytes
from .gamefont import GameFont
from .hashing import sha256_bytes
from .indexed_tga import Box, IndexedTGA, changed_pixel_count
from .ui_graphics import update_tga_from_rgba


@dataclass(frozen=True)
class GraphicBuild:
    data: bytes
    report_lines: tuple[str, ...]


def load_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_strings(path: str | Path) -> dict[str, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    strings = raw.get("strings")
    if not isinstance(strings, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in strings.items()):
        raise ValueError(f"invalid WAIT/TITLE localization file: {path}")
    return strings


def _box(values: list[int] | tuple[int, ...]) -> Box:
    result = tuple(int(value) for value in values)
    if len(result) != 4:
        raise ValueError(f"expected four box coordinates: {values!r}")
    return (result[0], result[1], result[2], result[3])


def fit_mask(font: GameFont, text: str, max_width: int, max_height: int):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for WAIT/TITLE rendering") from exc
    mask = font.text_mask(text, spacing=1)
    scale = min(1.0, max_width / mask.width, max_height / mask.height)
    if scale < 0.999:
        mask = mask.resize(
            (max(1, round(mask.width * scale)), max(1, round(mask.height * scale))),
            Image.Resampling.LANCZOS,
        )
    return mask


def draw_outlined(
    base,
    box: Box,
    font: GameFont,
    text: str,
    max_height: int,
    *,
    center: bool = True,
    outline: int = 1,
) -> Box:
    try:
        from PIL import Image, ImageFilter
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for WAIT/TITLE rendering") from exc
    x0, y0, x1, y1 = box
    mask = fit_mask(font, text, x1 - x0 - 4, min(max_height, y1 - y0 - 2))
    x = x0 + (x1 - x0 - mask.width) // 2 if center else x0 + 2
    y = y0 + (y1 - y0 - mask.height) // 2
    if outline:
        outline_mask = mask.filter(ImageFilter.MaxFilter(outline * 2 + 1))
        layer = Image.new("RGBA", outline_mask.size, (0, 0, 0, 255))
        layer.putalpha(outline_mask)
        base.alpha_composite(layer, (x, y))
    layer = Image.new("RGBA", mask.size, (241, 241, 241, 255))
    layer.putalpha(mask)
    base.alpha_composite(layer, (x, y))
    return (x, y, x + mask.width, y + mask.height)


def build_wait(source: bytes, font: GameFont, spec: dict[str, Any], strings: dict[str, str]) -> GraphicBuild:
    got = sha256_bytes(source)
    expected = spec.get("input_sha256")
    if expected and got != expected:
        raise ValueError(f"WAIT source SHA-256 {got} != expected {expected}")
    target_box = _box(spec["target_box"])
    text_box = _box(spec["text_box"])
    text_id = str(spec["text_id"])
    if text_id not in strings:
        raise ValueError(f"missing WAIT localization string: {text_id}")

    original = IndexedTGA(source)
    image = original.to_rgba_image()
    image.paste((0, 0, 0, 0), target_box)
    placed = draw_outlined(
        image,
        text_box,
        font,
        strings[text_id],
        int(spec["max_height"]),
        center=bool(spec.get("center", True)),
        outline=int(spec.get("outline", 1)),
    )
    edited = IndexedTGA(source)
    update_tga_from_rgba(edited, image, [target_box])
    output = edited.to_bytes()
    changed = changed_pixel_count(original, IndexedTGA(output), [target_box])
    if changed == 0:
        raise RuntimeError("WAIT patch changed no pixels")
    return GraphicBuild(
        output,
        (
            f"input_sha256={got}",
            f"output_sha256={sha256_bytes(output)}",
            f"target_box={target_box}",
            f"english_bbox={placed}",
            f"changed_pixels={changed}",
            "containment=PASS",
        ),
    )


def build_title(source: bytes, spec: dict[str, Any]) -> GraphicBuild:
    got = sha256_bytes(source)
    expected = spec.get("input_sha256")
    if expected and got != expected:
        raise ValueError(f"TITLE source SHA-256 {got} != expected {expected}")
    archive = parse_archive_bytes(source, decompress=True)
    member_name = str(spec["member"])
    member = next(row for row in archive.members if row.name == member_name)
    if member.raw is None:
        raise RuntimeError("TITLE member was not decompressed")
    boxes = [_box(row) for row in spec["clear_boxes"]]
    original = IndexedTGA(member.raw)
    image = original.to_rgba_image()
    for box in boxes:
        image.paste((0, 0, 0, 0), box)
    edited = IndexedTGA(member.raw)
    update_tga_from_rgba(edited, image, boxes)
    edited_bytes = edited.to_bytes()
    changed = changed_pixel_count(original, IndexedTGA(edited_bytes), boxes)
    if changed == 0:
        raise RuntimeError("TITLE patch changed no pixels")

    output = rebuild_archive_bytes(archive, {member_name: edited_bytes}, pad_to=len(source))
    check = parse_archive_bytes(output, decompress=True)
    old = {row.name: row.raw for row in archive.members}
    for row in check.members:
        if row.name != member_name and row.raw != old[row.name]:
            raise RuntimeError(f"non-target TITLE member changed: {row.name}")
    semantics = tuple(str(value) for value in spec.get("semantics", []))
    return GraphicBuild(
        output,
        (
            f"input_sha256={got}",
            f"output_sha256={sha256_bytes(output)}",
            f"clear_boxes={boxes}",
            f"changed_pixels={changed}",
            *semantics,
            "non_target_members=BYTE-IDENTICAL (decompressed)",
            "pixel_containment=PASS",
        ),
    )
