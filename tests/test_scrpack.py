from __future__ import annotations

import struct

import pytest

from botsd.errors import VerificationError
from botsd.scrpack import (
    parse_chunk_commands,
    relocate_probability_branch,
    replace_dialogue_command_text,
)


def _cmd(opcode: int, payload: bytes) -> bytes:
    return struct.pack("<HH", opcode, len(payload)) + payload


def _outer(chunks: list[bytes]) -> bytes:
    count = len(chunks)
    cursor = 12 + count * 4
    offsets = []
    body = bytearray()
    for chunk in chunks:
        offsets.append(cursor + len(body))
        body.extend(chunk)
    total = cursor + len(body)
    return b"sda\0" + struct.pack("<II", total, count) + struct.pack(
        f"<{count}I", *offsets
    ) + bytes(body)


def _branch_payload(probability: int, target: int) -> bytes:
    return b"\0\0" + struct.pack("<I", probability) + struct.pack("<I", target) + b"\0\0"


def test_scrpack_command_framing_and_branch_relocation_by_command_ordinal() -> None:
    commands = [
        _cmd(0x0001, b"AAAA"),
        _cmd(0x070C, _branch_payload(10, 0x1234)),
        _cmd(0x0002, b"BBBBBB"),
        _cmd(0x0103, b"CCCC"),
    ]
    blob = _outer([b"".join(commands)])
    parsed = parse_chunk_commands(blob, 0)
    assert [row.opcode for row in parsed] == [0x0001, 0x070C, 0x0002, 0x0103]
    target, report = relocate_probability_branch(
        blob,
        chunk_index=0,
        branch_command_index=1,
        target_command_index=3,
        probability=10,
    )
    reparsed = parse_chunk_commands(target, 0)
    assert report.new_target == reparsed[3].chunk_relative_offset
    assert report.old_target == 0x1234
    branch = reparsed[1]
    assert struct.unpack_from("<I", target, branch.file_offset + 10)[0] == report.new_target


def test_probability_branch_refuses_already_valid_target() -> None:
    first = _cmd(0x0001, b"")
    # Branch starts at relative 4 and target command starts after its 16-byte total size: 20.
    branch = _cmd(0x070C, _branch_payload(10, 20))
    target_cmd = _cmd(0x0103, b"")
    blob = _outer([first + branch + target_cmd])
    with pytest.raises(VerificationError, match="already a valid command boundary"):
        relocate_probability_branch(
            blob,
            chunk_index=0,
            branch_command_index=1,
            target_command_index=2,
            probability=10,
        )


def test_dialogue_edit_preserves_command_allocation_and_zero_fills_tail() -> None:
    source_text = "This sentence wraps badly."
    replacement = "This sentence#cr0wraps."
    encoded = source_text.encode("cp932")
    payload_size = 48
    prefix = b"\0" * 6 + struct.pack("<H", len(encoded))
    payload = prefix + encoded + b"\0" * (payload_size - len(prefix) - len(encoded))
    blob = _outer([_cmd(0x1D03, payload)])
    target, report = replace_dialogue_command_text(
        blob,
        chunk_index=0,
        command_index=0,
        source_text=source_text,
        replacement_text=replacement,
    )
    assert report.replacement_text == replacement
    before = parse_chunk_commands(blob, 0)[0]
    after = parse_chunk_commands(target, 0)[0]
    assert before == after
    assert struct.unpack_from("<H", target, after.file_offset + 10)[0] == len(
        replacement.encode("cp932")
    )
    start = after.file_offset + 12
    assert target[start : start + len(replacement)] == replacement.encode("cp932")
    assert set(target[start + len(replacement) : after.file_offset + after.total_size]) == {0}
