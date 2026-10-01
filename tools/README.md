# BOTSD development tools

These are the retained source/rebuild/verification tools for the English patch.

The public release is distributed as PPF3 patches. The tools are kept so the translation and later
maintenance fixes can be reproduced and audited without shipping original game files.

## Shared package migration

New reusable code lives under `botsd/`. Historical `tools/bosd_*` filenames remain while their
behavior is migrated behind regression tests so old build notes and downstream imports do not break.

The following historical tools are now compatibility wrappers around the shared package:

| Historical tool | Shared implementation |
|---|---|
| `bosd_ui_archive_tool_v1.py` | `botsd.archive` |
| `bosd_ui_lzss_strong.py` | `botsd.lzss.compress_optimal` |
| `bosd_iso_layout_patcher_v2.py` | `botsd.iso9660` |
| `bosd_make_ppf3.py` | `botsd.ppf` |

The ISO wrapper is intentionally streaming/seek-based and no longer reads multiple multi-gigabyte
ISO copies into memory.

For new code, prefer importing `botsd.*` directly. Keep historical filenames only where compatibility
or reproducibility requires them.

## v1.3 maintenance / release

| Tool | Purpose |
|---|---|
| `bosd_v13_maintenance.py` | Compatibility entry point for the canonical `botsd.v13` maintenance builder. Hash-guards the exact public v1.2 components and reproduces the published v1.3 outputs. Aura is repaired from the executable pointer-overlap invariant; SCRPACK branches are relocated from parsed command ordinals; the confirmed dialogue string comes from `localization/en/v13_maintenance.json`; CHANGE/TURN and `ACE` are generated from editable semantic recipes. The old raw v1.3 byte-diff tables and Base85/XOR release blobs are no longer canonical inputs. |
| `bosd_v13_release_builder.py` | Builds the public v1.2 → v1.3 hotfix PPF and composes the clean-ISO → v1.3 full PPF from the verified official v1.2 PPF. |
| `bosd_make_ppf3.py` | Compatibility CLI for generic PPF 3.0 source/target differencing; implementation now lives in `botsd.ppf`. |

### Historical keyboard helper

`bosd_keyboard_default_ui81.py` is retained to reproduce the **historical v1.2 UI81 build stage** and
its established downstream hashes. The preferred shared command is `python -m botsd keyboard-v12-stage`;
that stage sets keyboard mode `6`.

Post-v1.2 save-state/runtime QA proved that mode `6` stores full-width Latin characters. The final
v1.3 maintenance stage changes the public executable from mode `6` to mode `9`, the half-width Latin
path.

Do **not** treat the historical UI81 mode-6 output as the final v1.3 keyboard state. The reserved
`Ü` FONTLINK helper likewise has a package-native `python -m botsd font-ue-patch` command; its recipe
lives in `botsd/assets/font_ue.json` and its retail source hash comes from the release manifest.


## Localization-source helpers

| Tool | Purpose |
|---|---|
| `bosd_ui76_rules_wordwrap.py` | Historical compatibility CLI over `botsd.ruleswrap`. The shared implementation preserves encoded byte length by replacing only existing ASCII spaces with LF bytes and synchronizes matching display/master rule rows. |
| `bosd_flavor_import_v2.py` | Historical compatibility CLI over `botsd.flavor`. Printing-specific official English flavor import, verified-name joining, CP932 checks and safe reprint fallback now live in the shared package. |

Package-native equivalents are `python -m botsd rules-wrap ...` and `python -m botsd flavor-import ...`.

## Core translation / text tools

| Tool | Purpose |
|---|---|
| `bosd_cardtext_externalizer_v3.py` | Builds the enlarged combined `LIST_1.BIN` and patches the executable to use the externalized 2,376-entry master text table. |
| `bosd_rebuild_combined_list.py` | Rebuild helper for the combined display/master LIST resource. |
| `bosd_flavor_import_v2.py` | Imports verified card flavor text into the card-text dataset. |
| `bosd_ui76_cardinfo_patch.py` | Compatibility CLI over `botsd.cardinfo`; repacks only verified embedded rule master strings plus the 65-entry race table while preserving CardText lifecycle code/non-rule pointers. |
| `bosd_ui76_rules_wordwrap.py` | Card-rules word-wrap processing for the localized card-information path. |
| `bosd_deck_text_ui82.py` | Localizes the fixed-size hidden deck text records while preserving composition bytes. |
| `bosd_offline_exec_residuals_ui82.py` | Applies the final UI82 offline executable residual-string fixes while intentionally preserving obsolete network strings. |
| `bosd_shop_packdesc_fixed.py` | Correct booster-description tool using the verified `0x50`-byte description field and preserving price/image/index metadata. |

