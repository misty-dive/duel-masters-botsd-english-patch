from __future__ import annotations

import csv
import struct
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .errors import FormatError, HashMismatchError, VerificationError
from .hashing import sha256_bytes
from .manifest import BASELINE, CARD_TEXT_LAYOUT, RETAIL_SHA256

DISPLAY_COUNT = BASELINE.display_text_count
MASTER_COUNT = BASELINE.master_text_count
TOTAL_POINTERS = DISPLAY_COUNT + MASTER_COUNT
MASTER_POINTER_BYTE_OFFSET = DISPLAY_COUNT * 4

LOAD_VA_DELTA = CARD_TEXT_LAYOUT.load_va_delta
MASTER_TABLE_VA = CARD_TEXT_LAYOUT.master_table_va
LOOP_COUNT_VA = CARD_TEXT_LAYOUT.loop_count_va
LOADER_RETURN_VA = CARD_TEXT_LAYOUT.loader_return_va
CODE_CAVE_VA = CARD_TEXT_LAYOUT.code_cave_va
TEXT_RESOURCE_GLOBAL_GP_OFF = CARD_TEXT_LAYOUT.text_resource_global_gp_offset
CARD_TEXT_OBJECT_GLOBAL_GP_OFF = CARD_TEXT_LAYOUT.card_text_object_global_gp_offset


@dataclass(frozen=True)
class ExternalizedCardText:
    executable: bytes
    combined_list: bytes
    display_texts: tuple[str, ...]
    master_texts: tuple[str, ...]


def va_to_off(va: int) -> int:
    return va - LOAD_VA_DELTA


def read_cstr(blob: bytes, offset: int) -> str:
    if not 0 <= offset < len(blob):
        raise FormatError(f"string offset outside blob: 0x{offset:X}")
    end = blob.find(b"\0", offset)
    if end < 0:
        raise FormatError(f"unterminated string at 0x{offset:X}")
    return blob[offset:end].decode("cp932", errors="strict")


def parse_retail_list_bytes(raw: bytes) -> list[str]:
    if len(raw) < 4:
        raise FormatError("LIST_1 is too small")
    first = struct.unpack_from("<I", raw, 0)[0]
    if first % 4:
        raise FormatError("LIST_1 first pointer is not 4-byte aligned")
    count = first // 4
    # Retail has one EOF sentinel after the 1,682 meaningful display entries.
    if count != CARD_TEXT_LAYOUT.retail_list_pointer_count:
        raise FormatError(
            f"expected retail LIST_1 to contain {CARD_TEXT_LAYOUT.retail_list_pointer_count} pointers, found {count}"
        )
    ptrs = struct.unpack_from("<" + "I" * count, raw, 0)
    texts: list[str] = []
    for index, pointer in enumerate(ptrs):
        next_pointer = ptrs[index + 1] if index + 1 < count else len(raw)
        if not 0 <= pointer <= next_pointer <= len(raw):
            raise FormatError(f"LIST_1 pointer range invalid at entry {index}")
        if index == count - 1 and pointer == len(raw):
            texts.append("")
            continue
        slot = raw[pointer:next_pointer]
        nul = slot.find(b"\0")
        if nul < 0:
            raise FormatError(f"LIST_1 entry {index} has no NUL terminator")
        texts.append(slot[:nul].decode("cp932", errors="strict"))
    return texts


def parse_retail_list(path: str | Path, *, verify_hash: bool = True) -> list[str]:
    raw = Path(path).read_bytes()
    if verify_hash:
        expected = RETAIL_SHA256["LIST_1.BIN"]
        got = sha256_bytes(raw)
        if got != expected:
            raise HashMismatchError(f"LIST_1.BIN SHA-256 {got} != retail {expected}")
    return parse_retail_list_bytes(raw)


def parse_master_text(executable: bytes) -> list[str]:
    table = va_to_off(MASTER_TABLE_VA)
    if table < 0 or table + MASTER_COUNT * 4 > len(executable):
        raise FormatError("master pointer table lies outside executable")
    ptrs = struct.unpack_from("<" + "I" * MASTER_COUNT, executable, table)
    output: list[str] = []
    for pointer in ptrs:
        if pointer == 0:
            output.append("")
        else:
            output.append(read_cstr(executable, va_to_off(pointer)))
    return output


