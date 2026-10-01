from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable
from typing import BinaryIO

from .errors import FormatError, HashMismatchError, VerificationError
from .hashing import sha256_path, sha256_range
from .manifest import RETAIL_SHA256

SECTOR = 2048

KNOWN_RETAIL_SHA256 = RETAIL_SHA256



@dataclass(frozen=True)
class Entry:
    path: str
    name: str
    extent: int
    size: int
    flags: int
    record_off: int


@dataclass(frozen=True)
class PatchResult:
    path: str
    mode: str
    old_lba: int
    new_lba: int
    old_size: int
    new_size: int
    sha256: str


def _read_exact_at(stream: BinaryIO, offset: int, size: int) -> bytes:
    stream.seek(offset)
    raw = stream.read(size)
    if len(raw) != size:
        raise FormatError(f"short read at 0x{offset:X}: {len(raw)} != {size}")
    return raw


def _read_both32(raw: bytes, offset: int) -> int:
    le = struct.unpack_from("<I", raw, offset)[0]
    be = struct.unpack_from(">I", raw, offset + 4)[0]
    if le != be:
        raise FormatError(f"ISO9660 both-endian value mismatch: {le} != {be}")
    return le


def _write_both32(stream: BinaryIO, offset: int, value: int) -> None:
    stream.seek(offset)
    stream.write(struct.pack("<I", value))
    stream.write(struct.pack(">I", value))


