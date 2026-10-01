from __future__ import annotations

import struct
from pathlib import Path

from botsd.sda import OuterSDA, replace_chunks_in_copy


def _write_sda(path: Path, chunks: list[bytes]) -> None:
    count = len(chunks)
    header_size = 12 + count * 4
    offsets = []
    pos = header_size
    for chunk in chunks:
        offsets.append(pos)
        pos += len(chunk)
    raw = bytearray(pos)
    raw[:4] = b"sda\0"
    struct.pack_into("<II", raw, 4, pos, count)
    struct.pack_into(f"<{count}I", raw, 12, *offsets)
    for offset, chunk in zip(offsets, chunks, strict=True):
        raw[offset : offset + len(chunk)] = chunk
    path.write_bytes(raw)


def test_outer_sda_streaming_layout_and_replacement(tmp_path: Path) -> None:
    source_path = tmp_path / "source.img"
    _write_sda(source_path, [b"aaa", b"bbbb", b"cc"])
    source = OuterSDA(source_path)
    assert source.chunk_count == 3
    assert source.read_chunk(1) == b"bbbb"
    assert source.bounds(2).size == 2

    output = replace_chunks_in_copy(source, tmp_path / "output.img", {1: b"WXYZ"})
    assert source.same_layout(output)
    assert source.changed_chunks(output) == [1]
    assert output.read_chunk(1) == b"WXYZ"
