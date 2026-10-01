from botsd.manifest import BASELINE, CARD_LAYER_RANGES, UNPACK_CHUNK_COUNT


def test_baseline_counts_are_internally_consistent():
    assert BASELINE.internal_card_count == 673
    assert BASELINE.card_resource_count == 677
    assert BASELINE.combined_text_pointer_count == 4058
    assert CARD_LAYER_RANGES == ((677, 1353), (1360, 2036), (2037, 2713))
    assert UNPACK_CHUNK_COUNT == 2809


def test_v13_is_same_size_maintenance_update_for_each_component():
    for component in BASELINE.components:
        assert component.v12.size == component.v13.size
        assert component.v12.sha256 != component.v13.sha256


def test_versioned_binary_layouts_are_centralized():
    from botsd.manifest import CARD_TEXT_LAYOUT, DECK_TEXT_LAYOUT, SHOP_BOOSTER_LAYOUT

    assert CARD_TEXT_LAYOUT.master_table_va == 0x444268
    assert CARD_TEXT_LAYOUT.retail_list_pointer_count == 1683
    assert DECK_TEXT_LAYOUT.data_offset == 0x42
    assert DECK_TEXT_LAYOUT.record_count == 60
    assert SHOP_BOOSTER_LAYOUT.table_offset == 0x4FDFF8
    assert SHOP_BOOSTER_LAYOUT.description_size == 0x50
