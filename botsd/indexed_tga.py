from __future__ import annotations

import struct
from dataclasses import dataclass
from collections.abc import Iterable
from typing import TYPE_CHECKING

from .errors import FormatError

if TYPE_CHECKING:
    from PIL import Image

RGBA = tuple[int, int, int, int]
Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class IndexedTGAInfo:
    width: int
    height: int
    palette_first: int
    palette_length: int
    palette_bits: int
    descriptor: int


class IndexedTGA:
    """Parser/editor for the indexed 8-bit TGA flavor used by BOTSD UI assets.

    The class intentionally preserves the complete original header, palette and trailer.
    Editing methods only rewrite the indexed pixel plane unless callers explicitly replace
    other bytes themselves.
    """

    def __init__(self, raw: bytes):
        if len(raw) < 18:
            raise FormatError("TGA is too short")
        self.raw = raw
        self.id_length, cmap_type, image_type = raw[0], raw[1], raw[2]
        first, length, bits = struct.unpack_from("<HHB", raw, 3)
        _, _, width, height, bpp, descriptor = struct.unpack_from("<HHHHBB", raw, 8)
        if cmap_type != 1 or image_type != 1 or bpp != 8 or bits not in (24, 32):
            raise FormatError("unsupported TGA; expected indexed 8-bit with 24/32-bit palette")
        self.info = IndexedTGAInfo(width, height, first, length, bits, descriptor)
        self.palette_offset = 18 + self.id_length
        self.palette_entry_bytes = bits // 8
        self.pixel_offset = self.palette_offset + length * self.palette_entry_bytes
        pixel_size = width * height
        if self.pixel_offset + pixel_size > len(raw):
            raise FormatError("TGA pixel data exceeds file")
        self._indices = bytearray(raw[self.pixel_offset : self.pixel_offset + pixel_size])
        self._palette = self._parse_palette()

    def _parse_palette(self) -> tuple[RGBA, ...]:
        out: list[RGBA] = []
        for index in range(self.info.palette_length):
            start = self.palette_offset + index * self.palette_entry_bytes
            entry = self.raw[start : start + self.palette_entry_bytes]
            if self.info.palette_bits == 32:
                blue, green, red, alpha = entry
            else:
                blue, green, red = entry
                alpha = 255
            out.append((red, green, blue, alpha))
        return tuple(out)

    @property
    def width(self) -> int:
        return self.info.width

    @property
    def height(self) -> int:
        return self.info.height

    @property
    def palette(self) -> tuple[RGBA, ...]:
        return self._palette

    def indices_top_down(self) -> bytearray:
        width = self.width
        rows = [self._indices[y * width : (y + 1) * width] for y in range(self.height)]
        if not (self.info.descriptor & 0x20):
            rows.reverse()
        return bytearray().join(rows)

    def replace_top_down(self, indices: bytes | bytearray) -> None:
        if len(indices) != self.width * self.height:
            raise ValueError("replacement index plane has wrong size")
        width = self.width
        rows = [bytearray(indices[y * width : (y + 1) * width]) for y in range(self.height)]
        if not (self.info.descriptor & 0x20):
            rows.reverse()
        self._indices = bytearray().join(rows)

    def palette_color(self, index: int) -> RGBA:
        slot = index - self.info.palette_first
        if not (0 <= slot < len(self._palette)):
            raise ValueError(f"palette index {index} outside TGA palette")
        return self._palette[slot]

    def nearest_palette_index(self, color: RGBA, *, alpha_weight: int = 2) -> int:
        red, green, blue, alpha = color
        best_distance: int | None = None
        best_index = self.info.palette_first
        for slot, candidate in enumerate(self._palette):
            cr, cg, cb, ca = candidate
            distance = (
                (red - cr) ** 2
                + (green - cg) ** 2
                + (blue - cb) ** 2
                + alpha_weight * (alpha - ca) ** 2
            )
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = self.info.palette_first + slot
        return best_index

    def fill_box(self, box: Box, index: int) -> None:
        x0, y0, x1, y1 = checked_box(box, self.width, self.height)
        plane = self.indices_top_down()
        for y in range(y0, y1):
            start = y * self.width + x0
            plane[start : start + (x1 - x0)] = bytes([index]) * (x1 - x0)
        self.replace_top_down(plane)

    def copy_box(self, source: Box, destination_xy: tuple[int, int]) -> Box:
        sx0, sy0, sx1, sy1 = checked_box(source, self.width, self.height)
        dx0, dy0 = destination_xy
        width = sx1 - sx0
        height = sy1 - sy0
        destination = checked_box((dx0, dy0, dx0 + width, dy0 + height), self.width, self.height)
        plane = self.indices_top_down()
        rows = [bytes(plane[y * self.width + sx0 : y * self.width + sx1]) for y in range(sy0, sy1)]
        for row_index, row in enumerate(rows):
            start = (dy0 + row_index) * self.width + dx0
            plane[start : start + width] = row
        self.replace_top_down(plane)
        return destination

    def to_rgba_image(self) -> Image.Image:
        try:
            from PIL import Image as PILImage
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise RuntimeError("Pillow is required for RGBA rendering") from exc
        image = PILImage.new("RGBA", (self.width, self.height))
        image.putdata([self.palette_color(value) for value in self.indices_top_down()])
        return image

    def to_bytes(self) -> bytes:
        out = bytearray(self.raw)
        end = self.pixel_offset + len(self._indices)
        out[self.pixel_offset:end] = self._indices
        return bytes(out)


def checked_box(box: Box, width: int, height: int) -> Box:
    x0, y0, x1, y1 = box
    if not (0 <= x0 <= x1 <= width and 0 <= y0 <= y1 <= height):
        raise ValueError(f"box {box!r} outside {width}x{height} image")
    return box


def changed_pixel_count(before: IndexedTGA, after: IndexedTGA, allowed_boxes: Iterable[Box]) -> int:
    """Count changed indices and reject any change outside ``allowed_boxes``."""
    if (before.width, before.height) != (after.width, after.height):
        raise ValueError("TGA geometry changed")
    if before.raw[: before.pixel_offset] != after.raw[: after.pixel_offset]:
        raise ValueError("TGA metadata/palette changed")
    a = before.indices_top_down()
    b = after.indices_top_down()
    boxes = [checked_box(box, before.width, before.height) for box in allowed_boxes]
    changed = 0
    for y in range(before.height):
        for x in range(before.width):
            offset = y * before.width + x
            if a[offset] == b[offset]:
                continue
            changed += 1
            if not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in boxes):
                raise ValueError(f"pixel change escaped declared boxes at ({x}, {y})")
    return changed
