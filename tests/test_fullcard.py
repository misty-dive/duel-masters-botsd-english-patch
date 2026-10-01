from __future__ import annotations

import struct

import numpy as np
from PIL import Image

from botsd.fullcard import PRINTED_FACE, SOURCE_COLOR_ATTEMPTS, replace_region_preserving_palette
from botsd.indexed_tga import IndexedTGA


def make_tga(width: int = 8, height: int = 6, fill: int = 0) -> bytes:
    header = bytearray(18)
    header[1] = 1
    header[2] = 1
    struct.pack_into("<HHB", header, 3, 0, 256, 32)
    struct.pack_into("<HHHHBB", header, 8, 0, 0, width, height, 8, 0x20)
    palette = bytearray()
    for value in range(256):
        palette.extend((value, value, value, 255))
    return bytes(header + palette + bytes([fill]) * (width * height))


def test_palette_replacement_preserves_metadata_and_outside_pixels() -> None:
    raw = make_tga()
    before = IndexedTGA(raw)
    image = Image.new("RGBA", (4, 3), (255, 255, 255, 255))
    out = replace_region_preserving_palette(
        IndexedTGA(raw), image, (1, 1, 5, 4), source_colors=8
    )
    after = IndexedTGA(out)
    assert out[: before.pixel_offset] == raw[: before.pixel_offset]
    a = np.frombuffer(bytes(before.indices_top_down()), dtype=np.uint8).reshape(6, 8)
    b = np.frombuffer(bytes(after.indices_top_down()), dtype=np.uint8).reshape(6, 8)
    mask = np.zeros((6, 8), dtype=bool)
    mask[1:4, 1:5] = True
    assert np.array_equal(a[~mask], b[~mask])
    assert np.any(a[mask] != b[mask])


def test_ui76_fullcard_constants_match_frozen_pipeline() -> None:
    assert PRINTED_FACE == (0, 0, 384, 512)
    assert SOURCE_COLOR_ATTEMPTS[:4] == (224, 192, 160, 144)
    assert SOURCE_COLOR_ATTEMPTS[-1] == 32
