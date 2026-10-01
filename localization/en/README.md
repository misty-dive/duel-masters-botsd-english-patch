# English localization manifest

`manifest.json` describes the complete checked-in English localization surface without moving or
duplicating text. Historical release-critical CSVs under `data/` remain authoritative where required,
while semantic JSON/CSV resources under this directory are first-class manifest datasets. Schema v2
supports CSV rows, JSON record arrays, and keyed JSON string/object maps.

The manifest deliberately assigns the default review state `unreviewed`. Existing source/status
columns are preserved as provenance, but they are **not** automatically promoted to
`human_reviewed`, `official_terminology`, or `runtime_verified` because the repository does not
record those guarantees on a row-by-row basis.

Validate the mapping after installing the cleanup overlay over the full repository:

```bash
python -m botsd localization-audit localization/en/manifest.json --root .
```

Generate a review/provenance worklist without copying the translation text itself:

```bash
python -m botsd provenance-export localization/en/manifest.json \
  --root . --output local/provenance_en.csv
```

The generated CSV is intended as a local review worklist. It is not required for the v1.3 build.
`localization-audit` also checks directory coverage: every `.csv` or `.json` resource beside this
manifest (other than `manifest.json` itself) must be registered. This prevents new language data from
becoming invisible to provenance/QA.

## Semantic localization data registered by the manifest

`ace_badge_v13.json` contains the exact indexed-pixel language template for the Deck Builder key-card
badge (`ACE`). The destination box, palette-symbol mapping, compression and fixed-allocation rules
remain language-independent in `botsd/assets/ace_badge_v13.json`. Keeping the accepted pixels in the
language package preserves frozen v1.3 output while removing English raster content from asset
layout metadata.


`shop_boosters.json` is the first production string set moved out of patch logic. It contains only
English booster descriptions/codes; the executable-record layout and safety checks live in
`botsd.shop`. Future deck/story/UI migrations should use the same separation rather than embedding
English literals inside binary writers.

`deck_text.json` contains the 60 hidden DECK record callouts/titles plus their Japanese source guards.
The fixed binary field layout and containment checks live in `botsd.decktext`; card/deck composition
bytes are never part of the language data.

`static_labels_ui81.json` contains the English text for the historical UI81 static-label
rendering stage. Verified rectangles, palette indices and source hashes are language-independent
metadata in `botsd/assets/static_labels_ui81.json`; the binary writer lives in `botsd.static_labels`.

`offline_exec_residuals_ui82.json` contains the remaining UI82 offline executable strings
(civilization combinations, booster labels, local trade warning, and memory-card title). Their
verified offsets/sizes/source guards and the excluded network block live in
`botsd/assets/offline_exec_residuals_ui82.json`; `botsd.exec_strings` performs the fixed-slot writes.

`wait_title_ui82.json` contains the remaining UI82 WAIT string. TITLE cleanup is semantic
removal of duplicate Japanese overlays and therefore needs no replacement English text. The
verified rectangles/source hashes are in `botsd/assets/wait_title_ui82.json`; the renderer uses the
game's own half-width FONTLINK glyphs through `botsd.gamefont`.

`v13_maintenance.json` contains the confirmed v1.3 story-dialogue wrap replacement. The language
file contains source/replacement text and review status only; SCRPACK chunk/command ordinals and
opcode geometry are language-independent metadata in `botsd/assets/scrpack_v13.json`.


`story_dialogue_v12.csv` and `story_choices_v12.csv` are the editable translation-only v1.2
SCRPACK language datasets. They use stable command IDs such as `scrpack.123.0646`; they do not
contain extracted Japanese retail story text or raw file offsets. Dialogue rows also retain the
frozen target command allocation required for byte-exact v1.2 reproduction, while choice rows store
individual menu options rather than opaque payload bytes.

Use `python -m botsd scrpack-language-audit` to verify the datasets against an exact translated
SCRPACK, and `python -m botsd scrpack-apply-language` to rebuild the story-text layer from an exact
retail SCRPACK. `scrpack-catalog` remains the local archaeology/review exporter when paired retail
and translated binaries are available.
