from botsd.flavor import (
    choose_for_numbered_set,
    clean_text,
    cp932_ok,
    import_flavor,
    norm_name_relaxed,
)


def test_clean_text_normalizes_html_punctuation_and_whitespace() -> None:
    assert clean_text("A&nbsp;card<br>with &#8217;style&#8217;") == "A card with 'style'"


def test_relaxed_name_handles_diacritics() -> None:
    assert norm_name_relaxed("Überdragon Baham") == norm_name_relaxed("Uberdragon Baham")


def test_numbered_set_prefers_matching_printing() -> None:
    card = {
        "printings": [
            {"set": "DM-01", "flavor": "First printing."},
            {"set": "DM-03", "flavor": "Later printing."},
        ]
    }
    printing, flavor, mode = choose_for_numbered_set(card, 1, False)
    assert printing["set"] == "DM-01"
    assert flavor == "First printing."
    assert mode == "same_set"


def test_cp932_reserves_tilde_but_allows_umlaut_mapping() -> None:
    assert cp932_ok("Überdragon")[0]
    assert cp932_ok("literal ~ is reserved") == (False, "literal_tilde_reserved")


def test_import_flavor_preserves_existing_and_imports_verified_printed_card() -> None:
    cross = []
    for i in range(673):
        cross.append(
            {
                "internal_id": str(i),
                "resource_key": f"0_{i}",
                "set_label": "DM-01" if i == 0 else "Special/Promo",
                "official_english_name": "Example Card" if i == 0 else f"Card {i}",
                "status": "printed_english_name_mapped" if i == 0 else "wiki_established_english_name",
                "mapping_source": "",
            }
        )

    master = []
    for i in range(2376):
        master.append(
            {
                "master_text_id": str(i),
                "roles": "name",
                "cards": "",
                "source_japanese": "",
                "translation": "",
                "list_index": "",
            }
        )
    master[2] = {
        "master_text_id": "2",
        "roles": "flavor",
        "cards": "0:0_0:DM-01:カード",
        "source_japanese": "日本語フレーバー",
        "translation": "",
        "list_index": "10",
    }
    master[6] = {
        "master_text_id": "6",
        "roles": "flavor",
        "cards": "1:0_1:Special:カード",
        "source_japanese": "別の日本語",
        "translation": "Existing translation.",
        "list_index": "",
    }

    display = [
        {"list_index": str(i), "master_text_id": "", "translation": ""}
        for i in range(1682)
    ]
    display[10]["master_text_id"] = "2"

    cards = [
        {
            "name": "Example Card",
            "printings": [{"set": "DM-01 Base Set", "flavor": "Official flavor."}],
        }
    ]
    qa, report = import_flavor(cards, cross, master, display)
    assert master[2]["translation"] == "Official flavor."
    assert display[10]["translation"] == "Official flavor."
    assert master[6]["translation"] == "Existing translation."
    assert report.imported == 1
    assert report.preserved_existing == 1
    assert any(row["status"] == "same_set" for row in qa)
