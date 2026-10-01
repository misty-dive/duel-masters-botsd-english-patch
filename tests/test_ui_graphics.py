from __future__ import annotations

import struct

from botsd.indexed_tga import IndexedTGA, changed_pixel_count
from botsd.ui_graphics import inpaint_horizontal


def _tga(width: int = 12, height: int = 6) -> bytes:
    header = bytearray(18)
    header[1] = 1
    header[2] = 1
    struct.pack_into("<HHB", header, 3, 0, 4, 32)
    struct.pack_into("<HHHHBB", header, 8, 0, 0, width, height, 8, 0x20)
    palette = bytes(
        (
            0, 0, 0, 0,
            32, 32, 32, 255,
            128, 128, 128, 255,
            255, 255, 255, 255,
        )
    )
    pixels = bytearray([1] * (width * height))
    for y in range(height):
        pixels[y * width + 1] = 2
        pixels[y * width + width - 2] = 3
    return bytes(header) + palette + bytes(pixels)


def test_indexed_tga_palette_copy_and_fill() -> None:
    tga = IndexedTGA(_tga())
    assert tga.palette_color(3) == (255, 255, 255, 255)
    assert tga.nearest_palette_index((250, 250, 250, 255)) == 3
    tga.fill_box((3, 1, 6, 3), 2)
    destination = tga.copy_box((3, 1, 6, 3), (7, 2))
    assert destination == (7, 2, 10, 4)
    plane = tga.indices_top_down()
    assert plane[2 * tga.width + 7 : 2 * tga.width + 10] == bytes([2, 2, 2])


def test_changed_pixel_count_rejects_escape() -> None:
    raw = _tga()
    before = IndexedTGA(raw)
    after = IndexedTGA(raw)
    plane = after.indices_top_down()
    plane[2 * after.width + 4] = 3
    after.replace_top_down(plane)
    assert changed_pixel_count(before, after, [(4, 2, 5, 3)]) == 1


def test_horizontal_inpaint_is_contained() -> None:
    raw = _tga()
    before = IndexedTGA(raw)
    after = IndexedTGA(raw)
    box = (4, 1, 8, 5)
    inpaint_horizontal(after, box)
    assert changed_pixel_count(before, after, [box]) > 0
