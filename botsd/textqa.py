from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

FULLWIDTH_LATIN_RE = re.compile(r"[Ａ-Ｚａ-ｚ０-９]")
JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
LINE_BREAK_RE = re.compile(r"#cr0|\r?\n")


@dataclass(frozen=True)
class TextFinding:
    kind: str
    text: str
    source: str | None = None
    row: int | None = None
    field: str | None = None


def scan_english_text(text: str, *, max_segment: int | None = None) -> list[TextFinding]:
    findings: list[TextFinding] = []
    if FULLWIDTH_LATIN_RE.search(text):
        findings.append(TextFinding("fullwidth_latin", text))
    if JAPANESE_RE.search(text):
        findings.append(TextFinding("japanese", text))
    if "~" in text:
        findings.append(TextFinding("reserved_tilde", text))
    try:
        text.replace("Ü", "~").encode("cp932", errors="strict")
    except UnicodeEncodeError:
        findings.append(TextFinding("cp932_unencodable", text))
    if max_segment is not None:
        if max_segment < 1:
            raise ValueError("max_segment must be positive")
        if any(len(segment) > max_segment for segment in LINE_BREAK_RE.split(text)):
            findings.append(TextFinding("long_segment", text))
    return findings


def scan_csv_fields(
    path: str | Path,
    fields: tuple[str, ...],
    *,
    max_segment: int | None = None,
) -> list[TextFinding]:
    """Audit selected English/localized CSV columns without flagging source-Japanese fields."""
    csv_path = Path(path)
    findings: list[TextFinding] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [field for field in fields if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{csv_path}: missing requested fields {missing}")
        for row_number, row in enumerate(reader, start=2):
            for field in fields:
                value = row.get(field) or ""
                for finding in scan_english_text(value, max_segment=max_segment):
                    findings.append(
                        TextFinding(
                            finding.kind,
                            finding.text,
                            source=str(csv_path),
                            row=row_number,
                            field=field,
                        )
                    )
    return findings
