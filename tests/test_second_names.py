from __future__ import annotations

import hashlib
import struct
import zipfile
from pathlib import Path

from botsd.indexed_tga import IndexedTGA
from botsd.manifest import (
    LOCALIZED_UNPACK_SHA256,
    SECOND_NAME_PAYLOAD_SHA256,
    SECOND_NAME_TITLE_BAND,
)
from botsd.second_names import _find_title_ramp
from botsd.unpack import write_second_name_patch


def _synthetic_title_tga() -> bytes:
    width = height = 128
    header = bytearray(18)
    header[1] = 1
    header[2] = 1
    struct.pack_into("<HHB", header, 3, 0, 256, 32)
    struct.pack_into("<HHHHBB", header, 8, 0, 0, width, height, 8, 0x20)
    palette = bytearray(256 * 4)
    for index in range(256):
        palette[index * 4 : index * 4 + 4] = bytes((0, 0, 0, 0))
    for offset, alpha in enumerate((24, 64, 104, 144, 184, 224), start=10):
        # Stored as BGRA; all ramp entries share the same RGB.
        palette[offset * 4 : offset * 4 + 4] = bytes((40, 80, 120, alpha))
    pixels = bytearray(width * height)
    for y in range(3, 11):
        for x in range(20, 100):
            pixels[y * width + x] = 10 + ((x + y) % 6)
    return bytes(header + palette + pixels)


def test_recovered_second_name_release_constants() -> None:
    assert LOCALIZED_UNPACK_SHA256 == (
        "2d3fe1849b18e749fac2a9f496776c2d653c9450d566c9f90fdea216b370ff58"
    )
    assert SECOND_NAME_PAYLOAD_SHA256 == (
        "dea8fa559db96f9cc38bfeddac8996dc27a2c90c3f2fdd28e9ece659f76c0f92"
    )
    assert SECOND_NAME_TITLE_BAND == (0, 2, 128, 15)


def test_title_ramp_detector_prefers_exclusive_connected_component() -> None:
    mask, colour, method, bbox, pixels = _find_title_ramp(IndexedTGA(_synthetic_title_tga()))
    assert method == "exclusive"
    assert colour == (120, 80, 40)
    assert bbox == (20, 3, 100, 11)
    assert pixels == 80 * 8
    assert int(mask.sum()) == pixels


def test_second_name_patch_writer_is_deterministic(tmp_path: Path) -> None:
    payloads = [(2037, b"A" * 32), (2038, b"B" * 32)]
    rows = [
        {
            "chunk": str(index),
            "retail_sha256": hashlib.sha256(bytes([index & 0xFF]) * 32).hexdigest(),
            "patched_sha256": hashlib.sha256(payload).hexdigest(),
        }
        for index, payload in payloads
    ]
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    write_second_name_patch(first, rows, payloads)
    write_second_name_patch(second, rows, payloads)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.read("chunks/2037.bin") == b"A" * 32
        assert archive.read("chunks/2038.bin") == b"B" * 32
