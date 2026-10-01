from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import FormatError, VerificationError
from .lzss import compress as lzss_compress
from .lzss import decompress as lzss_decompress

ALIGN = 0x100
REC_SIZE = 0x114


@dataclass
class Member:
    index: int
    name: str
    record_off: int
    data_rel: int
    stored_size: int
    compression: int
    next_size: int
    blob: bytes
    raw: bytes | None = None


@dataclass
class Archive:
    path: Path
    raw: bytes
    header_size: int
    data_start: int
    members: list[Member]


def align_up(value: int, alignment: int = ALIGN) -> int:
    return (value + alignment - 1) // alignment * alignment


def decode_member_blob(blob: bytes, compression: int) -> bytes:
    if compression == 0:
        return blob
    if compression != 1:
        raise FormatError(f"unsupported compression flag {compression}")
    if len(blob) < 4:
        raise FormatError("compressed member is too short")
    expected = struct.unpack_from("<I", blob, 0)[0]
    return lzss_decompress(blob[4:], expected)


def encode_member_blob(raw: bytes, compression: int = 1, *, max_candidates: int = 96) -> bytes:
    if compression == 0:
        return raw
    if compression != 1:
        raise FormatError(f"unsupported compression flag {compression}")
    compressed = lzss_compress(raw, max_candidates=max_candidates)
    if lzss_decompress(compressed, len(raw)) != raw:
        raise VerificationError("internal LZSS round-trip verification failed")
    return struct.pack("<I", len(raw)) + compressed


def parse_archive_bytes(
    raw: bytes,
    *,
    label: str | Path = "<memory>",
    decompress: bool = False,
) -> Archive:
    """Parse a BOTSD UI archive already resident in memory.

    Keeping this separate from :func:`parse_archive` lets semantic builders work from
    hash-guarded component bytes without temporary files.
    """
    archive_path = Path(label)
    if len(raw) < 0x20:
        raise FormatError(f"{archive_path}: too small")
    declared = struct.unpack_from("<I", raw, 0)[0]
    if declared != len(raw):
        raise FormatError(f"{archive_path}: declared size {declared} != actual {len(raw)}")
    if raw[4:8] != b"ALL " or raw[12:16] != b"HDR ":
        raise FormatError(f"{archive_path}: unrecognized archive header")
    header_size = struct.unpack_from("<I", raw, 8)[0]
    record_size = struct.unpack_from("<I", raw, 16)[0]
    if record_size != REC_SIZE:
        raise FormatError(f"{archive_path}: unexpected record size 0x{record_size:X}")
    data_start = 8 + header_size
    if data_start > len(raw):
        raise FormatError(f"{archive_path}: data start outside file")

    members: list[Member] = []
    offset = 20
    index = 0
    while offset + REC_SIZE <= data_start:
        record = raw[offset : offset + REC_SIZE]
        if record[:4] != b"FILE":
            break
        name = record[4:260].split(b"\x00", 1)[0].decode("ascii", errors="strict")
        data_rel, stored_size, compression, next_size = struct.unpack_from("<IIII", record, 260)
        start = data_start + data_rel
        end = start + stored_size
        if start < data_start or end > len(raw):
            raise FormatError(f"{archive_path}: member {name} range outside archive")
        blob = raw[start:end]
        member = Member(index, name, offset, data_rel, stored_size, compression, next_size, blob)
        if decompress:
            member.raw = decode_member_blob(blob, compression)
        members.append(member)
        index += 1
        if next_size == 0:
            break
        if next_size != REC_SIZE:
            raise FormatError(
                f"{archive_path}: member {name} has unexpected next record size 0x{next_size:X}"
            )
        offset += next_size
    if not members:
        raise FormatError(f"{archive_path}: no FILE records found")
    return Archive(archive_path, raw, header_size, data_start, members)


def parse_archive(path: str | Path, decompress: bool = False) -> Archive:
    archive_path = Path(path)
    return parse_archive_bytes(
        archive_path.read_bytes(),
        label=archive_path,
        decompress=decompress,
    )


def member_allocation(archive: Archive, member: Member) -> int:
    """Return the fixed byte allocation available to a packed member."""
    if member.index + 1 < len(archive.members):
        return archive.members[member.index + 1].data_rel - member.data_rel
    return len(archive.raw) - archive.data_start - member.data_rel


