# v1.4 Release Notes

v1.4 is a translation and late-story stability hotfix.

## Changes

- Fixed untranslated **multi-race/composite creature race text** in Card Info, including Galzark's `Armored Dragon/Zombie Dragon` display and affected Survivor/composite race strings. The repair changes 27 shared executable-resident race-string allocations while preserving the master pointer table and guarding aliases/allocated size.
- Fixed the **dialogue overflow** reported with Issue #6. Fifty-six reviewed English dialogue commands were rewrapped/compacted within their existing command allocations; the conservative >3-line audit has no remaining findings in the corrected component.
- Added a conservative repair for the reported **late-story Xenon/Shobu progression freeze** after returning to Shobu's world and obtaining Bolblaze Dragon. Eleven English lines were compacted and the affected event was restored to the exact retail command geometry, with retail-identical non-dialogue control data and ending tail.
- No gameplay/card-balance logic was changed.

The Xenon/Shobu repair is **statically/control-flow verified** against the retail event and exact public-v1.3 binaries. A near-ending runtime save was not available for an emulator playthrough, so this release does not claim direct runtime confirmation of that specific freeze.

## New users

Apply:

`Duel_Masters_Birth_of_Super_Dragon_English_v1.4.ppf`

to a clean Japanese `SLPM-65882` ISO.

Clean ISO SHA-256:

`f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`

Patch SHA-256:

`2a37012be8ea61ecb9c2cecf1d1f2295a75bb3f3ec50dd00cca022cff8596767`

## Existing v1.3 users

Apply:

`BOTSD_v1.3_to_v1.4_hotfix.ppf`

to an ISO already patched with the public v1.3 release.

Hotfix SHA-256:

`7acfd4fdf4a28eaa236f7e198e9056d86b75287d05eee8ab523514dbbb680237`

The broader full-playthrough QA is still ongoing, so please continue reporting remaining issues through GitHub Issues.
