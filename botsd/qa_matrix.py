from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

PLAYTHROUGH_STATUSES = frozenset({"not_tested", "partial", "complete", "blocked"})
COMPATIBILITY_STATUSES = frozenset({"not_tested", "partial", "complete", "retest_desirable", "blocked"})
SAVE_STATUSES = frozenset({"not_tested", "partial", "complete", "blocked"})
SAVE_CHECK_VALUES = frozenset({"not_tested", "partial", "complete", "not_applicable", "platform_dependent", "unsupported_assumption"})
REGRESSION_RUNTIME_STATUSES = frozenset({"confirmed", "static_only", "pending"})
YES_NO = frozenset({"yes", "no"})

REQUIRED_PLAYTHROUGH_FIELDS = (
    "id",
    "area",
    "scenario",
    "status",
    "patch_version",
    "platform",
    "platform_version",
    "normal_save_checked",
    "notes",
)


@dataclass(frozen=True)
class QASummary:
    rows: int
    by_status: dict[str, int]
    by_area: dict[str, int]

    @property
    def complete(self) -> int:
        return self.by_status.get("complete", 0)

    @property
    def tested_or_partial(self) -> int:
        return self.complete + self.by_status.get("partial", 0)


@dataclass(frozen=True)
class QAIssue:
    file: str
    message: str
    row: int | None = None
    field: str | None = None


def _read(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    return fields, rows


def _missing(fields: tuple[str, ...], required: Iterable[str]) -> list[str]:
    return [field for field in required if field not in fields]


def _unique_ids(path: Path, rows: list[dict[str, str]], field: str = "id") -> list[QAIssue]:
    issues: list[QAIssue] = []
    seen: set[str] = set()
    for line, row in enumerate(rows, start=2):
        ident = row.get(field, "").strip()
        if not ident:
            issues.append(QAIssue(str(path), "empty id", line, field))
        elif ident in seen:
            issues.append(QAIssue(str(path), f"duplicate id {ident!r}", line, field))
        else:
            seen.add(ident)
    return issues


def read_playthrough_matrix(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    fields, rows = _read(csv_path)
    missing = _missing(fields, REQUIRED_PLAYTHROUGH_FIELDS)
    if missing:
        raise ValueError(f"{csv_path}: missing required fields {missing}")
    issues = _unique_ids(csv_path, rows)
    for line, row in enumerate(rows, start=2):
        status = row["status"].strip()
        if status not in PLAYTHROUGH_STATUSES:
            issues.append(
                QAIssue(
                    str(csv_path),
                    f"invalid status {status!r}; expected one of {sorted(PLAYTHROUGH_STATUSES)}",
                    line,
                    "status",
                )
            )
        save = row["normal_save_checked"].strip().casefold()
        if save not in YES_NO:
            issues.append(
                QAIssue(
                    str(csv_path),
                    f"normal_save_checked must be yes/no, got {save!r}",
                    line,
                    "normal_save_checked",
                )
            )
    if issues:
        first = issues[0]
        where = f":{first.row}" if first.row else ""
        raise ValueError(f"{first.file}{where}: {first.message}")
    return rows


def summarize_playthrough(path: str | Path) -> QASummary:
    rows = read_playthrough_matrix(path)
    by_status = Counter(row["status"] for row in rows)
    by_area = Counter(row["area"] for row in rows)
    return QASummary(len(rows), dict(sorted(by_status.items())), dict(sorted(by_area.items())))


def audit_qa_directory(path: str | Path) -> list[QAIssue]:
    root = Path(path)
    issues: list[QAIssue] = []

    play = root / "playthrough_matrix.csv"
    try:
        read_playthrough_matrix(play)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(QAIssue(str(play), str(exc)))

    compat = root / "compatibility_matrix.csv"
    issues.extend(
        _audit_table(
            compat,
            required=("platform", "patch_version", "status", "version_tested", "notes"),
            status_field="status",
            allowed_statuses=COMPATIBILITY_STATUSES,
            id_fields=("platform", "patch_version"),
        )
    )

    saves = root / "save_compatibility.csv"
    save_issues = _audit_table(
        saves,
        required=(
            "from_version",
            "to_version",
            "platform",
            "status",
            "normal_memory_card",
            "emulator_save_state",
            "notes",
        ),
        status_field="status",
        allowed_statuses=SAVE_STATUSES,
        id_fields=("from_version", "to_version", "platform"),
    )
    if saves.is_file():
        fields, rows = _read(saves)
        if not _missing(fields, ("normal_memory_card", "emulator_save_state")):
            for line, row in enumerate(rows, start=2):
                for field in ("normal_memory_card", "emulator_save_state"):
                    value = row[field].strip()
                    if value not in SAVE_CHECK_VALUES:
                        save_issues.append(
                            QAIssue(
                                str(saves),
                                f"invalid {field} value {value!r}",
                                line,
                                field,
                            )
                        )
    issues.extend(save_issues)

    regressions = root / "regressions.csv"
    regression_issues = _audit_table(
        regressions,
        required=(
            "id",
            "area",
            "first_fixed",
            "automated_check",
            "runtime_status",
            "normal_save_relevant",
            "notes",
        ),
        id_fields=("id",),
    )
    if regressions.is_file():
        fields, rows = _read(regressions)
        if "runtime_status" in fields:
            for line, row in enumerate(rows, start=2):
                status = row["runtime_status"].strip()
                if status not in REGRESSION_RUNTIME_STATUSES:
                    regression_issues.append(
                        QAIssue(
                            str(regressions),
                            f"invalid runtime_status {status!r}",
                            line,
                            "runtime_status",
                        )
                    )
                save = row["normal_save_relevant"].strip().casefold()
                if save not in YES_NO:
                    regression_issues.append(
                        QAIssue(
                            str(regressions),
                            f"normal_save_relevant must be yes/no, got {save!r}",
                            line,
                            "normal_save_relevant",
                        )
                    )
    issues.extend(regression_issues)
    return issues


def _audit_table(
    path: Path,
    *,
    required: tuple[str, ...],
    id_fields: tuple[str, ...],
    status_field: str | None = None,
    allowed_statuses: frozenset[str] | None = None,
) -> list[QAIssue]:
    if not path.is_file():
        return [QAIssue(str(path), "missing QA matrix")]
    fields, rows = _read(path)
    missing = _missing(fields, required)
    if missing:
        return [QAIssue(str(path), f"missing required fields {missing}")]

    issues: list[QAIssue] = []
    seen: set[tuple[str, ...]] = set()
    for line, row in enumerate(rows, start=2):
        ident = tuple(row[field].strip() for field in id_fields)
        if any(not value for value in ident):
            issues.append(QAIssue(str(path), f"empty key fields {id_fields}", line))
        elif ident in seen:
            issues.append(QAIssue(str(path), f"duplicate key {ident!r}", line))
        else:
            seen.add(ident)
        if status_field and allowed_statuses is not None:
            status = row[status_field].strip()
            if status not in allowed_statuses:
                issues.append(
                    QAIssue(
                        str(path),
                        f"invalid {status_field} {status!r}; expected one of {sorted(allowed_statuses)}",
                        line,
                        status_field,
                    )
                )
    return issues


def format_qa_issues(issues: Iterable[QAIssue]) -> list[str]:
    lines: list[str] = []
    for issue in issues:
        where = issue.file
        if issue.row is not None:
            where += f":{issue.row}"
        if issue.field:
            where += f":{issue.field}"
        lines.append(f"error: {where}: {issue.message}")
    return lines
