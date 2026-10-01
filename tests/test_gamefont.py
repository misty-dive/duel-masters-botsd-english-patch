from __future__ import annotations

import struct

from botsd.fontlink import page_geometry


def test_font_page_layout_used_by_gamefont_is_stable() -> None:
    width, height, count = 12, 24, 16
    glyph_bytes = width * height // 2
    page = struct.pack("<HHHH", width, height, glyph_bytes, 0) + bytes(glyph_bytes * count)
    assert page_geometry(page) == (12, 24, 144, 16)
