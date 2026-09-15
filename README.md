# Duel Masters: Birth of the Super Dragon — English Translation Patch

English translation patch for the Japanese PlayStation 2 release of **Duel Masters: Birth of the Super Dragon** (`SLPM-65882`).

## Apply the patch

1. Start with a clean Japanese ISO of SLPM-65882.
2. Verify its SHA-256:
   f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96
3. Download the .ppf from the Releases page.
4. Apply it using PPF-O-Matic 3 (Windows), MultiPatch (macOS), or ApplyPPF3.
5. The resulting ISO should have SHA-256:
   372e2d0d6931a95ff5d5ae82e1d352c794d47a6f69da49e7d9941010e8ab6230
RomPatcher.js also supports PPF3, but browser-based patching of a multi-gigabyte PS2 ISO does not reliably work.

Do not apply the patch to an already modified ISO.

## What is translated

- Story dialogue and offline events, including story-related card trading.
- Menus and user interface, including character select, duel phases, keyboard, startup/title screens, shop text, booster descriptions, deck names and callouts.
- All **677 cards**, including English card names, rules/effects, flavor text, full rendered cards, thumbnails, and the smaller card/name display layer.
- Card information and special-ability text.
- Numerous residual Japanese labels and graphics found during a full offline asset audit.

Deprecated online/network features are intentionally out of scope.

## Status

**v1.0 is not fully tested.** The major translated systems have been checked, but the entire game has not been played through from beginning to end.

If you find untranslated text, graphical issues, crashes, or other problems, please open a GitHub Issue with a screenshot and a short description of where it occurred.

Future maintenance may be limited, but contributions and further development are welcome. Technical notes and the original project tools/data are provided in the repository for anyone who wants to continue the work.

## Patch verification

PPF patch SHA-256:

`68221b10371c2783232cf5cb9f85fdcea14683d16a64afeaef9d8c8ab23b3c6b`

Patch format: **PPF 3.0**

## Credits & sources

This project would not have been possible without work already done by the Duel Masters community.
- Latepate64 / duel-masters-json — English TCG card data used as a major reference for card names, rules text, flavor text and other card information.
- Duel Masters Wiki contributors — invaluable reference for Japanese/English card identification, established English names and card information.
- Melkiss / Dueparture — overseas Duel Masters card-name correspondence and promotional-card references. Thanks also to Fubuki Furimuzon, Banzan, and the Duel Masters Reborn community, who are credited by Dueparture for helping create that reference material.
- Marc Robledo / Rom Patcher JS — PPF support/reference used when validating the release patch format and compatibility.
- Wizards of the Coast / Takara Tomy and the original Duel Masters creators — for the original game and TCG, including the official English card terminology used wherever available.
Thanks to everyone who has documented, preserved and translated Duel Masters material over the years. A lot of the groundwork for this patch existed because of that community work.

## Notes

This repository does **not** include the original game ISO. You must supply your own legally obtained copy.

Duel Masters and all related game content, artwork, names, and trademarks belong to their respective owners. This is an unofficial fan translation project and is not affiliated with or endorsed by the rights holders.
