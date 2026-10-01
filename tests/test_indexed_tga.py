import struct

from botsd.indexed_tga import IndexedTGA


def _tga() -> bytes:
    width, height = 4, 2
    header = bytearray(18)
    header[1] = 1
    header[2] = 1
    struct.pack_into("<HHB", header, 3, 0, 2, 32)
    struct.pack_into("<HHHHBB", header, 8, 0, 0, width, height, 8, 0x20)
    palette = bytes((0, 0, 0, 0, 255, 255, 255, 255))
    pixels = bytes((0, 1, 0, 1, 1, 0, 1, 0))
    return bytes(header) + palette + pixels


def test_indexed_tga_metadata_and_pixel_edit_are_contained():
    raw = _tga()
    tga = IndexedTGA(raw)
    assert (tga.width, tga.height) == (4, 2)
    indices = tga.indices_top_down()
    indices[0] = 1
    tga.replace_top_down(indices)
    out = tga.to_bytes()
    assert out[: tga.pixel_offset] == raw[: tga.pixel_offset]
    assert out[tga.pixel_offset] == 1
