#!/usr/bin/env python3
"""Compatibility CLI for the shared :mod:`botsd.archive` implementation.

Historical scripts may continue importing this filename. New code should import
``botsd.archive`` directly.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.archive import (
    ALIGN,
    REC_SIZE,
    Archive,
    Member,
    align_up,
    decode_member_blob,
    encode_member_blob,
    parse_archive,
    rebuild_archive,
)
from botsd.lzss import compress as lzss_compress
from botsd.lzss import decompress as lzss_decompress

__all__ = [
    "ALIGN",
    "REC_SIZE",
    "Archive",
    "Member",
    "align_up",
    "decode_member_blob",
    "encode_member_blob",
    "parse_archive",
    "rebuild_archive",
    "lzss_compress",
    "lzss_decompress",
]


def cmd_list(args: argparse.Namespace) -> None:
    archive = parse_archive(args.archive, decompress=True)
    print(
        f"{args.archive}: {len(archive.raw)} bytes; data_start=0x{archive.data_start:X}; "
        f"{len(archive.members)} members"
    )
    for member in archive.members:
        print(
            f"{member.index:02d} {member.name:40s} rel=0x{member.data_rel:06X} "
            f"stored={member.stored_size:7d} comp={member.compression} "
            f"raw={len(member.raw or b''):7d}"
        )


def cmd_extract(args: argparse.Namespace) -> None:
    archive = parse_archive(args.archive, decompress=True)
    args.output.mkdir(parents=True, exist_ok=True)
    for member in archive.members:
        suffix = ".tga" if member.name.upper().endswith("_TGA") else ".bin"
        path = args.output / (member.name + suffix)
        path.write_bytes(member.raw or b"")
        print(path)


def cmd_repack(args: argparse.Namespace) -> None:
    archive = parse_archive(args.archive)
    replacements: dict[str, bytes] = {}
    if args.input_dir:
        for member in archive.members:
            for extension in (".tga", ".bin", ""):
                path = args.input_dir / (member.name + extension)
                if path.is_file():
                    replacements[member.name] = path.read_bytes()
                    break
    rebuild_archive(archive, replacements, args.output, compression=1, pad_to=args.pad_to)
    print(f"Wrote {args.output} ({args.output.stat().st_size} bytes); verified {len(archive.members)} members")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    command = sub.add_parser("list")
    command.add_argument("archive", type=Path)
    command.set_defaults(func=cmd_list)
    command = sub.add_parser("extract")
    command.add_argument("archive", type=Path)
    command.add_argument("output", type=Path)
    command.set_defaults(func=cmd_extract)
    command = sub.add_parser("repack")
    command.add_argument("archive", type=Path)
    command.add_argument("input_dir", type=Path, nargs="?")
    command.add_argument("output", type=Path)
    command.add_argument("--pad-to", type=lambda value: int(value, 0))
    command.set_defaults(func=cmd_repack)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
