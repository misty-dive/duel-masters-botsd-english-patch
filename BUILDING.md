# Building and verification

## Environment

Supported Python: **3.10+**.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,graphics]'
```

`pyproject.toml` is the authoritative environment definition. `tools/requirements.txt` remains only
for historical compatibility.

## CI-equivalent checks

Run before committing:

```bash
ruff check botsd tests
mypy botsd
pytest
```

GitHub Actions runs the same checks on Python 3.10 and 3.12.

## Inspect the authoritative release manifest

```bash
python -m botsd manifest
```

Verify a public component:

```bash
python -m botsd verify-file SLPM_658.82 /path/to/SLPM_658.82 --version v1.3
```

## Rebuild the v1.3 maintenance delta from source-level recipes

Given the four exact public-v1.2 maintenance components:

```bash
python -m botsd v13-components /path/to/v12_components out/v13_components
```

The executable build derives the Aura repair from the pointer-overlap invariant and the keyboard
mode from versioned metadata. `SCRPACK.SDA` is parsed command-by-command; branch targets come from
command ordinals and the confirmed English dialogue replacement comes from
`localization/en/v13_maintenance.json`. No canonical raw v1.3 executable/SCRPACK byte-diff table is
used. The command still refuses any source component whose public-v1.2 hash is wrong and verifies
the exact published v1.3 output hash.

## One-command release-image build

Given your clean Japanese retail ISO and the published full v1.3 PPF:

```bash
python -m botsd build \
  --source /path/to/original.iso \
  --patch /path/to/Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf \
  --output /path/to/Duel_Masters_BOTSD_English_v1.3.iso
```

The command verifies:

- exact clean ISO size and SHA-256
- exact published v1.3 PPF size and SHA-256
- PPF3 structure/order/non-overlap
- final patched ISO size
- all four v1.3 maintenance component hashes at their verified ISO locations

The full output ISO SHA-256 is not hard-coded because no whole-v1.3-image hash was established as
part of the public release; component verification is therefore used after applying the exact
published PPF.

## PPF utilities

```bash
python -m botsd ppf-info patch.ppf
python -m botsd ppf-create source.bin target.bin output.ppf --description 'description'
```

Both creation and application stream data rather than loading complete disc images into memory.

## ISO utilities

List entries:

```bash
python -m botsd iso-list original.iso
python -m botsd iso-list original.iso --basename SCRPACK.SDA
```

Patch files into a retail ISO:

```bash
python -m botsd iso-patch original.iso patched.iso changes/SCRPACK.SDA changes/SLPM_658.82
```

Same-size replacements are written in their original sectors. Enlarged replacements are appended
at the ISO end and only their ISO9660 directory records are retargeted. Existing sectors are not
relocated.

## Text QA

Audit only translation/localized columns, not the Japanese source columns:

```bash
python -m botsd text-audit data/bosd_master_text_card_rules_complete.csv \
  --field translation --fail-on-findings
```

Use this selectively: some project text intentionally contains symbols such as `Ü` that are mapped
by the game font pipeline.

## Canonical v1.3 release generation

`botsd.release` is the canonical v1.3 release compositor. `python -m botsd v13-release` rebuilds
the public full and hotfix PPFs with byte-for-byte hash guards, while
`tools/bosd_v13_release_builder.py` is retained only as a compatibility entry point for historical
build notes.


## Rebuild the v1.3 maintenance components semantically

With the exact four public-v1.2 component files in one directory:

```bash
python -m botsd v13-components /path/to/v12_components /path/to/v13_components
```

Required input basenames are `SLPM_658.82`, `SCRPACK.SDA`, `TCHANGE.IMG`, and `DECK.DAT`.

The v1.3 DECK `ACE` badge uses `localization/en/ace_badge_v13.json` for the exact accepted language
pixel template. Its box, palette and compression rules remain in `botsd/assets/ace_badge_v13.json`;
this split changes no published bytes.
Every input is size/hash guarded. The command must reproduce the published v1.3 component hashes
from `botsd/release_manifest.json`; otherwise it fails.

For local golden tests using legally supplied game files:

```bash
BOTSD_V12_COMPONENT_DIR=/path/to/v12_components pytest
```

This activates the exact four-component regression tests that CI skips because copyrighted game
files are intentionally not stored in the repository.


## Rebuild the published v1.3 release PPFs

Once the exact public-v1.2 component directory and official v1.2 full PPF are available:

```bash
python -m botsd v13-release \
  /path/to/v12_components \
  /path/to/Duel_Masters_Birth_of_Super_Dragon_English_v1.2.ppf \
  /path/to/release_output
