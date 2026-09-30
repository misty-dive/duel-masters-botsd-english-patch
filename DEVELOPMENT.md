# Development Notes

These are the main notes for anyone who wants to continue work on the **Duel Masters: Birth of the Super Dragon** English patch. The old UIxx handoff files and intermediate QA packages are not needed for normal continuation work.

## Current baseline

- Game: Duel Masters: Birth of the Super Dragon
- Platform: PlayStation 2
- Serial: `SLPM-65882`
- Current public release: **v1.3**
- Clean Japanese ISO SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
- Full v1.3 PPF SHA-256: `b0533fa91e98640a1264179b4bbd721127043b66c6bbbf6aab0d884fc6275814`
- v1.2 → v1.3 hotfix SHA-256: `ce88a079c73555b735643bcd602a12ebf87aa8ec7a08d47b749d4883f0474ec1`
- Corrected v1.2/v1.3 `DUELPTS.DAT` SHA-256: `7162d840c58aca34391819c2df2787013454b0ad45449d1be2cab353f4ec7de3`

The full v1.3 PPF applied to the verified clean Japanese ISO is the best starting point for future work.

## What was worked on

The patch focuses on the playable offline game: story text, menus, card information, card graphics, shop and deck text, character select, duel UI, startup/title assets, and other Japanese text or graphics found during the audit.

The old online/network features were left alone because those services are no longer available.

The patch has had targeted testing, but the game has **not** been played through from beginning to end.

## Card assets

`UNPACK.IMG` contains several separate versions of the card graphics:

- Chunks `677–1353`: 677 full-size printed cards.
- Chunks `1360–2036`: 677 128×128 card thumbnails.
- Chunks `2037–2713`: another set of 677 128×128 card sprites/displays.

All three sets are included in the final build. The last set was handled separately because the Japanese card name is baked into the image.

v1.3 does not rebuild or alter these 677-card `UNPACK.IMG` layers.

## v1.3 maintenance fixes

v1.3 is a targeted maintenance update over the public v1.2 build. The four game files changed by the update are:

| File | v1.2 SHA-256 | v1.3 SHA-256 | Size |
|---|---|---|---:|
| `SLPM_658.82` | `74f71e9dc1f7adeba10a12d70d27494efd8b5d117a55cbb8e9f8610762de3981` | `165d962189cf78e5bad4c549ac2d43f4fd54492ba61ebc3a258903f907f953d7` | 5,459,220 |
| `SCRPACK.SDA` | `1e3208976bb90749598e1d7359cfda51fe7c095cf3db10459265aeb5dd133051` | `4d7e561344917193f9e672515edd5d2ccf576dcb7ed88d2ddc2092773689df26` | 3,801,088 |
| `TCHANGE.IMG` | `5441893433e1c0c1901aba018f7a917881bc4303106df865cf0c7d0443197427` | `b6f61cb44e79539c40f289b4c7956b2016a5e5fdb9bff3e20140638d22c71137` | 19,456 |
| `DECK.DAT` | `1c8abe004fe848983b317568d998379d674bce4df65773b93ef40131f20b4981` | `17eecd96502974c7899279d88a348269d59aa3cdd4ab92ffc50686854d7ad653` | 786,176 |

`tools/bosd_v13_maintenance.py` reproduces the final v1.3 maintenance changes from the exact public v1.2 inputs and rejects unexpected source hashes.

### Aura Pegasus text overrun

The v1.2 executable's master-name string for **Aura Pegasus, Avatar of Life** had no NUL terminator.

The name occupied:

`0x46A590..0x46A5AB`

and the next byte at:

`0x46A5AC`

was already the beginning of a different master-text entry containing an unrelated `Turbo rush` rule string. A normal C-string read therefore continued directly into unrelated text.

The v1.3 correction:

- moves the Aura name start two bytes earlier to `0x46A58E`
- writes the same English name followed by NUL bytes
- updates only master text pointer 2372
- leaves the unrelated rule entry and Aura's actual rules text untouched

