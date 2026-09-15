#!/usr/bin/env python3
"""BOSD packed UI .DAT archive extractor/repacker.

Reverse-engineered for Duel Masters: Birth of the Super Dragon (SLPM-65882).
Archives contain fixed 0x114-byte FILE records and LZSS-compressed TGA members.

This tool is intended for localization/patch generation. It does not contain retail assets.
"""
from __future__ import annotations
import argparse, struct, sys
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict, deque

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


def align_up(n: int, a: int = ALIGN) -> int:
    return (n + a - 1) // a * a


def lzss_decompress(stream: bytes, expected_size: int) -> bytes:
    """Decode the game's 4 KiB-window LZSS stream."""
    ring = bytearray(0x1000)
    r = 0xFEE
    src = 0
    out = bytearray()
    flags = 0
    while src < len(stream):
        flags >>= 1
        if not (flags & 0x100):
            if src >= len(stream):
                break
            flags = stream[src] | 0xFF00
            src += 1
        if flags & 1:
            if src >= len(stream):
                break
            c = stream[src]
            src += 1
            out.append(c)
            ring[r] = c
            r = (r + 1) & 0xFFF
        else:
            if src + 1 >= len(stream):
                break
            b1 = stream[src]
            b2 = stream[src + 1]
            src += 2
            off = b1 | ((b2 & 0xF0) << 4)
            count = (b2 & 0x0F) + 3
            for k in range(count):
                c = ring[(off + k) & 0xFFF]
                out.append(c)
                ring[r] = c
                r = (r + 1) & 0xFFF
    if len(out) != expected_size:
        raise ValueError(f"LZSS output length mismatch: expected {expected_size}, got {len(out)}")
    return bytes(out)


def _candidate_match(data: bytes, pos: int, q: int, max_len: int = 18) -> int:
    # Deliberately avoid overlap matches; valid but not required for good compression here.
    lim = min(max_len, len(data) - pos, pos - q)
    n = 0
    while n < lim and data[q+n] == data[pos+n]:
        n += 1
    return n


def lzss_compress(data: bytes, max_candidates: int = 96) -> bytes:
    """Encode a valid stream for the game's decoder.

    Uses a bounded dictionary search. Compression ratio is not required to match retail;
    the localization ISO patcher can append enlarged archives without relocating retail files.
    """
    # key -> recent absolute source positions
    recent: dict[bytes, deque[int]] = defaultdict(deque)
    out = bytearray()
    pos = 0

    def add_pos(p: int):
        if p + 2 >= len(data):
            return
        key = data[p:p+3]
        dq = recent[key]
        dq.append(p)
        cutoff = p - 0x1000
        while dq and dq[0] < cutoff:
            dq.popleft()
        # Keep memory/search bounded; newest matches are usually best.
        while len(dq) > 256:
            dq.popleft()

    while pos < len(data):
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if pos >= len(data):
                break
            best_len = 0
            best_q = -1
            if pos + 2 < len(data):
                key = data[pos:pos+3]
                dq = recent.get(key)
                if dq:
                    # Search newest candidates first.
                    for q in reversed(dq):
                        if pos - q > 0x1000:
                            break
                        n = _candidate_match(data, pos, q)
                        if n > best_len:
                            best_len, best_q = n, q
                            if n == 18:
                                break
                        max_candidates -= 1
                        if max_candidates <= 0:
                            break
                    # reset per token
                    max_candidates = 96
            if best_len >= 3:
                ring_off = (0xFEE + best_q) & 0xFFF
                length_code = best_len - 3
                out.append(ring_off & 0xFF)
                out.append(((ring_off >> 4) & 0xF0) | (length_code & 0x0F))
                old = pos
                pos += best_len
                for p in range(old, pos):
                    add_pos(p)
            else:
                flags |= (1 << bit)
                out.append(data[pos])
                add_pos(pos)
                pos += 1
        out[flag_pos] = flags
    return bytes(out)


def decode_member_blob(blob: bytes, compression: int) -> bytes:
    if compression == 0:
        return blob
    if compression != 1:
        raise ValueError(f"unsupported compression flag {compression}")
    if len(blob) < 4:
        raise ValueError("compressed member is too short")
    usize = struct.unpack_from('<I', blob, 0)[0]
    return lzss_decompress(blob[4:], usize)


def encode_member_blob(raw: bytes, compression: int = 1) -> bytes:
    if compression == 0:
        return raw
    if compression != 1:
        raise ValueError(f"unsupported compression flag {compression}")
    comp = lzss_compress(raw)
    # Self-verify every generated member.
    test = lzss_decompress(comp, len(raw))
    if test != raw:
        raise RuntimeError("internal LZSS round-trip verification failed")
    return struct.pack('<I', len(raw)) + comp


