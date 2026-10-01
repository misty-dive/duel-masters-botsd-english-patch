from __future__ import annotations

from pathlib import Path

import pytest

from botsd.qa_matrix import audit_qa_directory, read_playthrough_matrix, summarize_playthrough


def test_repository_playthrough_matrix_is_valid():
    path = Path("qa/playthrough_matrix.csv")
    rows = read_playthrough_matrix(path)
    assert rows
    assert any(row["id"] == "shop-leave" and row["status"] == "complete" for row in rows)
    assert any(row["status"] == "not_tested" for row in rows)


def test_summary_counts_rows():
    summary = summarize_playthrough("qa/playthrough_matrix.csv")
    assert summary.rows == sum(summary.by_status.values())
    assert summary.complete >= 1


def test_invalid_status_is_rejected(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "id,area,scenario,status,patch_version,platform,platform_version,"
        "normal_save_checked,notes\n"
        "x,A,B,maybe,v1.3,PCSX2,,no,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid status"):
        read_playthrough_matrix(path)


def test_repository_qa_directory_is_valid():
    assert audit_qa_directory("qa") == []


def test_regression_corpus_tracks_known_v13_cases():
    path = Path("qa/regressions.csv")
    text = path.read_text(encoding="utf-8")
    for ident in (
        "aura-pegasus",
        "shop-probability-branches",
        "keyboard-halfwidth",
        "change-turn",
        "ace-badge",
    ):
        assert ident in text
