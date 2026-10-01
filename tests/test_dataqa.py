from __future__ import annotations

import csv
from pathlib import Path

from botsd.dataqa import DatasetSpec, _structural_issues


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_structural_dataset_passes(tmp_path: Path) -> None:
    spec = DatasetSpec("sample.csv", 2, "id", 0, ("translation",))
    _write(
        tmp_path / "sample.csv",
        ["id", "translation"],
        [
            {"id": "0", "translation": "Alpha"},
            {"id": "1", "translation": "Überdragon"},
        ],
    )
    assert _structural_issues(tmp_path, spec) == []


def test_structural_dataset_detects_ids_and_text(tmp_path: Path) -> None:
    spec = DatasetSpec("sample.csv", 2, "id", 0, ("translation",))
    _write(
        tmp_path / "sample.csv",
        ["id", "translation"],
        [
            {"id": "0", "translation": "Ａlpha"},
            {"id": "0", "translation": "日本語"},
        ],
    )
    issues = _structural_issues(tmp_path, spec)
    messages = "\n".join(issue.message for issue in issues)
    assert "contiguous range" in messages
    assert "duplicate" in messages
    assert "fullwidth_latin" in messages
    assert "japanese" in messages
