# Development Notes

These are the main notes for anyone who wants to continue work on the **Duel Masters: Birth of the Super Dragon** English patch. The old UIxx handoff files and intermediate QA packages are not needed for normal continuation work.

## Current baseline

- Game: Duel Masters: Birth of the Super Dragon
- Platform: PlayStation 2
- Serial: `SLPM-65882`
- Current public release: **v1.2**
- Clean Japanese ISO SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
- Full v1.2 PPF SHA-256: `83429a57a8c6bba0bf3134600c9e08e9091ca0a7c366e583745db8209834c328`
- v1.1 → v1.2 hotfix SHA-256: `da58431791d0fe8297c0871f6b1e26a244f163b8a3c662c7f839a807d792967b`
- Corrected v1.2 `DUELPTS.DAT` SHA-256: `7162d840c58aca34391819c2df2787013454b0ad45449d1be2cab353f4ec7de3`

The full v1.2 PPF applied to the verified clean Japanese ISO is the best starting point for future work.

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
- corrected v1.2 `DUELPTS.DAT`: `7162d840c58aca34391819c2df2787013454b0ad45449d1be2cab353f4ec7de3`

The canonical v1.2 correction is reproduced by `tools/bosd_duelpts_issue2_fix.py`. It restores digits `6–9` from the verified clean atlas and relocates the already-rendered `LEFT` raster below the numeric strip while preserving unrelated archive members.

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
- Normal PS2 memory-card save compatibility has not yet been proven across the full v1.2 playthrough. Treat any reproducible normal-save incompatibility as a real bug; PCSX2 save-state incompatibility after executable changes is a separate issue.

## Repository files

`tools/` contains only the scripts that are still useful for the current patch: build tools, archive helpers, card pipelines, final UI fixes, release-patch generation, and verification utilities. Superseded one-off scripts should not be reintroduced. See `tools/README.md` for a short description of each remaining tool.

`data/` contains the card-name crosswalk, translated card text/rules tables, and card resource inventory.

The original ISO, patched ISO, extracted retail archives, modified game binaries, compiled `UNPACK.IMG`, card caches, and intermediate UIxx binaries are not included.

Anyone continuing the project can apply the full v1.2 PPF to the verified clean Japanese ISO and extract the patched files from there.

## If you want to continue the project

1. Start from the verified v1.2 build rather than redoing the reverse engineering from scratch.
2. The abandoned online/network features can be ignored unless someone specifically wants to investigate them.
3. Avoid rebuilding all card graphics or fonts when a smaller targeted change will do.
4. Check graphical changes against the actual game layout instead of guessing positions or dimensions.
5. Be careful with fixed-size executable records: text fields may be followed immediately by gameplay or UI metadata.
6. Prefer the hash-guarded Issue #2 repair tool when reproducing the v1.2 `DUELPTS.DAT` correction.
7. If you find a problem, screenshots and a note about where it appears in the game are especially useful.

For most future work, this file, `tools/`, `data/`, and the current release PPF should be enough to get started.
