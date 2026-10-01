from __future__ import annotations

import struct

from botsd.cardinfo import (
    CardInfoSpec,
    allocate_deduplicated,
    cstr_interval,
    decode_cstr,
    load_spec,
    merge_ranges,
    subtract_ranges,
    va_to_offset,
)


def tiny_spec() -> CardInfoSpec:
    return CardInfoSpec(
        expected_input_sha256="0" * 64,
        load_va_delta=0x1000,
        master_table_va=0x1100,
        master_count=4,
        rule_count=2,
        race_pointer_table_va=0x1200,
        race_count=1,
        race_overflow_start=0x1500,
        race_overflow_limit=0x1600,
        reserved_data=((0x1580, 0x1590),),
        safe_slack=(0x1400, 0x1500),
        slack_pointer_guard=0x10,
        getter_vas=(0x1010,),
        getter_length=4,
        loader_cave_va=0x1020,
        loader_cave_length=4,
        canary_rule_ids=(1,),
    )


def test_release_cardinfo_spec_tracks_known_layout() -> None:
    spec = load_spec()
    assert spec.master_table_va == 0x444268
    assert spec.master_count == 2376
    assert spec.rule_count == 654
    assert spec.race_pointer_table_va == 0x4436D8
    assert spec.race_count == 65
    assert spec.safe_slack == (0x46A5AC, 0x470000)


def test_cstring_helpers_use_virtual_addresses() -> None:
    spec = tiny_spec()
    blob = bytearray(0x800)
    blob[0x300:0x306] = b"Hello\0"
    assert va_to_offset(0x1300, spec) == 0x300
    assert decode_cstr(bytes(blob), 0x1300, spec) == "Hello"
    assert cstr_interval(bytes(blob), 0x1300, spec) == (0x1300, 0x1306)


def test_range_operations_are_deterministic() -> None:
    assert merge_ranges([(10, 20), (5, 8), (8, 12), (30, 31)]) == [(5, 20), (30, 31)]
    assert subtract_ranges([(0, 20)], [(3, 5), (10, 15)]) == [(0, 3), (5, 10), (15, 20)]


def test_deduplicated_allocator_prefers_best_fit() -> None:
    texts = {b"longer\0": [1], b"x\0": [2, 3]}
    allocation, remaining = allocate_deduplicated(texts, [(0x1000, 0x100A), (0x2000, 0x2010)])
    assert allocation[b"longer\0"] == 0x1000
    assert allocation[b"x\0"] == 0x1007
    assert remaining == [[0x1009, 0x100A], [0x2000, 0x2010]]


def test_cardinfo_spec_can_describe_pointer_tables() -> None:
    spec = tiny_spec()
    blob = bytearray(0x400)
    table = va_to_offset(spec.master_table_va, spec)
    struct.pack_into("<4I", blob, table, 0x1300, 0x1310, 0x1320, 0x1330)
    assert struct.unpack_from("<4I", blob, table)[2] == 0x1320
