# Tools

These are the scripts that are still useful for maintaining or rebuilding the English patch. Obsolete one-off and superseded development scripts have been removed from the public toolset.

Python 3.10+ is recommended. Install the shared Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

## v1.1 fixes

| Tool | Purpose |
| --- | --- |
| `bosd_shop_packdesc_fixed.py` | Applies the corrected booster descriptions without touching shop price or pack-image metadata. |
| `bosd_ui_polish_v11.py` | Builds the v1.1 Records, Options, Deck Builder, and Deck Stats fixes. |
| `bosd_iso_layout_patcher_v2.py` | Inserts replacement files into the PS2 ISO, including enlarged files that must be appended and retargeted. |

## Card text and card graphics

| Tool | Purpose |
| --- | --- |
| `bosd_cardtext_externalizer_v3.py` | Builds the enlarged external card-text table in `LIST_1.BIN`. |
| `bosd_flavor_import_v2.py` | Imports printing-specific English flavor text into the project card-text CSVs. |
| `bosd_rebuild_combined_list.py` | Rebuilds and validates the combined 4058-pointer `LIST_1.BIN`. |
| `bosd_ui76_cardinfo_patch.py` | Patches the executable-resident Card Info rules/race text used before `LIST_1.BIN` is loaded. |
| `bosd_ui76_rules_wordwrap.py` | Adds safe English word wrapping to Card Info rules text. |
| `ui76_webp_cardfaces.py` | Card-face conversion pipeline used to build the frozen English card cache. |
| `bosd_unpack_cardfaces_ui75_portable.py` | Card-face/archive helper used by later graphics tools; also contains the portable card-face builder. |
| `bosd_apply_unpack_second_names_ui82.py` | Applies the second 677-card small-sprite/name layer to the frozen card archive. |
| `bosd_verify_ui76_frozen_unpack_v2.py` | Verifies the frozen full-card and thumbnail layers against retail. |
| `bosd_verify_ui82_frozen_unpack.py` | Verifies the final card archive after the second 677-card sprite layer is added. |

## UI, fonts, and archives

| Tool | Purpose |
| --- | --- |
| `bosd_ui_archive_tool_v1.py` | Lists, extracts, and repacks the game's packed UI `.DAT` archives. |
| `bosd_ui_lzss_strong.py` | LZSS encoder used when edited UI members must still fit fixed archive allocations. |
| `bosd_font_ue_patch.py` | Adds the reserved font glyph used for `Ü` and validates the rebuilt FONTLINK archive. |
| `bosd_font_minimal_polish_ui81.py` | Applies the small runtime-font cleanup used by the final patch. |
| `bosd_static_label_polish_ui81.py` | Renders verified English static labels into indexed-TGA UI assets. |
| `bosd_keyboard_default_ui81.py` | Makes the existing English keyboard page the initial input mode. |
| `bosd_graphic_residuals_ui82.py` | Patches the remaining `LOBBY`, `TOUR`, and `DECK` graphical labels. |
| `bosd_wait_title_ui82.py` | Builds the localized WAIT and TITLE assets. |
| `bosd_deck_text_ui82.py` | Rewrites the text fields in all 60 `DECK/*.DAT` files while preserving deck data. |
| `bosd_offline_exec_residuals_ui82.py` | Applies the final offline executable string fixes used by the release baseline. |

## DATAPACK and verification

| Tool | Purpose |
| --- | --- |
| `bosd_apply_datapack_chunk_patch.py` | Applies the verified fixed-size DATAPACK chunk replacements. |
| `bosd_verify_extract_iso_assets.py` | Checks extracted ISO files against a SHA-256 manifest before build work. |

## Maintenance rules

- Treat hashes, offsets, chunk ranges, and fixed field sizes as part of the format. Do not casually change them.
- Prefer targeted edits over rebuilding unrelated assets.
- Fail on an unexpected source instead of guessing.
- Keep containment checks around image and archive edits where possible.
- When refactoring a working script, require identical output from the same input before accepting the change.

Version numbers such as `ui76`, `ui81`, and `ui82` remain in some filenames because they identify the development stage where that component stabilized. They do not mean those tools have been superseded; every script listed here still contributes to, supports, or verifies the current patch workflow.