```

The shared release builder reconstructs the four v1.3 components semantically, verifies their known
public-v1.2 ISO locations against the official v1.2 PPF, emits the v1.2 -> v1.3 hotfix, composes the
clean-ISO -> v1.3 full PPF, and refuses output unless both generated PPFs reproduce the published
v1.3 size and SHA-256 exactly.

For the complete local golden suite, also export:

```bash
export BOTSD_V12_COMPONENT_DIR=/path/to/v12_components
export BOTSD_V12_FULL_PPF=/path/to/Duel_Masters_Birth_of_Super_Dragon_English_v1.2.ppf
pytest
```

## Development environment

The repository pins its CI/development tools in both the `dev` extra and `requirements-dev.txt`.
Install the package and development tools with:

```bash
python -m pip install -e '.[dev,graphics]'
```

Graphics/image rebuild paths remain an explicit optional extra:

```bash
python -m pip install -e '.[graphics,dev]'
```

The release/runtime core intentionally has no mandatory third-party Python dependencies.

## Repository-wide QA and localization metadata

Validate all machine-readable QA matrices:

```bash
python -m botsd qa-audit qa
```

Validate the current English localization manifest against the historical release-critical CSVs:

```bash
python -m botsd localization-audit localization/en/manifest.json --root .
```

The schema-v2 manifest covers both CSV and JSON localization sources. The audit validates configured
record counts/selectors/review states and reports any `.csv`/`.json` file under `localization/en/`
that is not registered.

Export a conservative provenance/review worklist without copying translation text into a second
source file:

```bash
python -m botsd provenance-export localization/en/manifest.json \
  --root . --output local/provenance_en.csv
```

The exporter intentionally leaves every standardized review status as `unreviewed` unless a future
maintainer records stronger row-level evidence. Existing source and legacy status fields are
preserved rather than reinterpreted.

## Streaming component extraction

Historical `bosd_verify_extract_iso_assets.py` functionality is available through the shared package
without loading the disc image into memory:

```bash
python -m botsd iso-verify-assets original.iso hashes.tsv \
  --extract SCRPACK.SDA=work/SCRPACK.SDA
```

For an exact public v1.2/v1.3 patched ISO, extract the four maintenance components with release
manifest guards:

```bash
python -m botsd extract-components public_v1.2.iso work/v12 --version v1.2
```

If you possess the exact public-v1.2 ISO and official v1.2 full PPF, the complete v1.3 release PPF
rebuild can now be run without manually preparing a component directory:

```bash
python -m botsd v13-release-from-iso \
  public_v1.2.iso \
  Duel_Masters_Birth_of_Super_Dragon_English_v1.2.ppf \
  release_output
```

## Card-text source rebuilds

Verify the retail text structures and executable patch sites before externalizing them:

```bash
python -m botsd cardtext-check extracted/SLPM_658.82 extracted/LIST_1.BIN
```

Rebuild the localized 4,058-pointer `LIST_1.BIN` directly from the repository translation tables:

```bash
python -m botsd combined-list \
  --display data/bosd_list_display_card_rules_complete.csv \
  --master data/bosd_master_text_card_rules_complete.csv \
  --output work/LIST_1.BIN
```

For the original retail executable/LIST pair, build both the externalized executable and combined
LIST in one guarded step:

```bash
python -m botsd cardtext-externalize \
  extracted/SLPM_658.82 extracted/LIST_1.BIN \
  data/bosd_master_text_card_rules_complete.csv \
  data/bosd_list_display_card_rules_complete.csv \
  work/SLPM_658.82 work/LIST_1.BIN
```

The source-Japanese column is checked against the supplied retail game before translations are
accepted. The generated combined LIST is parsed back and compared entry-for-entry before output is
written. Literal `~` remains reserved for the patch's `Ü` glyph mapping.

## Rebuild hidden deck text

The 60 fixed DECK data records are now driven by editable localization data:

```bash
python -m botsd deck-text extracted/DECK localized/DECK \
  --translations localization/en/deck_text.json
