from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from collections.abc import Iterable
from typing import Any

from .manifest import BASELINE


_COUNT_KEYS = {
    "internal_cards": BASELINE.internal_card_count,
    "card_resources": BASELINE.card_resource_count,
    "display_text": BASELINE.display_text_count,
    "master_text": BASELINE.master_text_count,
}

REVIEW_STATUSES = frozenset(
    {
        "unreviewed",
        "machine_draft",
        "human_reviewed",
        "official_terminology",
        "community_established",
        "runtime_verified",
    }
)

_DATA_FORMATS = frozenset({"csv", "json_records", "json_mapping"})


@dataclass(frozen=True)
class LocalizationDataset:
    name: str
    path: str
    resource_type: str
    id_field: str
    text_fields: tuple[str, ...]
    expected_count: int | None = None
    source_field: str | None = None
    legacy_status_field: str | None = None
    data_format: str = "csv"
    records_path: tuple[str, ...] = ()
    text_selectors: tuple[str, ...] = ()
    source_fields: tuple[tuple[str, str], ...] = ()
    review_status_field: str | None = None
    notes_field: str | None = None

    def selector_for_text_field(self, field: str) -> str:
        index = self.text_fields.index(field)
        return self.text_selectors[index] if self.text_selectors else field

    def source_selector_for_text_field(self, field: str) -> str | None:
        per_field = dict(self.source_fields).get(field)
        return per_field or self.source_field


@dataclass(frozen=True)
class LocalizationManifest:
    schema_version: int
    language: str
    default_review_status: str
    datasets: tuple[LocalizationDataset, ...]


@dataclass(frozen=True)
class LocalizationIssue:
    dataset: str
    message: str
    row: int | None = None
    field: str | None = None


@dataclass(frozen=True)
class ProvenanceRow:
    dataset: str
    resource_type: str
    resource_id: str
    field: str
    language: str
    review_status: str
    source: str
    legacy_status: str
    notes: str


@dataclass(frozen=True)
class _DatasetRecord:
    value: Any
    key: str | None
    row: int | None