## Graphics / archive tools

| Tool | Purpose |
|---|---|
| `bosd_ui_archive_tool_v1.py` | Compatibility CLI for `botsd.archive`; parses/rebuilds packed UI archives and indexed TGA members. |
| `bosd_ui_lzss_strong.py` | Compatibility wrapper for `botsd.lzss.compress_optimal`, used for tight fixed allocations. |
| `bosd_static_label_polish_ui81.py` | Targeted static-label rendering into verified indexed-TGA rectangles. |
| `bosd_font_minimal_polish_ui81.py` | Minimal runtime-font polish for the accepted ASCII apostrophe/lowercase-l cells. |
| `bosd_font_ue_patch.py` | Runtime-font patch supporting the reserved English `Ü` mapping. |
| `bosd_ui_polish_v11.py` | Compatibility CLI over `botsd.ui_polish_v11`; v1.1 Records/Options/Deck Builder/Deck Stats cleanup with text/spec separation. |
| `bosd_graphic_residuals_ui82.py` | Remaining verified offline graphic residuals from the UI82 pass. |
| `bosd_wait_title_ui82.py` | WAIT/title graphic residual maintenance. |
| `bosd_duelpts_issue2_fix.py` | Compatibility CLI over `botsd.duelpts`; restores duel digits 6–9 and relocates `LEFT` below the shared number strip. |

## Card-image / UNPACK tools

| Tool | Purpose |
|---|---|
| `ui76_webp_cardfaces.py` | Compatibility CLI over `botsd.card_sources`/`botsd.fullcard`; pinned-source whole-card English conversion for all 677 UI76 resources. |
| `bosd_unpack_cardfaces_ui75_portable.py` | Compatibility CLI over `botsd.cardfaces`; streaming 677-card large-face/thumbnail renderer using game FONTLINK glyphs and semantic geometry. |
| `bosd_build_unpack_second_names_ui82.py` | Compatibility CLI for the recovered semantic 677-card UI82 name-sprite renderer; preserved source is under `tools/archaeology/`. |
| `bosd_create_unpack_second_names_ui82.py` | Creates the deterministic 677-chunk UI82 second-card-sprite/name patch ZIP from verified retail/UI76/UI82 images. |
| `bosd_apply_unpack_second_names_ui82.py` | Applies the UI82 second-card-sprite/name layer patch. |
| `bosd_verify_ui76_frozen_unpack_v2.py` | Verifies the accepted UI76 UNPACK checkpoint. |
| `bosd_verify_ui82_frozen_unpack.py` | Verifies the final UI82 frozen UNPACK. |

v1.3 does **not** rebuild the 677 card-image layers.

## ISO / package helpers

| Tool | Purpose |
|---|---|
| `bosd_iso_layout_patcher_v2.py` | Compatibility CLI for the streaming `botsd.iso9660` patcher. Same-size assets stay in place; enlarged assets are appended and directory records retargeted. |
| `bosd_verify_extract_iso_assets.py` | Verifies/extracts expected retail ISO assets for local development. |
| `bosd_apply_datapack_chunk_patch.py` | Applies verified fixed-size DATAPACK chunk patches. |

## Environment

`pyproject.toml` is now authoritative for Python/development dependencies. `requirements.txt` is
retained only for older workflows that expect it.

## Important constraints

- Do not use the obsolete `bosd_shop_packdesc_ui80.py`; it overwrote booster price/image metadata.
- Do not mass-rewrap every long `SCRPACK.SDA` candidate. v1.3 changes only the confirmed story line.
- Do not rebuild all 677 card graphics for v1.3 maintenance.
- Do not mix postponed AI research into the translation patch.
- Do not upload original or patched ISO images to the repository.

## Historical naming

See [`LEGACY_MAP.md`](LEGACY_MAP.md) for the mapping from checkpoint-era script names to the new shared package APIs.

## Shared QA commands

Repository-wide localization data validation is now provided by the shared package rather than a
new historical `bosd_*` script:

```bash
python -m botsd data-audit data
python -m botsd qa-summary qa/playthrough_matrix.csv
```

