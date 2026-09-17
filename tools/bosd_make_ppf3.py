#!/usr/bin/env python3
"""
Create a standard PPF 3.0 patch from two binary images.

Designed for the Duel Masters: Birth of the Super Dragon translation project,
but generic enough for any source/target binary pair.

No third-party Python packages are required.

PPF3 layout follows the public RomPatcher.js implementation/reference:
- magic/version: PPF30 + version byte 0x02
- 50-byte NUL-padded description
- image type BIN
- no block check
- no undo data
- records: uint64 little-endian offset, uint8 length, replacement bytes
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
from pathlib import Path

HEADER_SIZE = 60
MAX_RECORD = 0xFF
SCAN_CHUNK = 4 * 1024 * 1024


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_header(out, description: str) -> None:
    desc = description.encode("ascii", errors="strict")
    if len(desc) > 50:
        raise ValueError("PPF description must be at most 50 ASCII bytes")

    out.write(b"PPF")
    out.write(b"30")
    out.write(b"\x02")                 # version byte: 3 - 1
    out.write(desc.ljust(50, b"\x00"))
    out.write(b"\x00")                 # image type: BIN
    out.write(b"\x00")                 # block check: disabled
    out.write(b"\x00")                 # undo data: disabled
    out.write(b"\x00")                 # dummy


def write_record(out, offset: int, data: bytes) -> None:
    if not (1 <= len(data) <= MAX_RECORD):
        raise ValueError(f"invalid record length: {len(data)}")
    out.write(struct.pack("<Q", offset))
    out.write(bytes((len(data),)))
    out.write(data)


def build_ppf3(source: Path, target: Path, output: Path, description: str) -> tuple[int, int]:
    source_size = source.stat().st_size
    target_size = target.stat().st_size

    if target_size < source_size:
        raise SystemExit(
            "PPF3 cannot truncate the source image safely with this release tool: "
            f"source={source_size}, target={target_size}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    record_count = 0
    changed_bytes = 0
    payload_bytes = 0
    highest_written_end = 0

    with source.open("rb") as src, target.open("rb") as dst, output.open("wb") as ppf:
        write_header(ppf, description)

        base = 0
        while base < target_size:
            want = min(SCAN_CHUNK, target_size - base)
            t = dst.read(want)
            if len(t) != want:
                raise RuntimeError("short read from target")

            s = src.read(want)
            if len(s) < want:
                s += b"\x00" * (want - len(s))

            if s == t:
                base += want
                continue

            i = 0
            while i < want:
                if s[i] == t[i]:
                    i += 1
                    continue

                start = i
                run = bytearray()

                while i < want and s[i] != t[i] and len(run) < MAX_RECORD:
                    run.append(t[i])
                    i += 1

                write_record(ppf, base + start, bytes(run))
                record_count += 1
                changed_bytes += len(run)
                payload_bytes += len(run)
                highest_written_end = max(highest_written_end, base + start + len(run))

                # If the differing run exceeded 255 bytes, the next loop iteration
                # immediately emits the next record at the following offset.

            base += want

        # RomPatcher.js-compatible file-extension safeguard:
        # if the target is larger and ends in zero, ensure applying the patch
        # still extends the output image to the target's exact final byte.
        if target_size > source_size and highest_written_end < target_size:
            dst.seek(target_size - 1)
            final_byte = dst.read(1)
            if final_byte != b"\x00":
                raise RuntimeError("internal extension accounting error")
            write_record(ppf, target_size - 1, b"\x00")
            record_count += 1
            payload_bytes += 1

    return record_count, changed_bytes, payload_bytes


def verify_ppf3_structure(path: Path) -> tuple[int, int]:
    raw_size = path.stat().st_size
    records = 0
    payload = 0

    with path.open("rb") as f:
        header = f.read(HEADER_SIZE)
        if len(header) != HEADER_SIZE:
            raise RuntimeError("truncated PPF header")
        if header[:6] != b"PPF30\x02":
            raise RuntimeError("unexpected PPF3 header")
        if header[56:60] != b"\x00\x00\x00\x00":
            raise RuntimeError("unexpected PPF3 option bytes")

        pos = HEADER_SIZE
        while pos < raw_size:
            h = f.read(9)
            if len(h) != 9:
                raise RuntimeError(f"truncated record header at 0x{pos:X}")
            _, length = struct.unpack("<QB", h)
            if length == 0:
                raise RuntimeError(f"zero-length PPF record at 0x{pos:X}")
            data = f.read(length)
            if len(data) != length:
                raise RuntimeError(f"truncated PPF record at 0x{pos:X}")
            records += 1
            payload += length
            pos += 9 + length

        if pos != raw_size:
            raise RuntimeError("PPF parse did not end at EOF")

    return records, payload


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create a standard PPF 3.0 patch from source and target images."
    )
    ap.add_argument("source", type=Path, help="source/original image")
    ap.add_argument("target", type=Path, help="desired patched image")
    ap.add_argument("output", type=Path, help="output .ppf path")
    ap.add_argument(
        "--description",
        default="Duel Masters BOTSD English patch",
        help="ASCII PPF description, max 50 bytes",
    )
    args = ap.parse_args()

    for p in (args.source, args.target):
        if not p.is_file():
            ap.error(f"file not found: {p}")

    if args.output.resolve() in (args.source.resolve(), args.target.resolve()):
        ap.error("output must not overwrite source or target")

    print("Source:", args.source)
    print("Target:", args.target)
    print("Output:", args.output)
    print()

    source_hash = sha256_file(args.source)
    target_hash = sha256_file(args.target)

    records, changed, payload = build_ppf3(
        args.source, args.target, args.output, args.description
    )

    parsed_records, parsed_payload = verify_ppf3_structure(args.output)
    if (records, payload) != (parsed_records, parsed_payload):
        raise RuntimeError(
            f"verification mismatch: built {(records, payload)}, "
            f"parsed {(parsed_records, parsed_payload)}"
        )

    patch_hash = sha256_file(args.output)

    print("Source SHA-256:", source_hash)
    print("Target SHA-256:", target_hash)
    print("PPF SHA-256:   ", patch_hash)
    print("PPF size:      ", args.output.stat().st_size, "bytes")
    print("Records:       ", records)
    print("Changed bytes: ", changed)
    print()
    print("Verification: PASS")
    print("Format: PPF 3.0 / BIN / no blockcheck / no undo data")


if __name__ == "__main__":
    main()
