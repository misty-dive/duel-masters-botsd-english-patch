from __future__ import annotations

import csv
import struct
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .errors import VerificationError
from .scrpack import ScriptCommand, _sda_offsets, parse_chunk_commands

DIALOGUE_OPCODE = 0x1D03


@dataclass(frozen=True)
class StoryTextRecord:
    resource_id: str
    chunk_index: int
    command_index: int
    source_file_offset: int
    translation_file_offset: int
    source_payload_size: int
    translation_payload_size: int
    source_byte_length: int
    translation_byte_length: int
    source_text: str
    translation: str
    changed: bool
    explicit_breaks: int


@dataclass(frozen=True)
class StoryCatalogReport:
    rows: int
    translated_rows: int
    identical_rows: int
    chunks: int


def _decode_command_text(source: bytes, command, *, encoding: str = "cp932") -> str:
    if command.opcode != DIALOGUE_OPCODE:
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            f"expected dialogue opcode 0x{DIALOGUE_OPCODE:04X}, got 0x{command.opcode:04X}"
        )
    if command.payload_size < 8:
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            "dialogue payload is too short"
        )
    length_offset = command.file_offset + 10
    text_offset = command.file_offset + 12
    command_end = command.file_offset + command.total_size
    length = struct.unpack_from("<H", source, length_offset)[0]
    capacity = command_end - text_offset
    if length > capacity:
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            f"dialogue length {length} exceeds allocation {capacity}"
        )
    raw = source[text_offset : text_offset + length]
    if length < capacity and any(source[text_offset + length : command_end]):
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            "non-zero bytes follow the length-delimited dialogue text"
        )
    try:
        return raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            f"dialogue is not valid {encoding}"
        ) from exc


def _dialogue_commands(source: bytes, chunk_index: int):
    return tuple(
        command
        for command in parse_chunk_commands(source, chunk_index)
        if command.opcode == DIALOGUE_OPCODE
    )


def build_story_catalog(
    retail: bytes,
    translated: bytes,
    *,
    encoding: str = "cp932",
) -> tuple[tuple[StoryTextRecord, ...], StoryCatalogReport]:
    """Pair retail and translated SCRPACK dialogue by stable chunk/command ordinal.

    The reverse-engineered script command framing makes ``chunk_index`` + ``command_index`` a
    stable identity for the v1.0-v1.3 corpus.  This exporter deliberately does not use raw file
    offsets as identity: translated strings can change command sizes and therefore move later
    commands within their fixed SDA chunk.
    """
    retail_offsets = _sda_offsets(retail)
    translated_offsets = _sda_offsets(translated)
    if len(retail_offsets) != len(translated_offsets):
        raise VerificationError(
            f"SCRPACK chunk count differs: retail={len(retail_offsets)} "
            f"translated={len(translated_offsets)}"
        )

    rows: list[StoryTextRecord] = []
    for chunk_index in range(len(retail_offsets)):
        retail_commands = {row.command_index: row for row in _dialogue_commands(retail, chunk_index)}
        translated_commands = {
            row.command_index: row for row in _dialogue_commands(translated, chunk_index)
        }
        if retail_commands.keys() != translated_commands.keys():
            missing = sorted(retail_commands.keys() - translated_commands.keys())[:8]
            extra = sorted(translated_commands.keys() - retail_commands.keys())[:8]
            raise VerificationError(
                f"SCRPACK chunk {chunk_index}: dialogue command ordinals differ; "
                f"missing={missing} extra={extra}"
            )
        for command_index in sorted(retail_commands):
            source_command = retail_commands[command_index]
            translated_command = translated_commands[command_index]
            source_text = _decode_command_text(retail, source_command, encoding=encoding)
            translation = _decode_command_text(translated, translated_command, encoding=encoding)
            source_len = struct.unpack_from("<H", retail, source_command.file_offset + 10)[0]
            translation_len = struct.unpack_from(
                "<H", translated, translated_command.file_offset + 10
            )[0]
            rows.append(
                StoryTextRecord(
                    resource_id=f"scrpack.{chunk_index:03d}.{command_index:04d}",
                    chunk_index=chunk_index,
                    command_index=command_index,
                    source_file_offset=source_command.file_offset,
                    translation_file_offset=translated_command.file_offset,
                    source_payload_size=source_command.payload_size,
                    translation_payload_size=translated_command.payload_size,
                    source_byte_length=source_len,
                    translation_byte_length=translation_len,
                    source_text=source_text,
                    translation=translation,
                    changed=source_text != translation,
                    explicit_breaks=translation.count("#cr0"),
                )
            )

    changed = sum(row.changed for row in rows)
    return tuple(rows), StoryCatalogReport(
        rows=len(rows),
        translated_rows=changed,
        identical_rows=len(rows) - changed,
        chunks=len(retail_offsets),
    )


