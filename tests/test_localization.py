from __future__ import annotations

import csv
import json
from pathlib import Path

from botsd.localization import audit_manifest, export_provenance, load_manifest


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "language": "en",
                "default_review_status": "unreviewed",
                "datasets": [
                    {
                        "name": "names",
                        "path": "data/names.csv",
                        "resource_type": "card_name",
                        "id_field": "id",
                        "text_fields": ["translation"],
                        "source_field": "source",
                        "legacy_status_field": "status",
                        "expected_count": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_localization_manifest_audit_and_provenance_are_conservative(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    with (tmp_path / "data" / "names.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["id", "translation", "source", "status"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "id": "0",
                    "translation": "Alpha",
                    "source": "Printed card",
                    "status": "legacy-official-looking-status",
                },
                {
                    "id": "1",
                    "translation": "Beta",
                    "source": "Community reference",
                    "status": "legacy-community-status",
                },
            ]
        )
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    loaded = load_manifest(manifest)
    assert loaded.language == "en"
    assert audit_manifest(manifest, tmp_path) == []

    out = tmp_path / "provenance.csv"
    assert export_provenance(manifest, out, tmp_path) == 2
    with out.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["review_status"] for row in rows] == ["unreviewed", "unreviewed"]
    assert rows[0]["source"] == "Printed card"
    assert rows[0]["legacy_status"] == "legacy-official-looking-status"


def test_localization_audit_detects_missing_and_duplicate_ids(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "names.csv").write_text(
        "id,translation,source,status\n0,A,S,X\n0,B,S,Y\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)
    issues = audit_manifest(manifest, tmp_path)
    assert any("duplicate resource id" in issue.message for issue in issues)


def test_json_localization_datasets_preserve_sources_status_and_notes(tmp_path: Path) -> None:
    lang = tmp_path / "localization" / "en"
    lang.mkdir(parents=True)
    (lang / "records.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": "a",
                        "source_title": "source A",
                        "title": "Title A",
                        "callout": "Call A",
                    },
                    {
                        "id": "b",
                        "source_title": "source B",
                        "title": "Title B",
                        "callout": "Call B",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (lang / "strings.json").write_text(
        json.dumps({"strings": {"one": "One", "two": "Two"}}),
        encoding="utf-8",
    )
    (lang / "maintenance.json").write_text(
        json.dumps(
            {
                "dialogue": {
                    "wrap": {
                        "source": "Old text",
                        "replacement": "New text",
                        "review_status": "runtime_verified",
                        "note": "Checked in game.",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    manifest = lang / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "language": "en",
                "default_review_status": "unreviewed",
                "datasets": [
                    {
                        "name": "records",
                        "path": "localization/en/records.json",
                        "resource_type": "deck_text",
                        "format": "json_records",
                        "records_path": "records",
                        "id_field": "id",
                        "text_fields": {"title": "title", "callout": "callout"},
                        "source_fields": {"title": "source_title"},
                        "expected_count": 2,
                    },
                    {
                        "name": "strings",
                        "path": "localization/en/strings.json",
                        "resource_type": "ui_string",
                        "format": "json_mapping",
                        "records_path": "strings",
                        "id_field": "$key",
                        "text_fields": {"text": "$value"},
                        "expected_count": 2,
                    },
                    {
                        "name": "maintenance",
                        "path": "localization/en/maintenance.json",
                        "resource_type": "story_maintenance",
                        "format": "json_mapping",
                        "records_path": "dialogue",
                        "id_field": "$key",
                        "text_fields": {"replacement": "replacement"},
                        "source_fields": {"replacement": "source"},
                        "review_status_field": "review_status",
                        "notes_field": "note",
                        "expected_count": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert audit_manifest(manifest, tmp_path) == []
    out = tmp_path / "provenance.csv"
    assert export_provenance(manifest, out, tmp_path) == 7
    with out.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    title_a = next(row for row in rows if row["resource_id"] == "a" and row["field"] == "title")
    assert title_a["source"] == "source A"
    call_a = next(row for row in rows if row["resource_id"] == "a" and row["field"] == "callout")
    assert call_a["source"] == ""
    maintenance = next(row for row in rows if row["dataset"] == "maintenance")
    assert maintenance["review_status"] == "runtime_verified"
    assert maintenance["source"] == "Old text"
    assert maintenance["notes"] == "Checked in game."


def test_localization_audit_detects_unregistered_language_resource(tmp_path: Path) -> None:
    lang = tmp_path / "localization" / "en"
    lang.mkdir(parents=True)
    (lang / "known.json").write_text('{"strings":{"a":"A"}}', encoding="utf-8")
    (lang / "orphan.json").write_text('{"strings":{"b":"B"}}', encoding="utf-8")
    manifest = lang / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "language": "en",
                "default_review_status": "unreviewed",
                "datasets": [
                    {
                        "name": "known",
                        "path": "localization/en/known.json",
                        "resource_type": "ui_string",
                        "format": "json_mapping",
                        "records_path": "strings",
                        "id_field": "$key",
                        "text_fields": {"text": "$value"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    issues = audit_manifest(manifest, tmp_path)
    assert any("unregistered localization resource" in issue.message for issue in issues)
    assert any("orphan.json" in issue.message for issue in issues)


def test_repository_manifest_uses_authoritative_count_keys_and_registers_language_files() -> None:
    manifest = load_manifest("localization/en/manifest.json")
    counts = {dataset.name: dataset.expected_count for dataset in manifest.datasets}
    assert counts == {
        "card_names": 673,
        "display_card_text": 1682,
        "master_card_text": 2376,
        "story_dialogue_v12": 9499,
        "story_choices_v12": 293,
        "deck_text_ui82": 60,
        "shop_boosters": 8,
        "static_labels_ui81": 21,
        "offline_exec_residuals_ui82": 20,
        "ui_polish_v11": 37,
        "wait_title_ui82": 1,
        "v13_maintenance_dialogue": 1,
        "ace_badge_v13": 1,
    }
    configured = {Path(dataset.path).name for dataset in manifest.datasets}
    language_files = {
        path.name
        for path in Path("localization/en").iterdir()
        if path.is_file() and path.suffix in {".csv", ".json"} and path.name != "manifest.json"
    }
    assert language_files <= configured


def test_checked_in_language_resources_audit_and_export_without_public_data(tmp_path: Path) -> None:
    raw = json.loads(Path("localization/en/manifest.json").read_text(encoding="utf-8"))
    raw["datasets"] = [
        dataset
        for dataset in raw["datasets"]
        if dataset["path"].startswith("localization/en/")
    ]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    assert audit_manifest(manifest, Path(".")) == []

    out = tmp_path / "provenance.csv"
    assert export_provenance(manifest, out, Path(".")) == 10464
    with out.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    v13 = next(row for row in rows if row["dataset"] == "v13_maintenance_dialogue")
    assert v13["review_status"] == "runtime_verified"
    assert "character-boundary wrapper" in v13["notes"]
