# BOTSD development tools

These are the retained source/rebuild/verification tools for the English patch.

The public release is distributed as PPF3 patches. The tools are kept so the translation and later maintenance fixes can be reproduced and audited without shipping original game files.

## v1.3 maintenance / release

| Tool | Purpose |
|---|---|
| `bosd_v13_maintenance.py` | Canonical v1.2 → v1.3 component maintenance builder. Hash-guards the exact public v1.2 `SLPM_658.82`, `SCRPACK.SDA`, `TCHANGE.IMG`, and `DECK.DAT`, then reproduces the exact v1.3 outputs. Covers Aura Pegasus, half-width keyboard mode, the three SCRPACK probability branches, the confirmed story-wrap line, CHANGE/TURN geometry, and the Deck Builder `ACE` badge. |
| `bosd_v13_release_builder.py` | Builds the public v1.2 → v1.3 hotfix PPF and composes the clean-ISO → v1.3 full PPF from the verified official v1.2 PPF. It uses exact extracted public-v1.2 maintenance components rather than requiring a whole game ISO, and cross-checks their verified absolute ISO locations against the official PPF. |
| `bosd_make_ppf3.py` | Generic PPF 3.0 source/target image differ. Retained for independent patch generation/verification. |

### Historical keyboard helper

`bosd_keyboard_default_ui81.py` is retained to reproduce the **historical v1.2 UI81 build stage** and its established downstream hashes. That stage set keyboard mode `6`.

Post-v1.2 save-state/runtime QA proved that mode `6` stores full-width Latin characters. The final v1.3 maintenance stage changes the public executable from mode `6` to mode `9`, which is the half-width Latin path.

Do **not** treat the historical UI81 mode-6 output as the final v1.3 keyboard state.

## Core translation / text tools

| Tool | Purpose |
|---|---|
| `bosd_cardtext_externalizer_v3.py` | Builds the enlarged combined `LIST_1.BIN` and patches the executable to use the externalized 2,376-entry master text table. |
| `bosd_rebuild_combined_list.py` | Rebuild helper for the combined display/master LIST resource. |
| `bosd_flavor_import_v2.py` | Imports verified card flavor text into the card-text dataset. |
| `bosd_ui76_cardinfo_patch.py` | Card Info executable/rules handling used by the UI76 localization stage. |
| `bosd_ui76_rules_wordwrap.py` | Card-rules word-wrap processing for the localized card-information path. |
| `bosd_deck_text_ui82.py` | Localizes the fixed-size hidden deck text records while preserving composition bytes. |
| `bosd_offline_exec_residuals_ui82.py` | Applies the final UI82 offline executable residual-string fixes while intentionally preserving obsolete network strings. |
| `bosd_shop_packdesc_fixed.py` | Correct booster-description tool using the verified `0x50`-byte description field and preserving price/image/index metadata. |

## Graphics / archive tools

| Tool | Purpose |
|---|---|
| `bosd_ui_archive_tool_v1.py` | Parser/rebuilder for the packed UI archive format and its indexed TGA members. |
| `bosd_ui_lzss_strong.py` | Stronger compressor used where packed UI members have tight fixed allocations. |
| `bosd_static_label_polish_ui81.py` | Targeted static-label rendering into verified indexed-TGA rectangles. |
| `bosd_font_minimal_polish_ui81.py` | Minimal runtime-font polish for the accepted ASCII apostrophe/lowercase-l cells. |
| `bosd_font_ue_patch.py` | Runtime-font patch supporting the reserved English `Ü` mapping. |
| `bosd_ui_polish_v11.py` | v1.1 Records/Options/Deck Builder/Deck Stats UI cleanup. |
| `bosd_graphic_residuals_ui82.py` | Remaining verified offline graphic residuals from the UI82 pass. |
| `bosd_wait_title_ui82.py` | WAIT/title graphic residual maintenance. |
| `bosd_duelpts_issue2_fix.py` | v1.2 Issue #2 fix: restores duel digits 6–9 and relocates `LEFT` below the shared number strip. |

## Card-image / UNPACK tools

| Tool | Purpose |
|---|---|
| `ui76_webp_cardfaces.py` | Whole-card English image conversion used for the 677-card UI76 layer. |
| `bosd_unpack_cardfaces_ui75_portable.py` | Portable card-face conversion/rebuild helper from the earlier card-image stage. |
| `bosd_apply_unpack_second_names_ui82.py` | Applies the UI82 second-card-sprite/name layer patch. |
| `bosd_verify_ui76_frozen_unpack_v2.py` | Verifies the accepted UI76 UNPACK checkpoint. |
| `bosd_verify_ui82_frozen_unpack.py` | Verifies the final UI82 frozen UNPACK. |

v1.3 does **not** rebuild the 677 card-image layers.

## ISO / package helpers

| Tool | Purpose |
|---|---|
| `bosd_iso_layout_patcher_v2.py` | ISO9660 layout-preserving replacement tool. Same-size assets stay in place; enlarged localized assets can be appended and directory records retargeted. |
| `bosd_verify_extract_iso_assets.py` | Verifies/extracts expected retail ISO assets for local development. |
| `bosd_apply_datapack_chunk_patch.py` | Applies verified fixed-size DATAPACK chunk patches. |

## Other retained tools

| Tool | Purpose |
|---|---|
| `requirements.txt` | Python dependencies for the older image/archive development paths. |

## Important constraints

- Do not use the obsolete `bosd_shop_packdesc_ui80.py`; it overwrote booster price/image metadata.
- Do not mass-rewrap every long `SCRPACK.SDA` candidate. v1.3 changes only the confirmed story line.
- Do not rebuild all 677 card graphics for v1.3 maintenance.
- Do not mix the postponed AI research into the translation patch.
- Do not upload original or patched ISO images to the repository.