def write_story_catalog(path: str | Path, rows: Iterable[StoryTextRecord]) -> int:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "resource_id",
        "chunk_index",
        "command_index",
        "source_file_offset",
        "translation_file_offset",
        "source_payload_size",
        "translation_payload_size",
        "source_byte_length",
        "translation_byte_length",
        "source_text",
        "translation",
        "changed",
        "explicit_breaks",
    ]
    count = 0
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "resource_id": row.resource_id,
                    "chunk_index": row.chunk_index,
                    "command_index": row.command_index,
                    "source_file_offset": f"0x{row.source_file_offset:X}",
                    "translation_file_offset": f"0x{row.translation_file_offset:X}",
                    "source_payload_size": row.source_payload_size,
                    "translation_payload_size": row.translation_payload_size,
                    "source_byte_length": row.source_byte_length,
                    "translation_byte_length": row.translation_byte_length,
                    "source_text": row.source_text,
                    "translation": row.translation,
                    "changed": "yes" if row.changed else "no",
                    "explicit_breaks": row.explicit_breaks,
                }
            )
            count += 1
    return count


@dataclass(frozen=True)
class StoryDialogueTranslation:
    resource_id: str
    chunk_index: int
    command_index: int
    payload_size: int
    translation: str
    explicit_breaks: int


@dataclass(frozen=True)
class StoryChoiceTranslation:
    resource_id: str
    chunk_index: int
    command_index: int
    payload_size: int
    options: tuple[str, ...]


@dataclass(frozen=True)
class StoryLanguageAudit:
    dialogue_rows: int
    choice_rows: int
    dialogue_commands: int
    choice_commands: int
    chunks: int


def _stable_resource_id(chunk_index: int, command_index: int) -> str:
    return f"scrpack.{chunk_index:03d}.{command_index:04d}"


def _parse_resource_id(resource_id: str) -> tuple[int, int]:
    parts = resource_id.split(".")
    if len(parts) != 3 or parts[0] != "scrpack":
        raise ValueError(f"invalid SCRPACK resource id {resource_id!r}")
    try:
        chunk_index = int(parts[1], 10)
        command_index = int(parts[2], 10)
    except ValueError as exc:
        raise ValueError(f"invalid SCRPACK resource id {resource_id!r}") from exc
    if chunk_index < 0 or command_index < 0:
        raise ValueError(f"invalid SCRPACK resource id {resource_id!r}")
    if _stable_resource_id(chunk_index, command_index) != resource_id:
        raise ValueError(f"non-canonical SCRPACK resource id {resource_id!r}")
    return chunk_index, command_index


