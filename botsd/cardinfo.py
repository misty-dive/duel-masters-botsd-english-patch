from __future__ import annotations

import bisect
import csv
import hashlib
import json
import struct
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from .cardtext import decode_game_text, encode_cp932
from .errors import FormatError, HashMismatchError, VerificationError


@dataclass(frozen=True)
class CardInfoSpec:
    expected_input_sha256: str
    load_va_delta: int
    master_table_va: int
    master_count: int
    rule_count: int
    race_pointer_table_va: int
    race_count: int
    race_overflow_start: int
    race_overflow_limit: int
    reserved_data: tuple[tuple[int, int], ...]
    safe_slack: tuple[int, int]
    slack_pointer_guard: int
    getter_vas: tuple[int, ...]
    getter_length: int
    loader_cave_va: int
    loader_cave_length: int
    canary_rule_ids: tuple[int, ...]


@dataclass(frozen=True)
class CardInfoBuildResult:
    data: bytes
    rule_ids: tuple[int, ...]
    blocked_rule_intervals: int
    safe_rule_bytes: int
    allocation_pool_bytes: int
    allocation_bytes_remaining: int
    slack_segments: tuple[tuple[int, int], ...]
    slack_pointer_targets: tuple[int, ...]
    race_rows: int
    differing_bytes: int
    report_lines: tuple[str, ...]


def _int(value: int | str) -> int:
    return value if isinstance(value, int) else int(value, 0)


