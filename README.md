# Duel Masters: Birth of the Super Dragon — English Translation Patch

English translation patch for the Japanese PlayStation 2 release of **Duel Masters: Birth of the Super Dragon** (`SLPM-65882`).

## Apply the patch

### New users

1. Start with a clean, unmodified Japanese ISO of **SLPM-65882**.
2. Verify the clean ISO SHA-256:
   `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
3. Download `Duel_Masters_Birth_of_Super_Dragon_English_v1.4.ppf` from the [v1.4 release](https://github.com/misty-dive/duel-masters-botsd-english-patch/releases/tag/v1.4).
4. Apply the PPF3 patch using **PPF-O-Matic 3** on Windows, **MultiPatch** on macOS, **ApplyPPF3** on the command line, or another PPF3-compatible patcher.

Do not apply the full v1.4 patch to an already modified ISO.

### Updating from v1.3

If you already have an ISO patched with **v1.3**, download the hotfix from the [same v1.4 release](https://github.com/misty-dive/duel-masters-botsd-english-patch/releases/tag/v1.4) and apply:

`BOTSD_v1.3_to_v1.4_hotfix.ppf`

Do **not** apply the full v1.4 patch to a v1.3 ISO.

If you are still on v1.2 or older, the simplest option is to start again from a clean Japanese ISO with the full v1.4 patch.

## What is translated

- Story dialogue and offline events.
- Menus and user interface, including character select, duel phases, keyboard, startup/title screens, shop text, booster descriptions, deck names and callouts.
- All **677 cards**, including English card names, rules/effects, flavor text, full rendered cards, thumbnails, and the smaller card/name display layer.
- Card information and special-ability text.
- Deck Builder, Deck Stats, Options, Records and other player-facing screens.
- Numerous residual Japanese labels and graphics found during the offline asset audit.

Deprecated online/network features are intentionally out of scope.

## v1.4 fixes

- Fixed untranslated **multi-race/composite creature race text** in Card Info, including Galzark and affected Survivor/composite race strings.
- Fixed the Issue #6 **dialogue overflow** audit with 56 reviewed English dialogue rewrap/compaction edits.
- Added a conservative repair for the reported **late-story Xenon/Shobu progression freeze**. Eleven English lines were compacted so the event uses exact retail command geometry and retail-identical non-dialogue control data.
- The Xenon/Shobu repair is statically/control-flow verified; a near-ending runtime save was not available for direct emulator confirmation.

## v1.3 fixes

- Fixed **Aura Pegasus, Avatar of Life** displaying unrelated `Turbo rush` text and potentially causing hangs or crashes when viewing Card Info or navigating shop pack results.
- Fixed intermittent shop/script hangs, including the **Shop → Leave** freeze, by correcting three stale translated script branch targets.
- Fixed user-entered deck names using full-width Latin characters and excessive letter spacing by switching the English keyboard path to half-width Latin input.
- Fixed the frequently visible **CHANGE TURN** transition text clipping by restoring the English graphic to the retail two-row layout.
- Fixed the confirmed story-dialogue wrap where `release...` could split in the middle of the word.
- Localized the remaining Deck Builder **`切`** key-card badge as **`ACE`**.

## v1.2 fixes

- Fixed malformed lower portions of duel numbers `6`, `7`, `8`, and `9`.
- The same defect appeared in creature power, cards remaining in the deck, and available mana because those displays share the same number texture.
- Corrected the English `LEFT` label placement so it no longer overlaps the shared numeric strip.
- Restored the affected number pixels from the clean retail asset.
- The correction was confirmed in-game after being reported in GitHub Issue #2.

## v1.1 fixes

- Fixed booster shop packs displaying incorrectly and costing `0 DP`.
- Fixed formatting on the Records screen.
- Fixed broken text/UI on the Options screen.
- Fixed Deck Builder and Deck Stats labels and formatting.
- Cleaned up civilization abbreviations and card-count displays.

## Status

The full v1.4 patch and the hotfix produce byte-identical ISOs when applied to their respective supported inputs. A full v1.4 playthrough is still pending.

If you find untranslated text, graphical issues, crashes, save problems, or anything else that looks wrong, please open a GitHub Issue with a screenshot and a short description of where it occurred.

Future maintenance may be limited, but contributions and further development are welcome. Technical notes and the project tools/data are included in the repository for anyone who wants to continue the work.

## Patch verification

Full v1.4 patch SHA-256:

`2a37012be8ea61ecb9c2cecf1d1f2295a75bb3f3ec50dd00cca022cff8596767`

v1.3 → v1.4 hotfix SHA-256:

`7acfd4fdf4a28eaa236f7e198e9056d86b75287d05eee8ab523514dbbb680237`

Clean Japanese ISO SHA-256:

`f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`

Patch format: **PPF 3.0**

## Credits & sources

This project builds on a lot of work already done by the Duel Masters community.

- **Latepate64 / duel-masters-json** — English TCG card data used as a major reference for card names, rules text, flavor text and other card information.
- **Duel Masters Wiki contributors** — reference for Japanese/English card identification, established English names and card information.
- **Melkiss / Dueparture** — overseas Duel Masters card-name correspondence and promotional-card references. Dueparture also credits Fubuki Furimuzon, Banzan, and members of the Duel Masters Reborn community for helping create that reference material.
- **Marc Robledo / Rom Patcher JS** — PPF support/reference used when validating the release patch format.
- **Wizards of the Coast / Takara Tomy and the original Duel Masters creators** — for the original game and TCG, including the official English card terminology used wherever available.

Thanks to everyone who has documented, preserved and translated Duel Masters material over the years.

## Notes

This repository does **not** include the original game ISO. You must supply your own copy.

Duel Masters and all related game content, artwork, names, and trademarks belong to their respective owners. This is an unofficial fan translation project and is not affiliated with or endorsed by the rights holders.