def load_story_dialogue_translations(path: str | Path) -> tuple[StoryDialogueTranslation, ...]:
    rows: list[StoryDialogueTranslation] = []
    seen: set[str] = set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "resource_id",
            "chunk_index",
            "command_index",
            "payload_size",
            "translation",
            "explicit_breaks",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"story dialogue dataset missing columns: {sorted(missing)}")
        for line, raw in enumerate(reader, start=2):
            resource_id = (raw.get("resource_id") or "").strip()
            if not resource_id:
                raise ValueError(f"{path}:{line}: empty resource_id")
            if resource_id in seen:
                raise ValueError(f"{path}:{line}: duplicate resource_id {resource_id!r}")
            seen.add(resource_id)
            chunk_index, command_index = _parse_resource_id(resource_id)
            if int(raw["chunk_index"]) != chunk_index or int(raw["command_index"]) != command_index:
                raise ValueError(f"{path}:{line}: resource_id does not match chunk/command columns")
            payload_size = int(raw["payload_size"])
            if payload_size < 8:
                raise ValueError(f"{path}:{line}: invalid dialogue payload_size {payload_size}")
            translation = raw.get("translation") or ""
            explicit_breaks = int(raw["explicit_breaks"])
            if explicit_breaks != translation.count("#cr0"):
                raise ValueError(f"{path}:{line}: explicit_breaks does not match translation")
            rows.append(
                StoryDialogueTranslation(
                    resource_id,
                    chunk_index,
                    command_index,
                    payload_size,
                    translation,
                    explicit_breaks,
                )
            )
    return tuple(rows)


def load_story_choice_translations(path: str | Path) -> tuple[StoryChoiceTranslation, ...]:
    rows: list[StoryChoiceTranslation] = []
    seen: set[str] = set()
    option_fields = tuple(f"option_{index}" for index in range(8))
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "resource_id",
            "chunk_index",
            "command_index",
            "payload_size",
            "option_count",
            *option_fields,
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"story choice dataset missing columns: {sorted(missing)}")
        for line, raw in enumerate(reader, start=2):
            resource_id = (raw.get("resource_id") or "").strip()
            if not resource_id:
                raise ValueError(f"{path}:{line}: empty resource_id")
            if resource_id in seen:
                raise ValueError(f"{path}:{line}: duplicate resource_id {resource_id!r}")
            seen.add(resource_id)
            chunk_index, command_index = _parse_resource_id(resource_id)
            if int(raw["chunk_index"]) != chunk_index or int(raw["command_index"]) != command_index:
                raise ValueError(f"{path}:{line}: resource_id does not match chunk/command columns")
            count = int(raw["option_count"])
            if not 0 <= count <= len(option_fields):
                raise ValueError(f"{path}:{line}: invalid option_count {count}")
            options = tuple((raw.get(option_fields[index]) or "") for index in range(count))
            trailing = [raw.get(field) or "" for field in option_fields[count:]]
            if any(trailing):
                raise ValueError(f"{path}:{line}: non-empty option column after option_count")
            rows.append(
                StoryChoiceTranslation(
                    resource_id,
                    chunk_index,
                    command_index,
                    int(raw["payload_size"]),
                    options,
                )
            )
    return tuple(rows)


def _decode_choice_command(source: bytes, command, *, encoding: str = "cp932") -> tuple[str, ...]:
    if command.opcode != 0x1F03:
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            f"expected choice opcode 0x1F03, got 0x{command.opcode:04X}"
        )
    payload = source[command.file_offset + 4 : command.file_offset + command.total_size]
    if len(payload) < 8:
        raise VerificationError("SCRPACK choice payload is too short")
    if payload[:6] != b"\x00\x00\x02\x00\x00\x00":
        raise VerificationError(
            f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
            "unexpected 1F03 choice prefix"
        )
    count = struct.unpack_from("<H", payload, 6)[0]
    cursor = 8
    options: list[str] = []
    for _ in range(count):
        if cursor + 2 > len(payload):
            raise VerificationError("SCRPACK choice length table is truncated")
        length = struct.unpack_from("<H", payload, cursor)[0]
        cursor += 2
        if cursor + length > len(payload):
            raise VerificationError("SCRPACK choice string exceeds command allocation")
        raw = payload[cursor : cursor + length]
        cursor += length
        try:
            options.append(raw.decode(encoding, errors="strict"))
        except UnicodeDecodeError as exc:
            raise VerificationError("SCRPACK choice string is not valid CP932") from exc
    if any(payload[cursor:]):
        raise VerificationError("SCRPACK choice command has non-zero trailing padding")
    return tuple(options)


