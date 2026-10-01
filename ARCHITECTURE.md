# Architecture

The project is being migrated from a collection of historical `bosd_*` scripts into a shared,
tested Python package without changing the verified v1.3 release bytes.

## Layers

1. **`botsd/` shared library** — format parsing, hashing, compression, ISO/PPF operations,
   regression metadata and text QA.
2. **Compatibility CLIs in `tools/`** — historical filenames retained so old build notes and
   scripts keep working while their implementations move into `botsd/`.
3. **Localization data in `data/`** — card mappings and translated text, separate from the binary
   format implementation.
4. **Release-specific semantic maintenance** — v1.3 fixes and known release hashes. These remain
   hash-guarded and are gradually being converted from opaque byte reproduction to semantic source
   builders.

## Authoritative release manifest

`botsd/release_manifest.json` is the single release-level source of truth for:

- game serial and release version
- clean and patched ISO sizes
- release PPF/hotfix hashes and sizes
- component sizes, v1.2/v1.3 hashes and verified ISO offsets
- card/text counts and card-layer ranges
- keyboard-mode addresses
- the retained DUELPTS hash/location

`botsd.manifest` only exposes typed Python objects derived from that JSON. New tools should not
copy these values into additional scripts unless a format genuinely requires a local constant.

## Shared modules

- `botsd.hashing` — streaming SHA-256 helpers and ranged hashing.
- `botsd.lzss` — game LZSS decoder plus fast and fixed-allocation/optimal encoders.
- `botsd.archive` — packed UI archive parse/rebuild logic.
- `botsd.indexed_tga` — minimal indexed-TGA parser/editor for UI assets.
- `botsd.iso9660` — seek-based ISO9660 traversal and replacement/retarget patching.
- `botsd.ppf` — PPF3 parse, verify, apply and create operations.
- `botsd.build` — verified clean-ISO + release-PPF v1.3 build path.
- `botsd.patching` / `botsd.regressions` — guarded same-size maintenance edits and permanent
  regression definitions.
- `botsd.textqa` — localization text scans such as Japanese/full-width Latin/CP932 checks.

## Compatibility policy

Historical filenames are not renamed merely for cleanliness. A legacy tool should become a thin
wrapper around `botsd/` first. Rename/delete it only after automated tests prove the shared
implementation preserves the required behavior and downstream imports have been migrated.

Current wrappers include:

- `tools/bosd_ui_archive_tool_v1.py` → `botsd.archive`
- `tools/bosd_ui_lzss_strong.py` → `botsd.lzss.compress_optimal`
- `tools/bosd_iso_layout_patcher_v2.py` → `botsd.iso9660`
- `tools/bosd_make_ppf3.py` → `botsd.ppf`

## Memory model

Disc-image operations are streaming/seek based. The ISO patcher copies the source in bounded
chunks, reads only ISO9660 directory sectors/descriptors, and patches the output file directly.
The PPF builder/applier likewise works in bounded chunks. A multi-gigabyte ISO must never be read
into a single Python `bytes`/`bytearray` object.

## Release reproducibility

There are two distinct goals:

1. **Binary reproducibility** — prove the final bytes match the published release hashes.
2. **Semantic reproducibility** — prove an editable source transformation creates those bytes.

The maintained v1.3 path now has both strong binary reproducibility and semantic builders for the
formerly opaque maintenance assets. Published hashes remain the final verification oracle while
source recipes explain how the accepted bytes are derived. Remaining semantic gaps are confined to
older pre-v1.3 production steps that have not yet been proven from editable sources.


## Semantic v1.3 visual assets

Phase 3 removes the two opaque Base85/XOR release blobs from the canonical v1.3 maintenance path.
The final packed bytes are now generated from editable source recipes:

- `botsd/assets/tchange_layout_v13.json` describes the CHANGE/TURN layer order, source rows,
  pixel shifts, two-row boundary masks, background index, and exact compressor choice. The builder
  reuses the already-localized English glyph pixels from the exact public-v1.2 TGA.
- `botsd/assets/ace_badge_v13.json` describes the Deck Builder badge destination geometry, palette
  symbol mapping, compression and fixed-allocation guards. The exact accepted English 18x16 indexed
  pixel template lives in `localization/en/ace_badge_v13.json`.
