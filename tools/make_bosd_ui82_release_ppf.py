#!/usr/bin/env python3
"""Create the final BOSD UI82 PPF3 release patch by streaming two verified ISOs.

No third-party modules are required. The generated PPF is deliberately compatible
with RomPatcher.js's PPF3 reader: PPF30, 64-bit little-endian offsets, no undo data,
no block-check section, records of at most 255 bytes.

The source and target ISO size/SHA-256 values are hard-gated so a patch cannot be
accidentally produced from a different dump or development build.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys
import time
from pathlib import Path

SOURCE_SIZE = 3_080_880_128
SOURCE_SHA256 = "f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96"
TARGET_SIZE = 3_085_787_136
TARGET_SHA256 = "372e2d0d6931a95ff5d5ae82e1d352c794d47a6f69da49e7d9941010e8ab6230"
DEFAULT_NAME = "Duel_Masters_Birth_of_Super_Dragon_English_v1.0.ppf"
DESCRIPTION = "Duel Masters BOTSD English v1.0"
PPF_PAYLOAD_MAX = 0xFF
DEFAULT_COMPARE_BLOCK = 64 * 1024  # 64 KiB: fast on SSDs, keeps patch inflation low.


def fmt_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    v = float(n)
    for u in units:
        if v < 1024.0 or u == units[-1]:
            return f"{v:.2f} {u}" if u != "B" else f"{n} B"
        v /= 1024.0
    return f"{n} B"


def ppf3_header(description: str) -> bytes:
    desc = description.encode("ascii", errors="strict")
    if len(desc) > 50:
        raise ValueError("PPF description exceeds 50 ASCII bytes")
    # Matches RomPatcher.js PPF.export(): 'PPF30', version byte 2,
    # 50-byte NUL-padded description, then imageType/blockCheck/undo/dummy.
    return b"PPF30" + bytes([2]) + desc.ljust(50, b"\0") + bytes([0, 0, 0, 0])


def write_record(out, offset: int, payload: bytes) -> None:
    if not (1 <= len(payload) <= PPF_PAYLOAD_MAX):
        raise ValueError(f"invalid PPF record length: {len(payload)}")
    out.write(struct.pack("<Q", offset))
    out.write(bytes([len(payload)]))
    out.write(payload)


def create_patch(source: Path, target: Path, output: Path, block_size: int) -> dict:
    ss = source.stat().st_size
    ts = target.stat().st_size
    if ss != SOURCE_SIZE:
        raise SystemExit(f"ERROR: source size {ss} does not match required {SOURCE_SIZE}")
    if ts != TARGET_SIZE:
        raise SystemExit(f"ERROR: target size {ts} does not match required {TARGET_SIZE}")
    if block_size < 4096 or block_size % 255 == 0:
        # The modulo restriction is not technically required; it just avoids a
        # pathological repeated boundary pattern and catches accidental 255-byte use.
        if block_size < 4096:
            raise SystemExit("ERROR: compare block must be at least 4096 bytes")

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    if partial.exists():
        partial.unlink()

    h_src = hashlib.sha256()
    h_dst = hashlib.sha256()
    record_count = 0
    changed_blocks = 0
    payload_bytes = 0
    offset = 0
    started = time.time()
    last_status = started

    try:
        with source.open("rb") as fs, target.open("rb") as ft, partial.open("wb") as out:
            out.write(ppf3_header(DESCRIPTION))

            while offset < TARGET_SIZE:
                want = min(block_size, TARGET_SIZE - offset)
                dst = ft.read(want)
                if len(dst) != want:
                    raise IOError(f"short read from target at 0x{offset:X}")
                src = fs.read(min(want, max(0, SOURCE_SIZE - offset))) if offset < SOURCE_SIZE else b""
                if offset < SOURCE_SIZE and len(src) != min(want, SOURCE_SIZE - offset):
                    raise IOError(f"short read from source at 0x{offset:X}")

                h_dst.update(dst)
                if src:
                    h_src.update(src)

                if src != dst:
                    changed_blocks += 1
                    # Write the entire changed compare block. This intentionally trades
                    # a little patch size for very fast creation and avoids byte-at-a-time
                    # scanning of multi-gigabyte ISOs. PPF writes are absolute, so equal
                    # bytes inside the block are harmlessly rewritten with identical data.
                    local = 0
                    while local < len(dst):
                        piece = dst[local:local + PPF_PAYLOAD_MAX]
                        write_record(out, offset + local, piece)
                        record_count += 1
                        payload_bytes += len(piece)
                        local += len(piece)

                offset += want
                now = time.time()
                if now - last_status >= 5.0:
                    pct = offset * 100.0 / TARGET_SIZE
                    print(f"  {pct:6.2f}%  {fmt_bytes(offset)} / {fmt_bytes(TARGET_SIZE)}", flush=True)
                    last_status = now

            # Source is smaller than target in UI82. Hash any source tail only if a
            # future gated build ever changes that relationship.
            while fs.tell() < SOURCE_SIZE:
                src = fs.read(min(block_size, SOURCE_SIZE - fs.tell()))
                if not src:
                    raise IOError("unexpected EOF while finishing source hash")
                h_src.update(src)

        src_sha = h_src.hexdigest()
        dst_sha = h_dst.hexdigest()
        if src_sha != SOURCE_SHA256:
            partial.unlink(missing_ok=True)
            raise SystemExit(
                "ERROR: source SHA-256 mismatch\n"
                f"  got:      {src_sha}\n"
                f"  required: {SOURCE_SHA256}\n"
                "Use the untouched Japanese SLPM-65882 retail ISO."
            )
        if dst_sha != TARGET_SHA256:
            partial.unlink(missing_ok=True)
            raise SystemExit(
                "ERROR: UI82 target SHA-256 mismatch\n"
                f"  got:      {dst_sha}\n"
                f"  required: {TARGET_SHA256}\n"
                "Use the exact DM_BOTSD_UI82.iso that passed the runtime canary."
            )

        if output.exists():
            output.unlink()
        partial.rename(output)
        patch_sha = hashlib.sha256()
        with output.open("rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                patch_sha.update(chunk)

        # Structural re-read: validate header, record ordering/lengths, and prove the
        # last record reaches the exact UI82 target EOF. This mirrors the parts of the
        # RomPatcher.js PPF3 parser that matter for this patch.
        max_end = 0
        parsed_records = 0
        prev_off = -1
        with output.open("rb") as f:
            header = f.read(60)
            if len(header) != 60 or header[:6] != b"PPF30\x02":
                raise RuntimeError("internal PPF header verification failed")
            while True:
                rec = f.read(9)
                if not rec:
                    break
                if len(rec) != 9:
                    raise RuntimeError("truncated PPF record header")
                rec_off = struct.unpack_from("<Q", rec, 0)[0]
                rec_len = rec[8]
                if rec_len == 0:
                    raise RuntimeError("zero-length PPF record")
                data = f.read(rec_len)
                if len(data) != rec_len:
                    raise RuntimeError("truncated PPF record payload")
                if rec_off < prev_off:
                    raise RuntimeError("PPF records are not ordered")
                prev_off = rec_off
                parsed_records += 1
                max_end = max(max_end, rec_off + rec_len)
        if parsed_records != record_count:
            raise RuntimeError("PPF record count mismatch after re-read")
        if max_end != TARGET_SIZE:
            raise RuntimeError(
                f"PPF EOF coverage mismatch: max record end {max_end}, expected {TARGET_SIZE}"
            )

        return {
            "source_size": ss,
            "source_sha256": src_sha,
            "target_size": ts,
            "target_sha256": dst_sha,
            "patch_size": output.stat().st_size,
            "patch_sha256": patch_sha.hexdigest(),
            "compare_block": block_size,
            "changed_blocks": changed_blocks,
            "record_count": record_count,
            "payload_bytes": payload_bytes,
            "seconds": time.time() - started,
            "max_record_end": max_end,
        }
    except BaseException:
        if partial.exists():
            partial.unlink()
        raise


def write_report(path: Path, source: Path, target: Path, output: Path, info: dict) -> None:
    text = f"""Duel Masters: Birth of Super Dragon — English v1.0 PPF3 build report

