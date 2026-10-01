# BOTSD SCRPACK v1.2 language-dataset verification

Date: 2026-09-30

## Purpose

Document the evidence used to migrate the public-v1.2 `SCRPACK.SDA` story localization into
translation-only source data without checking extracted Japanese retail script text into the
repository.

## Exact translated target recovery

The handoff contains the published full v1.3 PPF. The complete `SCRPACK.SDA` range is covered by
that PPF, yielding the exact v1.3 component:

- size: 3,801,088 bytes
- SHA-256: `4d7e561344917193f9e672515edd5d2ccf576dcb7ed88d2ddc2092773689df26`

Reversing only the four documented v1.3 SCRPACK maintenance changes recovers the exact public-v1.2
component:

1. chunk 32 command 326: branch target `0x24D0 -> 0x24E8`
2. chunk 32 command 938: branch target `0x498C -> 0x4994`
3. chunk 162 command 123: branch target `0x0AE8 -> 0x0AE4`
4. chunk 123 command 646: restore `If the World's Balance tips too far toward release...`

Result SHA-256:

`1e3208976bb90749598e1d7359cfda51fe7c095cf3db10459265aeb5dd133051`

This equals the authoritative v1.2 release-manifest hash.

## Dialogue dataset

The Phase 15 paired retail/v1.2 catalog contains 9,581 stable `0x1D03` identities across 208 chunks:

- 9,499 translated/different rows
- 82 byte/text-identical rows
- 0 command-identity mismatches

Phase 17 stores only the 9,499 changed English target rows. Fields retained are stable resource ID,
chunk/command ordinal, frozen target payload size, English translation, and explicit `#cr0` count.
Retail Japanese text and raw file offsets are deliberately excluded.

## `0x1F03` discovery and dataset

Parsing the exact v1.2 target shows 293 `0x1F03` commands. Their payload form is:

- fixed six-byte prefix `00 00 02 00 00 00`
- `u16 option_count`
- repeated `u16 byte_length + CP932/ASCII option bytes`
- zero padding through the declared payload size

Examples include `Yes`/`No`, `Leave`, tournament names, and map/location choices.

To test whether another command family also changed command size during localization, consecutive
paired `0x1D03` offsets were compared after subtracting the known dialogue-size delta. There are 160
intervals with residual movement. Every one of those 160 intervals contains at least one `0x1F03`
command; zero residual-movement intervals lack `0x1F03`.

This does not prove that no same-size non-text payload byte ever changed, but it does establish that
`0x1D03` and `0x1F03` account for the observed text-driven command-size movement in the paired
retail/v1.2 corpus.

## Maintained source representation

- `localization/en/story_dialogue_v12.csv` — 9,499 changed dialogue rows
- `localization/en/story_choices_v12.csv` — 293 menu-choice rows
- `botsd/assets/story_v12.json` — frozen counts/hashes/opcodes/identity metadata
- `botsd.storytext` — parsing, loading, audit, serialization, containment

The maintained writer preserves every command not selected by one of those stable IDs, and it
requires each rebuilt SDA chunk to end at its original fixed boundary. Production CLI defaults also
require the exact retail input hash and exact public-v1.2 output hash.

## Verification status

Target audit against exact public-v1.2 SCRPACK: PASS

- dialogue dataset rows: 9,499
- target dialogue commands: 9,581
- choice dataset rows: 293
- target choice commands: 293
- chunks: 208

Retail-to-v1.2 golden build: not run in this workspace because the copyrighted retail
`SCRPACK.SDA` was not supplied. It is retained as an opt-in test guarded by the known retail hash:

`707e53a0f714dea7f3a059d973085fafd4f9120d0ef59e92bac42eb561514b11`

## Phase 21 follow-up — retail golden proof

The previously missing retail input was supplied on 2026-10-01 and matched the guarded retail hash.
The original preparatory reinsertion algorithm exposed one incorrect assumption: translated command
size changes alter the number of trailing zero-padding commands within a fixed outer chunk. Exact
retail/public-v1.2 comparison also proved five historical command-target relocation families.

The maintained compiler was corrected accordingly and now reproduces the exact public-v1.2 SCRPACK
hash from retail plus the translation-only datasets. Applying the semantic v1.3 maintenance to that
generated component also reproduces the exact public-v1.3 SCRPACK hash. See
`SCRPACK_RETAIL_TO_V12_COMPILER_VERIFICATION_2026-10-01.md` for the full proof.
