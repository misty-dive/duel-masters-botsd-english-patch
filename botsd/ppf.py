from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator
from typing import BinaryIO

from .errors import FormatError, VerificationError

HEADER_SIZE = 60
MAX_RECORD = 0xFF
SCAN_CHUNK = 4 * 1024 * 1024


@dataclass(frozen=True)
class PPFRecord:
    offset: int
    payload: bytes

    @property
    def end(self) -> int:
        return self.offset + len(self.payload)


@dataclass(frozen=True)
class PPFStats:
    records: int
    payload_bytes: int
    max_end: int


def header(description: str) -> bytes:
    desc = description.encode("ascii", errors="strict")
    if len(desc) > 50:
        raise ValueError("PPF description must be at most 50 ASCII bytes")
    return b"PPF30\x02" + desc.ljust(50, b"\x00") + b"\x00\x00\x00\x00"


def read_header(stream: BinaryIO) -> bytes:
    raw = stream.read(HEADER_SIZE)
    if len(raw) != HEADER_SIZE:
        raise FormatError("truncated PPF header")
    if raw[:6] != b"PPF30\x02":
        raise FormatError("unexpected PPF3 header")
    if raw[56:60] != b"\x00\x00\x00\x00":
        raise FormatError("PPF block-check/undo modes are not supported")
    return raw


def write_record(stream: BinaryIO, offset: int, payload: bytes) -> None:
    if offset < 0:
        raise ValueError("PPF record offset must be non-negative")
    if not 1 <= len(payload) <= MAX_RECORD:
        raise ValueError(f"invalid PPF record length: {len(payload)}")
    stream.write(struct.pack("<Q", offset))
    stream.write(bytes((len(payload),)))
    stream.write(payload)


def iter_records(path: str | Path) -> Iterator[PPFRecord]:
    with Path(path).open("rb") as stream:
        read_header(stream)
        while True:
            rec = stream.read(9)
            if not rec:
                break
            if len(rec) != 9:
                raise FormatError("truncated PPF record header")
            offset, length = struct.unpack("<QB", rec)
            if length == 0:
                raise FormatError(f"zero-length PPF record at 0x{offset:X}")
            payload = stream.read(length)
            if len(payload) != length:
                raise FormatError(f"truncated PPF record at 0x{offset:X}")
            yield PPFRecord(offset, payload)


def verify(
    path: str | Path, *, require_sorted: bool = True, allow_overlap: bool = False
) -> PPFStats:
    count = 0
    payload_bytes = 0
    max_end = 0
    previous_offset = -1
    previous_end = -1
    for record in iter_records(path):
        if require_sorted and record.offset < previous_offset:
            raise FormatError(f"PPF records are out of order at 0x{record.offset:X}")
        if not allow_overlap and previous_end >= 0 and record.offset < previous_end:
            raise FormatError(f"PPF records overlap at 0x{record.offset:X}")
        previous_offset = record.offset
        previous_end = record.end
        max_end = max(max_end, record.end)
        count += 1
        payload_bytes += len(record.payload)
    return PPFStats(count, payload_bytes, max_end)


def apply(
    source: str | Path,
    patch: str | Path,
    output: str | Path,
    *,
    target_size: int | None = None,
    copy_chunk_size: int = 16 * 1024 * 1024,
) -> PPFStats:
    """Apply a PPF3 patch without holding either disc image in memory."""
    source_path = Path(source)
    patch_path = Path(patch)
    output_path = Path(output)
    if source_path.resolve() == output_path.resolve():
        raise ValueError("output must not overwrite source")

    stats = verify(patch_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    partial.unlink(missing_ok=True)

    try:
        with source_path.open("rb") as src, partial.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=copy_chunk_size)

        with partial.open("r+b") as dst:
            for record in iter_records(patch_path):
                dst.seek(record.offset)
                dst.write(record.payload)
            wanted = (
                target_size
                if target_size is not None
                else max(source_path.stat().st_size, stats.max_end)
            )
            if stats.max_end > wanted:
                raise VerificationError(
                    f"PPF writes through 0x{stats.max_end:X}, beyond requested target size {wanted}"
                )
            dst.truncate(wanted)
            dst.flush()

        if output_path.exists():
            output_path.unlink()
        partial.replace(output_path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return stats


def build(
    source: str | Path,
    target: str | Path,
    output: str | Path,
    *,
    description: str = "Duel Masters BOTSD English patch",
    scan_chunk: int = SCAN_CHUNK,
) -> tuple[PPFStats, int]:
    """Create a standard PPF3 patch by streaming source and target images."""
    source_path = Path(source)
    target_path = Path(target)
    output_path = Path(output)
    source_size = source_path.stat().st_size
    target_size = target_path.stat().st_size
    if target_size < source_size:
        raise ValueError("this PPF3 builder does not encode source-image truncation")
    if scan_chunk < 1:
        raise ValueError("scan_chunk must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = 0
    payload_bytes = 0
    changed_bytes = 0
    highest_end = 0

    with (
        source_path.open("rb") as src,
        target_path.open("rb") as dst,
        output_path.open("wb") as out,
    ):
        out.write(header(description))
        base = 0
        while base < target_size:
            want = min(scan_chunk, target_size - base)
            target_block = dst.read(want)
            if len(target_block) != want:
                raise VerificationError("short read from target image")
            source_block = src.read(want)
            if len(source_block) < want:
                source_block += b"\x00" * (want - len(source_block))
            if source_block != target_block:
                i = 0
                while i < want:
                    if source_block[i] == target_block[i]:
                        i += 1
                        continue
                    start = i
                    payload = bytearray()
                    while (
                        i < want
                        and source_block[i] != target_block[i]
                        and len(payload) < MAX_RECORD
                    ):
                        payload.append(target_block[i])
                        i += 1
                    write_record(out, base + start, bytes(payload))
                    records += 1
                    payload_bytes += len(payload)
                    changed_bytes += len(payload)
                    highest_end = max(highest_end, base + start + len(payload))
            base += want

        if target_size > source_size and highest_end < target_size:
            dst.seek(target_size - 1)
            final_byte = dst.read(1)
            if final_byte != b"\x00":
                raise VerificationError("internal PPF extension accounting error")
            write_record(out, target_size - 1, b"\x00")
            records += 1
            payload_bytes += 1
            highest_end = target_size

    stats = verify(output_path)
    expected = PPFStats(records, payload_bytes, highest_end)
    if stats != expected:
        raise VerificationError(f"PPF self-verification mismatch: built {expected}, parsed {stats}")
    return stats, changed_bytes


def range_payload(path: str | Path, start: int, size: int) -> tuple[bytes, bytes]:
    """Return PPF payload bytes and a 0/1 coverage mask for an absolute image range."""
    if start < 0 or size < 0:
        raise ValueError("start and size must be non-negative")
    end = start + size
    payload = bytearray(size)
    mask = bytearray(size)
    for record in iter_records(path):
        a = max(start, record.offset)
        b = min(end, record.end)
        if a < b:
            payload[a - start : b - start] = record.payload[a - record.offset : b - record.offset]
            mask[a - start : b - start] = b"\x01" * (b - a)
    return bytes(payload), bytes(mask)