def load_language_json(
    language: str,
    filename: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Load a language-specific JSON resource.

    Repository localization data is packaged as ``localization.<language>`` so the same semantic
    builders work from a source checkout and from an installed wheel.  Callers may still pass an
    explicit path for experiments or another language.
    """
    if path is not None:
        raw = Path(path).read_text(encoding="utf-8")
    else:
        package = f"localization.{language}"
        raw = files(package).joinpath(filename).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"language resource {filename!r} must contain a JSON object")
    return value


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"localization manifest field {key!r} must be a non-empty string")
    return value


def _optional_selector_map(
    manifest_path: Path,
    dataset_name: str,
    raw: Any,
    *,
    field_name: str,
) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ValueError(
            f"{manifest_path}: {dataset_name}: {field_name} must be an object"
        )
    result: list[tuple[str, str]] = []
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(
                f"{manifest_path}: {dataset_name}: {field_name} contains an empty key"
            )
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{manifest_path}: {dataset_name}: {field_name}[{key!r}] must be a selector"
            )
        result.append((key, value))
    return tuple(result)


def _parse_text_fields(
    manifest_path: Path,
    dataset_name: str,
    raw: Any,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if isinstance(raw, list) and raw:
        fields = tuple(str(value) for value in raw)
        if any(not value.strip() for value in fields):
            raise ValueError(
                f"{manifest_path}: {dataset_name}: text_fields cannot contain empty names"
            )
        return fields, fields
    if isinstance(raw, dict) and raw:
        names: list[str] = []
        selectors: list[str] = []
        for name, selector in raw.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"{manifest_path}: {dataset_name}: text_fields contains an empty name"
                )
            if not isinstance(selector, str) or not selector.strip():
                raise ValueError(
                    f"{manifest_path}: {dataset_name}: text_fields[{name!r}] must be a selector"
                )
            names.append(name)
            selectors.append(selector)
        return tuple(names), tuple(selectors)
    raise ValueError(
        f"{manifest_path}: {dataset_name}: text_fields must be a non-empty list or object"
    )


def load_manifest(path: str | Path) -> LocalizationManifest:
    manifest_path = Path(path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_version = int(raw.get("schema_version", 0))
    if schema_version not in {1, 2}:
        raise ValueError(f"{manifest_path}: unsupported localization schema version")
    language = _required_string(raw, "language")
    default_review_status = _required_string(raw, "default_review_status")
    if default_review_status not in REVIEW_STATUSES:
        raise ValueError(
            f"{manifest_path}: invalid default_review_status {default_review_status!r}"
        )

    datasets: list[LocalizationDataset] = []
    names: set[str] = set()
    for entry in raw.get("datasets", []):
        if not isinstance(entry, dict):
            raise ValueError(f"{manifest_path}: dataset entry must be an object")
        name = _required_string(entry, "name")
        if name in names:
            raise ValueError(f"{manifest_path}: duplicate dataset name {name!r}")
        names.add(name)

        data_format = str(entry.get("format", "csv"))
        if data_format not in _DATA_FORMATS:
            raise ValueError(
                f"{manifest_path}: {name}: unsupported dataset format {data_format!r}"
            )
        text_fields, text_selectors = _parse_text_fields(
            manifest_path, name, entry.get("text_fields")
        )
        source_fields = _optional_selector_map(
            manifest_path,
            name,
            entry.get("source_fields"),
            field_name="source_fields",
        )
        unknown_source_fields = sorted(set(dict(source_fields)) - set(text_fields))
        if unknown_source_fields:
            raise ValueError(
                f"{manifest_path}: {name}: source_fields names are not text fields: "
                f"{unknown_source_fields}"
            )

        expected_count_raw = entry.get("expected_count")
        expected_count: int | None
        if isinstance(expected_count_raw, str):
            try:
                expected_count = _COUNT_KEYS[expected_count_raw]
            except KeyError as exc:
                raise ValueError(
                    f"{manifest_path}: {name}: unknown expected_count key {expected_count_raw!r}"
                ) from exc
        else:
            expected_count = (
                int(expected_count_raw) if expected_count_raw is not None else None
            )
        if expected_count is not None and expected_count < 0:
            raise ValueError(f"{manifest_path}: {name}: expected_count must be non-negative")

        records_path_raw = entry.get("records_path", "")
        if records_path_raw is None:
            records_path_raw = ""
        if not isinstance(records_path_raw, str):
            raise ValueError(f"{manifest_path}: {name}: records_path must be a string")
        records_path = tuple(part for part in records_path_raw.split(".") if part)

        source_field = entry.get("source_field")
        legacy_status_field = entry.get("legacy_status_field")
        review_status_field = entry.get("review_status_field")
        notes_field = entry.get("notes_field")
        datasets.append(
            LocalizationDataset(
                name=name,
                path=_required_string(entry, "path"),
                resource_type=_required_string(entry, "resource_type"),
                id_field=_required_string(entry, "id_field"),
                text_fields=text_fields,
                expected_count=expected_count,
                source_field=str(source_field) if source_field else None,
                legacy_status_field=str(legacy_status_field) if legacy_status_field else None,
                data_format=data_format,
                records_path=records_path,
                text_selectors=text_selectors,
                source_fields=source_fields,
                review_status_field=(
                    str(review_status_field) if review_status_field else None
                ),
                notes_field=str(notes_field) if notes_field else None,
            )
        )
    if not datasets:
        raise ValueError(f"{manifest_path}: no datasets configured")
    return LocalizationManifest(
        schema_version, language, default_review_status, tuple(datasets)
    )


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        return fields, [{key: value or "" for key, value in row.items()} for row in reader]


def _resolve_json_path(value: Any, parts: tuple[str, ...], path: Path) -> Any:
    current = value
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            dotted = ".".join(parts)
            raise ValueError(f"{path}: records_path {dotted!r} does not exist")
        current = current[part]
    return current


def _dataset_records(
    dataset: LocalizationDataset,
    path: Path,
) -> tuple[list[_DatasetRecord], tuple[str, ...] | None]:
    if dataset.data_format == "csv":
        fields, rows = _read_csv(path)
        return [
            _DatasetRecord(row, None, line)
            for line, row in enumerate(rows, start=2)
        ], fields

    raw = json.loads(path.read_text(encoding="utf-8"))
    root = _resolve_json_path(raw, dataset.records_path, path)
    if dataset.data_format == "json_records":
        if not isinstance(root, list):
            raise ValueError(f"{path}: json_records root must be an array")
        return [
            _DatasetRecord(value, None, index)
            for index, value in enumerate(root, start=1)
        ], None
    if dataset.data_format == "json_mapping":
        if not isinstance(root, dict):
            raise ValueError(f"{path}: json_mapping root must be an object")
        return [
            _DatasetRecord(value, str(key), index)
            for index, (key, value) in enumerate(root.items(), start=1)
        ], None
    raise AssertionError(dataset.data_format)


def _selector_value(record: _DatasetRecord, selector: str) -> Any:
    if selector == "$key":
        return record.key
    if selector == "$value":
        return record.value
    if not isinstance(record.value, dict):
        return None
    return record.value.get(selector)


def _value_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _required_selectors(dataset: LocalizationDataset) -> tuple[str, ...]:
    selectors = [dataset.id_field, *dataset.text_selectors]
    selectors.extend(selector for _, selector in dataset.source_fields)
    for selector in (
        dataset.source_field,
        dataset.legacy_status_field,
        dataset.review_status_field,
        dataset.notes_field,
    ):
        if selector:
            selectors.append(selector)
    return tuple(dict.fromkeys(selectors))


def _audit_localization_directory_coverage(
    manifest: LocalizationManifest,
    root: Path,
) -> list[LocalizationIssue]:
    """Require every checked-in language CSV/JSON to participate in the manifest.

    The manifest itself is metadata, not a localization dataset. Python package files and README
    documentation are intentionally ignored. If the language directory is not present (as in small
    synthetic tests), coverage checking is skipped.
    """
    language_dir = root / "localization" / manifest.language
    if not language_dir.is_dir():
        return []
    configured = {Path(dataset.path).as_posix() for dataset in manifest.datasets}
    issues: list[LocalizationIssue] = []
    for path in sorted(language_dir.iterdir()):
        if (
            not path.is_file()
            or path.name == "manifest.json"
            or path.suffix not in {".csv", ".json"}
        ):
            continue
        relative = path.relative_to(root).as_posix()
        if relative not in configured:
            issues.append(
                LocalizationIssue(
                    "manifest",
                    f"unregistered localization resource: {relative}",
                )
            )
    return issues


def audit_manifest(
    manifest_path: str | Path,
    repo_root: str | Path = ".",
) -> list[LocalizationIssue]:
    manifest = load_manifest(manifest_path)
    root = Path(repo_root)
    issues: list[LocalizationIssue] = []
    issues.extend(_audit_localization_directory_coverage(manifest, root))
    for dataset in manifest.datasets:
        path = root / dataset.path
        if not path.is_file():
            issues.append(LocalizationIssue(dataset.name, f"missing dataset: {dataset.path}"))
            continue
        try:
            records, csv_fields = _dataset_records(dataset, path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(LocalizationIssue(dataset.name, str(exc)))
            continue

        if dataset.data_format == "csv":
            assert csv_fields is not None
            missing = [
                selector
                for selector in _required_selectors(dataset)
                if selector not in {"$key", "$value"} and selector not in csv_fields
            ]
            if missing:
                issues.append(LocalizationIssue(dataset.name, f"missing columns: {missing}"))
                continue

        if dataset.expected_count is not None and len(records) != dataset.expected_count:
            issues.append(
                LocalizationIssue(
                    dataset.name,
                    f"row count {len(records)} != expected {dataset.expected_count}",
                )
            )

        seen: set[str] = set()
        required = _required_selectors(dataset)
        for record in records:
            if dataset.data_format != "csv":
                for selector in required:
                    value = _selector_value(record, selector)
                    if value is None:
                        issues.append(
                            LocalizationIssue(
                                dataset.name,
                                f"missing selector {selector!r}",
                                record.row,
                                selector,
                            )
                        )
            ident = _value_text(_selector_value(record, dataset.id_field))
            if not ident:
                issues.append(
                    LocalizationIssue(
                        dataset.name,
                        "empty resource id",
                        record.row,
                        dataset.id_field,
                    )
                )
            elif ident in seen:
                issues.append(
                    LocalizationIssue(
                        dataset.name,
                        f"duplicate resource id {ident!r}",
                        record.row,
                        dataset.id_field,
                    )
                )
            else:
                seen.add(ident)

            if dataset.review_status_field:
                review_status = _value_text(
                    _selector_value(record, dataset.review_status_field)
                )
                if review_status and review_status not in REVIEW_STATUSES:
                    issues.append(
                        LocalizationIssue(
                            dataset.name,
                            f"invalid review status {review_status!r}",
                            record.row,
                            dataset.review_status_field,
                        )
                    )
    return issues


def iter_provenance(
    manifest_path: str | Path,
    repo_root: str | Path = ".",
) -> Iterable[ProvenanceRow]:
    manifest = load_manifest(manifest_path)
    root = Path(repo_root)
    issues = audit_manifest(manifest_path, root)
    if issues:
        joined = "; ".join(f"{issue.dataset}: {issue.message}" for issue in issues[:8])
        raise ValueError(f"localization manifest/data audit failed: {joined}")

    for dataset in manifest.datasets:
        path = root / dataset.path
        records, _ = _dataset_records(dataset, path)
        for record in records:
            ident = _value_text(_selector_value(record, dataset.id_field))
            review_status = manifest.default_review_status
            if dataset.review_status_field:
                explicit = _value_text(
                    _selector_value(record, dataset.review_status_field)
                )
                if explicit:
                    review_status = explicit
            legacy_status = ""
            if dataset.legacy_status_field:
                legacy_status = _value_text(
                    _selector_value(record, dataset.legacy_status_field)
                )
            notes = "Imported from existing repository metadata; review status not inferred."
            if dataset.notes_field:
                explicit_notes = _value_text(_selector_value(record, dataset.notes_field))
                if explicit_notes:
                    notes = explicit_notes

            for field in dataset.text_fields:
                selector = dataset.selector_for_text_field(field)
                text = _value_text(_selector_value(record, selector))
                if not text:
                    continue
                source = ""
                source_selector = dataset.source_selector_for_text_field(field)
                if source_selector:
                    source = _value_text(_selector_value(record, source_selector))
                yield ProvenanceRow(
                    dataset=dataset.name,
                    resource_type=dataset.resource_type,
                    resource_id=ident,
                    field=field,
                    language=manifest.language,
                    review_status=review_status,
                    source=source,
                    legacy_status=legacy_status,
                    notes=notes,
                )


def export_provenance(
    manifest_path: str | Path,
    output: str | Path,
    repo_root: str | Path = ".",
) -> int:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(iter_provenance(manifest_path, repo_root))
    fields = [
        "dataset",
        "resource_type",
        "resource_id",
        "field",
        "language",
        "review_status",
        "source",
        "legacy_status",
        "notes",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fields})
    return len(rows)