def load_translation_csv(
    path: str | Path,
    id_column: str,
    expected_sources: list[str],
) -> list[str]:
    translations = list(expected_sources)
    seen: set[int] = set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {id_column, "source_japanese", "translation"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: CSV requires columns {sorted(required)}")
        for row in reader:
            index = int(row[id_column])
            if not 0 <= index < len(expected_sources):
                raise ValueError(f"{path}: {id_column} {index} out of range")
            if index in seen:
                raise ValueError(f"{path}: duplicate {id_column} {index}")
            seen.add(index)
            if row["source_japanese"] != expected_sources[index]:
                raise VerificationError(
                    f"{path}: source mismatch at {id_column} {index}: "
                    f"{row['source_japanese']!r} != {expected_sources[index]!r}"
                )
            translation = row["translation"]
            if translation == "<EMPTY>":
                translations[index] = ""
            elif translation:
                translations[index] = translation
    return translations


def materialize_translation_rows(
    rows: Iterable[dict[str, str]],
    id_column: str,
    expected_count: int,
) -> list[str]:
    """Materialize a complete translation table without needing retail source bytes.

    Used by the release-data rebuild path: blank translation falls back to source_japanese and
    `<EMPTY>` becomes an intentional zero-length string.
    """
    output: list[str | None] = [None] * expected_count
    for row in rows:
        index = int(row[id_column])
        if not 0 <= index < expected_count:
            raise ValueError(f"{id_column} {index} out of range")
        if output[index] is not None:
            raise ValueError(f"duplicate {id_column} {index}")
        translation = row.get("translation", "")
        source = row.get("source_japanese", "")
        output[index] = "" if translation == "<EMPTY>" else (translation or source)
    missing = [index for index, value in enumerate(output) if value is None]
    if missing:
        raise ValueError(f"missing {id_column} rows: {missing[:20]}")
    return [value or "" for value in output]


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(stream)]


def encode_cp932(text: str, label: str = "text") -> bytes:
    if "~" in text:
        raise ValueError(f"{label}: literal '~' is reserved for the patched Ü glyph")
    mapped = text.replace("Ü", "~")
    try:
        return mapped.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        bad = mapped[exc.start : exc.end]
        raise ValueError(
            f"{label}: character(s) not representable by the patched game font: {bad!r}"
        ) from exc


def decode_game_text(raw: bytes) -> str:
    return raw.decode("cp932", errors="strict").replace("~", "Ü")


def build_combined_list(display_texts: list[str], master_texts: list[str]) -> bytes:
    if len(display_texts) != DISPLAY_COUNT:
        raise ValueError(f"wrong display-text count: {len(display_texts)} != {DISPLAY_COUNT}")
    if len(master_texts) != MASTER_COUNT:
        raise ValueError(f"wrong master-text count: {len(master_texts)} != {MASTER_COUNT}")

    all_texts = display_texts + master_texts
    table_bytes = TOTAL_POINTERS * 4
    offsets: dict[bytes, int] = {}
    pointers: list[int] = []
    body = bytearray()
    for index, text in enumerate(all_texts):
        encoded = encode_cp932(text, f"combined text {index}") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = table_bytes + len(body)
            body.extend(encoded)
        pointers.append(offsets[encoded])
    return struct.pack("<" + "I" * TOTAL_POINTERS, *pointers) + bytes(body)


def parse_combined_relative(raw: bytes) -> tuple[list[str], list[str]]:
    table_bytes = TOTAL_POINTERS * 4
    if len(raw) < table_bytes:
        raise FormatError("combined LIST is too small")
    pointers = struct.unpack_from("<" + "I" * TOTAL_POINTERS, raw, 0)
    texts: list[str] = []
    for index, pointer in enumerate(pointers):
        if not table_bytes <= pointer < len(raw):
            raise FormatError(f"combined pointer {index} is out of range: 0x{pointer:X}")
        end = raw.find(b"\0", pointer)
        if end < 0:
            raise FormatError(f"combined pointer {index} has no NUL terminator")
        texts.append(decode_game_text(raw[pointer:end]))
    return texts[:DISPLAY_COUNT], texts[DISPLAY_COUNT:]


