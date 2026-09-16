# Development Notes

These are the main notes for anyone who wants to continue work on the **Duel Masters: Birth of the Super Dragon** English patch. The old UIxx handoff files and intermediate QA packages are not needed for normal continuation work.

## Current baseline

- Game: Duel Masters: Birth of the Super Dragon
- Platform: PlayStation 2
- Serial: `SLPM-65882`
- Current public release: **v1.1**
- Clean Japanese ISO SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
- Full v1.1 PPF SHA-256: `fc3d532ebde1efee52e446e310de59407a5bd28c4a4e562f7e5cf9dead3ddebf`
- v1.0 → v1.1 hotfix SHA-256: `7ec3adb614a251979b1dbbac7f9575f5b204ec1b8c2b9da16dcf7939653a4586`

The full v1.1 PPF applied to the verified clean Japanese ISO is the best starting point for future work.

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

## v1.1 fixes

v1.1 corrects several issues found after the original public release:

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

## Repository files

`tools/` contains only the scripts that are still useful for the current patch: build tools, archive helpers, card pipelines, final UI fixes, and verification utilities. Superseded one-off scripts have been removed from the public repository. See `tools/README.md` for a short description of each remaining tool.

`data/` contains the card-name crosswalk, translated card text/rules tables, and card resource inventory.

The original ISO, patched ISO, extracted retail archives, modified game binaries, compiled `UNPACK.IMG`, card caches, and intermediate UIxx binaries are not included.

Anyone continuing the project can apply the full v1.1 PPF to the verified clean Japanese ISO and extract the patched files from there.

## If you want to continue the project

1. Start from the verified v1.1 build rather than redoing the reverse engineering from scratch.
2. The abandoned online/network features can be ignored unless someone specifically wants to investigate them.
3. Avoid rebuilding all card graphics or fonts when a smaller targeted change will do.
4. Check graphical changes against the actual game layout instead of guessing positions or dimensions.
5. Be careful with fixed-size executable records: text fields may be followed immediately by gameplay or UI metadata.
6. If you find a problem, screenshots and a note about where it appears in the game are especially useful.

For most future work, this file, `tools/`, `data/`, and the current release PPF should be enough to get started.
