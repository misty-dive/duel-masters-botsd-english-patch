from __future__ import annotations

import struct
from pathlib import Path

from botsd.iso9660 import Iso9660, SECTOR, patch_iso


def _both32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def _both16(value: int) -> bytes:
    return struct.pack("<H", value) + struct.pack(">H", value)


def _dir_record(extent: int, size: int, flags: int, ident: bytes) -> bytes:
    length = 33 + len(ident) + (1 if len(ident) % 2 == 0 else 0)
    record = bytearray(length)
    record[0] = length
    record[1] = 0
    record[2:10] = _both32(extent)
    record[10:18] = _both32(size)
    record[18:25] = b"\x00" * 7
    record[25] = flags
    record[26] = 0
    record[27] = 0
    record[28:32] = _both16(1)
    record[32] = len(ident)
    record[33 : 33 + len(ident)] = ident
    return bytes(record)


def _make_iso(path: Path) -> None:
    sectors = 24
    raw = bytearray(sectors * SECTOR)

    pvd = memoryview(raw)[16 * SECTOR : 17 * SECTOR]
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[80:88] = _both32(sectors)
    root = _dir_record(20, SECTOR, 2, b"\x00")
    pvd[156 : 156 + len(root)] = root

    term = memoryview(raw)[17 * SECTOR : 18 * SECTOR]
    term[0] = 255
    term[1:6] = b"CD001"
    term[6] = 1

    directory = bytearray(SECTOR)
    records = [
        _dir_record(20, SECTOR, 2, b"\x00"),
        _dir_record(20, SECTOR, 2, b"\x01"),
        _dir_record(21, 4, 0, b"TEST.BIN;1"),
    ]
    pos = 0
    for record in records:
        directory[pos : pos + len(record)] = record
        pos += len(record)
    raw[20 * SECTOR : 21 * SECTOR] = directory
    raw[21 * SECTOR : 21 * SECTOR + 4] = b"ABCD"
    path.write_bytes(raw)


def test_iso_reader_and_in_place_patch(tmp_path: Path):
    source = tmp_path / "source.iso"
    output = tmp_path / "patched.iso"
    replacement = tmp_path / "TEST.BIN"
    _make_iso(source)
    replacement.write_bytes(b"WXYZ")

    image = Iso9660(source)
    entry = image.find_unique_basename("TEST.BIN")
    assert entry.extent == 21
    assert entry.size == 4

    rows = patch_iso(source, output, [replacement], strict_core=False)
    assert rows[0].mode == "in-place"
    patched = Iso9660(output).find_unique_basename("TEST.BIN")
    with output.open("rb") as stream:
        stream.seek(patched.extent * SECTOR)
        assert stream.read(patched.size) == b"WXYZ"


def test_iso_append_and_retarget(tmp_path: Path):
    source = tmp_path / "source.iso"
    output = tmp_path / "patched.iso"
    replacement = tmp_path / "TEST.BIN"
    _make_iso(source)
    replacement.write_bytes(b"R" * 3000)

    rows = patch_iso(source, output, [replacement], strict_core=False)
    assert rows[0].mode == "append+retarget"
    patched = Iso9660(output).find_unique_basename("TEST.BIN")
    assert patched.extent >= 24
    assert patched.size == 3000
    with output.open("rb") as stream:
        stream.seek(patched.extent * SECTOR)
        assert stream.read(3000) == b"R" * 3000
