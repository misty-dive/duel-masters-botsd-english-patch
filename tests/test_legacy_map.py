from __future__ import annotations

import re
from pathlib import Path


def test_every_top_level_historical_tool_is_documented_as_table_row() -> None:
    root = Path(__file__).resolve().parents[1]
    legacy_map = (root / "tools/LEGACY_MAP.md").read_text(encoding="utf-8")
    table, marker, _ = legacy_map.partition(
        "\n\nHistorical filenames remain intentionally retained"
    )
    assert marker
    rows = set(re.findall(r"^\| `([^`]+\.py)` \|", table, flags=re.MULTILINE))
    tool_names = {path.name for path in (root / "tools").glob("*.py")}
    assert rows == tool_names
