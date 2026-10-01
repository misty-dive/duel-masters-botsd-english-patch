from __future__ import annotations

import struct

from botsd.exe_maintenance import find_master_pointer_overlaps, repair_single_master_overlap
from botsd.manifest import BASELINE, CARD_TEXT_LAYOUT


def _synthetic_executable() -> bytes:
    table_offset = CARD_TEXT_LAYOUT.master_table_va - CARD_TEXT_LAYOUT.load_va_delta
    string_offset = table_offset + BASELINE.master_text_count * 4 + 0x100
    size = string_offset + 0x400
    data = bytearray(size)
    safe_va = string_offset + CARD_TEXT_LAYOUT.load_va_delta
    # Every unrelated row points at one valid empty string.
    for index in range(BASELINE.master_text_count):
        struct.pack_into("<I", data, table_offset + index * 4, safe_va)
    data[string_offset] = 0

    source_id = 2372
    intruder_id = 1161
    damaged_offset = string_offset + 0x80
    damaged_va = damaged_offset + CARD_TEXT_LAYOUT.load_va_delta
    intruder_offset = damaged_offset + 5
    intruder_va = intruder_offset + CARD_TEXT_LAYOUT.load_va_delta
    # Two zero bytes immediately precede the intended text.  Its missing terminator causes the
    # source C string to continue into the intruding string.
    data[damaged_offset : damaged_offset + 5] = b"ABCDE"
    data[intruder_offset : intruder_offset + 6] = b"WORLD\0"
    struct.pack_into("<I", data, table_offset + source_id * 4, damaged_va)
    struct.pack_into("<I", data, table_offset + intruder_id * 4, intruder_va)
    return bytes(data)


def test_master_overlap_is_discovered_structurally_and_repaired_without_text_literal() -> None:
    source = _synthetic_executable()
    overlaps = find_master_pointer_overlaps(source)
    assert len(overlaps) == 1
    assert (overlaps[0].source_id, overlaps[0].intruder_id) == (2372, 1161)
    target, overlap, new_pointer = repair_single_master_overlap(
        source,
        expected_source_id=2372,
        expected_intruder_id=1161,
        shift_bytes=2,
    )
    assert new_pointer == overlap.source_pointer - 2
    assert find_master_pointer_overlaps(target) == ()
    delta = CARD_TEXT_LAYOUT.load_va_delta
    start = new_pointer - delta
    assert target[start : start + 6] == b"ABCDE\0"
    intruder = overlap.intruder_pointer - delta
    assert target[intruder : intruder + 6] == b"WORLD\0"