- `botsd.semantic_assets` applies those recipes and `botsd.v13` combines them with the guarded
  executable/SCRPACK byte patches.

Both semantic builders preserve the original archive allocation and recompress with the historical
encoder/settings that reproduce the published v1.3 files byte-for-byte: optimal/256 for TCHANGE and
fast/96 for the ACE member. The published hashes remain the final authority.


## Language-specific semantic raster source

The v1.3 Deck Builder key-card badge is still reproduced from the exact accepted 18×16 indexed
pixel template so published output remains byte-identical. Phase 20 moves that template to
`localization/en/ace_badge_v13.json`; `botsd/assets/ace_badge_v13.json` now contains only the
language-independent destination geometry, palette-symbol mapping and archive/compression guards.
`botsd.v13` passes its selected language through to the DECK semantic builder.


## Release composition

`botsd.release` now owns the v1.3 PPF composition logic. It consumes the canonical manifest, the
semantic `botsd.v13` component builder, and the shared PPF3 parser/writer. The historical
`tools/bosd_v13_release_builder.py` filename remains only as a compatibility CLI. This removes a
second set of release hashes, component offsets, PPF parsing code, and maintenance imports from the
active architecture.


## Localization separation

The shared `botsd/` package is language-independent wherever practical. Existing v1.3 English CSVs
remain under `data/` so historical builders are not broken, while `localization/README.md` defines the
forward language-pack/provenance model. Migration must preserve current byte output before English
data is moved. No existing string is silently assigned a stronger review/provenance status than the
repository actually records.

## Localization manifests and provenance

`localization/en/manifest.json` is the bridge across the entire checked-in English localization
surface. Schema v2 supports historical CSV tables plus semantic JSON record lists and keyed maps,
including per-field source guards and explicit row-level review metadata. This lets deck/shop/UI and
v1.3 maintenance JSON participate in the same provenance layer without duplicating their text.

`botsd.localization` validates these mappings, rejects orphaned language `.csv`/`.json` files, and
can export one provenance worklist. The export remains conservative: legacy labels are preserved
verbatim, while stronger review states are used only when the language resource explicitly records
them (for example the runtime-verified v1.3 dialogue wrap).

The checked-in English localization surface is now represented through the schema-v2 manifest,
including the full v1.2 SCRPACK dialogue/choice datasets and the migrated deck/shop/UI resources.
Older pre-v1.3 production steps outside SCRPACK may still require semantic reconstruction, but new
language-bearing resources should not bypass `localization/<language>/` and its provenance audit.

## Machine-readable QA corpus

The `qa/` directory separates four kinds of evidence:

- `playthrough_matrix.csv` — game-area coverage and explicit not-tested/partial/complete states
- `compatibility_matrix.csv` — emulator/hardware coverage
- `save_compatibility.csv` — normal memory-card compatibility separate from emulator save states
- `regressions.csv` — permanent known-bug regressions and whether runtime confirmation exists

`botsd.qa_matrix` validates all four so documentation cannot silently drift into invalid status
values or duplicate cases.

## Streaming asset extraction

`botsd.extract` replaces the remaining historical ISO-verification helper that loaded the entire
disc into RAM. It can validate a basename/SHA-256 TSV against ISO9660 entries, selectively extract
verified files, or extract the four exact public-v1.2/v1.3 maintenance components using release
manifest offsets/hashes. `tools/bosd_verify_extract_iso_assets.py` is now a compatibility wrapper.

## Separating localization text from binary writers

The first historical text-bearing production tool has been split cleanly:

- `botsd.shop` knows only the verified `0x68` booster-record binary layout and containment rules.
- `localization/en/shop_boosters.json` contains the English descriptions.
- `tools/bosd_shop_packdesc_fixed.py` remains a compatibility CLI over those two layers.

This is the pattern future deck/story/UI migrations should follow: language-independent binary
structure in `botsd/`, editable language content under `localization/<language>/`, and hashes/tests
as verification rather than as the source of semantic intent.

`botsd.datapack` likewise owns the generic fixed-size, hash-gated DATAPACK chunk patch format rather
than leaving that parser embedded in a one-off command script.

## Card-text subsystem migration

The 4,058-pointer card-text path is now shared code instead of logic imported from one historical
command script:

