# Historical tool-name map

The repository preserves several historical filenames so old notes and build recipes remain usable.
New code should prefer the descriptive shared modules below.

| Historical filename | Current implementation / preferred API | Status |
|---|---|---|
| `bosd_ui_archive_tool_v1.py` | `botsd.archive` | compatibility CLI/module |
| `bosd_ui_lzss_strong.py` | `botsd.lzss.compress_optimal` | compatibility module |
| `bosd_make_ppf3.py` | `botsd.ppf` | compatibility CLI |
| `bosd_shop_packdesc_fixed.py` | `botsd.shop` + `localization/en/shop_boosters.json` | compatibility CLI; text separated from patch logic |
| `bosd_apply_datapack_chunk_patch.py` | `botsd.datapack` | compatibility CLI |
| `bosd_cardtext_externalizer_v3.py` | `botsd.cardtext` / `botsd cardtext-externalize` | compatibility CLI/module |
| `bosd_rebuild_combined_list.py` | `botsd.cardtext` / `botsd combined-list` | compatibility CLI |
| `bosd_deck_text_ui82.py` | `botsd.decktext` + `localization/en/deck_text.json` / `botsd deck-text` | compatibility CLI; text separated from binary writer |
| `bosd_iso_layout_patcher_v2.py` | `botsd.iso9660` | compatibility CLI |
| `bosd_verify_extract_iso_assets.py` | `botsd.extract` / `botsd iso-verify-assets` | compatibility CLI; now streaming |
| `bosd_v13_maintenance.py` | `botsd.v13` + `botsd.semantic_assets` | compatibility CLI |
| `bosd_v13_release_builder.py` | `botsd.release` | compatibility CLI |
| `bosd_flavor_import_v2.py` | `botsd.flavor` / `botsd flavor-import` | compatibility CLI; printing-specific flavor logic shared |
| `bosd_ui76_rules_wordwrap.py` | `botsd.ruleswrap` / `botsd rules-wrap` | compatibility CLI; byte-length-preserving rule wrapping shared |
| `bosd_font_ue_patch.py` | `botsd.fontlink` / `botsd font-ue-patch` | compatibility CLI; glyph recipe in `botsd/assets/font_ue.json` |
| `bosd_keyboard_default_ui81.py` | `botsd.keyboard` / `botsd keyboard-v12-stage` | compatibility CLI; historical mode metadata centralized |
| `bosd_font_minimal_polish_ui81.py` | `botsd.font_polish` | compatibility CLI; semantic glyph edits |
| `bosd_static_label_polish_ui81.py` | `botsd.static_labels` + `botsd.ui_graphics` + `localization/en/static_labels_ui81.json` | compatibility CLI; text separated from geometry |
| `bosd_graphic_residuals_ui82.py` | `botsd.graphic_residuals` + `botsd.ui_graphics` | compatibility CLI; raster-reuse edits described by asset spec |
| `bosd_offline_exec_residuals_ui82.py` | `botsd.exec_strings` + `localization/en/offline_exec_residuals_ui82.json` | compatibility CLI; fixed slots separated from English strings |
| `bosd_wait_title_ui82.py` | `botsd.wait_title` + `botsd.gamefont` + `localization/en/wait_title_ui82.json` | compatibility CLI; game-font rendering shared |
| `bosd_apply_unpack_second_names_ui82.py` | `botsd.sda` + `botsd.unpack` | compatibility CLI; streaming 677-chunk patch |
| `bosd_verify_ui76_frozen_unpack_v2.py` | `botsd.sda` + `botsd.unpack` | compatibility CLI; streaming checkpoint verifier |
| `bosd_verify_ui82_frozen_unpack.py` | `botsd.sda` + `botsd.unpack` | compatibility CLI; streaming layer/delta verifier |
| `bosd_ui_polish_v11.py` | `botsd.ui_polish_v11` / `botsd ui-polish-v11` | compatibility CLI; v1.1 UI text/spec separated |
| `bosd_duelpts_issue2_fix.py` | `botsd.duelpts` / `botsd duelpts-fix` | compatibility CLI; proven Issue #2 repair metadata centralized |
| `ui76_webp_cardfaces.py` | `botsd.card_sources` + `botsd.fullcard` / `botsd fullcard-build` | compatibility CLI; source provenance separated from streaming binary conversion |
| `bosd_ui76_cardinfo_patch.py` | `botsd.cardinfo` / `botsd cardinfo-embed` | compatibility CLI; rules/race repack metadata centralized |
| `bosd_unpack_cardfaces_ui75_portable.py` | `botsd.cardfaces` / `botsd cardfaces-build` | compatibility CLI; streaming 677-card semantic renderer |
| `bosd_build_unpack_second_names_ui82.py` | `botsd.second_names` / `botsd unpack-render-second-names` | recovered semantic 677-card name-sprite renderer; original preserved under `tools/archaeology/` |
| `bosd_create_unpack_second_names_ui82.py` | `botsd.unpack` / `botsd unpack-create-second-names` | deterministic packaging of an already-built second-name layer |

Historical filenames remain intentionally retained even after functionality moves into `botsd/`.
Do not rename or delete them solely for aesthetics; commit history and old handoffs still refer to
those names. `tests/test_legacy_map.py` requires every top-level Python compatibility tool to stay
documented as a real row in the table above.
