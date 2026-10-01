import struct

from botsd.fontlink import (
    compress,
    decompress,
    make_ue_from_u,
    pack_4bpp,
    page_geometry,
    unpack_4bpp,
)


def test_fontlink_compressor_roundtrip() -> None:
    raw = (b"abcabcabc" * 40) + bytes(range(64))
    assert decompress(compress(raw)) == raw


def test_font_page_geometry_and_4bpp_roundtrip() -> None:
    width, height, count = 12, 24, 2
    glyph_bytes = width * height // 2
    payload = bytes([0x12] * glyph_bytes * count)
    page = struct.pack("<HHHH", width, height, glyph_bytes, 0) + payload
    assert page_geometry(page) == (12, 24, 144, 2)
    pixels = unpack_4bpp(payload[:glyph_bytes])
    assert pack_4bpp(pixels) == payload[:glyph_bytes]


def test_make_ue_from_u_preserves_shape_and_adds_diaeresis() -> None:
    source = [0] * (12 * 24)
    source[2 * 12 + 1] = 15
    result = make_ue_from_u(source)
    assert len(result) == len(source)
    assert result[3 * 12 + 1] == 15
    assert result[2] == 5
    assert result[3] == 5
    assert result[7] == 5
    assert result[8] == 5
    assert result[12 + 2] == 15
