from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from .errors import VerificationError
from .keyboard import V13_FINAL_MODE, patch_mode
from .manifest import BASELINE, CARD_TEXT_LAYOUT


@dataclass(frozen=True)
class PointerOverlap:
    source_id: int
    source_pointer: int
    intruder_id: int
    intruder_pointer: int
    source_cstring_end: int


@dataclass(frozen=True)
class ExecutableMaintenanceResult:
    data: bytes
    overlap: PointerOverlap
    repaired_pointer: int
    keyboard_offset: int
    keyboard_old_mode: int
    keyboard_new_mode: int


def load_spec(path: str | Path | None = None) -> dict[str, Any]:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets").joinpath("exe_v13.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


def _master_pointers(source: bytes) -> tuple[int, ...]:
    table_offset = CARD_TEXT_LAYOUT.master_table_va - CARD_TEXT_LAYOUT.load_va_delta
    count = BASELINE.master_text_count
    end = table_offset + count * 4
    if not 0 <= table_offset <= end <= len(source):
        raise VerificationError("master pointer table is outside executable")
    return struct.unpack_from(f"<{count}I", source, table_offset)


def _cstring_end_va(source: bytes, pointer: int) -> int | None:
    offset = pointer - CARD_TEXT_LAYOUT.load_va_delta
    if not 0 <= offset < len(source):
        return None
    end = source.find(b"\0", offset)
    if end < 0:
        raise VerificationError(f"unterminated executable C string at VA 0x{pointer:X}")
    return end + CARD_TEXT_LAYOUT.load_va_delta + 1


def find_master_pointer_overlaps(source: bytes) -> tuple[PointerOverlap, ...]:
    """Return master pointers which land inside another master C string.

    This is the structural defect that caused the v1.2 Aura Pegasus name to flow directly into
    an unrelated rule string.  The audit intentionally derives the condition from the table and
    executable bytes instead of looking for the English card name.
    """
    pointers = _master_pointers(source)
    rows: list[PointerOverlap] = []
    ends: dict[int, int] = {}
    for pointer in set(pointers):
        end = _cstring_end_va(source, pointer)
        if end is not None:
            ends[pointer] = end

    for source_id, pointer in enumerate(pointers):
        end = ends.get(pointer)
        if end is None:
            continue
        for intruder_id, intruder in enumerate(pointers):
            if pointer < intruder < end:
                rows.append(
                    PointerOverlap(
                        source_id=source_id,
                        source_pointer=pointer,
                        intruder_id=intruder_id,
                        intruder_pointer=intruder,
                        source_cstring_end=end,
                    )
                )
    return tuple(rows)


def repair_single_master_overlap(
    source: bytes,
    *,
    expected_source_id: int,
    expected_intruder_id: int,
    shift_bytes: int,
) -> tuple[bytes, PointerOverlap, int]:
    """Repair the one proven v1.2 pointer-inside-string overlap semantically.

    The intended string bytes are the bytes from the damaged string's pointer up to the next
    master pointer which intrudes into that C string.  The v1.2 executable has exactly two zero
    bytes immediately before that string.  Moving the intended text left into those bytes creates
    room for a terminator without touching the following rule string.
    """
    if shift_bytes <= 0:
        raise ValueError("shift_bytes must be positive")
    overlaps = find_master_pointer_overlaps(source)
    if len(overlaps) != 1:
        raise VerificationError(
            f"expected exactly one master pointer overlap, found {len(overlaps)}"
        )
    overlap = overlaps[0]
    if (overlap.source_id, overlap.intruder_id) != (
        expected_source_id,
        expected_intruder_id,
    ):
        raise VerificationError(
            "unexpected master overlap: "
            f"{overlap.source_id}->{overlap.intruder_id}, expected "
            f"{expected_source_id}->{expected_intruder_id}"
        )

    delta = CARD_TEXT_LAYOUT.load_va_delta
    source_offset = overlap.source_pointer - delta
    intruder_offset = overlap.intruder_pointer - delta
    new_pointer = overlap.source_pointer - shift_bytes
    new_offset = source_offset - shift_bytes
    if new_offset < 0:
        raise VerificationError("overlap repair would move before executable start")
    if source[new_offset:source_offset] != b"\0" * shift_bytes:
        raise VerificationError("expected zero-byte slack before overlapping master string")
    intended = source[source_offset:intruder_offset]
    if not intended:
        raise VerificationError("overlap repair recovered an empty intended string")
    # The bytes up to the intruding pointer are the intended text.  They must not already contain
    # a NUL, otherwise there would be no C-string overlap in the first place.
    if b"\0" in intended:
        raise VerificationError("unexpected NUL inside intended overlapping master text")

    out = bytearray(source)
    out[new_offset : intruder_offset - shift_bytes] = intended
    out[intruder_offset - shift_bytes : intruder_offset] = b"\0" * shift_bytes
    table_offset = CARD_TEXT_LAYOUT.master_table_va - delta
    struct.pack_into("<I", out, table_offset + overlap.source_id * 4, new_pointer)
    repaired = bytes(out)

    # Prove the following string is untouched and the entire table is overlap-free afterward.
    intruder_tail_before = source[intruder_offset : overlap.source_cstring_end - delta]
    intruder_tail_after = repaired[intruder_offset : overlap.source_cstring_end - delta]
    if intruder_tail_after != intruder_tail_before:
        raise VerificationError("overlap repair modified the intruding master string")
    if find_master_pointer_overlaps(repaired):
        raise VerificationError("master pointer overlap remains after repair")
    pointers = _master_pointers(repaired)
    if pointers[overlap.source_id] != new_pointer:
        raise VerificationError("repaired master pointer did not persist")
    if pointers[overlap.intruder_id] != overlap.intruder_pointer:
        raise VerificationError("intruding master pointer unexpectedly changed")
    return repaired, overlap, new_pointer


def build_v13_executable(source: bytes, spec: dict[str, Any] | None = None) -> ExecutableMaintenanceResult:
    cfg = spec if spec is not None else load_spec()
    repair = cfg["master_overlap_repair"]
    repaired, overlap, new_pointer = repair_single_master_overlap(
        source,
        expected_source_id=int(repair["source_master_id"]),
        expected_intruder_id=int(repair["intruder_master_id"]),
        shift_bytes=int(repair["shift_bytes"]),
    )
    keyboard = cfg["keyboard"]
    old_mode = int(keyboard["old_mode"])
    new_mode = int(keyboard.get("new_mode", V13_FINAL_MODE))
    result = patch_mode(repaired, old_mode=old_mode, new_mode=new_mode)
    return ExecutableMaintenanceResult(
        data=result.data,
        overlap=overlap,
        repaired_pointer=new_pointer,
        keyboard_offset=result.offset,
        keyboard_old_mode=old_mode,
        keyboard_new_mode=new_mode,
    )
