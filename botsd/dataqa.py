from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .manifest import BASELINE
from .textqa import scan_english_text


@dataclass(frozen=True)
class DataIssue:
    severity: str
    dataset: str
    message: str
    row: int | None = None
    field: str | None = None


@dataclass(frozen=True)
class DatasetSpec:
    filename: str
    count: int
    id_field: str
    start: int
    english_fields: tuple[str, ...] = ()


DATASET_SPECS = (
    DatasetSpec(
        "bosd_english_name_crosswalk_verified.csv",
        BASELINE.internal_card_count,
        "internal_id",
        0,
        ("official_english_name",),
    ),
    DatasetSpec(
        "bosd_list_display_card_rules_complete.csv",
        BASELINE.display_text_count,
        "list_index",
        0,
        ("translation",),
    ),
    DatasetSpec(
        "bosd_master_text_card_rules_complete.csv",
        BASELINE.master_text_count,
        "master_text_id",
        0,
        ("translation",),
    ),
    DatasetSpec(
        "unpack_card_inventory.csv",
        BASELINE.card_resource_count,
        "seq",
        0,
        ("english_name", "race", "rules", "flavor"),
    ),
)


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        return fields, [dict(row) for row in reader]


def _structural_issues(data_dir: Path, spec: DatasetSpec) -> list[DataIssue]:
    path = data_dir / spec.filename
    dataset = spec.filename
    if not path.is_file():
        return [DataIssue("error", dataset, f"missing dataset: {path}")]

    fields, rows = _read_rows(path)
    issues: list[DataIssue] = []
    required = (spec.id_field, *spec.english_fields)
    missing = [field for field in required if field not in fields]
    if missing:
        issues.append(DataIssue("error", dataset, f"missing required columns: {missing}"))
        return issues

    if len(rows) != spec.count:
        issues.append(
            DataIssue(
                "error",
                dataset,
                f"row count {len(rows)} != expected {spec.count}",
            )
        )

    values: list[int] = []
    for row_number, row in enumerate(rows, start=2):
        raw = row.get(spec.id_field, "")
        try:
            values.append(int(raw))
        except ValueError:
            issues.append(
                DataIssue(
                    "error",
                    dataset,
                    f"non-integer {spec.id_field}: {raw!r}",
                    row_number,
                    spec.id_field,
                )
            )

    if len(values) == len(rows):
        expected = list(range(spec.start, spec.start + spec.count))
        if sorted(values) != expected:
            issues.append(
                DataIssue(
                    "error",
                    dataset,
                    f"{spec.id_field} values are not the expected contiguous range "
                    f"{spec.start}..{spec.start + spec.count - 1}",
                )
            )
        if len(set(values)) != len(values):
            issues.append(DataIssue("error", dataset, f"duplicate {spec.id_field} values"))

    for row_number, row in enumerate(rows, start=2):
        for field in spec.english_fields:
            text = row.get(field) or ""
            for finding in scan_english_text(text):
                # Japanese is expected in source columns, but never in the selected English fields.
                issues.append(
                    DataIssue(
                        "error",
                        dataset,
                        f"{finding.kind}: {finding.text!r}",
                        row_number,
                        field,
                    )
                )
    return issues


def audit_repository_data(data_dir: str | Path) -> list[DataIssue]:
    root = Path(data_dir)
    issues: list[DataIssue] = []
    for spec in DATASET_SPECS:
        issues.extend(_structural_issues(root, spec))
    return issues


def format_issues(issues: Iterable[DataIssue]) -> list[str]:
    lines: list[str] = []
    for issue in issues:
        where = issue.dataset
        if issue.row is not None:
            where += f":{issue.row}"
        if issue.field:
            where += f":{issue.field}"
        lines.append(f"{issue.severity}: {where}: {issue.message}")
    return lines
