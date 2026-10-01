from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hashing import sha256_bytes


@dataclass(frozen=True)
class ExecStringPatchResult:
    data: bytes
    differing_bytes: int
    report_lines: tuple[str, ...]


def decode_cstr(data: bytes, offset: int, size: int | None = None) -> str:
    end = len(data) if size is None else min(len(data), offset + size)
    raw = data[offset:end].split(b"\0", 1)[0]
    return raw.decode("cp932", errors="strict")


def load_asset_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_strings(path: str | Path) -> dict[str, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    strings = raw.get("strings")
    if not isinstance(strings, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in strings.items()):
        raise ValueError(f"invalid executable-string localization file: {path}")
    return strings


def patch_fixed_slots(
    source: bytes,
    spec: dict[str, Any],
    strings: dict[str, str],
    *,
    verify_input_hash: bool = True,
) -> ExecStringPatchResult:
    input_hash = sha256_bytes(source)
    expected = spec.get("input_sha256")
    if verify_input_hash and expected and input_hash != expected:
        raise ValueError(f"executable source SHA-256 {input_hash} != expected {expected}")

    for guard in spec.get("guards", []):
        offset = int(guard["offset"])
        expected_text = str(guard["expected"])
        got = decode_cstr(source, offset, 160)
        if got != expected_text:
            raise ValueError(f"guard 0x{offset:X}: {got!r} != {expected_text!r}")

    out = bytearray(source)
    allowed: list[tuple[int, int]] = []
    lines = [f"input_sha256={input_hash}"]
    slot_ids: set[str] = set()
    for row in spec.get("slots", []):
        slot_id = str(row["id"])
        if slot_id in slot_ids:
            raise ValueError(f"duplicate executable string slot id: {slot_id}")
        slot_ids.add(slot_id)
        if slot_id not in strings:
            raise ValueError(f"missing localized executable string: {slot_id}")
        offset = int(row["offset"])
        size = int(row["size"])
        text = strings[slot_id]
        encoded = text.encode("cp932", errors="strict")
        if len(encoded) + 1 > size:
            raise ValueError(f"{slot_id}: {len(encoded)} bytes will not fit {size - 1}")
        old = decode_cstr(source, offset, size)
        out[offset : offset + size] = encoded + b"\0" * (size - len(encoded))
        allowed.append((offset, offset + size))
        lines.append(
            f"{slot_id} @0x{offset:X} size=0x{size:X}: {old!r} -> {text!r} "
            f"({len(encoded)}/{size - 1})"
        )

    extra_strings = sorted(set(strings) - slot_ids)
    if extra_strings:
        raise ValueError(f"localized executable strings have no slot metadata: {extra_strings}")

    output = bytes(out)
    diffs = [index for index, (before, after) in enumerate(zip(source, output, strict=True)) if before != after]
    outside = [
        index
        for index in diffs
        if not any(start <= index < end for start, end in allowed)
    ]
    if outside:
        raise RuntimeError(f"changed outside approved executable slots: {outside[:16]}")

    unchanged = spec.get("network_unchanged_range")
    if unchanged is not None:
        start, end = (int(value) for value in unchanged)
        if output[start:end] != source[start:end]:
            raise RuntimeError(f"protected executable range 0x{start:X}-0x{end:X} changed")

    for row in spec.get("slots", []):
        slot_id = str(row["id"])
        offset = int(row["offset"])
        size = int(row["size"])
        if decode_cstr(output, offset, size) != strings[slot_id]:
            raise RuntimeError(f"executable string verification failed for {slot_id}")

    lines += [
        f"output_sha256={sha256_bytes(output)}",
        f"differing_bytes={len(diffs)}",
        f"patched_slots={len(slot_ids)}",
        "containment=PASS",
    ]
    if unchanged is not None:
        start, end = (int(value) for value in unchanged)
        lines.append(f"protected_range_0x{start:X}-0x{end:X}=UNCHANGED")
    return ExecStringPatchResult(output, len(diffs), tuple(lines))