def load_spec(path: str | Path | None = None) -> CardInfoSpec:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/cardinfo_ui76.json").read_text(encoding="utf-8")
    )
    raw = json.loads(text)
    protected = raw["protected_code"]
    return CardInfoSpec(
        expected_input_sha256=str(raw["expected_input_sha256"]),
        load_va_delta=_int(raw["load_va_delta"]),
        master_table_va=_int(raw["master_table_va"]),
        master_count=int(raw["master_count"]),
        rule_count=int(raw["rule_count"]),
        race_pointer_table_va=_int(raw["race_pointer_table_va"]),
        race_count=int(raw["race_count"]),
        race_overflow_start=_int(raw["race_overflow_start"]),
        race_overflow_limit=_int(raw["race_overflow_limit"]),
        reserved_data=tuple((_int(a), _int(z)) for a, z in raw["reserved_data"]),
        safe_slack=(_int(raw["safe_slack"][0]), _int(raw["safe_slack"][1])),
        slack_pointer_guard=_int(raw["slack_pointer_guard"]),
        getter_vas=tuple(_int(value) for value in protected["getter_vas"]),
        getter_length=int(protected["getter_length"]),
        loader_cave_va=_int(protected["loader_cave_va"]),
        loader_cave_length=int(protected["loader_cave_length"]),
        canary_rule_ids=tuple(int(value) for value in raw["canary_rule_ids"]),
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def va_to_offset(va: int, spec: CardInfoSpec) -> int:
    return va - spec.load_va_delta


def decode_cstr(blob: bytes, va: int, spec: CardInfoSpec) -> str:
    offset = va_to_offset(va, spec)
    if not 0 <= offset < len(blob):
        raise FormatError(f"pointer outside executable: 0x{va:X}")
    end = blob.find(b"\0", offset)
    if end < 0:
        raise FormatError(f"unterminated string at 0x{va:X}")
    return decode_game_text(blob[offset:end])


def cstr_interval(blob: bytes, va: int, spec: CardInfoSpec) -> tuple[int, int]:
    offset = va_to_offset(va, spec)
    if not 0 <= offset < len(blob):
        raise FormatError(f"pointer outside executable: 0x{va:X}")
    end = blob.find(b"\0", offset)
    if end < 0:
        raise FormatError(f"unterminated string at 0x{va:X}")
    return va, end + spec.load_va_delta + 1


def load_master_rows(path: str | Path, expected_count: int) -> dict[int, dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = {
            int(row["master_text_id"]): {key: value or "" for key, value in row.items()}
            for row in csv.DictReader(handle)
        }
    expected = set(range(expected_count))
    if set(rows) != expected:
        missing = sorted(expected - set(rows))
        extra = sorted(set(rows) - expected)
        raise ValueError(
            f"master CSV IDs are not exactly 0..{expected_count - 1}; "
            f"missing={missing[:8]} extra={extra[:8]}"
        )
    return rows


def merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def subtract_ranges(
    ranges: Iterable[tuple[int, int]], blocked: Iterable[tuple[int, int]]
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    blockers = merge_ranges(blocked)
    for start, end in merge_ranges(ranges):
        current = [(start, end)]
        for bstart, bend in blockers:
            next_ranges: list[tuple[int, int]] = []
            for left, right in current:
                if bend <= left or bstart >= right:
                    next_ranges.append((left, right))
                else:
                    if left < bstart:
                        next_ranges.append((left, bstart))
                    if bend < right:
                        next_ranges.append((bend, right))
            current = next_ranges
        result.extend(current)
    return merge_ranges(result)


def decoded_mips_memory_refs(source: bytes, start: int, end: int, spec: CardInfoSpec):
    """Conservatively detect LUI-derived absolute memory references into a range."""
    text_start, text_end = 0x100000, 0x439CB0
    mem_ops = {
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
        0x28, 0x29, 0x2A, 0x2B, 0x2E, 0x2F, 0x31, 0x35, 0x39, 0x3D,
    }
    hits: list[tuple[int, int, int, int]] = []
    upper = min(text_end, spec.load_va_delta + len(source))
    for va in range(text_start, upper, 4):
        offset = va_to_offset(va, spec)
        if offset < 0 or offset + 4 > len(source):
            continue
        word = struct.unpack_from("<I", source, offset)[0]
        if word >> 26 != 0x0F:
            continue
        register = (word >> 16) & 31
        current = (word & 0xFFFF) << 16
        for step in range(1, 13):
            va2 = va + step * 4
            offset2 = va_to_offset(va2, spec)
            if va2 >= upper or offset2 < 0 or offset2 + 4 > len(source):
                break
            word2 = struct.unpack_from("<I", source, offset2)[0]
            op = word2 >> 26
            rs = (word2 >> 21) & 31
            rt = (word2 >> 16) & 31
            imm = word2 & 0xFFFF
            simm = imm if imm < 0x8000 else imm - 0x10000
            if op in mem_ops and rs == register:
                address = (current + simm) & 0xFFFFFFFF
                if start <= address < end:
                    hits.append((va, va2, address, op))
            if rt == register:
                if op in (0x09, 0x19) and rs == register:
                    current = (current + simm) & 0xFFFFFFFF
                elif op == 0x0D and rs == register:
                    current |= imm
                elif op == 0x0F:
                    current = imm << 16
                elif op in mem_ops:
                    break
                elif op != 0:
                    break
            if op == 0:
                rd = (word2 >> 11) & 31
                if rd == register and rd != 0:
                    break
    return hits


def verified_slack_segments(source: bytes, spec: CardInfoSpec):
    start, end = spec.safe_slack
    o1, o2 = va_to_offset(start, spec), va_to_offset(end, spec)
    if o1 < 0 or o2 > len(source):
        raise FormatError("Card Info slack range lies outside executable")
    if any(source[o1:o2]):
        raise VerificationError(f"Card Info slack 0x{start:X}-0x{end:X} is not all zero")
    memrefs = decoded_mips_memory_refs(source, start, end, spec)
    if memrefs:
        raise VerificationError(f"Card Info slack has decoded MIPS memory refs: {memrefs[:8]}")

    targets: set[int] = set()
    for offset in range(0, len(source) - 3, 4):
        value = struct.unpack_from("<I", source, offset)[0]
        if start <= value < end:
            targets.add(value)
    blocked = [
        (max(start, value - spec.slack_pointer_guard), min(end, value + spec.slack_pointer_guard))
        for value in sorted(targets)
    ]
    segments = subtract_ranges([(start, end)], blocked)
    if not segments:
        raise VerificationError("all Card Info slack eliminated by conservative pointer guards")
    return segments, sorted(targets), memrefs


def load_race_map(rows: dict[int, dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows.values():
        roles = set((row.get("roles") or "").split("|"))
        japanese = row.get("source_japanese") or ""
        english = row.get("translation") or ""
        if "race" in roles and japanese and english and english != "<EMPTY>":
            result.setdefault(japanese, english)
    return result


def patch_races(
    source: bytes,
    output: bytearray,
    rows: dict[int, dict[str, str]],
    spec: CardInfoSpec,
    changes: list[tuple[int, int, str]],
):
    race_map = load_race_map(rows)
    table_offset = va_to_offset(spec.race_pointer_table_va, spec)
    pointers = struct.unpack_from(f"<{spec.race_count}I", source, table_offset)
    pool = spec.race_overflow_start
    patched: list[tuple[int, int, str, str]] = []
    for index, pointer in enumerate(pointers):
        start, end = cstr_interval(source, pointer, spec)
        old = source[va_to_offset(start, spec) : va_to_offset(end, spec)]
        japanese = old[:-1].decode("cp932", errors="strict")
        english = race_map.get(japanese)
        if not english:
            raise ValueError(f"no canonical race translation for table row {index}: {japanese!r}")
        encoded = encode_cp932(english, f"race[{index}]") + b"\0"
        final_pointer = pointer
        if len(encoded) <= len(old):
            replacement = encoded + b"\0" * (len(old) - len(encoded))
            if replacement != old:
                a, z = va_to_offset(start, spec), va_to_offset(end, spec)
                output[a:z] = replacement
                changes.append((a, z, f"race string {index}: {japanese} -> {english}"))
        else:
            pool = (pool + 3) & ~3
            if pool + len(encoded) > spec.race_overflow_limit:
                raise VerificationError("race overflow pool exhausted")
            start_offset = va_to_offset(pool, spec)
            if any(source[start_offset : start_offset + len(encoded)]):
                raise VerificationError(f"race overflow destination not zero: 0x{pool:X}")
            output[start_offset : start_offset + len(encoded)] = encoded
            changes.append((start_offset, start_offset + len(encoded), f"race overflow {index}: {english}"))
            pointer_offset = table_offset + index * 4
            output[pointer_offset : pointer_offset + 4] = struct.pack("<I", pool)
            changes.append((pointer_offset, pointer_offset + 4, f"race pointer {index} -> 0x{pool:X}"))
            final_pointer = pool
            pool += len(encoded)
        patched.append((index, final_pointer, japanese, english))
    return patched, pool


def build_safe_rule_pool(
    source: bytes,
    pointers: tuple[int, ...],
    rule_ids: list[int],
    spec: CardInfoSpec,
):
    rule_set = set(rule_ids)
    intervals = {pointer: cstr_interval(source, pointer, spec) for pointer in sorted({pointers[i] for i in rule_ids})}
    ranges = sorted(intervals.values())
    starts = [start for start, _ in ranges]

    def containing(value: int):
        index = bisect.bisect_right(starts, value) - 1
        if index >= 0 and value < ranges[index][1]:
            return ranges[index]
        return None

    blocked: set[int] = set()
    reasons: list[tuple[str, int, int, tuple[int, int]]] = []
    for index, pointer in enumerate(pointers):
        if index in rule_set:
            continue
        interval = containing(pointer)
        if interval:
            blocked.add(interval[0])
            reasons.append(("nonrule_master", index, pointer, interval))

    table_offset = va_to_offset(spec.master_table_va, spec)
    rule_slots = {table_offset + index * 4 for index in rule_ids}
    for offset in range(0, len(source) - 3, 4):
        if offset in rule_slots:
            continue
        value = struct.unpack_from("<I", source, offset)[0]
        interval = containing(value)
        if interval:
            blocked.add(interval[0])
            reasons.append(("other_ptr", offset + spec.load_va_delta, value, interval))

    free = [interval for pointer, interval in intervals.items() if pointer not in blocked]
    free = subtract_ranges(free, spec.reserved_data)
    slack, slack_targets, slack_memrefs = verified_slack_segments(source, spec)
    return (
        merge_ranges(free + slack),
        blocked,
        reasons,
        intervals,
        slack,
        slack_targets,
        slack_memrefs,
    )


def allocate_deduplicated(
    texts: dict[bytes, list[int]], pool: list[tuple[int, int]]
) -> tuple[dict[bytes, int], list[list[int]]]:
    segments = [[start, end] for start, end in pool]
    allocation: dict[bytes, int] = {}
    for raw, ids in sorted(texts.items(), key=lambda item: (-len(item[0]), item[0])):
        candidates = [(end - start, index, start) for index, (start, end) in enumerate(segments) if end - start >= len(raw)]
        if not candidates:
            raise VerificationError(
                f"not enough safe embedded space for rule IDs {ids[:8]} ({len(raw)} bytes)"
            )
        _, index, _ = min(candidates)
        start, _ = segments[index]
        allocation[raw] = start
        segments[index][0] = start + len(raw)
    return allocation, segments


def build_embedded_cardinfo(
    source: bytes,
    master_csv: str | Path,
    *,
    spec: CardInfoSpec | None = None,
    verify_input_hash: bool = True,
) -> CardInfoBuildResult:
    spec = spec or load_spec()
    got_hash = sha256(source)
    if verify_input_hash and got_hash != spec.expected_input_sha256:
        raise HashMismatchError(
            f"Card Info input SHA-256 {got_hash} != expected {spec.expected_input_sha256}"
        )
    rows = load_master_rows(master_csv, spec.master_count)
    table_offset = va_to_offset(spec.master_table_va, spec)
    if table_offset < 0 or table_offset + spec.master_count * 4 > len(source):
        raise FormatError("master pointer table lies outside executable")
    pointers = struct.unpack_from(f"<{spec.master_count}I", source, table_offset)
    rule_ids = sorted(
        index
        for index, row in rows.items()
        if "rules" in set((row.get("roles") or "").split("|"))
    )
    if len(rule_ids) != spec.rule_count:
        raise VerificationError(f"expected {spec.rule_count} rule rows, got {len(rule_ids)}")

    for index in rule_ids:
        embedded = decode_cstr(source, pointers[index], spec)
        expected = rows[index].get("source_japanese") or ""
        if embedded != expected:
            raise VerificationError(
                f"embedded source mismatch at rule ID {index}: {embedded!r} != {expected!r}"
            )
        if not rows[index].get("translation"):
            raise VerificationError(f"rule ID {index} lacks English translation")

    protected = {
        va: source[va_to_offset(va, spec) : va_to_offset(va, spec) + spec.getter_length]
        for va in spec.getter_vas
    }
    protected[spec.loader_cave_va] = source[
        va_to_offset(spec.loader_cave_va, spec) :
        va_to_offset(spec.loader_cave_va, spec) + spec.loader_cave_length
    ]
    nonrule_ids = set(range(spec.master_count)) - set(rule_ids)
    nonrule_pointers = {index: pointers[index] for index in nonrule_ids}

    (
        pool,
        blocked,
        reasons,
        intervals,
        slack,
        slack_targets,
        slack_memrefs,
    ) = build_safe_rule_pool(source, pointers, rule_ids, spec)
    if not pool:
        raise VerificationError("no safe embedded rule repack pool")

    id_raw: dict[int, bytes] = {}
    dedup: dict[bytes, list[int]] = {}
    for index in rule_ids:
        text = rows[index]["translation"]
        encoded = encode_cp932("" if text == "<EMPTY>" else text, f"rule[{index}]") + b"\0"
        id_raw[index] = encoded
        dedup.setdefault(encoded, []).append(index)
    allocation, remaining = allocate_deduplicated(dedup, pool)

    output = bytearray(source)
    changes: list[tuple[int, int, str]] = []
    safe_rule_intervals = [interval for pointer, interval in intervals.items() if pointer not in blocked]
    safe_rule_intervals = subtract_ranges(safe_rule_intervals, spec.reserved_data)
    for start, end in safe_rule_intervals:
        a, z = va_to_offset(start, spec), va_to_offset(end, spec)
        if any(output[a:z]):
            output[a:z] = b"\0" * (z - a)
            changes.append((a, z, f"reclaim embedded Japanese rule pool 0x{start:X}-0x{end:X}"))

    for raw, va in sorted(allocation.items(), key=lambda item: item[1]):
        offset = va_to_offset(va, spec)
        output[offset : offset + len(raw)] = raw
        changes.append((offset, offset + len(raw), f"English rule text at 0x{va:X}"))

    for index in rule_ids:
        va = allocation[id_raw[index]]
        offset = table_offset + index * 4
        output[offset : offset + 4] = struct.pack("<I", va)
        changes.append((offset, offset + 4, f"master rule pointer {index} -> 0x{va:X}"))

    race_rows, race_pool_end = patch_races(source, output, rows, spec, changes)
    result = bytes(output)
    if len(result) != len(source):
        raise VerificationError("executable size changed")

    for va, blob in protected.items():
        offset = va_to_offset(va, spec)
        if result[offset : offset + len(blob)] != blob:
            raise VerificationError(f"protected CardText code changed at 0x{va:X}")

    new_pointers = struct.unpack_from(f"<{spec.master_count}I", result, table_offset)
    for index, pointer in nonrule_pointers.items():
        if new_pointers[index] != pointer:
            raise VerificationError(f"non-rule master pointer changed at ID {index}")
    for index in rule_ids:
        if decode_cstr(result, new_pointers[index], spec) != rows[index]["translation"]:
            raise VerificationError(f"English embedded rule verify failed at ID {index}")

    race_pointers = struct.unpack_from(f"<{spec.race_count}I", result, va_to_offset(spec.race_pointer_table_va, spec))
    race_map = load_race_map(rows)
    original_race_pointers = struct.unpack_from(f"<{spec.race_count}I", source, va_to_offset(spec.race_pointer_table_va, spec))
    for index, pointer in enumerate(race_pointers):
        japanese = decode_cstr(source, original_race_pointers[index], spec)
        if decode_cstr(result, pointer, spec) != race_map[japanese]:
            raise VerificationError(f"race verify failed at row {index}")

    allowed = bytearray(len(source))
    for start, end, _ in changes:
        allowed[start:end] = b"\1" * (end - start)
    diffs = [index for index, (a, b) in enumerate(zip(source, result, strict=True)) if a != b]
    unexpected = [index for index in diffs if not allowed[index]]
    if unexpected:
        raise VerificationError(f"unexpected Card Info diff offsets: {unexpected[:20]}")

    for index in spec.canary_rule_ids:
        if index in rule_ids and decode_cstr(result, new_pointers[index], spec) != rows[index]["translation"]:
            raise VerificationError(f"Card Info canary failed at rule ID {index}")

    free_left = sum(end - start for start, end in remaining)
    safe_rule_bytes = sum(end - start for start, end in safe_rule_intervals)
    lines = [
        "UI76 EMBEDDED ENGLISH CARD INFO: PASS",
        f"input_sha256={got_hash}",
        f"output_sha256={sha256(result)}",
        f"file_size={len(result)}",
        f"differing_bytes={len(diffs)}",
        f"rule_master_ids={len(rule_ids)}",
        f"unique_original_rule_strings={len(intervals)}",
        f"conservatively_blocked_rule_intervals={len(blocked)}",
        f"safe_reclaimed_original_rule_bytes={safe_rule_bytes}",
        f"unique_english_rule_strings={len(dedup)}",
        f"safe_allocation_pool_bytes={sum(end-start for start,end in pool)}",
        f"guarded_zero_slack_segments={len(slack)}",
        f"pointer_like_slack_targets={len(slack_targets)}",
        f"decoded_mips_memory_accesses_into_slack={len(slack_memrefs)}",
        f"allocation_bytes_remaining={free_left}",
        f"race_rows_localized={len(race_rows)}",
        f"race_overflow_pool_end=0x{race_pool_end:X}",
        f"reference_records_blocking_rules={len(reasons)}",
        "protected_cardtext_getters=BYTE-IDENTICAL",
        "protected_list_loader_cave=BYTE-IDENTICAL",
        "non_rule_master_pointers=BYTE-IDENTICAL",
        "RESULT=PASS",
    ]
    return CardInfoBuildResult(
        result,
        tuple(rule_ids),
        len(blocked),
        safe_rule_bytes,
        sum(end - start for start, end in pool),
        free_left,
        tuple(slack),
        tuple(slack_targets),
        len(race_rows),
        len(diffs),
        tuple(lines),
    )
