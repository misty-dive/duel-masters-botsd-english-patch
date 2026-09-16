#!/usr/bin/env python3
"""
External master-card-text builder for:
Duel Masters: Birth of the Super Dragon (SLPM-65882, v1.03)

Purpose
-------
The retail game has two card-text systems:

1) COMMON/LIST_1.BIN
   1682 meaningful display-text entries (plus an unused EOF sentinel in retail).
   Entries 0..1676 correspond to master text IDs 466..2142 (DM-06..DM-11).
   Entries 1677..1681 are test strings.

2) An executable-resident master table
   2376 text pointers used by the 673-card retail database.

This tool creates one enlarged LIST_1.BIN containing:
    [1682 original/display pointers]
    [2376 master-card-text pointers]
    [deduplicated strings]

It also applies a tiny same-size patch to SLPM_658.82:
- relocate all 4058 pointers instead of 1682;
- after LIST_1 loads, point the game's existing master-card-text object at
  the appended 2376-pointer table.

That removes the fixed-size executable string-pool constraint while preserving
the original LIST_1 display layer.

No game data is embedded in this tool. It only transforms files supplied by
the user from their own dump.

Commands
--------
Build:
  python bosd_cardtext_externalizer.py build \
      SLPM_658.82 LIST_1.BIN \
      bosd_master_text_translation.csv bosd_list_display_translation.csv \
      OUT_SLPM_658.82 OUT_LIST_1.BIN

Check source files / patch assumptions:
  python bosd_cardtext_externalizer.py check SLPM_658.82 LIST_1.BIN

Translation CSV behavior
------------------------
If `translation` is blank, the original Japanese source is retained.
If `translation` is exactly `<EMPTY>`, the translated string is intentionally zero-length.
Unicode `Ü` is mapped to reserved internal byte 0x7E
use this only with the FONTLINK Ü patch.
The `source_japanese` field is checked before building to guard against using
the CSV with the wrong game revision.

Text is encoded as CP932. Use ASCII apostrophes/quotes/hyphens in English.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import struct
from pathlib import Path

EXPECTED_EXE_SHA256 = "846ed10f8247dc5fe6d9f41ccf11179bbbe3a9c9fde5991c8ebcc271dc38b11d"
EXPECTED_LIST1_SHA256 = "8e07816855adf656a95bed7d86d2434ef2842204b44237848204fb450772ebcf"

MASTER_COUNT = 2376
DISPLAY_COUNT = 1682
TOTAL_POINTERS = DISPLAY_COUNT + MASTER_COUNT
MASTER_POINTER_BYTE_OFFSET = DISPLAY_COUNT * 4  # 0x1A48

LOAD_VA_DELTA = 0x000FF000
MASTER_TABLE_VA = 0x00444268

# Executable patch sites.
LOOP_COUNT_VA = 0x002DE4C8
LOADER_RETURN_VA = 0x002DE4DC
CODE_CAVE_VA = 0x0041285C

# Global offsets from $gp recovered from retail executable.
TEXT_RESOURCE_GLOBAL_GP_OFF = 0x2038
CARD_TEXT_OBJECT_GLOBAL_GP_OFF = 0x2818

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def va_to_off(va: int) -> int:
    return va - LOAD_VA_DELTA

def read_cstr(blob: bytes, off: int) -> str:
    if not (0 <= off < len(blob)):
        raise ValueError(f"string offset out of range: {off:#x}")
    end = blob.find(b"\x00", off)
    if end < 0:
        raise ValueError(f"unterminated string at {off:#x}")
    return blob[off:end].decode("cp932", errors="strict")

def parse_retail_list(path: Path) -> list[str]:
    raw = path.read_bytes()
    if sha256(raw) != EXPECTED_LIST1_SHA256:
        raise ValueError(
            f"{path}: unexpected SHA-256\n"
            f" expected {EXPECTED_LIST1_SHA256}\n"
            f" actual   {sha256(raw)}"
        )
    first = struct.unpack_from("<I", raw, 0)[0]
    if first % 4:
        raise ValueError("LIST_1 first pointer is not 4-byte aligned")
    count = first // 4
    if count != 1683:
        raise ValueError(f"expected retail LIST_1 to contain 1683 pointers, found {count}")
    ptrs = list(struct.unpack_from("<" + "I"*count, raw, 0))
    texts = []
    for i, p in enumerate(ptrs):
        q = ptrs[i+1] if i+1<count else len(raw)
        slot = raw[p:q]
        if i == count - 1 and p == len(raw):
            texts.append("")
            continue
        nul = slot.find(b"\x00")
        if nul < 0:
            raise ValueError(f"LIST_1 entry {i} has no NUL terminator")
        texts.append(slot[:nul].decode("cp932", errors="strict"))
    return texts

def parse_master_text(exe: bytes) -> list[str]:
    p = va_to_off(MASTER_TABLE_VA)
    if p < 0 or p + MASTER_COUNT*4 > len(exe):
        raise ValueError("master pointer table is outside executable")
    ptrs = struct.unpack_from("<" + "I"*MASTER_COUNT, exe, p)
    out = []
    for i, va in enumerate(ptrs):
        if va == 0:
            out.append("")
        else:
            out.append(read_cstr(exe, va_to_off(va)))
    return out

def load_translation_csv(path: Path, id_column: str, expected_sources: list[str]) -> list[str]:
    translations = list(expected_sources)
    seen = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        required = {id_column, "source_japanese", "translation"}
        if not required.issubset(r.fieldnames or []):
            raise ValueError(f"{path}: CSV requires columns {sorted(required)}")
        for row in r:
            idx = int(row[id_column])
            if not (0 <= idx < len(expected_sources)):
                raise ValueError(f"{path}: {id_column} {idx} out of range")
            if idx in seen:
                raise ValueError(f"{path}: duplicate {id_column} {idx}")
            seen.add(idx)
            if row["source_japanese"] != expected_sources[idx]:
                raise ValueError(
                    f"{path}: source mismatch at {id_column} {idx}\n"
                    f" CSV : {row['source_japanese']!r}\n"
                    f" game: {expected_sources[idx]!r}"
                )
            if row["translation"] == "<EMPTY>":
                translations[idx] = ""
            elif row["translation"] != "":
                translations[idx] = row["translation"]

    # Missing rows are allowed only because it is useful for tiny POC CSVs;
    # omitted entries simply retain Japanese.
    return translations

def encode_cp932(text: str, label: str) -> bytes:
    if "~" in text:
        raise ValueError(f"{label}: literal '~' is reserved for the English-patch Ü glyph")
    mapped = text.replace("Ü", "~")
    try:
        return mapped.encode("cp932", errors="strict")
    except UnicodeEncodeError as e:
        bad = mapped[e.start:e.end]
        raise ValueError(
            f"{label}: text contains character(s) not representable by the patched game font: {bad!r}."
        ) from e

def decode_game_text(raw: bytes) -> str:
    return raw.decode("cp932", errors="strict").replace("~", "Ü")

def build_combined_list(display_texts: list[str], master_texts: list[str]) -> bytes:
    if len(display_texts) != DISPLAY_COUNT:
        raise ValueError("wrong display-text count")
    if len(master_texts) != MASTER_COUNT:
        raise ValueError("wrong master-text count")

    all_texts = display_texts + master_texts
    table_bytes = TOTAL_POINTERS * 4

    # Deduplicate byte-identical output strings. This is safe because all entries
    # are immutable C strings; it also keeps the enlarged resource compact.
    offsets: dict[bytes, int] = {}
    pointers = []
    body = bytearray()
    for i, text in enumerate(all_texts):
        raw = encode_cp932(text, f"combined text {i}") + b"\x00"
        if raw not in offsets:
            offsets[raw] = table_bytes + len(body)
            body += raw
        pointers.append(offsets[raw])

    out = bytearray(struct.pack("<" + "I"*TOTAL_POINTERS, *pointers))
    out += body
    return bytes(out)

def encode_i(op: int, rs: int, rt: int, imm: int) -> int:
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)

def encode_j(op: int, addr: int) -> int:
    return (op << 26) | ((addr >> 2) & 0x03FFFFFF)

def encode_r(rs: int, rt: int, rd: int, shamt: int, funct: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct

def check_patch_sites(exe: bytes):
    expected = {
        LOOP_COUNT_VA: 0x2C830692,     # sltiu $3,$4,0x692
        LOADER_RETURN_VA: 0x03E00008,  # jr $ra
    }
    for va, word in expected.items():
        actual = struct.unpack_from("<I", exe, va_to_off(va))[0]
        if actual != word:
            raise ValueError(
                f"unexpected instruction at {va:#x}: {actual:#010x}, "
                f"expected {word:#010x}"
            )

    cave = exe[va_to_off(CODE_CAVE_VA):va_to_off(CODE_CAVE_VA)+20]
    if cave != b"\x00" * 20:
        raise ValueError(
            f"expected 20-byte zero code cave at {CODE_CAVE_VA:#x}; "
            f"found {cave.hex()}"
        )

def patch_executable(original: bytes) -> bytes:
    if sha256(original) != EXPECTED_EXE_SHA256:
        raise ValueError(
            "unexpected executable SHA-256\n"
            f" expected {EXPECTED_EXE_SHA256}\n"
            f" actual   {sha256(original)}"
        )
    check_patch_sites(original)
    exe = bytearray(original)

    # Relocate all 4058 pointers in the combined LIST.
    struct.pack_into(
        "<I", exe, va_to_off(LOOP_COUNT_VA),
        encode_i(0x0B, 4, 3, TOTAL_POINTERS)  # sltiu $v1,$a0,0xFDA
    )

    # Replace loader return with a jump into an unused alignment cave.
    struct.pack_into(
        "<I", exe, va_to_off(LOADER_RETURN_VA),
        encode_j(0x02, CODE_CAVE_VA)
    )

    cave_words = [
        # lw $t0, 0x2818($gp)  ; card-text singleton pointer
        encode_i(0x23, 28, 8, CARD_TEXT_OBJECT_GLOBAL_GP_OFF),
        # lw $t1, 0x2038($gp)  ; relocated LIST_1 base
        encode_i(0x23, 28, 9, TEXT_RESOURCE_GLOBAL_GP_OFF),
        # addiu $t1,$t1,0x1A48 ; appended master pointer table
        encode_i(0x09, 9, 9, MASTER_POINTER_BYTE_OFFSET),
        # jr $ra
        encode_r(31, 0, 0, 0, 8),
        # sw $t1,0x0C($t0)     ; delay slot: replace embedded master-table ptr
        encode_i(0x2B, 8, 9, 0x000C),
    ]
    for i, word in enumerate(cave_words):
        struct.pack_into("<I", exe, va_to_off(CODE_CAVE_VA) + i*4, word)

    return bytes(exe)

def parse_combined_relative(raw: bytes):
    if len(raw) < TOTAL_POINTERS*4:
        raise ValueError("combined LIST is too small")
    ptrs = struct.unpack_from("<" + "I"*TOTAL_POINTERS, raw, 0)
    out = []
    for i,p in enumerate(ptrs):
        if not (TOTAL_POINTERS*4 <= p < len(raw)):
            raise ValueError(f"combined pointer {i} is out of range: {p:#x}")
        end = raw.find(b"\x00", p)
        if end < 0:
            raise ValueError(f"combined pointer {i} has no NUL terminator")
        out.append(decode_game_text(raw[p:end]))
    return out[:DISPLAY_COUNT], out[DISPLAY_COUNT:]

def build(args):
    exe_raw = args.exe.read_bytes()
    if sha256(exe_raw) != EXPECTED_EXE_SHA256:
        raise ValueError("executable hash does not match SLPM-65882 v1.03")
    retail_display_all = parse_retail_list(args.list1)
    retail_display = retail_display_all[:DISPLAY_COUNT]  # omit retail EOF sentinel
    master = parse_master_text(exe_raw)

    display_out = load_translation_csv(
        args.display_csv, "list_index", retail_display
    )
    master_out = load_translation_csv(
        args.master_csv, "master_text_id", master
    )

    combined = build_combined_list(display_out, master_out)
    patched_exe = patch_executable(exe_raw)

    # Strong offline validation: parse the produced relative pointers and prove
    # every text entry matches the requested output before writing.
    dcheck, mcheck = parse_combined_relative(combined)
    if dcheck != display_out:
        raise RuntimeError("combined LIST display-table self-check failed")
    if mcheck != master_out:
        raise RuntimeError("combined LIST master-table self-check failed")

    args.out_exe.write_bytes(patched_exe)
    args.out_list1.write_bytes(combined)

    print(f"Patched executable: {args.out_exe}")
    print(f"  size: {len(patched_exe)} bytes (unchanged)")
    print(f"  SHA-256: {sha256(patched_exe)}")
    print(f"Combined LIST_1: {args.out_list1}")
    print(f"  pointers: {TOTAL_POINTERS} ({DISPLAY_COUNT} display + {MASTER_COUNT} master)")
    print(f"  size: {len(combined)} bytes")
    print(f"  SHA-256: {sha256(combined)}")
    print("Offline pointer/text validation: OK")

def check(args):
    exe_raw = args.exe.read_bytes()
    list_raw = args.list1.read_bytes()
    print(f"Executable SHA-256: {sha256(exe_raw)}")
    print(f"LIST_1 SHA-256:     {sha256(list_raw)}")
    parse_retail_list(args.list1)
    parse_master_text(exe_raw)
    check_patch_sites(exe_raw)
    print(f"Retail LIST meaningful entries: {DISPLAY_COUNT}")
    print(f"Embedded master text entries:   {MASTER_COUNT}")
    print(f"Combined relocation count:      {TOTAL_POINTERS} (0x{TOTAL_POINTERS:X})")
    print(f"Appended master table offset:   0x{MASTER_POINTER_BYTE_OFFSET:X}")
    print("Source/patch-site validation: OK")

def main():
    """Run the command-line patch/verification workflow."""
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("check")
    p.add_argument("exe", type=Path)
    p.add_argument("list1", type=Path)

    p = sp.add_parser("build")
    p.add_argument("exe", type=Path)
    p.add_argument("list1", type=Path)
    p.add_argument("master_csv", type=Path)
    p.add_argument("display_csv", type=Path)
    p.add_argument("out_exe", type=Path)
    p.add_argument("out_list1", type=Path)

    args = ap.parse_args()
    if args.cmd == "check":
        check(args)
    else:
        build(args)

if __name__ == "__main__":
    main()
