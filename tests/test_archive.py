from __future__ import annotations

import struct
from pathlib import Path

from botsd.archive import REC_SIZE, encode_member_blob, parse_archive, rebuild_archive


def _make_archive(path: Path, payload: bytes) -> None:
    data_start = 0x140
    blob = encode_member_blob(payload)
    total = data_start + len(blob)
    total = (total + 0xFF) & ~0xFF
    raw = bytearray(total)
    struct.pack_into("<I", raw, 0, total)
    raw[4:8] = b"ALL "
    struct.pack_into("<I", raw, 8, data_start - 8)
    raw[12:16] = b"HDR "
    struct.pack_into("<I", raw, 16, REC_SIZE)
    off = 20
    raw[off : off + 4] = b"FILE"
    raw[off + 4 : off + 4 + len(b"TEST_TGA")] = b"TEST_TGA"
    struct.pack_into("<IIII", raw, off + 260, 0, len(blob), 1, 0)
    raw[data_start : data_start + len(blob)] = blob
    path.write_bytes(raw)


def test_archive_parse_and_rebuild(tmp_path: Path):
    source = tmp_path / "source.dat"
    output = tmp_path / "output.dat"
    _make_archive(source, b"abc123" * 100)
    archive = parse_archive(source, decompress=True)
    assert len(archive.members) == 1
    assert archive.members[0].raw == b"abc123" * 100

    replacement = b"replacement" * 80
    rebuild_archive(archive, {"TEST_TGA": replacement}, output)
    rebuilt = parse_archive(output, decompress=True)
    assert rebuilt.members[0].raw == replacement