The earlier full pointer-overlap audit found this to be the only pointer-inside-string overlap in the 2,376-entry embedded master table.

### Keyboard / deck-name spacing

Runtime save-state inspection proved that user-entered deck names in v1.2 were stored as full-width CP932 Latin characters rather than normal half-width Latin.

The persistent keyboard mode byte is at:

- runtime VA: `0x62852B`
- executable file offset: `0x52952B`

The A/ABC handler toggles modes `6/9`. Runtime testing established that mode `6` is the full-width Latin path and mode `9` is the half-width Latin path. v1.3 changes the final default to mode `9`.

### SCRPACK probability-branch relocation

The intermittent shop hang, including the **Shop → Leave** freeze, was ultimately traced to stale translated script branch destinations rather than a renderer or semaphore deadlock.

Three `0C/07` probability-branch targets in `SCRPACK.SDA` still pointed to their pre-translation command positions.

For the known Shop → Leave case, the 10% branch in v1.2 targeted resource-relative:

`0x4994`

which resolves to file offset:

`0x58994`

That lands eight bytes inside the translated `cm_tips` command/string. The actual command begins at:

`0x5898C`

so the corrected resource-relative target is:

`0x498C`

The known byte correction is:

- file offset `0x58882`
- v1.2: `0x94`
- v1.3: `0x8C`

The v1.3 maintenance pass corrects all three stale probability-branch destinations.

### CHANGE TURN clipping

The relevant file is:

`LO/TCHANGE.IMG`

with member:

`STRIG_IMG_TCHANGE_TGA`

The retail texture uses two clearly separated rows. The v1.2 English graphic packed `TURN` and `CHANGE` into a touching/overlapping vertical region, which caused runtime clipping.

v1.3 restores the intended two-row geometry:

- `CHANGE` on the top row
- `TURN` on the lower row

The archive remains exactly `19,456 bytes`.

### Confirmed story-dialogue wrap

The confirmed visible line:

`If the World's Balance tips too far toward release...`

could wrap by character boundary and split the word `release`.

v1.3 uses the game's explicit line-break control:

`If World's Balance tips too far#cr0toward release...`

Only the confirmed line is changed. The broader long-line audit remains a QA list rather than proof that every candidate needs modification.

### Deck Builder `切` badge

The remaining Japanese badge was isolated to:

`DECK_SRC_DC_P02_TGA`

inside `DECK.DAT`.

It appears only on the deck's designated key/trump card rather than as a general card action, so the English localization uses the compact label:

`ACE`

The change is contained to that single Deck Builder texture member. `DECK.DAT` remains the same `786,176-byte` archive.

## v1.2 fix: duel numbers 6–9

GitHub Issue #2 reported malformed lower portions of the duel-rendered digits `6`, `7`, `8`, and `9`. The same defect appeared in creature power, deck-count, and available-mana displays because those displays share the same texture atlas.

The affected asset is `DUELPTS_SRC_G_P00_TGA` inside `IMG/DUELPTS.DAT`.

The v1.1 English `LEFT` label used the rectangle `(145, 374, 221, 408)`. Rows `374–384` also contain the lower portion of the shared numeric strip, so clearing that rectangle damaged the latter number glyphs.

Clean-vs-v1.1 pixel verification found:

- digits `1–5`: 0 altered pixels
- digit `6`: 71 altered pixels
- digit `7`: 136 altered pixels
- digit `8`: 205 altered pixels
- digit `9`: 206 altered pixels

Relevant file hashes:

- clean retail `DUELPTS.DAT`: `b90825eb09f455e473cf47f3721a46a277fd3fbb78bd361df6d5b5dc1141e89e`
- affected v1.1 `DUELPTS.DAT`: `d9296abff10b847157e54f8b59e6bcb084e0a727db77d99be3cb268005d5faa4`
- corrected v1.2/v1.3 `DUELPTS.DAT`: `7162d840c58aca34391819c2df2787013454b0ad45449d1be2cab353f4ec7de3`