def _encode_dialogue_command(
    source: bytes,
    command,
    row: StoryDialogueTranslation,
    *,
    encoding: str = "cp932",
) -> bytes:
    if command.opcode != DIALOGUE_OPCODE:
        raise VerificationError(
            f"{row.resource_id}: expected opcode 0x{DIALOGUE_OPCODE:04X}, "
            f"got 0x{command.opcode:04X}"
        )
    raw = row.translation.encode(encoding, errors="strict")
    if len(raw) > row.payload_size - 8:
        raise VerificationError(
            f"{row.resource_id}: translation needs {len(raw)} bytes, "
            f"payload allocation allows {row.payload_size - 8}"
        )
    prefix = source[command.file_offset + 4 : command.file_offset + 10]
    payload = prefix + struct.pack("<H", len(raw)) + raw
    payload += b"\0" * (row.payload_size - len(payload))
    return struct.pack("<HH", command.opcode, row.payload_size) + payload


def _encode_choice_command(
    source: bytes,
    command,
    row: StoryChoiceTranslation,
    *,
    encoding: str = "cp932",
) -> bytes:
    if command.opcode != 0x1F03:
        raise VerificationError(
            f"{row.resource_id}: expected opcode 0x1F03, got 0x{command.opcode:04X}"
        )
    prefix = source[command.file_offset + 4 : command.file_offset + 10]
    if prefix != b"\x00\x00\x02\x00\x00\x00":
        raise VerificationError(f"{row.resource_id}: unexpected source 1F03 choice prefix")
    payload = bytearray(prefix)
    payload += struct.pack("<H", len(row.options))
    for option in row.options:
        raw = option.encode(encoding, errors="strict")
        if len(raw) > 0xFFFF:
            raise VerificationError(f"{row.resource_id}: choice string is too long")
        payload += struct.pack("<H", len(raw))
        payload += raw
    if len(payload) > row.payload_size:
        raise VerificationError(
            f"{row.resource_id}: choices need {len(payload)} bytes, "
            f"payload allocation is {row.payload_size}"
        )
    payload += b"\0" * (row.payload_size - len(payload))
    return struct.pack("<HH", command.opcode, row.payload_size) + bytes(payload)


def _meaningful_commands(source: bytes, chunk_index: int) -> tuple[ScriptCommand, ...]:
    """Return one chunk's command stream without trailing all-zero allocation padding.

    Retail and translated SCRPACK keep the same 4 KiB outer chunk allocations.  The unused tail is
    represented by repeated ``opcode=0, payload_size=0`` four-byte commands.  English text growth
    consumes some of those padding commands and text shrinkage creates more of them, so the padding
    command count is not a stable part of script identity.
    """
    commands = list(parse_chunk_commands(source, chunk_index))
    while commands and commands[-1].opcode == 0 and commands[-1].payload_size == 0:
        commands.pop()
    return tuple(commands)


def _historical_v12_relocation_payload_offsets(
    source: bytes,
    command: ScriptCommand,
) -> tuple[int, ...]:
    """Return payload-relative u32 command-target fields relocated by the v1.2 compiler.

    Paired retail/public-v1.2 archaeology proves five command families were structurally relocated
    after text-bearing commands changed size.  The historical 0x070C probability-branch family is
    intentionally *not* included: its three stale retail targets survived into v1.2 and were fixed
    later by the semantic v1.3 maintenance stage.
    """
    if command.opcode in (0x010C, 0x020C):
        if command.payload_size != 4:
            raise VerificationError(
                f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
                f"opcode 0x{command.opcode:04X} payload {command.payload_size} != 4"
            )
        return (0,)
    if command.opcode in (0x1212, 0x1312):
        if command.payload_size != 16:
            raise VerificationError(
                f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
                f"opcode 0x{command.opcode:04X} payload {command.payload_size} != 16"
            )
        return (12,)
    if command.opcode == 0x1412:
        payload = source[command.file_offset + 4 : command.file_offset + command.total_size]
        if len(payload) < 8:
            raise VerificationError(
                f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
                "0x1412 payload is too short"
            )
        count = struct.unpack_from("<H", payload, 6)[0]
        expected = 8 + 4 * count
        if command.payload_size != expected:
            raise VerificationError(
                f"SCRPACK chunk {command.chunk_index} command {command.command_index}: "
                f"0x1412 payload {command.payload_size} != 8 + 4*{count} ({expected})"
            )
        return tuple(range(8, expected, 4))
    return ()