The first command validates authoritative dataset counts/IDs and audits only English/localized
fields; it deliberately does not flag the Japanese source/reference columns.

## Streaming extraction / verification cleanup

`bosd_verify_extract_iso_assets.py` now delegates to `botsd.extract`. Historical command syntax is
preserved, but the implementation no longer calls `iso.read_bytes()` on a multi-gigabyte disc image.

Preferred shared commands:

```bash
python -m botsd iso-verify-assets game.iso hashes.tsv --extract SCRPACK.SDA=out/SCRPACK.SDA
python -m botsd extract-components public_v1.2.iso v12_components --version v1.2
```

If you already have an exact public-v1.2 ISO, release generation can now skip the manual extraction
step entirely:

```bash
python -m botsd v13-release-from-iso \
  public_v1.2.iso Duel_Masters_Birth_of_Super_Dragon_English_v1.2.ppf out
```

## Additional shared migrations

Two more production helpers now use descriptive shared modules while preserving their historical
filenames:

- `bosd_shop_packdesc_fixed.py` -> `botsd.shop`. The English booster descriptions themselves now
  live in `localization/en/shop_boosters.json`, so language text is no longer embedded in the binary
  record writer.
- `bosd_apply_datapack_chunk_patch.py` -> `botsd.datapack`. The patch ZIP manifest remains
  hash-gated and every changed chunk must keep its exact allocation.

Equivalent shared commands are `python -m botsd shop-descriptions ...` and
`python -m botsd datapack-patch ...`.

## Card-text shared migration

`bosd_cardtext_externalizer_v3.py` and `bosd_rebuild_combined_list.py` now delegate to
`botsd.cardtext`. The shared module owns the retail/combined pointer formats, executable master-text
parsing, CP932/`Ü` rules, CSV source guards and externalization patch. Historical command syntax is
retained for old notes and handoffs.

Preferred package commands are:

```bash
python -m botsd cardtext-check SLPM_658.82 LIST_1.BIN
python -m botsd combined-list --display DISPLAY.csv --master MASTER.csv --output LIST_1.BIN
python -m botsd cardtext-externalize SLPM_658.82 LIST_1.BIN MASTER.csv DISPLAY.csv OUT_ELF OUT_LIST
```

`bosd_deck_text_ui82.py` is also now a compatibility CLI over `botsd.decktext`; its 60 English deck
callouts/titles and Japanese source guards live in `localization/en/deck_text.json`. The preferred
command is:

```bash
python -m botsd deck-text RETAIL_DECK_DIR OUTPUT_DECK_DIR \
  --translations localization/en/deck_text.json
```

## Shared package status

The following historical filenames are now compatibility CLIs over shared `botsd` modules rather than independent implementations:

- `bosd_iso_layout_patcher_v2.py` → `botsd.iso9660`
- `bosd_make_ppf3.py` → `botsd.ppf`
- `bosd_ui_archive_tool_v1.py` → `botsd.archive`
- `bosd_ui_lzss_strong.py` → `botsd.lzss`
- `bosd_v13_maintenance.py` → `botsd.v13` / `botsd.semantic_assets`
- `bosd_v13_release_builder.py` → `botsd.release`
- `bosd_verify_extract_iso_assets.py` → `botsd.extract`
- `bosd_shop_packdesc_fixed.py` → `botsd.shop`
- `bosd_apply_datapack_chunk_patch.py` → `botsd.datapack`
- `bosd_cardtext_externalizer_v3.py` / `bosd_rebuild_combined_list.py` → `botsd.cardtext`
- `bosd_deck_text_ui82.py` → `botsd.decktext`
- `bosd_ui76_rules_wordwrap.py` → `botsd.ruleswrap`
- `bosd_flavor_import_v2.py` → `botsd.flavor`
- `bosd_keyboard_default_ui81.py` → `botsd.keyboard`
- `bosd_font_ue_patch.py` → `botsd.fontlink`

The wrappers are intentionally retained as compatibility/history entry points even after their active logic moves into shared modules.

## Phase 8 graphics/font migrations

Three additional checkpoint-era tools are now compatibility CLIs over shared code:

- `bosd_font_minimal_polish_ui81.py` → `botsd.font_polish`; the apostrophe and lowercase-l glyph
  derivation is source-readable and uses `botsd.fontlink`.
