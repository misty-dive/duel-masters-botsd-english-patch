from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable, Sequence

from .archive import member_allocation, parse_archive_bytes
from .errors import FormatError, VerificationError
from .indexed_tga import Box, IndexedTGA, changed_pixel_count, checked_box
from .lzss import compress_optimal, decompress as lzss_decompress

RGBA = tuple[int, int, int, int]


@dataclass(frozen=True)
class MemberPatchResult:
    archive: bytes
    changed_pixels: int
    stored_size: int
    allocation: int


def _average(colors: Sequence[RGBA]) -> RGBA:
    if not colors:
        raise ValueError("cannot average an empty color list")
    values = [
        round(sum(color[channel] for color in colors) / len(colors)) for channel in range(4)
    ]
    return tuple(values)  # type: ignore[return-value]


def clear_box(tga: IndexedTGA, box: Box, index: int) -> None:
    tga.fill_box(box, index)


def inpaint_horizontal(tga: IndexedTGA, box: Box, *, sample_radius: int = 2, edge_gap: int = 5) -> None:
    """Fill a label rectangle by interpolating neighboring palette colors.

    This reproduces the historical static-label cleanup behavior while keeping the indexed
    palette itself untouched.
    """
    x0, y0, x1, y1 = checked_box(box, tga.width, tga.height)
    plane = tga.indices_top_down()
    for y in range(y0, y1):
        left_x = max(0, x0 - edge_gap)
        right_x = min(tga.width - 1, x1 + edge_gap - 1)
        left_colors = [
            tga.palette_color(plane[y * tga.width + x])
            for x in range(max(0, left_x - sample_radius), min(tga.width, left_x + sample_radius + 1))
        ]
        right_colors = [
            tga.palette_color(plane[y * tga.width + x])
            for x in range(max(0, right_x - sample_radius), min(tga.width, right_x + sample_radius + 1))
        ]
        left = _average(left_colors)
        right = _average(right_colors)
        span = max(1, x1 - x0 - 1)
        for x in range(x0, x1):
            weight = (x - x0) / span
            color = tuple(round(left[c] * (1 - weight) + right[c] * weight) for c in range(4))
            plane[y * tga.width + x] = tga.nearest_palette_index(color)  # type: ignore[arg-type]
    tga.replace_top_down(plane)