def _relocate_historical_v12_command(
    command_bytes: bytearray,
    source_command: ScriptCommand,
    source_offset_to_ordinal: dict[int, int],
    target_offsets: list[int],
    source: bytes,
) -> None:
    for payload_offset in _historical_v12_relocation_payload_offsets(source, source_command):
        field_offset = 4 + payload_offset
        old_target = struct.unpack_from("<I", command_bytes, field_offset)[0]
        try:
            target_ordinal = source_offset_to_ordinal[old_target]
        except KeyError as exc:
            raise VerificationError(
                f"SCRPACK chunk {source_command.chunk_index} command "
                f"{source_command.command_index}: opcode 0x{source_command.opcode:04X} "
                f"target 0x{old_target:X} is not a meaningful retail command boundary"
            ) from exc
        struct.pack_into("<I", command_bytes, field_offset, target_offsets[target_ordinal])


def apply_story_language(
    source: bytes,
    dialogue_rows: Iterable[StoryDialogueTranslation],
    choice_rows: Iterable[StoryChoiceTranslation],
    *,
    encoding: str = "cp932",
) -> bytes:
    """Rebuild the exact public-v1.2 story layer from retail plus language data.

    The outer SDA uses fixed 4 KiB chunk allocations.  Within each allocation, 1D03 dialogue and
    1F03 choice commands may grow or shrink, five historical command families relocate their
    command-relative targets, and the remaining capacity is encoded as repeated four-byte zero
    commands.  The historical v1.2 compiler did *not* relocate 0x070C probability branches; those
    three stale targets are deliberately preserved here so v1.2 remains byte-exact and the v1.3
    maintenance stage remains the canonical semantic repair.
    """
    dialogue_items = tuple(dialogue_rows)
    choice_items = tuple(choice_rows)
    dialogue = {(row.chunk_index, row.command_index): row for row in dialogue_items}
    choices = {(row.chunk_index, row.command_index): row for row in choice_items}
    if len(dialogue) != len(dialogue_items):
        raise ValueError("duplicate dialogue resource identity")
    if len(choices) != len(choice_items):
        raise ValueError("duplicate choice resource identity")
    overlap = dialogue.keys() & choices.keys()
    if overlap:
        raise ValueError(f"story language resource appears in both datasets: {sorted(overlap)[:3]}")

    offsets = _sda_offsets(source)
    output = bytearray(source)
    seen_dialogue: set[tuple[int, int]] = set()
    seen_choices: set[tuple[int, int]] = set()
    for chunk_index in range(len(offsets)):
        start = offsets[chunk_index]
        end = offsets[chunk_index + 1] if chunk_index + 1 < len(offsets) else len(source)
        commands = _meaningful_commands(source, chunk_index)
        source_offset_to_ordinal = {
            command.chunk_relative_offset: command.command_index for command in commands
        }
        if len(source_offset_to_ordinal) != len(commands):
            raise VerificationError(f"SCRPACK chunk {chunk_index}: duplicate command offsets")

        parts: list[bytearray] = []
        for command in commands:
            key = (chunk_index, command.command_index)
            if key in dialogue:
                encoded = _encode_dialogue_command(
                    source, command, dialogue[key], encoding=encoding
                )
                seen_dialogue.add(key)
            elif key in choices:
                encoded = _encode_choice_command(source, command, choices[key], encoding=encoding)
                seen_choices.add(key)
            else:
                encoded = source[command.file_offset : command.file_offset + command.total_size]
            parts.append(bytearray(encoded))

        target_offsets: list[int] = []
        cursor = 0
        for part in parts:
            target_offsets.append(cursor)
            cursor += len(part)

        for command, part in zip(commands, parts, strict=True):
            _relocate_historical_v12_command(
                part,
                command,
                source_offset_to_ordinal,
                target_offsets,
                source,
            )

        rebuilt = b"".join(parts)
        capacity = end - start
        if len(rebuilt) > capacity:
            raise VerificationError(
                f"SCRPACK chunk {chunk_index}: language rebuild needs {len(rebuilt)} bytes, "
                f"fixed allocation is {capacity} (overflow {len(rebuilt) - capacity:+d})"
            )
        padding = capacity - len(rebuilt)
        if padding % 4:
            raise VerificationError(
                f"SCRPACK chunk {chunk_index}: trailing padding {padding} is not 4-byte aligned"
            )
        output[start:end] = rebuilt + b"\0" * padding

    missing_dialogue = set(dialogue) - seen_dialogue
    missing_choices = set(choices) - seen_choices
    if missing_dialogue or missing_choices:
        raise VerificationError(
            f"story language resources missing from SCRPACK: "
            f"dialogue={sorted(missing_dialogue)[:3]} choices={sorted(missing_choices)[:3]}"
        )
    result = bytes(output)
    for chunk_index in range(len(offsets)):
        before = _meaningful_commands(source, chunk_index)
        after = _meaningful_commands(result, chunk_index)
        if (
            len(before) != len(after)
            or [row.opcode for row in before] != [row.opcode for row in after]
        ):
            raise VerificationError(f"SCRPACK chunk {chunk_index}: meaningful command identity changed")
    return result

