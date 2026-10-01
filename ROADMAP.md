# Maintenance roadmap

This roadmap is for repository/tooling cleanup. It does not change the published v1.3 patch.

## Completed cleanup foundation

- automated pytest regression suite and GitHub Actions CI
- MIT license for project-authored tooling/documentation with third-party-content exclusions
- shared `botsd/` package for release manifest, hashing, patching, LZSS, archives, indexed TGA,
  ISO9660, PPF3, release generation and QA
- fixed caller-controlled LZSS candidate-limit behavior
- streaming/seek-based ISO and PPF operations instead of multi-gigabyte in-memory copies
- centralized machine-readable release constants
- canonical semantic v1.3 builders for CHANGE/TURN and the Deck Builder ACE badge
- byte-exact v1.3 component and full/hotfix PPF reproduction tests when legal local inputs are supplied
- architecture/build/format/history/reverse-engineering/security/contribution documentation split
- playthrough, compatibility, save-compatibility and regression QA matrices
- release-critical CSV structure/text audit
- language/provenance manifest infrastructure that does not invent historical review status
- shared card-text parser/externalizer and source-level combined `LIST_1.BIN` builder
- deck callout/title strings separated from the UI82 patch script into editable language data
- shared Card Info rule word-wrap implementation with byte-preserving regressions
- shared official-flavor importer with explicit printing-selection and encoding rules
- shared FONTLINK codec/glyph primitives and keyboard-mode patch metadata
- shared indexed-TGA static-label/residual-graphics primitives with editable UI81 English strings
- semantic minimal FONTLINK apostrophe/lowercase-l repair
- offline executable residual strings separated into fixed-slot metadata and English language data
- shared game-font renderer and semantic WAIT/TITLE graphics stage
- streaming outer-SDA/UNPACK parser, deterministic second-name patch creation/application and UI76/UI82 checkpoint verification
- shared UI75 677-card large-face/thumbnail renderer with semantic geometry and streaming UNPACK writes
- shared UI76 executable-resident Card Info rule/race repacker with versioned layout metadata
- semantic/shared v1.1 Options/Deck/Records polish with English strings separated from binary layout metadata
- semantic DUELPTS Issue #2 digit/LEFT repair with the proven corruption signature encoded as regression data
- shared UI76 whole-card source mapping/provenance and streaming full-card/thumbnail conversion pipeline
- historical UNPACK/keyboard/FONTLINK checkpoint constants moved into machine-readable manifests
- v1.3 executable/SCRPACK maintenance rebuilt structurally: Aura from pointer-overlap repair, three probability branches from parsed command ordinals, and the confirmed dialogue fix from language data rather than raw byte-diff tables
- recovered and migrated the semantic renderer for the 677 UI82 second-name sprites (UNPACK chunks 2037..2713), with exact frozen-v1.3 payload reproduction
- moved the v1.2 SCRPACK story baseline into translation-only stable-ID datasets for 9,499 changed dialogue commands and all 293 menu-choice commands, with exact-v1.2 target auditing
- completed top-level historical-tool mapping coverage and removed the final duplicated frozen SHA-256 literal from a compatibility wrapper; FONTLINK Ü/keyboard stages now have package-native commands
- unified CSV and JSON English localization resources under schema-v2 manifest/provenance auditing, including orphan-resource detection and explicit runtime-review metadata
- separated the frozen v1.3 `ACE` badge raster template into the English language package while retaining byte-identical indexed pixels and language-independent binary geometry
- proved the complete SCRPACK story compiler path from exact retail + repository English data to byte-identical public v1.2, including historical target relocation and the deliberate v1.2 `0x070C` stale-branch quirk; the existing v1.3 semantic stage then reproduces exact public v1.3
- completed a final pre-upload consistency audit, corrected stale architecture/build statements, and centralized the remaining maintained-code copies of authoritative resource/text/UNPACK counts

## Next engineering work

1. Continue replacing remaining binary-only historical asset derivations outside SCRPACK with editable semantic recipes when they can be proven without distributing copyrighted game assets.
2. Continue moving remaining older v1.0-v1.2 UI English strings outside SCRPACK out of historical patch logic into explicit language datasets where doing so preserves byte-identical release output. The SCRPACK story/choice compiler path is now proven end-to-end.
3. Expand provenance/review metadata during actual human review rather than bulk-assigning status.
4. Complete the full-playthrough matrix, including all civilizations, tournaments, pack sets, endings/postgame and explicit normal memory-card save/load checkpoints.
5. Add real-hardware and Android emulator compatibility results when someone performs those tests.

## Long-term build goal

The ideal source-level workflow is a clean ISO plus repository source/data producing the localized
image and release patches without relying on a previous binary release as an intermediate. The
SCRPACK story path now satisfies that requirement through v1.2 and v1.3. Remaining gaps are older
v1.0-v1.2 localization production steps outside SCRPACK plus runtime/playthrough compatibility
evidence; those should be migrated only when exact source recipes can be proven.

### Completed in Phase 15

- Added stable source-level extraction of all SCRPACK `0x1D03` story strings by chunk/command ID.
- Verified full retail/v1.2 pairing for 9,581 dialogue resources, removing raw offsets as the future
  localization identity layer.
- Existing text QA can now audit the complete story translation corpus from a generated catalog.