- `botsd.cardtext` owns retail `LIST_1.BIN` parsing, the 2,376-entry executable master-text table,
  CP932/`Ü` encoding rules, translation-CSV source guards, combined-LIST construction/deduplication,
  pointer-table validation, and the executable externalization patch.
- `tools/bosd_cardtext_externalizer_v3.py` and `tools/bosd_rebuild_combined_list.py` are compatibility
  CLIs over that module.
- The authoritative counts (1,682 display + 2,376 master = 4,058 pointers) come from the release
  manifest instead of being independently redefined by each active build path.

This is an important step toward language separation: the binary layout/encoding logic lives in the
shared package while the English rows remain in the existing release-critical CSV datasets. CI can
rebuild `LIST_1.BIN` from those CSVs and compare it with the published localized hash whenever the
full repository data is present.

## Fixed DECK text localization separation

The historical `bosd_deck_text_ui82.py` table no longer needs to embed English/Japanese strings in
binary-writing code. `botsd.decktext` owns the two verified fixed fields (`0x06+40` callout and
`0x2E+20` title), source-CP932 guards, ASCII fit checks and the hard containment rule that every byte
from `0x42` onward remains identical. `localization/en/deck_text.json` now owns the 60 English deck
text records and their Japanese source guards. The old script remains a compatibility CLI.

## Translation processing

Language-independent translation processing is being moved out of historical stage scripts.
`botsd.ruleswrap` owns Card Info word-boundary wrapping and `botsd.flavor` owns printing-specific
flavor import/encoding validation. The English strings remain in `data/` / `localization/en/`; the
shared package contains transformation rules, not a duplicate language corpus.

## Font/input maintenance

`botsd.fontlink` owns the reverse-engineered FONTLINK/DPAC directory, member codec and 4bpp glyph
helpers. The reserved English `Ü` derivation is described by `botsd/assets/font_ue.json`; its retail
input hash is resolved through the central release manifest instead of duplicated in the historical
wrapper. `botsd.keyboard` owns the verified keyboard-default byte location and keeps the historical
v1.2 mode-6 stage distinct from the final v1.3 mode-9 correction. Both stages now have package-native
commands while the historical filenames remain compatibility wrappers.

## Static UI graphics migration

The historical UI81/UI82 graphics stages no longer need to reimplement indexed-TGA parsing,
palette matching, fixed-allocation archive writes or pixel-containment checks. `botsd.ui_graphics`
provides those shared primitives on top of `botsd.indexed_tga`, `botsd.archive` and the optimal
LZSS encoder.

`botsd.static_labels` separates UI81 English label text into
`localization/en/static_labels_ui81.json`; verified boxes, palette indices and source hashes live in
`botsd/assets/static_labels_ui81.json`. `tools/bosd_static_label_polish_ui81.py` is now a
compatibility CLI over that semantic source.

`botsd.graphic_residuals` similarly owns the UI82 `NO RANK`, `BLOCK C` and `HOF` raster-reuse
operations described by `botsd/assets/graphic_residuals_ui82.json`. Those operations copy or derive
pixels from accepted source artwork rather than storing replacement binary blobs.

The minimal runtime-font apostrophe/lowercase-l repair has also moved to `botsd.font_polish`, using
the shared FONTLINK codec/glyph primitives. This leaves the historical filename as a wrapper while
keeping the actual glyph derivation source-readable.

## Executable residual-string separation

`botsd.exec_strings` now owns the generic CP932 fixed-slot writer and containment checks used by the
final UI82 executable-residual stage. English target strings are stored in
`localization/en/offline_exec_residuals_ui82.json`; verified offsets, slot sizes, source guards and
the intentionally untouched network-trading range are stored separately in
`botsd/assets/offline_exec_residuals_ui82.json`. This removes another block of English literals and
magic offsets from an active writer while retaining the historical script as a compatibility CLI.

## Game-font renderer and WAIT/TITLE migration

`botsd.gamefont` exposes the game's half-width ASCII FONTLINK pages as Pillow glyph masks. This
removes the dependency on dynamically importing `GameFont` from the large UI75 card-face script and
gives later UI/card-image migrations one canonical renderer.

`botsd.wait_title` uses that renderer plus the shared indexed-TGA quantizer for the UI82 WAIT text.
The TITLE stage is represented semantically as two verified clear rectangles; it rebuilds the packed
archive through `botsd.archive` and verifies all non-target members decompressed byte-identically.
The English WAIT string lives in `localization/en/wait_title_ui82.json`, while source hashes and
rectangles live in `botsd/assets/wait_title_ui82.json`.