```

The command requires an exact filename inventory, checks both Japanese source fields before writing,
keeps file sizes unchanged, and proves that all deck/card composition bytes at `0x42..EOF` remain
byte-identical.

## Historical UI semantic stages

Checkpoint-era command filenames remain available, but the preferred shared commands for migrated
UI stages are now:

```bash
python -m botsd font-ue-patch RETAIL_FONTLINK.PAC FONTLINK_UE.PAC
python -m botsd font-polish FONTLINK_UE.PAC FONTLINK_POLISHED.PAC
python -m botsd keyboard-v12-stage PRE_UI81_SLPM_658.82 UI81_SLPM_658.82
python -m botsd static-labels ADV.DAT ADVSCN.DAT DUELPTS.DAT out --font path/to/font.ttf
python -m botsd graphic-residuals \
  --lobby-in LOBBY.DAT --lobby-out out/LOBBY.DAT \
  --tour-in TOUR.DAT --tour-out out/TOUR.DAT \
  --deck-in DECK.DAT --deck-out out/DECK.DAT
python -m botsd exec-residuals UI81_SLPM_658.82 out/SLPM_658.82
python -m botsd wait-title \
  --wait-in WAIT.TGA --wait-out out/WAIT.TGA \
  --title-in TITLE.DAT --title-out out/TITLE.DAT --fontlink FONTLINK.PAC
```

These commands are historical build-stage reproduction tools, not steps required to apply the public
v1.3 PPF. Their input hashes/specs intentionally reject the wrong checkpoint.

## Historical Card Info and card-face source builds

The migrated historical stages are available through package-native commands:

```bash
python -m botsd cardinfo-embed UI68_SLPM_658.82 \
  data/bosd_master_text_card_rules_complete.csv out/SLPM_658.82

python -m botsd cardfaces-build RETAIL_UNPACK.IMG \
  data/unpack_card_inventory.csv FONTLINK.PAC out/UNPACK_UI75.IMG \
  --master data/bosd_master_text_card_rules_complete.csv
```

Both commands are checkpoint reproduction tools, not steps needed by users applying the v1.3 PPF.
They retain strict source guards/containment. The card-face command streams the outer UNPACK and only
keeps individual card chunks in memory.

## Historical whole-card UI76 source build

The accepted whole-card production path is now available without the checkpoint-era dynamic module arguments:

```bash
python -m botsd fullcard-build RETAIL_UNPACK.IMG \
  data/unpack_card_inventory.csv data/bosd_english_name_crosswalk_verified.csv \
  out/UNPACK_UI76.IMG out/ui76_qa \
  --cache-dir .cache/botsd --exception-dir path/to/UI76_EXCEPTION_IMAGES \
  --db path/to/duelmasters.db --offline
```

Omit `--db`/`--offline` only when intentionally allowing the development tool to obtain the pinned database and public card images. Normal CI/release application does not use the network. Source identity/provenance is written to `UI76_WEBP_MAPPING.csv`.

## Historical v1.1 / v1.2 UI maintenance builders

```bash
python -m botsd ui-polish-v11 OPT.DAT DECK.DAT SLPM_658.82 out/v11 \
  --font path/to/font.ttf

python -m botsd duelpts-fix CLEAN_DUELPTS.DAT V11_DUELPTS.DAT out/DUELPTS.DAT
```

The DUELPTS command is hash-guarded to the diagnosed clean/v1.1 pair and verifies the exact corrected v1.2 hash. `--allow-nonretail` exists only for synthetic/development tests.

The reserved-English `Ü` FONTLINK recipe is machine-readable in `botsd/assets/font_ue.json`; its
retail input hash comes from the central release manifest rather than a compatibility-script literal.
`font-ue-patch` verifies that retail checkpoint by default. `keyboard-v12-stage` reproduces the
historical mode-6 checkpoint with the source hash and byte location from `botsd/assets/keyboard_ui81.json`;
the final v1.3 mode-9 correction remains part of the later maintenance stage.

## Semantic UI82 second-name renderer

The recovered source renderer for chunks `2037..2713` is now package-native. With a verified retail
`UNPACK.IMG`, the existing card inventory CSV and the localized `FONTLINK.PAC`, regenerate the
canonical deterministic second-name patch directly from semantic English names:

```bash
python -m botsd unpack-render-second-names RETAIL_UNPACK \
  data/unpack_card_inventory.csv FONTLINK.PAC second_names.zip \
  --report second_names.csv --qa-dir qa/second_names
