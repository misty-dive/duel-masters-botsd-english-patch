# Duel Masters: Birth of the Super Dragon — English Translation

English localization patch for **Duel Masters: Birth of the Super Dragon** on PlayStation 2.

- Game serial: `SLPM-65882`
- Current public release: **v1.3**
- Patch format: **PPF 3.0**
- Base image: clean Japanese retail ISO

## Applying the patch

### New users

Apply:

`Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf`

to a clean Japanese `SLPM-65882` ISO.

Required clean ISO:

- Size: `3,080,880,128 bytes`
- SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`

Full v1.3 PPF SHA-256:

`b0533fa91e98640a1264179b4bbd721127043b66c6bbbf6aab0d884fc6275814`

### Existing v1.2 users

Apply:

`BOTSD_v1.2_to_v1.3_hotfix.ppf`

to an ISO already patched with the public **v1.2** release.

v1.2 → v1.3 hotfix SHA-256:

`ce88a079c73555b735643bcd602a12ebf87aa8ec7a08d47b749d4883f0474ec1`

If you are on v1.1 or older, the simplest path is to apply the full v1.3 patch to a clean Japanese ISO.

## v1.3 changes

v1.3 rolls the confirmed post-v1.2 QA fixes into the public patch:

- Fixed **Aura Pegasus, Avatar of Life** displaying unrelated `Turbo rush` text and potentially hanging Card Info / shop-result navigation. The executable-resident card name had no terminating NUL and ran directly into another master-text string.
- Fixed intermittent **shop/script hangs**, including the **Shop → Leave** failure. Three translated `SCRPACK.SDA` probability branches still targeted pre-translation command positions; the affected destinations are now relocated to the actual English command boundaries.
- Changed the software keyboard's English default from mode `6` to mode `9`, so user-entered deck names use **half-width Latin characters** instead of full-width Latin spacing.
- Fixed the frequently visible **CHANGE TURN** transition clipping by restoring the English words to the retail texture's two-row geometry.
- Fixed the confirmed story line where `release...` could split in the middle of the word by using the game's explicit line-break control.
- Localized the Deck Builder's one-card **`切` key-card badge** as **`ACE`**.
- Retains the v1.2 fix for malformed duel digits **6, 7, 8, and 9**.

The post-v1.2 functional fixes were tested together in-game before release. The final `ACE` badge is a tightly contained static Deck Builder localization added at the v1.3 packaging stage. The broader full-playthrough QA is still ongoing.

## Translation scope

The playable offline game localization covers:

- story dialogue and offline events
- menus and general UI
- startup/title and memory-card-facing text
- character/civilization selection
- software keyboard/input UI
- shop text and booster descriptions
- deck/deck-builder text and graphics
- duel UI
- Card Info / rules / effect text
- all 677 card display assets across all three card-image layers
- residual Japanese-bearing offline graphics found during QA

Intentionally outside the normal patch scope:

- deprecated online/network functionality
- old network terms/conditions
- optional movie/media-stream localization

## Patch verification

### v1.3

Full clean-ISO → v1.3 PPF:

- File: `Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf`
- Size: `141102291 bytes`
- SHA-256: `b0533fa91e98640a1264179b4bbd721127043b66c6bbbf6aab0d884fc6275814`

v1.2 → v1.3 hotfix:

- File: `BOTSD_v1.2_to_v1.3_hotfix.ppf`
- Size: `55567 bytes`
- SHA-256: `ce88a079c73555b735643bcd602a12ebf87aa8ec7a08d47b749d4883f0474ec1`

### Previous release reference

v1.2 full PPF:

`83429a57a8c6bba0bf3134600c9e08e9091ca0a7c366e583745db8209834c328`

v1.1 → v1.2 hotfix:

`da58431791d0fe8297c0871f6b1e26a244f163b8a3c662c7f839a807d792967b`

## Save compatibility

The normal PS2 memory-card identifiers remain `BISLPM-65882` / `PS2D`.

PCSX2 save states are emulator snapshots and can become incompatible after executable changes. That is separate from normal memory-card save compatibility.

## Reporting issues

The project is still being played through and checked screen by screen. If you find remaining untranslated text, layout problems, crashes, or other regressions, please open a GitHub Issue and include:

- the screen/location
- what happened
- whether it reproduces
- a screenshot when possible
- a save state immediately before the problem when useful

For crashes/hangs, a before/after save-state pair is especially helpful.

## Development

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the technical history and [`tools/README.md`](tools/README.md) for the retained build/verification tools.

## Credits

This is a fan translation/localization project for archival and preservation purposes. Duel Masters and related trademarks belong to their respective owners.
