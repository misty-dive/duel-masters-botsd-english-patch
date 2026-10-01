from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

MAX_CELLS = 24
EXPECTED_RULE_COUNT = 654


@dataclass(frozen=True)
class WrapReport:
    rules_verified: int
    rules_with_added_wraps: int
    new_linebreaks_inserted: int
    display_rows_synchronized: int
    max_line_cells_before: int
    max_line_cells_after: int
    max_wrapped_lines_per_rule: int


def cells(text: str) -> int:
    """Return the measured Card Info width in half-width cells.

    The established v1.3 rules corpus uses ASCII plus BLACK SQUARE. ASCII consumes one
    cell and BLACK SQUARE consumes two. Callers should reject any other non-ASCII glyphs
    before relying on this model.
    """
    return sum(1 if ord(ch) < 128 else 2 for ch in text)


def wrap_paragraph(paragraph: str, max_cells: int = MAX_CELLS) -> str:
    """Replace existing ASCII separator spaces with LF without changing character count."""
    if not paragraph:
        return paragraph
    chars = list(paragraph)
    words = list(re.finditer(r"[^ ]+", paragraph))
    too_long = [m.group() for m in words if cells(m.group()) > max_cells]
    if too_long:
        raise ValueError(f"token longer than panel width: {too_long!r}")

    line_start = 0
    previous = None
    for match in words:
        if previous is not None and cells(paragraph[line_start:match.end()]) > max_cells:
            sep_start = previous.end()
            sep_end = match.start()
            if sep_start >= sep_end or paragraph[sep_start:sep_end].strip(" "):
                raise ValueError("expected ASCII-space separator")
            chars[sep_start] = "\n"
            line_start = sep_start + 1
            if cells(paragraph[line_start:match.end()]) > max_cells:
                raise ValueError(
                    f"word plus preserved indentation exceeds width: {match.group()!r}"
                )
        previous = match

    wrapped = "".join(chars)
    if len(wrapped) != len(paragraph):
        raise AssertionError("wrap changed character count")
    for before, after in zip(paragraph, wrapped, strict=True):
        if before != after and not (before == " " and after == "\n"):
            raise AssertionError((before, after))
    return wrapped


def wrap_text(text: str, max_cells: int = MAX_CELLS) -> str:
    return "\n".join(wrap_paragraph(p, max_cells=max_cells) for p in text.split("\n"))


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing CSV header")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def wrap_rule_tables(
    master_rows: list[dict[str, str]],
    display_rows: list[dict[str, str]],
    *,
    max_cells: int = MAX_CELLS,
    expected_rule_count: int | None = EXPECTED_RULE_COUNT,
) -> WrapReport:
    rules: dict[int, str] = {}
    inserted = changed = 0
    max_before = max_after = 0
    line_counts: list[int] = []

    original_nonrules: dict[int, str] = {
        int(row["master_text_id"]): row.get("translation", "") for row in master_rows
    }

    for row in master_rows:
        roles = set((row.get("roles") or "").split("|"))
        if "rules" not in roles:
            continue
        mid = int(row["master_text_id"])
        text = row.get("translation", "")
        if not text or text == "<EMPTY>":
            raise ValueError(f"rule {mid} missing English translation")
        bad = sorted({ch for ch in text if ord(ch) >= 128 and ch != "■"})
        if bad:
            raise ValueError(f"rule {mid} unsupported width chars {bad!r}")

        before_lines = text.split("\n")
        max_before = max(max_before, max(cells(line) for line in before_lines))
        wrapped = wrap_text(text, max_cells=max_cells)
        if len(wrapped.encode("cp932")) != len(text.encode("cp932")):
            raise ValueError(f"rule {mid}: byte length changed")
        if normalize_whitespace(wrapped) != normalize_whitespace(text):
            raise ValueError(f"rule {mid}: semantic token stream changed")

        after_lines = wrapped.split("\n")
        widest = max(cells(line) for line in after_lines) if after_lines else 0
        if widest > max_cells:
            raise ValueError(f"rule {mid}: wrapped line still too wide: {widest}")
        max_after = max(max_after, widest)
        inserted += wrapped.count("\n") - text.count("\n")
        if wrapped != text:
            changed += 1
        row["translation"] = wrapped
        rules[mid] = wrapped
        line_counts.append(len(after_lines))

    if expected_rule_count is not None and len(rules) != expected_rule_count:
        raise ValueError(f"expected {expected_rule_count} rules, got {len(rules)}")

    display_count = 0
    for row in display_rows:
        master_id_text = (row.get("master_text_id") or "").strip()
        if master_id_text and int(master_id_text) in rules:
            row["translation"] = rules[int(master_id_text)]
            display_count += 1

    for row in master_rows:
        mid = int(row["master_text_id"])
        if mid not in rules and row.get("translation", "") != original_nonrules[mid]:
            raise ValueError(f"non-rule translation changed: {mid}")

    return WrapReport(
        rules_verified=len(rules),
        rules_with_added_wraps=changed,
        new_linebreaks_inserted=inserted,
        display_rows_synchronized=display_count,
        max_line_cells_before=max_before,
        max_line_cells_after=max_after,
        max_wrapped_lines_per_rule=max(line_counts, default=0),
    )