## Streaming outer-SDA / UNPACK handling

`botsd.sda.OuterSDA` now owns the top-level `sda\0` offset-table format used by `UNPACK.IMG`.
It reads only the header/offset table and individual chunk ranges, rather than loading the entire
151,525,376-byte archive for simple verification or fixed-size replacement. Layout comparisons and
changed-chunk scans operate chunk-by-chunk.

`botsd.unpack` builds on that primitive for the frozen UI76/UI82 card-layer workflows: inventory
chunk-set validation, deterministic creation/application of the 677-chunk second-name patch ZIP,
retail/UI76/UI82 changed-set assertions, and per-chunk manifest hashes. The historical apply/verify
scripts remain compatibility CLIs and `bosd_create_unpack_second_names_ui82.py` is the descriptive
creation-side wrapper.

`botsd.second_names` now owns the recovered semantic source step for the UI82 second-name layer.
Starting from exact retail chunks 2037..2713, it detects the Japanese title anti-alias palette ramp,
clears only the connected title component, renders the canonical English name with `botsd.gamefont`,
and quantizes only `(0,2,128,15)` back into the original indexed palette. The recovered historical
script is preserved verbatim under `tools/archaeology/`; the historical filename at `tools/` is now a
compatibility CLI over the shared implementation. The frozen English payload digest is
`dea8fa559db96f9cc38bfeddac8996dc27a2c90c3f2fdd28e9ece659f76c0f92`, proven against all 677
chunks of the accepted v1.3 UNPACK.

## UI75 card-face pipeline

`botsd.cardfaces` now owns the 677-card large-face/thumbnail renderer that was previously embedded in
`bosd_unpack_cardfaces_ui75_portable.py`. The editable geometry and chunk mapping live in
`botsd/assets/cardfaces_ui75.json`; card names/rules/races/flavor continue to come from the existing
release-critical CSVs. The builder uses `botsd.gamefont`, `botsd.indexed_tga`, `botsd.archive`,
`botsd.lzss` and the streaming `botsd.sda.OuterSDA` API. It patches one card at a time in a copied
UNPACK image instead of materializing the entire ~151 MiB container in Python memory. Large-card
inner archives keep their fixed allocation and outer slack byte-identical; thumbnails derive from
the final palette-quantized large face, matching the accepted historical pipeline.

## UI76 embedded Card Info repack

`botsd.cardinfo` now owns the executable-resident Card Info rule/race repacker. Its checkpoint hash,
pointer-table addresses, safe zero-slack range, race overflow range, protected getter/cave addresses
and canary IDs are declared in `botsd/assets/cardinfo_ui76.json`. English rule/race text remains in
the master CSV. The builder conservatively scans for shared pointers before reclaiming Japanese rule
storage, guards pointer-like values around the zero-slack pool, deduplicates English rule strings,
retargets only rule master slots, and verifies that every non-rule master pointer and the accepted
CardText lifecycle code remain byte-identical. The historical UI76 script is now only a wrapper.
## UI76 whole-card source/conversion pipeline

`botsd.card_sources` owns the pinned external-card-database identity, card-name normalization, printing-selection rules, exception-image manifest validation and source provenance fields used by the historical UI76 whole-card build. Network acquisition is an optional development action; tests and normal patch application never download card images.

`botsd.fullcard` owns the binary conversion. It streams the retail `UNPACK.IMG`, rewrites only the 677 large-card chunks and corresponding 677 printed-thumbnail chunks, preserves each card texture's original indexed palette/header and fixed chunk allocations, and derives the thumbnail from the final palette-quantized large face. The historical `ui76_webp_cardfaces.py` filename is retained as a compatibility CLI.

This keeps source acquisition/provenance separate from the game-format writer and prevents the old production script from being the only specification of how the accepted UI76 layer was made.

## DUELPTS Issue #2 maintenance repair

`botsd.duelpts` is the maintained source-level implementation of the v1.2 duel-number repair. `botsd/assets/duelpts_issue2.json` records the clean/v1.1/corrected hashes, the exact damaged numeric rectangle, the original and corrected `LEFT` geometry, palette indices, digit boxes, and the measured v1.1 mismatch signature (`6=71`, `7=136`, `8=205`, `9=206`; digits 1–5 unchanged).

