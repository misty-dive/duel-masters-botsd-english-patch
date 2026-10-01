from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from botsd.manifest import BASELINE


def test_v13_maintenance_wrapper_uses_shared_manifest_without_raw_patch_tables() -> None:
    path = Path("tools/bosd_v13_maintenance.py")
    if not path.exists():
        pytest.skip("overlay-only test run: legacy v1.3 maintenance script is not present")
    spec = importlib.util.spec_from_file_location("legacy_v13_maintenance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.V12_HASHES == {row.name: row.v12.sha256 for row in BASELINE.components}
    assert module.V13_HASHES == {row.name: row.v13.sha256 for row in BASELINE.components}
    assert not hasattr(module, "EXE_PATCHES")
    assert not hasattr(module, "SCR_PATCHES")
