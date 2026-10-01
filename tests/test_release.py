from __future__ import annotations

import os
from pathlib import Path

import pytest

from botsd.manifest import BASELINE
from botsd.release import _diff_records, build_v13_release


def test_diff_records_are_split_to_ppf3_limit():
    old = bytes([0]) * 700
    new = bytes([1]) * 700
    records = _diff_records(old, new, 1234)
    assert [len(row.payload) for row in records] == [255, 255, 190]
    assert [row.offset for row in records] == [1234, 1489, 1744]


def test_optional_exact_published_release_rebuild(tmp_path: Path):
    v12_dir = os.environ.get("BOTSD_V12_COMPONENT_DIR")
    v12_ppf = os.environ.get("BOTSD_V12_FULL_PPF")
    if not v12_dir or not v12_ppf:
        pytest.skip(
            "set BOTSD_V12_COMPONENT_DIR and BOTSD_V12_FULL_PPF for exact release regression"
        )
    result = build_v13_release(v12_dir, v12_ppf, tmp_path)
    assert result.full.sha256 == BASELINE.full_ppf_sha256
    assert result.full.size == BASELINE.full_ppf_size
    assert result.hotfix.sha256 == BASELINE.hotfix_from_v12_sha256
    assert result.hotfix.size == BASELINE.hotfix_from_v12_size
