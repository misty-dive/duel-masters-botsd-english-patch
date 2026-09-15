# Development Notes

This is the consolidated continuation note for the **Duel Masters: Birth of the Super Dragon** English translation project. It replaces the many internal handoff, audit, and QA documents created during development.

## Release baseline

Public release: **English v1.0**

- Game: Duel Masters: Birth of the Super Dragon
- Platform: PlayStation 2
- Serial: `SLPM-65882`
- Clean Japanese ISO SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
- Patched v1.0 ISO SHA-256: `372e2d0d6931a95ff5d5ae82e1d352c794d47a6f69da49e7d9941010e8ab6230`
- v1.0 PPF SHA-256: `68221b10371c2783232cf5cb9f85fdcea14683d16a64afeaef9d8c8ab23b3c6b`

The PPF release should be treated as the canonical v1.0 state.

## Scope

The project targets offline/player-visible content. Story dialogue, menus, card data, card graphics, shop/deck text, character select, duel UI, startup/title assets, and story-related trading are in scope.

Deprecated online/network functionality is intentionally out of scope.

The v1.0 release received targeted runtime testing and extensive static verification, but has **not** been fully played through from start to finish.

## Card assets

The game contains multiple card-display layers inside `UNPACK.IMG`:

- Chunks `677–1353`: 677 full-size printed cards.
- Chunks `1360–2036`: 677 128×128 card thumbnails.
- Chunks `2037–2713`: a second 677-card 128×128 sprite/display layer whose Japanese card-name strip was separately localized.

All three card layers are represented in the final v1.0 build. The second small-card layer was patched without unnecessarily reconverting the full cards.

## Other notable localization layers

- All 60 `DECK/*.DAT` files contain fixed-size player-visible deck/callout text fields and were localized without changing card-composition data.
- The offline executable includes localized civilization combinations, booster descriptions, story-trade prompts, and the minimum-10-card trading warning.
- Story dialogue for the 10-card exchange is in scope and localized.
- The DATAPACK visual audit found Japanese-bearing graphics only in the 33 localized graphical chunks `0–6`, `13`, and `108–132`.
- Residual fixed graphics such as title/startup text, `NO RANK`, `BLOCK C`, and the deck HOF marker were localized.
- Japanese shown by PCSX2 as the game-list/window title is emulator metadata, not an untranslated ISO asset.

## Public source package

The repository intentionally contains only **selected original development tools and human-authored translation/source data**. It is not a turnkey redistribution of the complete build workspace because that workspace also contained extracted or modified commercial game binaries that should not be committed publicly.

`tools/` contains the useful Python utilities used for card text, card graphics, archive handling, UI fixes, verification, and release-patch creation.

`data/` contains the verified card-name crosswalk, translated card rules/text tables, and the 677-card resource inventory.

The original ISO, patched ISO, extracted retail archives, modified game binaries, compiled `UNPACK.IMG`, card caches, and intermediate UIxx binary assets are intentionally excluded.

A contributor can recreate the canonical v1.0 game state by applying the public PPF to the verified clean Japanese ISO, then extract files from that patched ISO for further investigation.

## Continuing development

For future fixes:

1. Work from the verified v1.0 ISO/PPF baseline rather than restarting the reverse engineering.
2. Keep offline/story trading in scope.
3. Leave defunct online/network content alone unless the project scope is deliberately expanded.
4. Preserve already-correct card and font pipelines; avoid broad reconversion when a targeted fix is possible.
5. Verify graphical changes against actual retail geometry rather than estimating positions.
6. Report new findings through GitHub Issues and, where possible, include a screenshot plus the location in the game.

## Old project documents

The numerous UIxx handoff files, QA logs, screenshots, and intermediate proof packages were useful during development but do not need to live in the public repository. They can remain in a private/archive backup.

For public continuation, this document, the selected source tools/data, and the canonical v1.0 PPF provide the cleanest starting point.
