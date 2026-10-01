from __future__ import annotations

import struct
from pathlib import Path

from botsd.archive import parse_archive, replace_member_in_place
from botsd.lzss import compress, decompress


def _archive(tmp_path: Path) -> tuple[Path, bytes]:
    # One-member fixed-allocation archive: header is 0x200 bytes, payload is 0x100 bytes.
    raw_member = b"ABCD" * 16
    stream = compress(raw_member)
    blob = struct.pack("<I", len(raw_member)) + stream
    data_start = 0x200
    total = data_start + 0x100
    out = bytearray(total)
    struct.pack_into("<I", out, 0, total)
    out[4:8] = b"ALL "
    struct.pack_into("<I", out, 8, data_start - 8)
    out[12:16] = b"HDR "
    struct.pack_into("<I", out, 16, 0x114)
    rec = 20
    out[rec : rec + 4] = b"FILE"
    name = b"TEST_TGA"
    out[rec + 4 : rec + 4 + len(name)] = name
    struct.pack_into("<IIII", out, rec + 260, 0, len(blob), 1, 0)
    out[data_start : data_start + len(blob)] = blob
    path = tmp_path / "archive.dat"
    path.write_bytes(out)
    return path, bytes(out)


def test_replace_member_in_place_preserves_layout(tmp_path: Path):
    path, original = _archive(tmp_path)
    parsed = parse_archive(path, decompress=True)
    old = parsed.members[0]
    replacement = b"XYZ" * 20
    stream = compress(replacement)
    rebuilt = replace_member_in_place(
        original,
        "TEST_TGA",
        replacement,
        compressed_stream=stream,
        expected_stored_size=4 + len(stream),
    )
    out = tmp_path / "out.dat"
    out.write_bytes(rebuilt)
    check = parse_archive(out, decompress=True)
    member = check.members[0]
    assert member.data_rel == old.data_rel
    assert member.raw == replacement
    assert decompress(member.blob[4:], struct.unpack_from("<I", member.blob, 0)[0]) == replacement