def render_text_mask(text: str, width: int, height: int, font_path: str | Path, *, threshold: int = 112):
    """Render fitted text to a 1-bit-style Pillow mask using the historical UI81 algorithm."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError("Pillow is required for static-label rendering") from exc
    scale = 4
    canvas = Image.new("L", (max(16, width * scale), max(16, height * scale)), 0)
    draw = ImageDraw.Draw(canvas)
    low, high = 4, 160
    while low < high:
        middle = (low + high + 1) // 2
        font = ImageFont.truetype(str(font_path), middle * scale)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=0)
        if bbox[2] - bbox[0] <= (width - 2) * scale and bbox[3] - bbox[1] <= (height - 2) * scale:
            low = middle
        else:
            high = middle - 1
    font = ImageFont.truetype(str(font_path), low * scale)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (canvas.width - text_width) // 2 - bbox[0]
    y = (canvas.height - text_height) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=255)
    small = canvas.resize((width, height), Image.Resampling.LANCZOS)
    return small.point(lambda value: 255 if value >= threshold else 0)


def paint_indexed_text(
    tga: IndexedTGA,
    text: str,
    box: Box,
    font_path: str | Path,
    *,
    clear_mode: str,
    face_index: int,
    outline_index: int,
    background_index: int | None = None,
) -> None:
    x0, y0, x1, y1 = checked_box(box, tga.width, tga.height)
    if clear_mode == "transparent":
        clear_box(tga, box, 0 if background_index is None else background_index)
    elif clear_mode == "horizontal":
        inpaint_horizontal(tga, box)
    else:
        raise ValueError(f"unsupported clear mode {clear_mode!r}")

    mask = render_text_mask(text, x1 - x0 - 2, y1 - y0 - 2, font_path)
    plane = tga.indices_top_down()
    pixels = mask.load()
    width, height = mask.size
    origin_x, origin_y = x0 + 1, y0 + 1

    # One-pixel indexed outline, matching the historical production tool.
    for yy in range(height):
        for xx in range(width):
            if pixels[xx, yy]:
                continue
            found = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = xx + dx, yy + dy
                    if 0 <= nx < width and 0 <= ny < height and pixels[nx, ny]:
                        found = True
                        break
                if found:
                    break
            if found:
                plane[(origin_y + yy) * tga.width + origin_x + xx] = outline_index
    for yy in range(height):
        for xx in range(width):
            if pixels[xx, yy]:
                plane[(origin_y + yy) * tga.width + origin_x + xx] = face_index
    tga.replace_top_down(plane)


def replace_member_fixed(
    archive_bytes: bytes,
    member_name: str,
    new_raw: bytes,
    *,
    compressor=compress_optimal,
) -> bytes:
    """Replace one UI archive member without changing its allocation or other members."""
    archive = parse_archive_bytes(archive_bytes, decompress=True)
    try:
        target = next(member for member in archive.members if member.name == member_name)
    except StopIteration as exc:
        raise FormatError(f"archive member not found: {member_name}") from exc

    if target.compression == 0:
        blob = new_raw
    elif target.compression == 1:
        compressed = compressor(new_raw)
        if lzss_decompress(compressed, len(new_raw)) != new_raw:
            raise VerificationError(f"{member_name}: LZSS round-trip failed")
        blob = struct.pack("<I", len(new_raw)) + compressed
    else:
        raise FormatError(f"unsupported compression {target.compression}")

    allocation = member_allocation(archive, target)
    if len(blob) > allocation:
        raise FormatError(f"{member_name}: compressed {len(blob)} exceeds fixed allocation {allocation}")

    out = bytearray(archive_bytes)
    start = archive.data_start + target.data_rel
    out[start : start + allocation] = blob + b"\x00" * (allocation - len(blob))
    struct.pack_into("<I", out, target.record_off + 264, len(blob))
    rebuilt = bytes(out)
    if len(rebuilt) != len(archive_bytes):
        raise VerificationError("archive size changed")

    check = parse_archive_bytes(rebuilt, decompress=True)
    original = {member.name: member.raw for member in archive.members}
    for member in check.members:
        if member.name == member_name:
            if member.raw != new_raw:
                raise VerificationError(f"{member_name}: rebuilt member mismatch")
        elif member.raw != original[member.name]:
            raise VerificationError(f"non-target archive member changed: {member.name}")
    return rebuilt


def patch_indexed_member(
    archive_bytes: bytes,
    member_name: str,
    new_tga: IndexedTGA,
    allowed_boxes: Iterable[Box],
    *,
    compressor=compress_optimal,
) -> MemberPatchResult:
    archive = parse_archive_bytes(archive_bytes, decompress=True)
    try:
        target = next(member for member in archive.members if member.name == member_name)
    except StopIteration as exc:
        raise FormatError(f"archive member not found: {member_name}") from exc
    if target.raw is None:
        raise VerificationError("archive was not decompressed")
    before = IndexedTGA(target.raw)
    after_bytes = new_tga.to_bytes()
    after = IndexedTGA(after_bytes)
    changed = changed_pixel_count(before, after, allowed_boxes)
    if changed == 0:
        raise VerificationError(f"{member_name}: declared patch changed no pixels")

    rebuilt = replace_member_fixed(archive_bytes, member_name, after_bytes, compressor=compressor)
    check = parse_archive_bytes(rebuilt, decompress=False)
    stored = next(member.stored_size for member in check.members if member.name == member_name)
    allocation = member_allocation(check, next(member for member in check.members if member.name == member_name))
    return MemberPatchResult(rebuilt, changed, stored, allocation)


def update_tga_from_rgba(tga: IndexedTGA, image, boxes: Iterable[Box]) -> IndexedTGA:
    """Quantize selected RGBA rectangles back into an indexed TGA palette.

    The distance metric matches the historical card/UI editors: RGB squared distance plus
    double-weighted alpha squared distance. Pixels outside the declared boxes are untouched.
    """
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for indexed-TGA RGBA quantization") from exc
    if image.size != (tga.width, tga.height):
        raise ValueError(f"image size {image.size} != {(tga.width, tga.height)}")
    indices = np.frombuffer(bytes(tga.indices_top_down()), dtype=np.uint8).reshape(
        tga.height, tga.width
    ).copy()
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    palette = np.asarray(tga.palette, dtype=np.int16)
    first = tga.info.palette_first
    for box in boxes:
        x0, y0, x1, y1 = checked_box(box, tga.width, tga.height)
        crop = rgba[y0:y1, x0:x1].reshape(-1, 4)
        unique, inverse = np.unique(crop, axis=0, return_inverse=True)
        values = unique.astype(np.int16)
        best = np.empty(len(values), dtype=np.uint16)
        for start in range(0, len(values), 1024):
            delta = values[start : start + 1024, None, :] - palette[None, :, :]
            distance = (
                (delta[:, :, :3].astype(np.int32) ** 2).sum(axis=2)
                + 2 * (delta[:, :, 3].astype(np.int32) ** 2)
            )
            best[start : start + 1024] = np.argmin(distance, axis=1).astype(np.uint16) + first
        if np.any(best > 255):
            raise ValueError("indexed TGA palette index exceeds 8-bit pixel range")
        indices[y0:y1, x0:x1] = best[inverse].reshape(y1 - y0, x1 - x0).astype(np.uint8)
    tga.replace_top_down(indices.tobytes())
    return tga
