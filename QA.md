# QA and regression matrix

A hash/containment check is not the same as an in-game test, and a PCSX2 save state is not the same
as a normal PS2 memory-card save.

## Automated suite

The repository now has permanent tests for:

- release manifest integrity and v1.2/v1.3 same-size maintenance assumptions
- guarded Aura/keyboard/SCRPACK byte patches
- Japanese/full-width-Latin/CP932 text scanning
- fast LZSS round trips with caller-controlled candidate limits
- optimal overlap-capable LZSS round trips
- packed UI archive parse/rebuild containment
- indexed-TGA pixel-plane editing without metadata/palette mutation
- PPF3 build/parse/apply, including target-file extension
- ISO9660 traversal, same-size replacement and append+retarget behavior on synthetic images
- consistency between shared regression metadata and the retained v1.3 maintenance script when the
  complete repository is present

CI runs `ruff`, `mypy` and `pytest` on Python 3.10 and 3.12.

## Permanent v1.3 regression cases

| Area | Regression | Automated | In-game status |
|---|---|---:|---|
| Card text | Aura Pegasus name terminates before unrelated Turbo rush text | byte-patch guard | confirmed in combined QA build |
| Shop/script | all three translated probability branches land on command boundaries | byte-patch guard | confirmed in combined QA build; Shop → Leave no longer reproduced |
| Keyboard | English default mode is 9, not 6 | byte-patch guard | confirmed in combined QA build |
| Duel UI | digits 6–9 remain intact and LEFT does not overlap them | component hash/visual metadata | confirmed for v1.2 and retained in v1.3 |
| Turn transition | CHANGE/TURN use separate retail-style rows | component hash/visual metadata | confirmed in combined QA build |
| Dialogue | World's Balance line uses explicit word-boundary break | byte-patch guard | confirmed in combined QA build |
| Deck Builder | `切` badge is localized as `ACE` | component hash/containment metadata | static containment verified; dedicated final in-game screenshot still desirable |

## Full-playthrough matrix

Use `not tested`, `partial`, or `complete`. Record exact patch version, emulator/hardware and normal
memory-card behavior separately from emulator save states.

| Area | Status | Notes |
|---|---|---|
| New game / startup / memory-card prompts | partial | translated screens exercised during development |
| Character/civilization selection | partial | major UI checked; full branch coverage not recorded |
| Fire civilization story | partial | no chapter-by-chapter completion record yet |
| Water civilization story | not tested | add exact progress here |
| Nature civilization story | not tested | add exact progress here |
| Light civilization story | partial | add exact progress here |
| Darkness civilization story | partial | add exact progress here |
| Tournaments | not tested | record each tournament separately |
| Shop: Info | partial | translated UI checked |
| Shop: Buy / pack opening | partial | v1.3 crash regression tested; exhaustive set coverage pending |
| Shop: Research | partial | no exhaustive coverage record |
| Shop: Leave | complete for reported regression | repeated v1.3 QA no longer reproduced reported hang |
| Deck Builder | partial | key screens tested; exhaustive card/action coverage pending |
| Deck Stats | partial | layout fixes checked |
| Card Info | partial | Aura regression tested; exhaustive 677-card pass not complete |
| Save / load with normal PS2 memory card | not tested across versions | must be tested separately from save states |
| Endings / postgame | not tested | full playthrough required |

## Save compatibility matrix

| From | To | Normal PS2 memory-card save | Emulator save state | Notes |
|---|---|---|---|---|
| v1.2 | v1.3 | not formally tested | do not assume compatible | executable changes can invalidate snapshots without affecting memory-card saves |
| v1.3 | v1.3 | partial during normal QA | emulator/version dependent | add explicit save/load checkpoints |

## Compatibility matrix

| Platform | Version | Status | Notes |
|---|---|---|---|
| PCSX2 | v1.3 | partial | primary QA environment; record exact version for future passes |
| NetherSX2 / Android | v1.3 | external retest desirable | Issue #3 originated on Android/NetherSX2 |
| Real PS2 hardware | v1.3 | not tested | include normal memory-card save testing when available |


## Semantic-source release regressions

Phase 3 adds two levels of regression coverage for the v1.3 visual fixes:

1. CI validates the recipe structure, dimensions, compressor parameters, archive in-place replacement,
   and shared patch metadata without distributing game content.
2. A maintainer who supplies the exact public-v1.2 components through `BOTSD_V12_COMPONENT_DIR` runs
   golden tests that rebuild all four maintenance components and compare their SHA-256 values to the
   published v1.3 hashes.

The local semantic reconstruction performed during this cleanup reproduced all four v1.3 component
hashes exactly, including `TCHANGE.IMG` and `DECK.DAT`.


### Published PPF reproduction

The optional full golden suite also accepts `BOTSD_V12_FULL_PPF`. With both local variables set,
`tests/test_release.py` rebuilds the full v1.3 PPF and the v1.2 -> v1.3 hotfix and verifies the exact
published hashes. During Phase 3 cleanup this passed against the official v1.2 PPF.

## Repository-level QA

The CI suite also validates the public repository itself when the cleanup overlay is installed over
an actual checkout. It checks that the four release-critical CSV datasets retain their authoritative
row counts and contiguous IDs, scans their English fields for Japanese/full-width Latin/reserved
characters/encoding failures, verifies that `DEVELOPMENT.md` still identifies v1.3 as the baseline,
and protects the complete `README.md` Credits & sources section from accidental removal.

Run the dataset audit directly with:

```bash
python -m botsd data-audit data
```

## Machine-readable QA audit

Run:

```bash
python -m botsd qa-audit qa
```

This validates the playthrough, emulator/hardware, save-compatibility and permanent regression
corpora together. The audit validates schema/status consistency only; it never upgrades an untested
manual case to tested.

`qa/regressions.csv` is the permanent release-regression corpus. The `ACE` case is deliberately
recorded as `static_only` until a dedicated final in-game screenshot is captured; exact archive/hash
reproduction is strong binary evidence but is not mislabeled as runtime evidence.