def encode_i(op: int, rs: int, rt: int, imm: int) -> int:
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def encode_j(op: int, address: int) -> int:
    return (op << 26) | ((address >> 2) & 0x03FFFFFF)


def encode_r(rs: int, rt: int, rd: int, shamt: int, funct: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct


def check_patch_sites(executable: bytes) -> None:
    expected = {
        LOOP_COUNT_VA: 0x2C830692,
        LOADER_RETURN_VA: 0x03E00008,
    }
    for va, word in expected.items():
        offset = va_to_off(va)
        if offset < 0 or offset + 4 > len(executable):
            raise FormatError(f"patch site VA 0x{va:X} lies outside executable")
        actual = struct.unpack_from("<I", executable, offset)[0]
        if actual != word:
            raise VerificationError(
                f"unexpected instruction at 0x{va:X}: 0x{actual:08X} != 0x{word:08X}"
            )
    cave_offset = va_to_off(CODE_CAVE_VA)
    cave = executable[cave_offset : cave_offset + 20]
    if cave != b"\0" * 20:
        raise VerificationError(f"expected 20-byte zero code cave at 0x{CODE_CAVE_VA:X}")


def patch_executable(original: bytes) -> bytes:
    expected_hash = RETAIL_SHA256["SLPM_658.82"]
    got_hash = sha256_bytes(original)
    if got_hash != expected_hash:
        raise HashMismatchError(f"retail executable SHA-256 {got_hash} != {expected_hash}")
    check_patch_sites(original)
    executable = bytearray(original)
    struct.pack_into(
        "<I",
        executable,
        va_to_off(LOOP_COUNT_VA),
        encode_i(0x0B, 4, 3, TOTAL_POINTERS),
    )
    struct.pack_into(
        "<I",
        executable,
        va_to_off(LOADER_RETURN_VA),
        encode_j(0x02, CODE_CAVE_VA),
    )
    cave_words = [
        encode_i(0x23, 28, 8, CARD_TEXT_OBJECT_GLOBAL_GP_OFF),
        encode_i(0x23, 28, 9, TEXT_RESOURCE_GLOBAL_GP_OFF),
        encode_i(0x09, 9, 9, MASTER_POINTER_BYTE_OFFSET),
        encode_r(31, 0, 0, 0, 8),
        encode_i(0x2B, 8, 9, 0x000C),
    ]
    cave_offset = va_to_off(CODE_CAVE_VA)
    for index, word in enumerate(cave_words):
        struct.pack_into("<I", executable, cave_offset + index * 4, word)
    return bytes(executable)


def build_externalized(
    executable: bytes,
    retail_list: bytes,
    master_csv: str | Path,
    display_csv: str | Path,
) -> ExternalizedCardText:
    exe_hash = sha256_bytes(executable)
    if exe_hash != RETAIL_SHA256["SLPM_658.82"]:
        raise HashMismatchError("executable hash does not match verified retail SLPM-65882")
    list_hash = sha256_bytes(retail_list)
    if list_hash != RETAIL_SHA256["LIST_1.BIN"]:
        raise HashMismatchError("LIST_1 hash does not match verified retail resource")

    display_source = parse_retail_list_bytes(retail_list)[:DISPLAY_COUNT]
    master_source = parse_master_text(executable)
    display_output = load_translation_csv(display_csv, "list_index", display_source)
    master_output = load_translation_csv(master_csv, "master_text_id", master_source)
    combined = build_combined_list(display_output, master_output)
    display_check, master_check = parse_combined_relative(combined)
    if display_check != display_output or master_check != master_output:
        raise VerificationError("combined LIST round-trip self-check failed")
    return ExternalizedCardText(
        patch_executable(executable),
        combined,
        tuple(display_output),
        tuple(master_output),
    )