The builder refuses unexpected preimages, restores the shared digit pixels from the verified retail atlas, moves only the accepted `LEFT` raster below row 385, verifies no pixel escapes the original LEFT rectangle, and checks the corrected archive hash.
## Versioned historical checkpoint metadata

Release-wide constants live in `botsd/release_manifest.json`. It now also owns the retail `UNPACK.IMG` identity/size and UI82 second-name range used by the streaming card-layer tools. Checkpoint-specific semantic recipes that are not release-wide belong under `botsd/assets/`, including `keyboard_ui81.json`, `font_polish_ui80.json`, `cardinfo_ui76.json`, and `duelpts_issue2.json`. Shared code reads these manifests rather than maintaining another copy of the same hashes, counts, offsets or glyph geometry.

## Semantic v1.3 executable and SCRPACK maintenance

The v1.3 maintenance delta no longer depends on a canonical table of absolute byte patches for the
executable or `SCRPACK.SDA`.

`botsd.exe_maintenance` audits the 2,376-entry executable master-text pointer table and proves the
v1.2 Aura Pegasus defect structurally: exactly one live master pointer lands inside another live
C string. The repair moves the intended bytes into the two verified zero bytes immediately before
the damaged string, inserts termination before the intruding rule pointer, updates only the damaged
master pointer, and then requires the entire pointer-overlap audit to be clean. The keyboard
maintenance byte is applied afterward through the shared `botsd.keyboard` mode metadata.

`botsd.scrpack` parses script chunks as a sequence of `u16 opcode, u16 payload_size` commands. The
three translated `0x070C` probability branches are identified by SDA chunk and command ordinal;
their destinations are expressed as target command ordinals. This lets the builder calculate the
correct translated chunk-relative address from the actual command stream, rather than preserving
retail offsets that became stale when English commands changed length.

The confirmed story wrap is an `0x1D03` dialogue command edit. Its source/replacement English text
lives in `localization/en/v13_maintenance.json`, while command ordinals/opcodes live in
`botsd/assets/scrpack_v13.json`. The writer updates the embedded string length and zero-fills only
the existing command allocation. Exact component and release-PPF hashes remain the final guard.


## Story/script localization compiler

`botsd.storytext` uses **SDA chunk index + script command ordinal** as the stable identity of story
resources, for example `scrpack.123.0646`. Raw byte offsets are deliberately not identities because
English payload sizes move later commands within the same fixed chunk.

The maintained language source is split into `localization/en/story_dialogue_v12.csv` and
`localization/en/story_choices_v12.csv`. The repository stores only stable IDs and English text;
extracted Japanese retail story text is not checked in.

Exact retail/v1.2 pairing proves that all 208 outer SDA chunk boundaries stay fixed and all 184,683
meaningful command opcodes retain stable chunk/ordinal identity. Variable-size `0x1D03` dialogue
and `0x1F03` choice commands grow or shrink by consuming/releasing trailing four-byte zero commands
(`opcode=0,payload_size=0`) inside the fixed chunk allocation.

Five historical opcode families contain command-relative u32 targets that the v1.2 production pass
relocated after text resizing: `0x010C`, `0x020C`, `0x1212`, `0x1312`, and `0x1412`. Exact paired
verification accounts for 2,799 relocated target fields in 1,960 commands, with each retail target
and translated target resolving to the same command ordinal. The three `0x070C` probability branches
are the documented exception: their retail numeric targets remained stale in v1.2 and are therefore
preserved deliberately by the v1.2 compiler before the semantic v1.3 maintenance stage corrects
them by command ordinal.

With the exact retail SCRPACK plus the checked-in English datasets, the compiler reproduces the
public-v1.2 SHA-256 `1e3208976bb90749598e1d7359cfda51fe7c095cf3db10459265aeb5dd133051`
byte-for-byte. Applying the existing semantic v1.3 maintenance stage then reproduces public v1.3
SHA-256 `4d7e561344917193f9e672515edd5d2ccf576dcb7ed88d2ddc2092773689df26`.

The catalog exporter remains useful for review: it pairs retail and translated resources by stable
identity and can emit a local CSV containing both sides. That catalog should normally remain outside
version control because it contains extracted retail script text; it is no longer required as a
production source input.
