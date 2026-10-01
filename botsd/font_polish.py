from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .fontlink import (
    compress,
    decompress,
    pack_4bpp,
    page_geometry,
    parse_pac,
    replace_member_in_place,
    unpack_4bpp,
)
from .hashing import sha256_bytes

if TYPE_CHECKING:
    from PIL import Image


def _image_values(image: Image.Image) -> Iterable[int]:
    """Return flattened grayscale pixels across Pillow 11/12 API variants."""
    flattened = getattr(image, "get_flattened_data", None)
    if callable(flattened):
        return cast(Iterable[int], flattened())
    return cast(Iterable[int], image.getdata())


def load_spec(path: str | Path | None = None) -> dict:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/font_polish_ui80.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


_FONT_SPEC = load_spec()
UI80_FONTLINK_SHA256 = str(_FONT_SPEC["input_sha256"])


@dataclass(frozen=True)
class FontPolishResult:
    data: bytes
    changed_members: tuple[str, ...]
    member_sizes: tuple[tuple[str, int, int, int], ...]


def half_location(character: str) -> tuple[str, int]:
    if len(character) != 1:
        raise ValueError("half_location expects one character")
    code = ord(character)
    if not 0x20 <= code <= 0x7E:
        raise ValueError(f"character {character!r} is outside printable ASCII")
    return f"half{(code - 0x20) // 0x10:04d}.lz", (code - 0x20) % 0x10


def glyph_to_image(page: bytes, index: int) -> Image.Image:
    try:
        from PIL import Image as PILImage
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for font-polish rendering") from exc
    width, height, glyph_bytes, count = page_geometry(page)
    if not 0 <= index < count:
        raise ValueError(f"glyph index {index} outside page count {count}")
    pixels = unpack_4bpp(page[8 + index * glyph_bytes : 8 + (index + 1) * glyph_bytes])
    image = PILImage.new("L", (width, height))
    image.putdata([value * 17 for value in pixels])
    return image


def put_glyph_image(page: bytearray, index: int, image: Image.Image) -> None:
    width, height, glyph_bytes, count = page_geometry(page)
    if not 0 <= index < count:
        raise ValueError(f"glyph index {index} outside page count {count}")
    if image.size != (width, height):
        raise ValueError(f"glyph image size {image.size} != {(width, height)}")
    pixels = [max(0, min(15, (int(value) + 8) // 17)) for value in _image_values(image)]
    page[8 + index * glyph_bytes : 8 + (index + 1) * glyph_bytes] = pack_4bpp(pixels)


def _member_allocation(entries, name: str, raw_size: int) -> int:
    entry = next(row for row in entries if row.name == name)
    later = [row.offset for row in entries if row.offset > entry.offset]
    end = min(later) if later else raw_size
    return end - entry.offset


def patch_minimal_ascii_polish(
    raw: bytes,
    *,
    expected_sha256: str | None = UI80_FONTLINK_SHA256,
) -> FontPolishResult:
    """Apply the historical apostrophe/lowercase-l UI80 font polish semantically."""
    if expected_sha256 is not None:
        got = sha256_bytes(raw)
        if got != expected_sha256:
            raise ValueError(f"base FONTLINK hash {got} != {expected_sha256}")

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for font-polish rendering") from exc

    entries = parse_pac(raw)
    by_name = {entry.name: entry for entry in entries}
    apostrophe = _FONT_SPEC["apostrophe"]
    lower_l = _FONT_SPEC["lowercase_l"]
    target_apostrophe_page, _ = half_location(str(apostrophe["target_char"]))
    target_l_page, _ = half_location(str(lower_l["target_char"]))
    needed = (target_apostrophe_page, target_l_page, str(apostrophe["source_page"]), str(lower_l["source_page"]))
    missing = [name for name in needed if name not in by_name]
    if missing:
        raise ValueError(f"FONTLINK missing required pages: {missing}")
    pages = {name: bytearray(decompress(by_name[name].blob)) for name in needed}

    # Apostrophe: downsample the clean retail full-width quote into the half cell,
    # then shift it three pixels right as in the accepted UI80 production stage.
    page_name, glyph_index = half_location(str(apostrophe["target_char"]))
    resize_values = tuple(int(v) for v in apostrophe["resize"])
    if len(resize_values) != 2:
        raise ValueError("apostrophe resize must contain two dimensions")
    resize = (resize_values[0], resize_values[1])
    source = glyph_to_image(
        bytes(pages[str(apostrophe["source_page"])]),
        int(apostrophe["source_glyph"]),
    ).resize(resize, Image.Resampling.BOX)
    quantized = Image.new("L", (12, 24))
    quantized.putdata([max(0, min(15, (int(value) + 8) // 17)) * 17 for value in _image_values(source)])
    shifted = Image.new("L", resize, 0)
    shift_values = tuple(int(v) for v in apostrophe["shift"])
    if len(shift_values) != 2:
        raise ValueError("apostrophe shift must contain two coordinates")
    shifted.paste(quantized, (shift_values[0], shift_values[1]))
    put_glyph_image(pages[page_name], glyph_index, shifted)

    # Lowercase l: crop the clean full-width l stem and preserve half-width metrics.
    page_name, glyph_index = half_location(str(lower_l["target_char"]))
    source = glyph_to_image(
        bytes(pages[str(lower_l["source_page"])]),
        int(lower_l["source_glyph"]),
    )
    bbox = source.getbbox()
    expected_bbox_values = tuple(int(v) for v in lower_l["expected_source_bbox"])
    if len(expected_bbox_values) != 4:
        raise ValueError("lowercase-l expected bbox must contain four coordinates")
    expected_bbox = (
        expected_bbox_values[0],
        expected_bbox_values[1],
        expected_bbox_values[2],
        expected_bbox_values[3],
    )
    if bbox != expected_bbox:
        raise ValueError(f"unexpected clean l source bbox {bbox}")
    clean = Image.new("L", (12, 24), 0)
    paste_values = tuple(int(v) for v in lower_l["paste"])
    if len(paste_values) != 2:
        raise ValueError("lowercase-l paste must contain two coordinates")
    clean.paste(source.crop(bbox), (paste_values[0], paste_values[1]))
    put_glyph_image(pages[page_name], glyph_index, clean)

    output = raw
    changed_members = tuple(str(value) for value in _FONT_SPEC["changed_members"])
    stats: list[tuple[str, int, int, int]] = []
    for name in changed_members:
        entry = by_name[name]
        new_blob = compress(bytes(pages[name]))
        if decompress(new_blob) != bytes(pages[name]):
            raise RuntimeError(f"FONTLINK round-trip failed for {name}")
        allocation = _member_allocation(entries, name, len(raw))
        output = replace_member_in_place(output, parse_pac(output), name, new_blob)
        stats.append((name, entry.stored_size, len(new_blob), allocation))

    old_entries = {entry.name: entry for entry in entries}
    new_entries = parse_pac(output)
    actual = tuple(
        entry.name
        for entry in new_entries
        if entry.stored_size != old_entries[entry.name].stored_size
        or entry.blob != old_entries[entry.name].blob
    )
    if actual != changed_members:
        raise RuntimeError(f"unexpected FONTLINK members changed: {actual}")
    for entry in new_entries:
        decompress(entry.blob)
    if len(output) != len(raw):
        raise RuntimeError("FONTLINK archive size changed")
    return FontPolishResult(output, changed_members, tuple(stats))
