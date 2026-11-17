from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from .errors import HashMismatchError, VerificationError


@dataclass(frozen=True)
class V14BuildResult:
    executable: bytes
    scrpack: bytes
    executable_differing_bytes: int
    scrpack_differing_bytes: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _spec() -> dict[str, Any]:
    resource = files("botsd").joinpath("assets").joinpath("v14.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _language(language: str = "en") -> dict[str, Any]:
    package = f"localization.{language}"
    return json.loads(files(package).joinpath("v14_maintenance.json").read_text(encoding="utf-8"))


def _guard(data: bytes, expected: str, label: str) -> None:
    got = _sha256(data)
    if got != expected:
        raise HashMismatchError(f"{label}: SHA-256 {got} != expected {expected}")


def _sda_offsets(source: bytes) -> tuple[int, ...]:
    if len(source) < 12 or source[:4] != b"sda\0":
        raise VerificationError("SCRPACK is not an sda\\0 archive")
    declared, count = struct.unpack_from("<II", source, 4)
    if declared != len(source):
        raise VerificationError(f"SCRPACK declared size {declared} != actual {len(source)}")
    offsets = tuple(struct.unpack_from(f"<{count}I", source, 12))
    if not offsets:
        raise VerificationError("SCRPACK has no chunks")
    return offsets


def _parse_chunk(source: bytes, chunk_index: int) -> list[tuple[int, int, int, int, int]]:
    offsets = _sda_offsets(source)
    start = offsets[chunk_index]
    end = offsets[chunk_index + 1] if chunk_index + 1 < len(offsets) else len(source)
    rows: list[tuple[int, int, int, int, int]] = []
    cursor = start
    index = 0
    while cursor < end:
        if cursor + 4 > end:
            raise VerificationError(f"chunk {chunk_index}: truncated command header")
        opcode, payload_size = struct.unpack_from("<HH", source, cursor)
        command_end = cursor + 4 + payload_size
        if command_end > end:
            raise VerificationError(f"chunk {chunk_index} command {index}: payload overruns chunk")
        rows.append((index, cursor, cursor - start, opcode, payload_size))
        cursor = command_end
        index += 1
    if cursor != end:
        raise VerificationError(f"chunk {chunk_index}: command stream does not end at boundary")
    return rows


def _dialogue_text(source: bytes, row: tuple[int, int, int, int, int]) -> str:
    _, file_offset, _, opcode, payload_size = row
    if opcode != 0x1D03 or payload_size < 8:
        raise VerificationError("expected 1D03 dialogue command")
    length = struct.unpack_from("<H", source, file_offset + 10)[0]
    capacity = payload_size - 8
    if length > capacity:
        raise VerificationError("dialogue length exceeds payload allocation")
    raw = source[file_offset + 12 : file_offset + 12 + length]
    return raw.decode("cp932", errors="strict")


def _replace_dialogue_in_place(
    source: bytes,
    *,
    chunk_index: int,
    command_index: int,
    source_text: str,
    replacement_text: str,
) -> bytes:
    commands = _parse_chunk(source, chunk_index)
    command = commands[command_index]
    _, file_offset, _, opcode, payload_size = command
    if opcode != 0x1D03:
        raise VerificationError(
            f"chunk {chunk_index} command {command_index}: expected 0x1D03, got 0x{opcode:04X}"
        )
    if _dialogue_text(source, command) != source_text:
        raise VerificationError(
            f"chunk {chunk_index} command {command_index}: source text guard failed"
        )
    raw = replacement_text.encode("cp932")
    capacity = payload_size - 8
    if len(raw) > capacity:
        raise VerificationError(
            f"chunk {chunk_index} command {command_index}: replacement exceeds allocation"
        )
    out = bytearray(source)
    struct.pack_into("<H", out, file_offset + 10, len(raw))
    out[file_offset + 12 : file_offset + 4 + payload_size] = (
        raw + b"\0" * (capacity - len(raw))
    )
    result = bytes(out)
    if _parse_chunk(result, chunk_index) != commands:
        raise VerificationError(
            f"chunk {chunk_index} command {command_index}: in-place edit changed framing"
        )
    return result


def build_v14_executable(
    source: bytes,
    *,
    language: str = "en",
    strings: Mapping[str, Any] | None = None,
) -> bytes:
    cfg = _spec()
    localized = dict(strings) if strings is not None else _language(language)
    _guard(source, cfg["public_v13"]["SLPM_658.82"], "public v1.3 executable")

    delta = int(cfg["executable"]["load_va_delta"])
    table_va = int(cfg["executable"]["master_table_va"])
    master_count = int(cfg["executable"]["master_count"])
    table_offset = table_va - delta
    pointers = struct.unpack_from(f"<{master_count}I", source, table_offset)
    original_table = source[table_offset : table_offset + master_count * 4]
    output = bytearray(source)

    races = localized.get("races")
    if not isinstance(races, list) or len(races) != 27:
        raise VerificationError("v1.4 race maintenance must contain exactly 27 entries")

    touched: set[int] = set()
    for row in races:
        va = int(row["va"])
        japanese = str(row["source"])
        english = str(row["replacement"])
        master_ids = tuple(int(value) for value in row["master_ids"])

        if tuple(index for index, pointer in enumerate(pointers) if pointer == va) != master_ids:
            raise VerificationError(f"{japanese!r}: master pointer alias guard failed")

        offset = va - delta
        old = japanese.encode("cp932") + b"\0"
        new = english.encode("cp932") + b"\0"
        if source[offset : offset + len(old)] != old:
            raise VerificationError(f"{japanese!r}: source allocation guard failed")
        if len(new) > len(old):
            raise VerificationError(f"{japanese!r}: replacement exceeds source allocation")
        if offset in touched:
            raise VerificationError(f"duplicate race allocation 0x{offset:X}")
        touched.add(offset)

        interior = [
            (index, pointer)
            for index, pointer in enumerate(pointers)
            if va < pointer < va + len(old)
        ]
        if interior:
            raise VerificationError(f"{japanese!r}: interior pointer alias found")

        output[offset : offset + len(old)] = new + b"\0" * (len(old) - len(new))

    result = bytes(output)
    if result[table_offset : table_offset + master_count * 4] != original_table:
        raise VerificationError("v1.4 race repair changed the master pointer table")
    if len(result) != len(source):
        raise VerificationError("v1.4 executable size changed")
    _guard(result, cfg["v14"]["SLPM_658.82"], "v1.4 executable")
    return result


def _rebuild_xenon_chunk(
    retail: bytes,
    source: bytes,
    localized: Mapping[str, Any],
) -> bytes:
    cfg = _spec()
    chunk_index = int(cfg["xenon"]["chunk"])
    retail_offsets = _sda_offsets(retail)
    source_offsets = _sda_offsets(source)
    if retail_offsets != source_offsets:
        raise VerificationError("retail/public-v1.3 SCRPACK outer layouts differ")

    retail_rows = _parse_chunk(retail, chunk_index)
    source_rows = _parse_chunk(source, chunk_index)
    retail_meaningful = list(retail_rows)
    source_meaningful = list(source_rows)
    while retail_meaningful and retail_meaningful[-1][3:] == (0, 0):
        retail_meaningful.pop()
    while source_meaningful and source_meaningful[-1][3:] == (0, 0):
        source_meaningful.pop()

    if len(retail_meaningful) != 261 or len(source_meaningful) != 261:
        raise VerificationError("Xenon chunk meaningful command count mismatch")
    if [row[3] for row in retail_meaningful] != [row[3] for row in source_meaningful]:
        raise VerificationError("Xenon chunk opcode sequence differs from retail")

    replacements = {
        int(row["command_index"]): row for row in localized["xenon_dialogue"]
    }
    size_overrides = {
        int(key): int(value)
        for key, value in localized["xenon_payload_sizes"].items()
    }

    parts: list[bytes] = []
    for row in source_meaningful:
        index, file_offset, _, opcode, payload_size = row
        if opcode != 0x1D03:
            parts.append(source[file_offset : file_offset + 4 + payload_size])
            continue

        target_payload_size = size_overrides.get(index, payload_size)
        text = _dialogue_text(source, row)
        if index in replacements:
            expected = str(replacements[index]["source"])
            if text != expected:
                raise VerificationError(
                    f"Xenon command {index}: source text guard failed"
                )
            text = str(replacements[index]["replacement"])

        raw = text.encode("cp932")
        capacity = target_payload_size - 8
        if len(raw) > capacity:
            raise VerificationError(
                f"Xenon command {index}: text does not fit retail geometry"
            )
        prefix = source[file_offset + 4 : file_offset + 10]
        payload = prefix + struct.pack("<H", len(raw)) + raw
        payload += b"\0" * (target_payload_size - len(payload))
        parts.append(struct.pack("<HH", opcode, target_payload_size) + payload)

    start = source_offsets[chunk_index]
    end = source_offsets[chunk_index + 1]
    rebuilt = b"".join(parts)
    capacity = end - start
    if len(rebuilt) > capacity or (capacity - len(rebuilt)) % 4:
        raise VerificationError("Xenon chunk allocation/padding mismatch")
    rebuilt += b"\0" * (capacity - len(rebuilt))

    output = bytearray(source)
    output[start:end] = rebuilt
    result = bytes(output)

    result_rows = _parse_chunk(result, chunk_index)
    if [(r[2], r[3], r[4]) for r in result_rows] != [
        (r[2], r[3], r[4]) for r in retail_rows
    ]:
        raise VerificationError("Xenon chunk command geometry is not exact retail")

    for retail_row, result_row in zip(retail_rows, result_rows, strict=True):
        index, retail_file, _, opcode, payload_size = retail_row
        _, result_file, _, _, _ = result_row
        if opcode != 0x1D03:
            if retail[retail_file : retail_file + 4 + payload_size] != result[
                result_file : result_file + 4 + payload_size
            ]:
                raise VerificationError(
                    f"Xenon command {index}: non-dialogue bytes differ from retail"
                )
        else:
            if retail[retail_file : retail_file + 10] != result[
                result_file : result_file + 10
            ]:
                raise VerificationError(
                    f"Xenon command {index}: dialogue metadata differs from retail"
                )

    for index in range(221, 261):
        rr = retail_rows[index]
        tr = result_rows[index]
        _, rf, _, _, psz = rr
        _, tf, _, _, _ = tr
        if retail[rf : rf + 4 + psz] != result[tf : tf + 4 + psz]:
            raise VerificationError(f"Xenon ending tail command {index} is not exact retail")

    return result


def build_v14_scrpack(
    retail: bytes,
    source: bytes,
    *,
    language: str = "en",
    strings: Mapping[str, Any] | None = None,
) -> bytes:
    cfg = _spec()
    localized = dict(strings) if strings is not None else _language(language)
    _guard(retail, cfg["retail"]["SCRPACK.SDA"], "retail SCRPACK")
    _guard(source, cfg["public_v13"]["SCRPACK.SDA"], "public v1.3 SCRPACK")

    output = source
    overflow = localized.get("overflow_dialogue")
    if not isinstance(overflow, list) or len(overflow) != 56:
        raise VerificationError("v1.4 overflow maintenance must contain exactly 56 entries")
    for row in overflow:
        output = _replace_dialogue_in_place(
            output,
            chunk_index=int(row["chunk"]),
            command_index=int(row["command_index"]),
            source_text=str(row["source"]),
            replacement_text=str(row["replacement"]),
        )

    output = _rebuild_xenon_chunk(retail, output, localized)
    if len(output) != len(source):
        raise VerificationError("v1.4 SCRPACK size changed")
    _guard(output, cfg["v14"]["SCRPACK.SDA"], "v1.4 SCRPACK")
    return output


def build_v14(
    public_v13_executable: bytes,
    public_v13_scrpack: bytes,
    retail_scrpack: bytes,
    *,
    language: str = "en",
) -> V14BuildResult:
    executable = build_v14_executable(public_v13_executable, language=language)
    scrpack = build_v14_scrpack(retail_scrpack, public_v13_scrpack, language=language)
    return V14BuildResult(
        executable=executable,
        scrpack=scrpack,
        executable_differing_bytes=sum(
            a != b for a, b in zip(public_v13_executable, executable, strict=True)
        ),
        scrpack_differing_bytes=sum(
            a != b for a, b in zip(public_v13_scrpack, scrpack, strict=True)
        ),
    )
