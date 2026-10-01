from pathlib import Path

from botsd.textqa import scan_csv_fields, scan_english_text


def kinds(text, **kwargs):
    return {finding.kind for finding in scan_english_text(text, **kwargs)}


def test_clean_ascii():
    assert kinds("Bolshack Shobu") == set()


def test_fullwidth_latin():
    assert "fullwidth_latin" in kinds("Ｐｈｏｅｎｉｘ")


def test_japanese():
    assert "japanese" in kinds("切")


def test_reserved_tilde():
    assert "reserved_tilde" in kinds("literal ~ is not allowed")
    assert "reserved_tilde" not in kinds("Überdragon")


def test_long_segment_respects_explicit_break():
    assert "long_segment" in kinds("A" * 49, max_segment=48)
    assert "long_segment" not in kinds("A" * 30 + "#cr0" + "B" * 30, max_segment=48)


def test_csv_field_scanner_ignores_unrequested_source_column(tmp_path: Path):
    path = tmp_path / "x.csv"
    path.write_text(
        "source_japanese,translation\n切,ACE\nPhoenix,Ｐｈｏｅｎｉｘ\n", encoding="utf-8"
    )
    findings = scan_csv_fields(path, ("translation",))
    assert [finding.kind for finding in findings] == ["fullwidth_latin"]
    assert findings[0].row == 3
    assert findings[0].field == "translation"