- `bosd_static_label_polish_ui81.py` → `botsd.static_labels` / `botsd.ui_graphics`; English label
  strings live in `localization/en/static_labels_ui81.json` while geometry/palette metadata lives in
  `botsd/assets/static_labels_ui81.json`.
- `bosd_graphic_residuals_ui82.py` → `botsd.graphic_residuals` / `botsd.ui_graphics`; NO RANK,
  BLOCK C and HOF are rebuilt from accepted source pixels under declared containment boxes.

These migrations preserve the historical command filenames and fixed archive allocations.

- `bosd_offline_exec_residuals_ui82.py` → `botsd.exec_strings`; UI82 English fixed-slot strings live
  in `localization/en/offline_exec_residuals_ui82.json`, while source guards and offsets live in
  `botsd/assets/offline_exec_residuals_ui82.json`. The obsolete network-trading block remains an
  explicit protected range.

- `bosd_wait_title_ui82.py` → `botsd.wait_title` / `botsd.gamefont`; the WAIT string is externalized
  to `localization/en/wait_title_ui82.json` and TITLE overlay-removal rectangles are semantic asset
  metadata. The renderer now uses the shared FONTLINK glyph API instead of importing the UI75 card
  pipeline dynamically.

## Streaming UNPACK migrations

The frozen-card checkpoint tools no longer need to load the full ~151 MiB `UNPACK.IMG` into Python
memory:

- `bosd_apply_unpack_second_names_ui82.py` → `botsd.sda` / `botsd.unpack`
- `bosd_verify_ui76_frozen_unpack_v2.py` → `botsd.sda` / `botsd.unpack`
- `bosd_verify_ui82_frozen_unpack.py` → `botsd.sda` / `botsd.unpack`

Preferred shared commands are `unpack-render-second-names`, `unpack-apply-second-names`,
`unpack-verify-ui76`, and `unpack-verify-ui82`. The parser verifies the complete outer offset table and checks the final chunk
through EOF.


## UI75/UI76 production-stage migrations

- `bosd_unpack_cardfaces_ui75_portable.py` now delegates to `botsd.cardfaces`. Geometry/chunk metadata
  lives in `botsd/assets/cardfaces_ui75.json`; names/rules/races/flavor stay in the existing CSVs.
  The new implementation streams `UNPACK.IMG`, preserves outer slack, and uses the final
  palette-quantized large face as the thumbnail source.
- `bosd_ui76_cardinfo_patch.py` now delegates to `botsd.cardinfo`. Checkpoint addresses/ranges and
  source hash are in `botsd/assets/cardinfo_ui76.json`; English text remains in the master CSV.
- `bosd_build_unpack_second_names_ui82.py` now delegates to `botsd.second_names`, the recovered
  semantic renderer for all 677 UI82 name sprites. The exact recovered historical script is retained
  under `tools/archaeology/` for provenance.
- `bosd_create_unpack_second_names_ui82.py` / `unpack-create-second-names` remain the binary
  checkpoint-packaging path for comparing or preserving an already-built UI82 layer.
## Phase 12 production migrations

- `ui76_webp_cardfaces.py` now delegates to `botsd.card_sources` and `botsd.fullcard`. Pinned card-database/source selection is separated from the streaming UNPACK writer; the accepted large/thumbnail palette and fixed-allocation guards are retained.
- `bosd_ui_polish_v11.py` now delegates to `botsd.ui_polish_v11`; label/slot geometry is machine-readable and English UI strings live under `localization/en/`.
- `bosd_duelpts_issue2_fix.py` now delegates to `botsd.duelpts`; the measured Issue #2 corruption signature and geometry are versioned in `botsd/assets/duelpts_issue2.json`.


## Phase 17 SCRPACK language source

The v1.2 story baseline is no longer represented only by a generated paired catalog. Maintained
translation-only source now lives in:

- `localization/en/story_dialogue_v12.csv` — 9,499 changed `0x1D03` dialogue rows
- `localization/en/story_choices_v12.csv` — 293 `0x1F03` menu-choice rows

Use the package-native commands rather than adding another one-off story patch script:

```bash
python -m botsd scrpack-language-audit /path/to/v1.2/SCRPACK.SDA
python -m botsd scrpack-apply-language /path/to/retail/SCRPACK.SDA out/SCRPACK.SDA
```

The second command is production-strict by default: exact retail input hash, fixed SDA chunk
allocations, and exact public-v1.2 output hash are required.