def replace_member_in_place(
    archive_bytes: bytes,
    member_name: str,
    raw_member: bytes,
    *,
    compressed_stream: bytes,
    expected_stored_size: int | None = None,
) -> bytes:
    """Replace one member without moving any archive record or allocation.

    ``compressed_stream`` is the raw LZSS stream *without* the four-byte uncompressed
    size prefix. This explicit API makes the chosen compressor part of the semantic
    build recipe and allows release builds to reproduce historical packed bytes exactly.
    """
    archive = parse_archive_bytes(archive_bytes, decompress=False)
    try:
        member = next(row for row in archive.members if row.name == member_name)
    except StopIteration as exc:
        raise FormatError(f"archive member not found: {member_name}") from exc
    if member.compression != 1:
        raise FormatError(
            f"{member_name}: expected compressed member flag 1, got {member.compression}"
        )

    blob = struct.pack("<I", len(raw_member)) + compressed_stream
    if expected_stored_size is not None and len(blob) != expected_stored_size:
        raise VerificationError(
            f"{member_name}: encoded size {len(blob)} != expected {expected_stored_size}"
        )
    allocation = member_allocation(archive, member)
    if len(blob) > allocation:
        raise FormatError(
            f"{member_name}: encoded member {len(blob)} exceeds fixed allocation {allocation}"
        )
    if lzss_decompress(compressed_stream, len(raw_member)) != raw_member:
        raise VerificationError(f"{member_name}: generated LZSS stream failed round-trip")

    out = bytearray(archive_bytes)
    start = archive.data_start + member.data_rel
    out[start : start + allocation] = blob + b"\x00" * (allocation - len(blob))
    struct.pack_into("<I", out, member.record_off + 264, len(blob))

    rebuilt = bytes(out)
    check = parse_archive_bytes(rebuilt, decompress=True)
    got = next(row for row in check.members if row.name == member_name)
    if got.raw != raw_member:
        raise VerificationError(f"{member_name}: in-place archive verification failed")
    return rebuilt


def rebuild_archive_bytes(
    archive: Archive,
    replacements: dict[str, bytes],
    compression: int = 1,
    pad_to: int | None = None,
) -> bytes:
    """Rebuild an archive in memory and verify every decompressed member."""
    header = bytearray(archive.raw[: archive.data_start])
    payload = bytearray()
    encoded: list[tuple[Member, bytes, int]] = []

    for member in archive.members:
        raw = replacements.get(member.name)
        if raw is None:
            raw = decode_member_blob(member.blob, member.compression)
        blob = encode_member_blob(raw, compression)
        relative = align_up(len(payload), ALIGN)
        if relative > len(payload):
            payload.extend(b"\x00" * (relative - len(payload)))
        payload.extend(blob)
        encoded.append((member, blob, relative))

    total = archive.data_start + len(payload)
    aligned = align_up(total, ALIGN)
    payload.extend(b"\x00" * (aligned - total))
    total = archive.data_start + len(payload)
    if pad_to is not None:
        if total > pad_to:
            raise FormatError(f"rebuilt archive is {total} bytes, cannot pad down to {pad_to}")
        payload.extend(b"\x00" * (pad_to - total))
        total = pad_to

    for member, blob, relative in encoded:
        struct.pack_into("<III", header, member.record_off + 260, relative, len(blob), compression)
    struct.pack_into("<I", header, 0, total)
    rebuilt = bytes(header) + bytes(payload)
    if len(rebuilt) != total:
        raise VerificationError("archive size accounting error")

    check = parse_archive_bytes(rebuilt, label=f"{archive.path}::<rebuilt>", decompress=True)
    if len(check.members) != len(archive.members):
        raise VerificationError("member count changed after rebuild")
    for original, got in zip(archive.members, check.members, strict=True):
        if original.name != got.name:
            raise VerificationError("member order/name changed after rebuild")
        expected = replacements.get(original.name)
        if expected is None:
            expected = decode_member_blob(original.blob, original.compression)
        if got.raw != expected:
            raise VerificationError(f"verification failed for {original.name}")
    return rebuilt


def rebuild_archive(
    archive: Archive,
    replacements: dict[str, bytes],
    output: str | Path,
    compression: int = 1,
    pad_to: int | None = None,
) -> None:
    output_path = Path(output)
    rebuilt = rebuild_archive_bytes(archive, replacements, compression=compression, pad_to=pad_to)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(rebuilt)
