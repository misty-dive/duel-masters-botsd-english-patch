from __future__ import annotations

import struct

from PIL import Image

from botsd.font_polish import glyph_to_image, half_location, put_glyph_image
from botsd.fontlink import pack_4bpp, unpack_4bpp


def _page(count: int = 16) -> bytearray:
    width, height = 12, 24
    glyph_bytes = width * height // 2
    pixels = [0] * (width * height)
    pixels[2 * width + 3] = 15
    glyph = pack_4bpp(pixels)
    payload = glyph * count
    return bytearray(struct.pack("<HHHH", width, height, glyph_bytes, 0) + payload)


def test_half_location_maps_ascii_pages() -> None:
    assert half_location("'") == ("half0000.lz", 7)
    assert half_location("l") == ("half0004.lz", 12)


def test_glyph_image_roundtrip() -> None:
    page = _page()
    image = glyph_to_image(page, 0)
    assert image.size == (12, 24)
    edited = Image.new("L", (12, 24), 0)
    edited.putpixel((5, 5), 255)
    put_glyph_image(page, 0, edited)
    glyph_bytes = 144
    pixels = unpack_4bpp(page[8 : 8 + glyph_bytes])
    assert pixels[5 * 12 + 5] == 15