Source ISO: {source}
Source size: {info['source_size']} bytes
Source SHA-256: {info['source_sha256']}

UI82 target ISO: {target}
Target size: {info['target_size']} bytes
Target SHA-256: {info['target_sha256']}

Patch: {output}
Patch format: PPF 3.0 (PPF30; 64-bit offsets; no undo data; no block-check section)
Patch size: {info['patch_size']} bytes
Patch SHA-256: {info['patch_sha256']}
Compare block: {info['compare_block']} bytes
Changed compare blocks: {info['changed_blocks']}
PPF records: {info['record_count']}
PPF payload bytes: {info['payload_bytes']}
Maximum record end: {info['max_record_end']} bytes
Generation time: {info['seconds']:.1f} seconds

Compatibility target: RomPatcher.js PPF3 parser/application logic.
The final record coverage reaches the exact expected target ISO size.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create the browser-friendly PPF3 release patch from the exact BOSD retail and UI82 ISOs."
    )
    ap.add_argument("source_iso", type=Path, help="untouched Japanese retail original.iso")
    ap.add_argument("target_iso", type=Path, help="tested patched/DM_BOTSD_UI82.iso")
    ap.add_argument("-o", "--output", type=Path, help="output .ppf path")
    ap.add_argument(
        "--block-size", type=int, default=DEFAULT_COMPARE_BLOCK,
        help=f"comparison granularity in bytes (default {DEFAULT_COMPARE_BLOCK})"
    )
    args = ap.parse_args()

    source = args.source_iso.expanduser().resolve()
    target = args.target_iso.expanduser().resolve()
    if not source.is_file():
        ap.error(f"source ISO not found: {source}")
    if not target.is_file():
        ap.error(f"target ISO not found: {target}")
    output = (args.output.expanduser().resolve() if args.output else target.parent / DEFAULT_NAME)
    if output.suffix.lower() != ".ppf":
        output = output.with_suffix(".ppf")
    report = output.with_suffix(".txt")

    print("BOSD UI82 final PPF3 release builder")
    print(f"Source: {source}")
    print(f"Target: {target}")
    print(f"Output: {output}")
    print("Scanning and hashing both ISOs while creating the patch...")

    info = create_patch(source, target, output, args.block_size)
    write_report(report, source, target, output, info)

    print("\nPASS — release PPF created from the exact tested ISOs.")
    print(f"Patch: {output}")
    print(f"Patch size: {fmt_bytes(info['patch_size'])}")
    print(f"Patch SHA-256: {info['patch_sha256']}")
    print(f"Report: {report}")
    print("\nUpload the .ppf and its .txt report back to this chat for final independent packaging/QA.")


if __name__ == "__main__":
    main()
