from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from botsd.extract import verify_hash_manifest
from botsd.iso9660 import SECTOR


def _both32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def _both16(value: int) -> bytes:
    return struct.pack("<H", value) + struct.pack(">H", value)


def _dir_record(extent: int, size: int, flags: int, ident: bytes) -> bytes:
    length = 33 + len(ident) + (1 if len(ident) % 2 == 0 else 0)
    record = bytearray(length)
    record[0] = length
    record[2:10] = _both32(extent)
    record[10:18] = _both32(size)
    record[25] = flags
    record[28:32] = _both16(1)
    record[32] = len(ident)
    record[33 : 33 + len(ident)] = ident
    return bytes(record)


def _make_iso(path: Path) -> bytes:
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
    payload = b"ABCD"
    raw[21 * SECTOR : 21 * SECTOR + len(payload)] = payload
    path.write_bytes(raw)
    return payload


def test_verify_hash_manifest_and_extract_streaming(tmp_path: Path) -> None:
    iso = tmp_path / "fixture.iso"
    payload = _make_iso(iso)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = tmp_path / "hashes.tsv"
    manifest.write_text(f"basename\tsha256\nTEST.BIN\t{digest}\n", encoding="utf-8")
    output = tmp_path / "out" / "TEST.BIN"

    rows = verify_hash_manifest(iso, manifest, {"TEST.BIN": output})
    assert len(rows) == 1
    assert rows[0].iso_path == "/TEST.BIN"
    assert rows[0].sha256 == digest
    assert output.read_bytes() == payload
