# Reverse-engineering notes

This file preserves discoveries that should not depend on remembering the historical UI75/UI82
sequence.

## Executable/card text

The retail game uses both external `LIST_1.BIN` display text and an executable-resident master text
pointer table. The localized combined list contains 1,682 display pointers and 2,376 master pointers.
The executable master table begins at VA `0x444268`.

The v1.3 Aura Pegasus bug was a C-string boundary error: master text ID 2372 pointed at a 28-byte
English name with no NUL before unrelated master text ID 1161. The verified repair moves that name
start two bytes earlier and updates only the affected pointer.

## Keyboard

Persistent/default keyboard mode:

- executable file offset `0x52952B`
- runtime VA `0x62852B`
- v1.2 mode `6`: full-width Latin path
- v1.3 mode `9`: half-width Latin path

## SCRPACK control flow

Three translated probability-branch destinations retained stale pre-translation targets. The
reported Shop → Leave hang came from a 10% branch whose old target landed eight bytes inside the
translated `cm_tips` command rather than on its command boundary.

Known Leave correction:

- branch byte file offset `0x58882`
- v1.2 `0x94`
- v1.3 `0x8C`

The earlier save-state sample at EE syscall `0x42` was `SignalSema`, not evidence of a thread blocked
on semaphore 10.

Phase 21 established the older retail-to-v1.2 production structure directly from the exact pair.
All 208 outer chunk boundaries remain fixed, while English `0x1D03`/`0x1F03` payload resizing consumes
or releases trailing zero-command padding. Five opcode families (`0x010C`, `0x020C`, `0x1212`,
`0x1312`, `0x1412`) carry command-relative targets that are relocated to the same destination command
ordinal after resizing. Across the exact pair this accounts for 2,799 changed target fields in 1,960
commands with zero ordinal-resolution failures.

The three `0x070C` probability branches are a historical exception: their retail numeric targets were
not relocated in v1.2, creating the stale destinations described above. The maintained v1.2 compiler
reproduces that quirk for byte identity, and the v1.3 semantic maintenance pass is the layer that
repairs them. This yields an exact source chain from retail + English datasets to the frozen v1.2 and
v1.3 SCRPACK hashes.

## CHANGE TURN

`LO/TCHANGE.IMG` contains `STRIG_IMG_TCHANGE_TGA`, a 256×256 indexed texture. Retail uses two
separated text rows. v1.2 packed the English words into an overlapping connected region; v1.3
restores CHANGE to the upper footprint and TURN to the lower footprint.

## Deck Builder ACE badge

The remaining `切` badge was isolated to `DECK_SRC_DC_P02_TGA` in `DECK.DAT`. It marks the designated
key/trump card rather than a generic remove action. v1.3 localizes it to `ACE`.

## Duel digits

The v1.1 `LEFT` label edit overlapped rows used by the shared number atlas, damaging the lower parts
of digits 6–9. v1.2 moved the label below row 385 and restored the retail digit pixels. The corrected
asset is retained unchanged in v1.3.

## UI82 second-name sprite renderer

The third 677-card image layer is UNPACK chunks `2037..2713`. Each chunk is an 18,432-byte indexed
128×128 TGA. The recovered production renderer starts from the exact retail chunk and edits only the
measured title band `(0,2,128,15)`. It identifies the Japanese title by grouping palette entries with
near-identical RGB values across alpha levels, preferring members unused below the title band. One
known card, sequence 623 (`Cosmic Darts`), uses the conservative top-dominant fallback.

The English title is normalized through the historical ASCII path, rendered from the game's half-width
FONTLINK glyphs at a 10-pixel target height, centered within a 120-pixel interior width, and quantized
back into the original palette. TGA metadata, palette, trailer and all pixels outside the title band are
hard invariants.

Recovery verification used retail UNPACK SHA-256
`179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece` and final localized UNPACK
SHA-256 `2d3fe1849b18e749fac2a9f496776c2d653c9450d566c9f90fdea216b370ff58`. All 677 generated
payloads matched the final archive byte-for-byte. Their ordered concatenation SHA-256 is
`dea8fa559db96f9cc38bfeddac8996dc27a2c90c3f2fdd28e9ece659f76c0f92`.

The exact recovered source is retained under `tools/archaeology/`; `botsd.second_names` is the
maintained implementation.

## Future AI work

AI modifications remain intentionally separate from translation maintenance. Preserved research
identifies profile/evaluation structures, but no AI change belongs in v1.3 or the cleanup refactor.
