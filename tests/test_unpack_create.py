from __future__ import annotations

import csv
import io
import struct
import zipfile

from botsd.unpack import CARD_COUNT, SECOND_NAME_FIRST, SECOND_NAME_LAST, create_second_name_patch


def make_outer(path, values: list[int]) -> None:
    count = len(values)
    table_end = 12 + count * 4
    offsets = [table_end + i for i in range(count)]
    total = table_end + count
    raw = bytearray(b"sda\0" + struct.pack("<II", total, count))
    raw.extend(struct.pack(f"<{count}I", *offsets))
    raw.extend(bytes(values))
    path.write_bytes(raw)


def test_create_second_name_patch_is_deterministic_and_complete(tmp_path) -> None:
    count = SECOND_NAME_LAST + 1
    retail_values = [0] * count
    ui76_values = retail_values.copy()
    ui82_values = retail_values.copy()
    for index in range(SECOND_NAME_FIRST, SECOND_NAME_LAST + 1):
        ui82_values[index] = (index % 251) + 1
    retail = tmp_path / "retail.img"
    ui76 = tmp_path / "ui76.img"
    ui82 = tmp_path / "ui82.img"
    make_outer(retail, retail_values)
    make_outer(ui76, ui76_values)
    make_outer(ui82, ui82_values)
    out1 = tmp_path / "a.zip"
    out2 = tmp_path / "b.zip"
    result = create_second_name_patch(retail, ui76, ui82, out1, verify_retail=False)
    create_second_name_patch(retail, ui76, ui82, out2, verify_retail=False)
    assert out1.read_bytes() == out2.read_bytes()
    assert len(result.changed_chunks) == CARD_COUNT
    assert result.changed_chunks[0] == SECOND_NAME_FIRST
    assert result.changed_chunks[-1] == SECOND_NAME_LAST
    with zipfile.ZipFile(out1) as archive:
        rows = list(csv.DictReader(io.TextIOWrapper(archive.open("manifest.csv"), encoding="utf-8")))
        assert len(rows) == CARD_COUNT
        assert archive.read(f"chunks/{SECOND_NAME_FIRST:04d}.bin") == bytes([ui82_values[SECOND_NAME_FIRST]])