```

By default the command requires the exact retail UNPACK and verifies the concatenated 677 generated
payloads against the frozen v1.3 digest
`dea8fa559db96f9cc38bfeddac8996dc27a2c90c3f2fdd28e9ece659f76c0f92`.
The `--allow-nonfrozen-output` switch exists for deliberate development/other-language experiments;
it must not be used to silently redefine the v1.3 release.

## Frozen UNPACK checkpoints

For historical UI76/UI82 card-layer maintenance, prefer the streaming shared commands:

```bash
python -m botsd unpack-verify-ui76 RETAIL_UNPACK UI76_UNPACK data/unpack_card_inventory.csv
python -m botsd unpack-create-second-names RETAIL_UNPACK UI76_UNPACK UI82_UNPACK second_names.zip \
  --inventory data/unpack_card_inventory.csv
python -m botsd unpack-apply-second-names UI76_UNPACK second_names.zip UI82_REBUILT
python -m botsd unpack-verify-ui82 RETAIL_UNPACK UI76_UNPACK UI82_UNPACK \
  data/unpack_card_inventory.csv second_names.zip
```

The `unpack-create-second-names` command still packages an already-built UI82 layer for archaeology
and checkpoint comparison. `unpack-render-second-names` is the semantic source renderer. Apply/verify
commands preserve the retail outer SDA layout.

## Rebuild v1.2 SCRPACK from retail + repository language data

With the exact retail `SCRPACK.SDA`, the maintained compiler can reproduce the frozen public v1.2
component directly from the checked-in English dialogue/choice datasets:

```bash
python -m botsd scrpack-apply-language \
  /path/to/retail/SCRPACK.SDA \
  localization/en/story_dialogue_v12.csv \
  localization/en/story_choices_v12.csv \
  /path/to/output/SCRPACK.SDA
```

The command verifies the exact retail input hash and refuses output unless the generated archive
matches the public-v1.2 SCRPACK size and SHA-256. Variable-size `0x1D03`/`0x1F03` commands consume
or release trailing zero-command padding inside the unchanged 208 outer chunk allocations. The
historical relocation pass updates the five proven target-bearing opcode families (`0x010C`,
`0x020C`, `0x1212`, `0x1312`, `0x1412`). The three `0x070C` probability targets intentionally
retain their retail numeric values to reproduce the frozen v1.2 bug; `botsd v13-components`/the
semantic v1.3 SCRPACK stage repairs those three branches afterward.

For local golden verification with legally supplied files:

```bash
export BOTSD_RETAIL_COMPONENT_DIR=/path/to/retail_components
export BOTSD_V12_COMPONENT_DIR=/path/to/v12_components
pytest tests/test_storytext.py
```

The exact proven chain is:

`retail SCRPACK + repository English data -> public v1.2 SCRPACK -> public v1.3 SCRPACK`.

## Exporting the story-text catalog

With legally obtained retail and translated SCRPACK files, generate the stable story/localization
review catalog with:

```bash
python -m botsd scrpack-catalog \
  extracted-retail/SCRPACK.SDA \
  extracted-v1.2/SCRPACK.SDA \
  local/SCRPACK_story_catalog_v12.csv
```

The resource IDs are based on script command identity (`scrpack.<chunk>.<command>`), not byte
offsets. This means a translation may become longer or shorter without changing the ID of later
commands. The catalog is not required for the published v1.3 build and should normally remain
outside version control because it contains extracted retail script text.

The generated `translation` column can be passed through the existing text QA command, for example:

```bash
python -m botsd text-audit local/SCRPACK_story_catalog_v12.csv \
  --field translation --max-segment 48
```

A long segment is an audit candidate, not automatically a runtime defect; dialogue layouts have
different usable widths.
