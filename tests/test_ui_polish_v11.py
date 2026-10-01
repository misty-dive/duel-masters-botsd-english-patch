from __future__ import annotations

from botsd.ui_polish_v11 import load_spec, patch_executable


def test_ui_polish_v11_spec_externalizes_labels_and_geometry() -> None:
    spec = load_spec()
    assert spec["archives"]["opt"]["source_sha256"] == "6e5a8a2e07fa0acb1cc7e487f74531b36bd7407fee1bdce4845d6db39689c09b"
    assert "OPT_SRC_OP_P00_TGA" in spec["archives"]["opt"]["members"]
    assert "DECK_SRC_DC_P02_TGA" in spec["archives"]["deck"]["members"]
    assert len(spec["executable"]["copy_counts"]) == 4


def test_v11_executable_patch_is_contained_with_custom_spec() -> None:
    source = bytearray(128)
    source[10:25] = b"   G    W    %\0"
    jp = ["１枚", "２枚", "３枚", "４枚"]
    rows = []
    for i, text in enumerate(jp):
        off = 32 + i * 12
        raw = text.encode("cp932")
        source[off:off+len(raw)] = raw
        rows.append({"offset": off, "slot": 8, "source": text, "text": f"copy_{i+1}"})
    spec = {
        "source_sha256": "ignored",
        "record_units": {"offset": 10, "end": 30, "source_ascii": "   G    W    %"},
        "copy_counts": rows,
    }
    strings = {
        "record_units": "   G     W     %",
        "copy_1": "1", "copy_2": "2", "copy_3": "3", "copy_4": "4",
    }
    result, lines = patch_executable(bytes(source), spec, strings, verify_hash=False)
    assert result[10:27].startswith(b"   G     W     %\0")
    for i in range(4):
        off = 32 + i * 12
        assert result[off:off+2] == str(i+1).encode("ascii") + b"\0"
    assert any(line.startswith("executable_differing_bytes=") for line in lines)
