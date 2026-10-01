from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .errors import FormatError, VerificationError


@dataclass(frozen=True)
class ScriptCommand:
    chunk_index: int
    command_index: int
    file_offset: int
    chunk_relative_offset: int
    opcode: int
    payload_size: int

    @property
    def total_size(self) -> int:
        return 4 + self.payload_size


@dataclass(frozen=True)
class BranchRelocation:
    chunk_index: int
    branch_command_index: int
    target_command_index: int
    old_target: int
    new_target: int


@dataclass(frozen=True)
class DialogueEdit:
    chunk_index: int
    command_index: int
    source_text: str
    replacement_text: str


@dataclass(frozen=True)
class ScrpackBuildResult:
    data: bytes
    branches: tuple[BranchRelocation, ...]
    dialogue_edits: tuple[DialogueEdit, ...]


def load_spec(path: str | Path | None = None) -> dict[str, Any]:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets").joinpath("scrpack_v13.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


def _sda_offsets(source: bytes) -> tuple[int, ...]:
    if len(source) < 12 or source[:4] != b"sda\0":
        raise FormatError("SCRPACK is not an sda\\0 archive")
    declared, count = struct.unpack_from("<II", source, 4)
    if declared != len(source):
        raise FormatError(f"SCRPACK declared size {declared} != actual {len(source)}")
    table_end = 12 + count * 4
    if table_end > len(source):
        raise FormatError("SCRPACK SDA offset table is truncated")
    offsets = struct.unpack_from(f"<{count}I", source, 12)
    if not offsets:
        raise FormatError("SCRPACK SDA has no chunks")
    previous = table_end
    for index, offset in enumerate(offsets):
        if not previous <= offset <= len(source):
            raise FormatError(f"SCRPACK chunk {index} offset is invalid: 0x{offset:X}")
        previous = offset
    return tuple(offsets)


def parse_chunk_commands(source: bytes, chunk_index: int) -> tuple[ScriptCommand, ...]:
    """Parse one SCRPACK script chunk using the reverse-engineered command framing.

    Each command begins with ``u16 opcode, u16 payload_size`` and occupies exactly
    ``4 + payload_size`` bytes.  Valid translated retail chunks consume their fixed SDA chunk
    allocation exactly, which makes command ordinals stable even when English changes lengths.
    """
    offsets = _sda_offsets(source)
    if not 0 <= chunk_index < len(offsets):
        raise IndexError(chunk_index)
    start = offsets[chunk_index]
    end = offsets[chunk_index + 1] if chunk_index + 1 < len(offsets) else len(source)
    rows: list[ScriptCommand] = []
    cursor = start
    command_index = 0
    while cursor < end:
        if cursor + 4 > end:
            raise FormatError(f"SCRPACK chunk {chunk_index}: truncated command header")
        opcode, payload_size = struct.unpack_from("<HH", source, cursor)
        command_end = cursor + 4 + payload_size
        if command_end > end:
            raise FormatError(
                f"SCRPACK chunk {chunk_index} command {command_index}: payload overruns chunk"
            )
        rows.append(
            ScriptCommand(
                chunk_index=chunk_index,
                command_index=command_index,
                file_offset=cursor,
                chunk_relative_offset=cursor - start,
                opcode=opcode,
                payload_size=payload_size,
            )
        )
        cursor = command_end
        command_index += 1
    if cursor != end:
        raise FormatError(f"SCRPACK chunk {chunk_index}: command stream does not end at chunk boundary")
    return tuple(rows)


def relocate_probability_branch(
    source: bytes,
    *,
    chunk_index: int,
    branch_command_index: int,
    target_command_index: int,
    opcode: int = 0x070C,
    probability: int | None = None,
) -> tuple[bytes, BranchRelocation]:
    commands = parse_chunk_commands(source, chunk_index)
    try:
        branch = commands[branch_command_index]
        target = commands[target_command_index]
    except IndexError as exc:
        raise VerificationError(
            f"SCRPACK chunk {chunk_index}: branch/target command ordinal is outside command stream"
        ) from exc
    if branch.opcode != opcode or branch.payload_size != 12:
        raise VerificationError(
            f"SCRPACK chunk {chunk_index} command {branch_command_index}: expected "
            f"probability branch opcode 0x{opcode:04X}/payload 12, got "
            f"0x{branch.opcode:04X}/{branch.payload_size}"
        )
    # Observed 0C/07 payload layout: u16 reserved, u32 percentage, u32 target, u16 reserved.
    probability_value = struct.unpack_from("<I", source, branch.file_offset + 6)[0]
    if probability is not None and probability_value != probability:
        raise VerificationError(
            f"SCRPACK chunk {chunk_index} command {branch_command_index}: probability "
            f"{probability_value} != expected {probability}"
        )
    old_target = struct.unpack_from("<I", source, branch.file_offset + 10)[0]
    new_target = target.chunk_relative_offset
    command_offsets = {row.chunk_relative_offset for row in commands}
    if old_target in command_offsets:
        raise VerificationError(
            f"SCRPACK chunk {chunk_index} command {branch_command_index}: branch target "
            f"0x{old_target:X} is already a valid command boundary"
        )
    if new_target not in command_offsets:
        raise AssertionError("selected SCRPACK target command is not a command boundary")

    out = bytearray(source)
    struct.pack_into("<I", out, branch.file_offset + 10, new_target)
    return bytes(out), BranchRelocation(
        chunk_index=chunk_index,
        branch_command_index=branch_command_index,
        target_command_index=target_command_index,
        old_target=old_target,
        new_target=new_target,
    )


