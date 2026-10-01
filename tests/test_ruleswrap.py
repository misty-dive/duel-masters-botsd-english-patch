from botsd.ruleswrap import cells, normalize_whitespace, wrap_paragraph, wrap_rule_tables


def test_wrap_paragraph_replaces_only_existing_space() -> None:
    source = "■ This creature gets +1000 power whenever it attacks"
    wrapped = wrap_paragraph(source, max_cells=24)
    assert len(wrapped) == len(source)
    assert normalize_whitespace(wrapped) == normalize_whitespace(source)
    assert all(cells(line) <= 24 for line in wrapped.split("\n"))
    for before, after in zip(source, wrapped, strict=True):
        if before != after:
            assert (before, after) == (" ", "\n")


def test_wrap_paragraph_rejects_unbreakable_token() -> None:
    try:
        wrap_paragraph("A" * 25, max_cells=24)
    except ValueError as exc:
        assert "token longer" in str(exc)
    else:
        raise AssertionError("expected width failure")


def test_wrap_rule_tables_syncs_display_without_touching_nonrules() -> None:
    master = [
        {
            "master_text_id": "0",
            "roles": "rules",
            "translation": "■ This creature gets +1000 power whenever it attacks",
        },
        {"master_text_id": "1", "roles": "name", "translation": "Sample Card"},
    ]
    display = [
        {"list_index": "0", "master_text_id": "0", "translation": "old"},
        {"list_index": "1", "master_text_id": "1", "translation": "Sample Card"},
    ]
    report = wrap_rule_tables(master, display, expected_rule_count=None)
    assert report.rules_verified == 1
    assert report.rules_with_added_wraps == 1
    assert display[0]["translation"] == master[0]["translation"]
    assert master[1]["translation"] == "Sample Card"
