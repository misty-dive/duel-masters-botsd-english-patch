# Duel Masters: Birth of the Super Dragon — English Translation Patch

English translation patch for the Japanese PlayStation 2 release of **Duel Masters: Birth of the Super Dragon** (`SLPM-65882`).

## Apply the patch

### New users

1. Start with a clean, unmodified Japanese ISO of **SLPM-65882**.
2. Verify the clean ISO SHA-256:
   `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
3. Download `Duel_Masters_Birth_of_Super_Dragon_English_v1.1.ppf` from the **Releases** page.
4. Apply the PPF3 patch using **PPF-O-Matic 3** on Windows, **MultiPatch** on macOS, **ApplyPPF3** on the command line, or another PPF3-compatible patcher.

Do not apply the full v1.1 patch to an already modified ISO.

### Updating from v1.0

If you already have an ISO patched with the original **v1.0** release, you can instead apply:

`BOTSD_v1.0_to_v1.1_hotfix.ppf`

Do **not** apply both patches to the same ISO. Use either the full v1.1 patch on a clean Japanese ISO, or the v1.0 → v1.1 hotfix on an existing v1.0-patched ISO.

## What is translated

- Story dialogue and offline events.
- Menus and user interface, including character select, duel phases, keyboard, startup/title screens, shop text, booster descriptions, deck names and callouts.
- All **677 cards**, including English card names, rules/effects, flavor text, full rendered cards, thumbnails, and the smaller card/name display layer.
- Card information and special-ability text.
- Deck Builder, Deck Stats, Options, Records and other player-facing screens.
- Numerous residual Japanese labels and graphics found during the offline asset audit.

Deprecated online/network features are intentionally out of scope.

## v1.1 fixes

- Fixed booster shop packs displaying incorrectly and costing `0 DP`.
- Fixed formatting on the Records screen.
- Fixed broken text/UI on the Options screen.
- Fixed Deck Builder and Deck Stats labels and formatting.
- Cleaned up civilization abbreviations and card-count displays.

## Status

**v1.1 is not fully tested.** The major translated systems have been checked, but the entire game has not been played through from beginning to end.

If you find untranslated text, graphical issues, crashes, save problems, or anything else that looks wrong, please open a GitHub Issue with a screenshot and a short description of where it occurred.

Future maintenance may be limited, but contributions and further development are welcome. Technical notes and the project tools/data are included in the repository for anyone who wants to continue the work.

## Patch verification

Full v1.1 patch SHA-256:

`fc3d532ebde1efee52e446e310de59407a5bd28c4a4e562f7e5cf9dead3ddebf`

v1.0 → v1.1 hotfix SHA-256:

`7ec3adb614a251979b1dbbac7f9575f5b204ec1b8c2b9da16dcf7939653a4586`

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