def replace_dialogue_command_text(
    source: bytes,
    *,
    chunk_index: int,
    command_index: int,
    source_text: str,
    replacement_text: str,
    opcode: int = 0x1D03,
    encoding: str = "cp932",
) -> tuple[bytes, DialogueEdit]:
    commands = parse_chunk_commands(source, chunk_index)
    try:
        command = commands[command_index]
    except IndexError as exc:
        raise VerificationError(
            f"SCRPACK chunk {chunk_index}: dialogue command ordinal {command_index} is missing"
        ) from exc
    if command.opcode != opcode:
        raise VerificationError(
            f"SCRPACK chunk {chunk_index} command {command_index}: expected dialogue opcode "
            f"0x{opcode:04X}, got 0x{command.opcode:04X}"
        )
    if command.payload_size < 9:
        raise VerificationError("SCRPACK dialogue payload is too short")

    expected = source_text.encode(encoding)
    replacement = replacement_text.encode(encoding)
    # 1D03 command layout observed in the story scripts: six payload bytes, a u16 string length,
    # then a NUL-terminated string occupying the rest of the fixed command allocation.
    length_offset = command.file_offset + 10
    text_offset = command.file_offset + 12
    command_end = command.file_offset + command.total_size
    old_length = struct.unpack_from("<H", source, length_offset)[0]
    if old_length != len(expected):
        raise VerificationError(
            f"SCRPACK dialogue length {old_length} != expected source length {len(expected)}"
        )
    if source[text_offset : text_offset + old_length] != expected:
        raise VerificationError("SCRPACK dialogue source text does not match semantic recipe")
    capacity = command_end - text_offset
    if old_length > capacity:
        raise VerificationError(
            f"SCRPACK dialogue source length {old_length} exceeds allocation {capacity}"
        )
    # Length-delimited 1D03 strings either fill the remaining allocation exactly or are followed
    # by zero padding.  A NUL is therefore common but not required when length == capacity.
    if old_length < capacity and source[text_offset + old_length] != 0:
        raise VerificationError("SCRPACK dialogue source padding does not begin with NUL")
    if len(replacement) > capacity:
        raise VerificationError(
            f"SCRPACK replacement needs {len(replacement)} bytes, allocation is {capacity}"
        )

    out = bytearray(source)
    struct.pack_into("<H", out, length_offset, len(replacement))
    out[text_offset:command_end] = replacement + b"\0" * (capacity - len(replacement))
    result = bytes(out)
    # The command framing and total chunk allocation must remain unchanged.
    after = parse_chunk_commands(result, chunk_index)
    if len(after) != len(commands):
        raise VerificationError("SCRPACK dialogue edit changed command count")
    if after[command_index] != command:
        raise VerificationError("SCRPACK dialogue edit changed command framing")
    return result, DialogueEdit(chunk_index, command_index, source_text, replacement_text)


def build_v13_scrpack(
    source: bytes,
    strings: Mapping[str, Any],
    spec: dict[str, Any] | None = None,
) -> ScrpackBuildResult:
    cfg = spec if spec is not None else load_spec()
    out = source
    branches: list[BranchRelocation] = []
    for row in cfg["branch_relocations"]:
        out, branch_report = relocate_probability_branch(
            out,
            chunk_index=int(row["chunk"]),
            branch_command_index=int(row["branch_command_index"]),
            target_command_index=int(row["target_command_index"]),
            opcode=int(str(row.get("opcode", "0x070C")), 0),
            probability=int(row["probability"]) if "probability" in row else None,
        )
        branches.append(branch_report)

    edits: list[DialogueEdit] = []
    dialogue_map = strings.get("dialogue", {})
    if not isinstance(dialogue_map, Mapping):
        raise ValueError("v1.3 maintenance localization dialogue map must be an object")
    for row in cfg.get("dialogue_edits", []):
        key = str(row["string_key"])
        payload = dialogue_map.get(key)
        if not isinstance(payload, Mapping):
            raise ValueError(f"missing v1.3 maintenance dialogue localization key {key!r}")
        source_text = str(payload["source"])
        replacement_text = str(payload["replacement"])
        out, dialogue_report = replace_dialogue_command_text(
            out,
            chunk_index=int(row["chunk"]),
            command_index=int(row["command_index"]),
            source_text=source_text,
            replacement_text=replacement_text,
            opcode=int(str(row.get("opcode", "0x1D03")), 0),
        )
        edits.append(dialogue_report)
    return ScrpackBuildResult(out, tuple(branches), tuple(edits))
