from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import FormatError, VerificationError


@dataclass(frozen=True)
class ChunkRange:
    index: int
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


class OuterSDA:
    """Streaming reader for BOTSD's outer ``sda\0`` offset-table container."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        with self.path.open("rb") as handle:
            header = handle.read(12)
            if len(header) != 12 or header[:4] != b"sda\0":
                raise FormatError(f"{self.path}: not an outer SDA container")
            declared, count = struct.unpack_from("<II", header, 4)
            if declared != self.size:
                raise FormatError(
                    f"{self.path}: declared size {declared} != actual {self.size}"
                )
            raw_offsets = handle.read(count * 4)
            if len(raw_offsets) != count * 4:
                raise FormatError(f"{self.path}: truncated SDA offset table")
        self.offsets = tuple(struct.unpack(f"<{count}I", raw_offsets))
        if not self.offsets:
            raise FormatError(f"{self.path}: SDA has no chunks")
        table_end = 12 + count * 4
        previous = table_end
        for index, offset in enumerate(self.offsets):
            if offset < table_end or offset < previous or offset > self.size:
                raise FormatError(
                    f"{self.path}: invalid chunk offset[{index}]={offset} "
                    f"(table_end={table_end}, previous={previous}, size={self.size})"
                )
            previous = offset

    @property
    def chunk_count(self) -> int:
        return len(self.offsets)

    def bounds(self, index: int) -> ChunkRange:
        if not 0 <= index < self.chunk_count:
            raise IndexError(index)
        start = self.offsets[index]
        end = self.offsets[index + 1] if index + 1 < self.chunk_count else self.size
        return ChunkRange(index, start, end)

    def read_chunk(self, index: int) -> bytes:
        bounds = self.bounds(index)
        with self.path.open("rb") as handle:
            handle.seek(bounds.start)
            data = handle.read(bounds.size)
        if len(data) != bounds.size:
            raise FormatError(f"{self.path}: short read for chunk {index}")
        return data

    def chunk_sha256(self, index: int, *, block_size: int = 1024 * 1024) -> str:
        bounds = self.bounds(index)
        digest = hashlib.sha256()
        remaining = bounds.size
        with self.path.open("rb") as handle:
            handle.seek(bounds.start)
            while remaining:
                chunk = handle.read(min(block_size, remaining))
                if not chunk:
                    raise FormatError(f"{self.path}: short read for chunk {index}")
                digest.update(chunk)
                remaining -= len(chunk)
        return digest.hexdigest()

    def same_layout(self, other: OuterSDA) -> bool:
        return self.size == other.size and self.offsets == other.offsets

    def changed_chunks(self, other: OuterSDA) -> list[int]:
        if not self.same_layout(other):
            raise VerificationError("outer SDA size/offset table changed")
        changed: list[int] = []
        with self.path.open("rb") as left, other.path.open("rb") as right:
            for index in range(self.chunk_count):
                bounds = self.bounds(index)
                left.seek(bounds.start)
                right.seek(bounds.start)
                remaining = bounds.size
                differs = False
                while remaining:
                    size = min(1024 * 1024, remaining)
                    a = left.read(size)
                    b = right.read(size)
                    if len(a) != size or len(b) != size:
                        raise FormatError(f"short chunk read at index {index}")
                    if a != b:
                        differs = True
                        break
                    remaining -= size
                if differs:
                    changed.append(index)
        return changed


def replace_chunks_in_copy(
    source: OuterSDA,
    output: str | Path,
    replacements: dict[int, bytes],
) -> OuterSDA:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Stream the source once rather than materializing the ~150 MiB UNPACK in memory.
    with source.path.open("rb") as src, output_path.open("wb") as dst:
        while True:
            block = src.read(8 * 1024 * 1024)
            if not block:
                break
            dst.write(block)
    with output_path.open("r+b") as handle:
        for index, payload in sorted(replacements.items()):
            bounds = source.bounds(index)
            if len(payload) != bounds.size:
                raise ValueError(
                    f"chunk {index}: replacement size {len(payload)} != allocation {bounds.size}"
                )
            handle.seek(bounds.start)
            handle.write(payload)
    result = OuterSDA(output_path)
    if not source.same_layout(result):
        raise VerificationError("outer SDA layout changed after chunk replacement")
    return result