class Iso9660:
    """Small, seek-based ISO9660 reader.

    Only directory sectors and descriptors are loaded; a multi-gigabyte ISO is never
    copied into RAM.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        self.descriptors: list[tuple[int, int]] = []
        self.pvd_off: int | None = None
        self.root_extent: int | None = None
        self.root_size: int | None = None
        self._entries: tuple[Entry, ...] | None = None
        self._read_descriptors()

    def _read_descriptors(self) -> None:
        with self.path.open("rb") as stream:
            sector = 16
            while True:
                off = sector * SECTOR
                if off + SECTOR > self.size:
                    raise FormatError("truncated ISO before volume descriptor terminator")
                desc = _read_exact_at(stream, off, SECTOR)
                typ = desc[0]
                if desc[1:6] != b"CD001":
                    raise FormatError(f"not ISO9660 at volume descriptor sector {sector}")
                self.descriptors.append((typ, off))
                if typ == 1 and self.pvd_off is None:
                    self.pvd_off = off
                    root_len = desc[156]
                    if root_len < 34:
                        raise FormatError("invalid PVD root directory record")
                    root = desc[156 : 156 + root_len]
                    self.root_extent = _read_both32(root, 2)
                    self.root_size = _read_both32(root, 10)
                if typ == 255:
                    break
                sector += 1
        if self.pvd_off is None or self.root_extent is None or self.root_size is None:
            raise FormatError("ISO9660 primary volume descriptor not found")

    def entries(self) -> tuple[Entry, ...]:
        if self._entries is not None:
            return self._entries
        out: list[Entry] = []
        seen: set[tuple[int, int]] = set()
        with self.path.open("rb") as stream:
            self._walk_dir(stream, self.root_extent or 0, self.root_size or 0, "", out, seen)
        self._entries = tuple(out)
        return self._entries

    def _walk_dir(
        self,
        stream: BinaryIO,
        extent: int,
        size: int,
        parent: str,
        out: list[Entry],
        seen: set[tuple[int, int]],
    ) -> None:
        key = (extent, size)
        if key in seen:
            return
        seen.add(key)
        start = extent * SECTOR
        if start + size > self.size:
            raise FormatError(f"directory {parent or '/'} exceeds ISO size")
        children: list[Entry] = []
        consumed = 0
        while consumed < size:
            sector_off = start + consumed
            block = _read_exact_at(stream, sector_off, min(SECTOR, size - consumed))
            pos = 0
            while pos < len(block):
                rec_len = block[pos]
                if rec_len == 0:
                    break
                if rec_len < 34 or pos + rec_len > len(block):
                    raise FormatError(f"bad directory record at ISO offset 0x{sector_off + pos:X}")
                rec = block[pos : pos + rec_len]
                ext = _read_both32(rec, 2)
                data_len = _read_both32(rec, 10)
                flags = rec[25]
                name_len = rec[32]
                ident = rec[33 : 33 + name_len]
                if ident == b"\x00":
                    name = "."
                elif ident == b"\x01":
                    name = ".."
                else:
                    name = ident.decode("ascii", errors="strict").split(";", 1)[0]
                if name not in (".", ".."):
                    path = f"{parent.rstrip('/')}/{name}" if parent else f"/{name}"
                    entry = Entry(path, name, ext, data_len, flags, sector_off + pos)
                    out.append(entry)
                    if flags & 0x02:
                        children.append(entry)
                pos += rec_len
            consumed += len(block)
        for child in children:
            self._walk_dir(stream, child.extent, child.size, child.path, out, seen)

    def find_unique_basename(self, basename: str) -> Entry:
        matches = [
            entry
            for entry in self.entries()
            if entry.name.casefold() == basename.casefold()
        ]
        if not matches:
            raise FormatError(f"{basename}: not found in ISO")
        if len(matches) != 1:
            raise FormatError(f"{basename}: multiple matches: {[entry.path for entry in matches]}")
        return matches[0]


def patch_iso(
    source: str | Path,
    output: str | Path,
    replacements: Iterable[str | Path],
    *,
    strict_core: bool = True,
    copy_chunk_size: int = 16 * 1024 * 1024,
) -> list[PatchResult]:
    source_path = Path(source)
    output_path = Path(output)
    replacement_paths = [Path(path) for path in replacements]
    if source_path.resolve() == output_path.resolve():
        raise ValueError("output must not overwrite source")
    if source_path.stat().st_size % SECTOR:
        raise FormatError(f"source ISO length is not a multiple of {SECTOR}")
    for path in replacement_paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    iso = Iso9660(source_path)
    entries = {path.name: iso.find_unique_basename(path.name) for path in replacement_paths}

    for path in replacement_paths:
        entry = entries[path.name]
        expected = KNOWN_RETAIL_SHA256.get(path.name.upper())
        if expected and strict_core:
            got = sha256_range(source_path, entry.extent * SECTOR, entry.size)
            if got != expected:
                raise HashMismatchError(
                    f"{entry.path}: source SHA-256 {got} does not match expected retail {expected}"
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    partial.unlink(missing_ok=True)
    results: list[PatchResult] = []
    append_jobs: list[tuple[Path, Entry]] = []

    try:
        with source_path.open("rb") as src, partial.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=copy_chunk_size)

        with partial.open("r+b") as out:
            for path in replacement_paths:
                entry = entries[path.name]
                if entry.flags & 0x02:
                    raise FormatError(f"{entry.path}: replacement target is a directory")
                new_size = path.stat().st_size
                old_alloc = ((entry.size + SECTOR - 1) // SECTOR) * SECTOR
                if new_size <= old_alloc:
                    if new_size != entry.size:
                        raise FormatError(
                            f"{entry.path}: replacement is {new_size} bytes but source file is "
                            f"{entry.size}; size-changing replacements must exceed the original "
                            "allocation or be padded "
                            "to the exact recorded size"
                        )
                    out.seek(entry.extent * SECTOR)
                    with path.open("rb") as repl:
                        shutil.copyfileobj(repl, out, length=1024 * 1024)
                    if old_alloc > new_size:
                        out.write(b"\x00" * (old_alloc - new_size))
                    results.append(
                        PatchResult(
                            entry.path,
                            "in-place",
                            entry.extent,
                            entry.extent,
                            entry.size,
                            new_size,
                            sha256_path(path),
                        )
                    )
                else:
                    append_jobs.append((path, entry))

            for path, entry in append_jobs:
                out.seek(0, 2)
                end = out.tell()
                pad = (-end) % SECTOR
                if pad:
                    out.write(b"\x00" * pad)
                    end += pad
                new_extent = end // SECTOR
                new_size = path.stat().st_size
                with path.open("rb") as repl:
                    shutil.copyfileobj(repl, out, length=1024 * 1024)
                alloc = ((new_size + SECTOR - 1) // SECTOR) * SECTOR
                if alloc > new_size:
                    out.write(b"\x00" * (alloc - new_size))
                _write_both32(out, entry.record_off + 2, new_extent)
                _write_both32(out, entry.record_off + 10, new_size)
                results.append(
                    PatchResult(
                        entry.path,
                        "append+retarget",
                        entry.extent,
                        new_extent,
                        entry.size,
                        new_size,
                        sha256_path(path),
                    )
                )

            if append_jobs:
                out.seek(0, 2)
                new_sectors = out.tell() // SECTOR
                for typ, off in iso.descriptors:
                    if typ in (1, 2):
                        _write_both32(out, off + 80, new_sectors)
            out.flush()

        if output_path.exists():
            output_path.unlink()
        partial.replace(output_path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    check = Iso9660(output_path)
    for path in replacement_paths:
        entry = check.find_unique_basename(path.name)
        got = sha256_range(output_path, entry.extent * SECTOR, entry.size)
        want = sha256_path(path)
        if got != want:
            raise VerificationError(f"verification failed for {entry.path}: {got} != {want}")
    return results