def audit_story_language(
    translated: bytes,
    dialogue_rows: Iterable[StoryDialogueTranslation],
    choice_rows: Iterable[StoryChoiceTranslation],
    *,
    encoding: str = "cp932",
) -> StoryLanguageAudit:
    dialogue = {(row.chunk_index, row.command_index): row for row in dialogue_rows}
    choices = {(row.chunk_index, row.command_index): row for row in choice_rows}
    offsets = _sda_offsets(translated)
    seen_dialogue: set[tuple[int, int]] = set()
    seen_choices: set[tuple[int, int]] = set()
    dialogue_commands = 0
    choice_commands = 0
    for chunk_index in range(len(offsets)):
        for command in parse_chunk_commands(translated, chunk_index):
            key = (chunk_index, command.command_index)
            if command.opcode == DIALOGUE_OPCODE:
                dialogue_commands += 1
                dialogue_row = dialogue.get(key)
                if dialogue_row is not None:
                    if command.payload_size != dialogue_row.payload_size:
                        raise VerificationError(
                            f"{dialogue_row.resource_id}: payload {command.payload_size} "
                            f"!= dataset {dialogue_row.payload_size}"
                        )
                    text = _decode_command_text(translated, command, encoding=encoding)
                    if text != dialogue_row.translation:
                        raise VerificationError(
                            f"{dialogue_row.resource_id}: translated text mismatch"
                        )
                    seen_dialogue.add(key)
            elif command.opcode == 0x1F03:
                choice_commands += 1
                choice_row = choices.get(key)
                if choice_row is None:
                    raise VerificationError(
                        f"{_stable_resource_id(chunk_index, command.command_index)}: "
                        "choice command missing from language dataset"
                    )
                if command.payload_size != choice_row.payload_size:
                    raise VerificationError(
                        f"{choice_row.resource_id}: payload {command.payload_size} "
                        f"!= dataset {choice_row.payload_size}"
                    )
                if (
                    _decode_choice_command(translated, command, encoding=encoding)
                    != choice_row.options
                ):
                    raise VerificationError(
                        f"{choice_row.resource_id}: choice options mismatch"
                    )
                seen_choices.add(key)
    missing_dialogue = set(dialogue) - seen_dialogue
    missing_choices = set(choices) - seen_choices
    if missing_dialogue or missing_choices:
        raise VerificationError(
            f"language dataset contains resources missing from translated SCRPACK: "
            f"dialogue={sorted(missing_dialogue)[:3]} choices={sorted(missing_choices)[:3]}"
        )
    return StoryLanguageAudit(
        dialogue_rows=len(dialogue),
        choice_rows=len(choices),
        dialogue_commands=dialogue_commands,
        choice_commands=choice_commands,
        chunks=len(offsets),
    )
