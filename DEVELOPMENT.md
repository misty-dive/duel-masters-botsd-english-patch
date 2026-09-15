# Development Notes

These are the main notes for anyone who wants to continue work on the **Duel Masters: Birth of the Super Dragon** English patch. The older UIxx handoff files and QA notes were useful while the patch was being built, but most of that information has been condensed here.

## v1.0 baseline

- Game: Duel Masters: Birth of the Super Dragon
- Platform: PlayStation 2
- Serial: `SLPM-65882`
- Clean Japanese ISO SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
- Patched v1.0 ISO SHA-256: `372e2d0d6931a95ff5d5ae82e1d352c794d47a6f69da49e7d9941010e8ab6230`
- v1.0 PPF SHA-256: `68221b10371c2783232cf5cb9f85fdcea14683d16a64afeaef9d8c8ab23b3c6b`

The public v1.0 PPF is the best starting point for any future work.

## What was worked on

The patch focuses on the playable offline game: story text, menus, card information, card graphics, shop and deck text, character select, duel UI, startup/title assets, and other Japanese text or graphics found during the audit.

The old online/network features were left alone because those services are no longer available.

v1.0 has had targeted testing, but the game has **not** been played through from beginning to end.

## Card assets

`UNPACK.IMG` contains several separate versions of the card graphics:

- Chunks `677–1353`: 677 full-size printed cards.
- Chunks `1360–2036`: 677 128×128 card thumbnails.
- Chunks `2037–2713`: another set of 677 128×128 card sprites/displays.

All three sets are included in the final v1.0 build. The last set was handled separately because the Japanese card name is baked into the image.

## Other useful notes

- All 60 `DECK/*.DAT` files have player-visible text fields that were translated without changing the actual deck/card data.
- The executable contains a number of player-visible strings that were patched directly, including civilization combinations and booster descriptions.
- The DATAPACK visual audit found Japanese-bearing graphics in 33 chunks: `0–6`, `13`, and `108–132`. These were already covered by the final patch.
- Fixed graphics such as title/startup text, `NO RANK`, `BLOCK C`, and the deck HOF marker were also localized.
- If PCSX2 still shows the Japanese game title in its game list or window title, that is emulator metadata rather than text coming from the ISO.

## Files in this repository

The repository only includes the development material that is useful to keep around.

`tools/` contains the Python utilities used for card text, card graphics, archive work, UI fixes, verification, ISO patching, and PPF creation.

`data/` contains the card-name crosswalk, translated card text/rules tables, and the card resource inventory.

The original ISO, patched ISO, extracted retail archives, modified game binaries, compiled `UNPACK.IMG`, card caches, and intermediate UIxx binaries are not included.

Anyone continuing the project can apply the v1.0 PPF to the verified clean Japanese ISO and extract the patched files from there.

## If you want to continue the project

A few things are worth keeping in mind:

1. Start from the verified v1.0 build rather than redoing the reverse engineering from scratch.
2. The abandoned online/network features can be ignored unless someone specifically wants to investigate them.
3. Avoid rebuilding all of the card graphics or fonts when a smaller targeted change will do.
4. Check graphical changes against the actual game layout instead of guessing at positions or dimensions.
5. If you find a problem, screenshots and a note about where it appears in the game are especially useful.

## Older project files

There were a lot of handoff documents, QA logs, screenshots, and intermediate builds made while this patch was being developed. They are not needed in the public repository.

For most future work, this file, the `tools/` and `data/` folders, and the v1.0 PPF should be enough to get started.
