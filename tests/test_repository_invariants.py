from __future__ import annotations

from pathlib import Path

import pytest

from botsd.dataqa import audit_repository_data
from botsd.localization import audit_manifest as audit_localization_manifest
from botsd.manifest import BASELINE


ROOT = Path(__file__).resolve().parents[1]


def test_readme_preserves_credits_when_full_repository_is_present() -> None:
    readme = ROOT / "README.md"
    if not readme.is_file():
        pytest.skip("standalone cleanup overlay does not contain the release README")
    text = readme.read_text(encoding="utf-8")
    assert "## Credits & sources" in text
    for credit in (
        "Latepate64 / duel-masters-json",
        "Duel Masters Wiki contributors",
        "Melkiss / Dueparture",
        "Marc Robledo / Rom Patcher JS",
        "Wizards of the Coast / Takara Tomy",
    ):
        assert credit in text


def test_development_tracks_v13_when_full_repository_is_present() -> None:
    development = ROOT / "DEVELOPMENT.md"
    if not development.is_file():
        pytest.skip("standalone cleanup overlay does not contain DEVELOPMENT.md")
    text = development.read_text(encoding="utf-8")
    assert "Current public release: **v1.3**" in text


def test_public_data_structures_when_full_repository_is_present() -> None:
    data_dir = ROOT / "data"
    if not data_dir.is_dir():
        pytest.skip("standalone cleanup overlay does not contain public data CSVs")
    issues = audit_repository_data(data_dir)
    assert issues == []


def test_supported_revision_matches_release_manifest() -> None:
    supported = (ROOT / "SUPPORTED.md").read_text(encoding="utf-8")
    assert BASELINE.serial in supported
    assert str(BASELINE.clean_iso_size) in supported.replace(",", "")
    assert BASELINE.clean_iso_sha256 in supported


def test_localization_manifest_when_full_repository_is_present() -> None:
    data_dir = ROOT / "data"
    if not data_dir.is_dir():
        pytest.skip("standalone cleanup overlay does not contain public data CSVs")
    assert audit_localization_manifest(ROOT / "localization/en/manifest.json", ROOT) == []


def test_package_version_matches_pyproject() -> None:
    import re

    import botsd

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_block = pyproject.split("[project]", 1)[1].split("[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', project_block, re.MULTILINE)
    assert match is not None
    assert botsd.__version__ == match.group(1)
