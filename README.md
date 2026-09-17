# Duel Masters: Birth of the Super Dragon — English Translation Patch

English translation patch for the Japanese PlayStation 2 release of **Duel Masters: Birth of the Super Dragon** (`SLPM-65882`).

## Apply the patch

### New users

1. Start with a clean, unmodified Japanese ISO of **SLPM-65882**.
2. Verify the clean ISO SHA-256:
   `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`
3. Download `Duel_Masters_Birth_of_Super_Dragon_English_v1.2.ppf` from the **Releases** page.
4. Apply the PPF3 patch using **PPF-O-Matic 3** on Windows, **MultiPatch** on macOS, **ApplyPPF3** on the command line, or another PPF3-compatible patcher.

Do not apply the full v1.2 patch to an already modified ISO.

### Updating from v1.1

If you already have an ISO patched with **v1.1**, apply:

`BOTSD_v1.1_to_v1.2_hotfix.ppf`

Do **not** apply the full v1.2 patch to a v1.1 ISO.

If you are still on v1.0, either start again from a clean Japanese ISO with the full v1.2 patch, or first apply the existing v1.0 → v1.1 hotfix and then the v1.1 → v1.2 hotfix.

## What is translated

- Story dialogue and offline events.
- Menus and user interface, including character select, duel phases, keyboard, startup/title screens, shop text, booster descriptions, deck names and callouts.
- All **677 cards**, including English card names, rules/effects, flavor text, full rendered cards, thumbnails, and the smaller card/name display layer.
- Card information and special-ability text.
- Deck Builder, Deck Stats, Options, Records and other player-facing screens.
- Numerous residual Japanese labels and graphics found during the offline asset audit.

Deprecated online/network features are intentionally out of scope.

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

**v1.2 is not fully playthrough-tested.** The Issue #2 duel-number correction has been confirmed in-game and the major translated systems have been checked, but the entire game has not yet been played through from beginning to end.

If you find untranslated text, graphical issues, crashes, save problems, or anything else that looks wrong, please open a GitHub Issue with a screenshot and a short description of where it occurred.

Future maintenance may be limited, but contributions and further development are welcome. Technical notes and the project tools/data are included in the repository for anyone who wants to continue the work.

## Patch verification

Full v1.2 patch SHA-256:

`83429a57a8c6bba0bf3134600c9e08e9091ca0a7c366e583745db8209834c328`

v1.1 → v1.2 hotfix SHA-256:

`da58431791d0fe8297c0871f6b1e26a244f163b8a3c662c7f839a807d792967b`

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