def parse_archive(path: Path, decompress: bool = False) -> Archive:
    raw = path.read_bytes()
    if len(raw) < 0x20:
        raise ValueError(f"{path}: too small")
    declared = struct.unpack_from('<I', raw, 0)[0]
    if declared != len(raw):
        raise ValueError(f"{path}: declared size {declared} != actual {len(raw)}")
    if raw[4:8] != b'ALL ' or raw[12:16] != b'HDR ':
        raise ValueError(f"{path}: unrecognized archive header")
    header_size = struct.unpack_from('<I', raw, 8)[0]
    rec_size = struct.unpack_from('<I', raw, 16)[0]
    if rec_size != REC_SIZE:
        raise ValueError(f"{path}: unexpected record size 0x{rec_size:X}")
    data_start = 8 + header_size
    if data_start > len(raw):
        raise ValueError(f"{path}: data start outside file")

    members = []
    off = 20
    idx = 0
    while off + REC_SIZE <= data_start:
        rec = raw[off:off+REC_SIZE]
        if rec[:4] != b'FILE':
            # Remaining header area is padding.
            break
        name_bytes = rec[4:260].split(b'\0', 1)[0]
        name = name_bytes.decode('ascii', errors='strict')
        data_rel, stored_size, compression, next_size = struct.unpack_from('<IIII', rec, 260)
        start = data_start + data_rel
        end = start + stored_size
        if start < data_start or end > len(raw):
            raise ValueError(f"{path}: member {name} range outside archive")
        blob = raw[start:end]
        m = Member(idx, name, off, data_rel, stored_size, compression, next_size, blob)
        if decompress:
            m.raw = decode_member_blob(blob, compression)
        members.append(m)
        idx += 1
        if next_size == 0:
            break
        if next_size != REC_SIZE:
            raise ValueError(f"{path}: member {name} has unexpected next record size 0x{next_size:X}")
        off += next_size
    if not members:
        raise ValueError(f"{path}: no FILE records found")
    return Archive(path, raw, header_size, data_start, members)


def rebuild_archive(arc: Archive, replacements: dict[str, bytes], output: Path,
                    compression: int = 1, pad_to: int | None = None) -> None:
    # Keep the retail header bytes verbatim except for mutable record fields.
    header = bytearray(arc.raw[:arc.data_start])
    payload = bytearray()
    member_blobs: list[tuple[Member, bytes, int]] = []

    for m in arc.members:
        raw = replacements.get(m.name)
        if raw is None:
            # Decode/re-encode unchanged members so record offsets can be rebuilt consistently.
            raw = decode_member_blob(m.blob, m.compression)
        blob = encode_member_blob(raw, compression)
        rel = align_up(len(payload), ALIGN)
        if rel > len(payload):
            payload += b'\0' * (rel - len(payload))
        payload += blob
        member_blobs.append((m, blob, rel))

    total = arc.data_start + len(payload)
    total_aligned = align_up(total, ALIGN)
    payload += b'\0' * (total_aligned - total)
    total = arc.data_start + len(payload)
    if pad_to is not None:
        if total > pad_to:
            raise ValueError(f"rebuilt archive is {total} bytes, cannot pad down to {pad_to}")
        payload += b'\0' * (pad_to - total)
        total = pad_to

    for m, blob, rel in member_blobs:
        struct.pack_into('<III', header, m.record_off + 260, rel, len(blob), compression)
        # +272 next record size is preserved from retail header.
    struct.pack_into('<I', header, 0, total)
    out = bytes(header) + bytes(payload)
    if len(out) != total:
        raise RuntimeError("archive size accounting error")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(out)

    # Full verification: parse and compare every member's decompressed bytes.
    chk = parse_archive(output, decompress=True)
    if len(chk.members) != len(arc.members):
        raise RuntimeError("member count changed after rebuild")
    for orig, got in zip(arc.members, chk.members):
        if orig.name != got.name:
            raise RuntimeError("member order/name changed after rebuild")
        expected = replacements.get(orig.name)
        if expected is None:
            expected = decode_member_blob(orig.blob, orig.compression)
        if got.raw != expected:
            raise RuntimeError(f"verification failed for {orig.name}")


def cmd_list(a):
    arc = parse_archive(a.archive, decompress=True)
    print(f"{a.archive}: {len(arc.raw)} bytes; data_start=0x{arc.data_start:X}; {len(arc.members)} members")
    for m in arc.members:
        print(f"{m.index:02d} {m.name:40s} rel=0x{m.data_rel:06X} stored={m.stored_size:7d} comp={m.compression} raw={len(m.raw or b''):7d}")


def cmd_extract(a):
    arc = parse_archive(a.archive, decompress=True)
    a.output.mkdir(parents=True, exist_ok=True)
    for m in arc.members:
        suffix = '.tga' if m.name.upper().endswith('_TGA') else '.bin'
        p = a.output / (m.name + suffix)
        p.write_bytes(m.raw or b'')
        print(p)


def cmd_repack(a):
    arc = parse_archive(a.archive)
    repl = {}
    if a.input_dir:
        for m in arc.members:
            for ext in ('.tga', '.bin', ''):
                p = a.input_dir / (m.name + ext)
                if p.is_file():
                    repl[m.name] = p.read_bytes()
                    break
    rebuild_archive(arc, repl, a.output, compression=1, pad_to=a.pad_to)
    print(f"Wrote {a.output} ({a.output.stat().st_size} bytes); verified {len(arc.members)} members")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list'); p.add_argument('archive', type=Path); p.set_defaults(func=cmd_list)
    p = sub.add_parser('extract'); p.add_argument('archive', type=Path); p.add_argument('output', type=Path); p.set_defaults(func=cmd_extract)
    p = sub.add_parser('repack'); p.add_argument('archive', type=Path); p.add_argument('input_dir', type=Path, nargs='?'); p.add_argument('output', type=Path); p.add_argument('--pad-to', type=lambda x:int(x,0)); p.set_defaults(func=cmd_repack)
    a = ap.parse_args(); a.func(a)

if __name__ == '__main__':
    main()