The canonical correction is reproduced by `tools/bosd_duelpts_issue2_fix.py`. It restores digits `6–9` from the verified clean atlas and relocates the already-rendered `LEFT` raster below the numeric strip while preserving unrelated archive members.

`tools/bosd_static_label_polish_ui81.py` is also corrected so future clean rebuilds do not begin the `LEFT` region above row `385`. Because that path rerenders the label from a font, it should still receive normal runtime visual QA after a fresh rebuild.

## v1.1 fixes

v1.1 corrected several issues found after the original public release:

- Booster shop pack prices and pack artwork were restored. The earlier shop-description edit had overwritten metadata in the executable record.
- Records-screen unit spacing was corrected.
- Options-screen labels were rerendered to remove the striped/broken text appearance.
- Deck Builder and Deck Stats labels were cleaned up.
- Civilization abbreviations and card-count displays were adjusted for the English layout.

The corrected shop record layout is:

- `+0x00`: 8-byte pack code
- `+0x08`: 0x50-byte description field
- `+0x58`: price
- `+0x5C`: pack image ID
- `+0x60`: pack index
- `+0x64`: pack index

`tools/bosd_shop_packdesc_fixed.py` preserves those metadata fields. `tools/bosd_ui_polish_v11.py` contains the v1.1 Records, Options, Deck Builder, and Deck Stats cleanup work.

## Other useful notes

- All 60 `DECK/*.DAT` files have player-visible text fields that were translated without changing the actual deck/card data.
- The executable contains player-visible strings that were patched directly, including civilization combinations and booster descriptions.
- The DATAPACK visual audit found Japanese-bearing graphics in 33 chunks: `0–6`, `13`, and `108–132`.
- Fixed graphics such as title/startup text, `NO RANK`, `BLOCK C`, and the deck HOF marker were also localized.
- If PCSX2 still shows the Japanese game title in its game list or window title, that is emulator metadata rather than text coming from the ISO.
- Normal PS2 memory-card save compatibility has not yet been proven across a complete v1.3 playthrough. Treat any reproducible normal-save incompatibility as a real bug; PCSX2 save-state incompatibility after executable changes is a separate issue.
- AI behavior changes are not part of v1.3 and should remain separate from translation-maintenance releases.

## Repository files

`tools/` contains only the scripts that are still useful for the current patch: build tools, archive helpers, card pipelines, final UI fixes, release-patch generation, and verification utilities. Superseded one-off scripts should not be reintroduced. See `tools/README.md` for a short description of each remaining tool.

For v1.3 maintenance, the important additions are:

- `tools/bosd_v13_maintenance.py` — reproduces the final v1.3 component changes from exact public v1.2 inputs.
- `tools/bosd_v13_release_builder.py` — builds and verifies the full v1.3 PPF and v1.2 → v1.3 hotfix.

`data/` contains the card-name crosswalk, translated card text/rules tables, and card resource inventory. v1.3 does not require changes to the data CSVs.

The original ISO, patched ISO, extracted retail archives, modified game binaries, compiled `UNPACK.IMG`, card caches, and intermediate UIxx binaries are not included.

Anyone continuing the project can apply the full v1.3 PPF to the verified clean Japanese ISO and extract the patched files from there.

## If you want to continue the project

1. Start from the verified v1.3 build rather than redoing the reverse engineering from scratch.
2. The abandoned online/network features can be ignored unless someone specifically wants to investigate them.
3. Avoid rebuilding all card graphics or fonts when a smaller targeted change will do.
4. Check graphical changes against the actual game layout instead of guessing positions or dimensions.
5. Be careful with fixed-size executable records: text fields may be followed immediately by gameplay or UI metadata.
6. Prefer the hash-guarded maintenance tools when reproducing v1.2/v1.3 fixes.
7. If you find a problem, screenshots and a note about where it appears in the game are especially useful.

For most future work, this file, `tools/`, `data/`, and the current release PPF should be enough to get started.
