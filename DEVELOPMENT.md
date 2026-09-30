# Duel Masters: Birth of the Super Dragon — Development Notes

## Current baseline

Current public target: **v1.3**  
Game: **Duel Masters: Birth of the Super Dragon**  
Serial: **SLPM-65882**

Clean Japanese ISO:

- Size: `3,080,880,128 bytes`
- SHA-256: `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`

v1.3 release patches:

- `Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf`
  - size: `141102291 bytes`
  - SHA-256: `b0533fa91e98640a1264179b4bbd721127043b66c6bbbf6aab0d884fc6275814`
- `BOTSD_v1.2_to_v1.3_hotfix.ppf`
  - size: `55567 bytes`
  - SHA-256: `ce88a079c73555b735643bcd602a12ebf87aa8ec7a08d47b749d4883f0474ec1`

The patch remains an offline-game localization. Deprecated network functionality and old network terms/conditions are intentionally outside the normal scope. AI changes remain postponed and must stay separate from the translation-maintenance release.

---

## v1.3 maintenance component hashes

v1.3 is a same-size maintenance update over the exact public v1.2 assets:

| File | v1.2 SHA-256 | v1.3 SHA-256 | Size |
|---|---|---|---:|
| `SLPM_658.82` | `74f71e9dc1f7adeba10a12d70d27494efd8b5d117a55cbb8e9f8610762de3981` | `165d962189cf78e5bad4c549ac2d43f4fd54492ba61ebc3a258903f907f953d7` | 5,459,220 |
| `SCRPACK.SDA` | `1e3208976bb90749598e1d7359cfda51fe7c095cf3db10459265aeb5dd133051` | `4d7e561344917193f9e672515edd5d2ccf576dcb7ed88d2ddc2092773689df26` | 3,801,088 |
| `TCHANGE.IMG` | `5441893433e1c0c1901aba018f7a917881bc4303106df865cf0c7d0443197427` | `b6f61cb44e79539c40f289b4c7956b2016a5e5fdb9bff3e20140638d22c71137` | 19,456 |
| `DECK.DAT` | `1c8abe004fe848983b317568d998379d674bce4df65773b93ef40131f20b4981` | `17eecd96502974c7899279d88a348269d59aa3cdd4ab92ffc50686854d7ad653` | 786,176 |

`tools/bosd_v13_maintenance.py` reproduces these four exact outputs from the public v1.2 inputs and refuses any source hash mismatch.

---

## v1.3 fixes and root causes

### Aura Pegasus / Card Info / shop-result instability

**Card:** Aura Pegasus, Avatar of Life  
**Internal card ID:** `672`  
**Master text IDs:** `2372–2375`

The v1.2 executable's master-name pointer for ID 2372 was `0x46A590`. The 28-byte ASCII name:

`Aura Pegasus, Avatar of Life`

occupied `0x46A590..0x46A5AB` with **no terminating NUL**. Byte `0x46A5AC` was the beginning of master text ID 1161, an unrelated `Turbo rush` rule string. A normal C-string read therefore continued from Aura Pegasus's name directly into unrelated rules text.

The v1.3 correction:

- moves the Aura name start two bytes earlier to `0x46A58E`
- writes the same English name followed by NUL bytes
- changes only master pointer 2372 to the new address
- leaves master text ID 1161 and Aura's actual rules entry untouched

The original 2,376-entry overlap audit found this to be the only pointer-inside-string overlap.

### Software-keyboard / deck-name spacing

Save-state inspection proved that v1.2 user-entered deck names were stored as **full-width CP932 Latin**, e.g.:

`Ｐｈｏｅｎｉｘ`

rather than ASCII/half-width `Phoenix`.

The persistent keyboard mode byte is:

- runtime VA: `0x62852B`
- executable file offset: `0x52952B`

The A/ABC handler toggles modes `6/9`. Runtime QA proved mode `6` is the full-width Latin path and mode `9` is the half-width Latin path. v1.3 changes the final public executable from `6` to `9`.

The older `bosd_keyboard_default_ui81.py` remains in the repository only to reproduce the historical v1.2 build stage and its hashes. `bosd_v13_maintenance.py` is the canonical final v1.3 correction.

### SCRPACK probability-branch relocation / Shop → Leave hang

The intermittent Leave failure was not a generic renderer freeze or an unsignaled semaphore. PCSX2 save-state analysis initially sampled EE syscall `0x42`; that syscall is `SignalSema`, and the captured call was `SignalSema(10)`. The EE thread table showed no thread waiting on semaphore 10.

The actual root cause was script control flow.

The translated `SCRPACK.SDA` changed command positions but three `0C/07` probability-branch destinations still used stale pre-translation targets. The Shop → Leave sequence contains a **10% branch**. In v1.2 it targeted resource-relative `0x4994`, which resolves to file offset `0x58994` — eight bytes into the translated `cm_tips` command/string. The command actually begins at `0x5898C`, so the correct resource-relative target is `0x498C`.

The known Leave byte correction is:

- file offset `0x58882`
- v1.2: `0x94`
- v1.3: `0x8C`

The full v1.3 maintenance pass corrects **all three** stale probability-branch destinations. Runtime QA of the combined build no longer reproduced the reported Shop Leave / pack-result failures.

### Confirmed story-dialogue wrap

The visible line:

`If the World's Balance tips too far toward release...`

was wrapping by character boundary and could split `release` as `relea` / `se...`.

v1.3 uses the game's explicit `#cr0` control for the confirmed case:

`If World's Balance tips too far#cr0toward release...`

Only this confirmed line is changed. A prior audit found other long-line candidates, but those remain an audit list rather than proof of bugs and are not mass-rewrapped.

### CHANGE TURN clipping

`LO/TCHANGE.IMG` contains one indexed 256×256 TGA member:

`STRIG_IMG_TCHANGE_TGA`

Retail uses two separate vertical rows. v1.2 had the English `TURN` and `CHANGE` graphics packed into a touching/overlapping region, causing runtime clipping.

The v1.3 geometry places:

- `CHANGE` on the retail top-row footprint
- `TURN` on the retail lower-row footprint

The rebuilt archive remains exactly `19,456 bytes` and the geometry was accepted in runtime QA.

### Deck Builder `切` → `ACE`

The remaining Japanese badge was isolated to:

`DECK_SRC_DC_P02_TGA` inside `DECK.DAT`.

It appears only on the deck's designated key/trump card rather than as a general card action. The English localization uses the compact label:

`ACE`

Containment QA against v1.2:

- exactly one decompressed `DECK.DAT` member changed
- changed member: `DECK_SRC_DC_P02_TGA`
- changed indexed pixels: `230`
- pixel-difference bounds: `x=165..182`, `y=84..99`
- TGA header, palette, and trailer: byte-identical
- all other decompressed archive members: byte-identical
- target member compressed size: `27,520`
- target allocation: `29,696`
- remaining compressed headroom: `2,176`

v1.3 `DECK.DAT` remains the same `786,176-byte` archive.

---

## v1.2 history — duel digits 6–9

GitHub Issue #2 reported malformed lower portions of digits 6, 7, 8, and 9 during duels.

The cause was proven inside `IMG/DUELPTS.DAT`, member:

`DUELPTS_SRC_G_P00_TGA`

The English `LEFT` label had originally been cleared/painted beginning at `y=374`, while rows `374–384` were still occupied by the lower pixels of the shared numeric strip.

Measured v1.1 corruption:

- digit 6: 71 altered pixels
- digit 7: 136 altered pixels
- digit 8: 205 altered pixels
- digit 9: 206 altered pixels
- digits 1–5: 0 altered pixels

v1.2 restored the clean digit pixels and moved `LEFT` below the strip. This fix remains unchanged in v1.3.

---

## Card-text architecture

Two card-text systems remain relevant:

1. `COMMON/LIST_1.BIN`
2. a 2,376-pointer executable-resident master text table

The localization's combined `LIST_1.BIN` contains:

- 1,682 display pointers
- 2,376 master pointers
- total: 4,058 pointers

Key master-table constants:

- master table VA: `0x444268`
- master count: `2376`
- appended master-pointer table begins after the 1,682 display pointers

Current v1.2/v1.3 `LIST_1.BIN` is unchanged by v1.3:

`772775021faadd371a1fa3dbc8736586b290d9250bd11169e3478446c8c90f48`

---

## Card-image architecture

`UNPACK.IMG` card layers remain:

- chunks `677–1353`: 677 full-size printed cards
- chunks `1360–2036`: 677 128×128 thumbnails
- chunks `2037–2713`: 677 secondary 128×128 sprites/display assets with names baked into the image

v1.3 does **not** rebuild or alter the 677-card `UNPACK.IMG` layers.

---

## Shop booster-record warning

The executable booster record is:

- base: `0x4FDFF8`
- stride: `0x68`
- `+0x00`: 8-byte code
- `+0x08`: `0x50`-byte description
- `+0x58`: price
- `+0x5C`: image ID
- `+0x60`: pack index
- `+0x64`: pack index

The obsolete `bosd_shop_packdesc_ui80.py` treated the description as too large and overwrote metadata. It is intentionally not part of the retained toolset. Use `bosd_shop_packdesc_fixed.py`.

---

## Release construction

`tools/bosd_v13_release_builder.py` requires:

1. a directory containing the exact public-v1.2 `SLPM_658.82`, `SCRPACK.SDA`, `TCHANGE.IMG`, and `DECK.DAT` files
2. the official v1.2 full PPF whose SHA-256 is:
   `83429a57a8c6bba0bf3134600c9e08e9091ca0a7c366e583745db8209834c328`

A whole v1.2 ISO is not required. The verified public-v1.2 ISO locations are:

- `SLPM_658.82`: offset `0xB60E7800`, LBA `1491407`
- `SCRPACK.SDA`: offset `0x55C91800`, LBA `702755`
- `TCHANGE.IMG`: offset `0x22A2A800`, LBA `283733`
- `DECK.DAT`: offset `0xB7CD3000`, LBA `1505702`

The builder:

- verifies the exact public-v1.2 component hashes
- verifies those absolute locations against the official v1.2 PPF and the exact component bytes
- reconstructs `SCRPACK.SDA`, `TCHANGE.IMG`, and `DECK.DAT` byte-for-byte from the official v1.2 PPF as an independent location check
- verifies all PPF-covered executable bytes and every v1.3 executable edit
- generates the v1.2 → v1.3 hotfix PPF from only the verified changed bytes
- composes the clean-ISO → v1.3 full PPF from the official v1.2 full PPF plus those same maintenance writes
- verifies the resulting v1.3 target bytes and PPF3 structure

For this release, every v1.3 edit falls inside data already written by the official v1.2 full PPF, so the v1.3 full PPF has the same size, record count, payload byte count, and target EOF coverage as v1.2; only the affected target bytes and PPF description changed.

Do not upload a game ISO or extracted game-data binaries to GitHub.

---

## Save compatibility

Known memory-card identifiers remain:

- `BISLPM-65882`
- `PS2D`

PCSX2 save-state incompatibility after executable changes is not equivalent to memory-card incompatibility.

---

## AI research — future / separate patch only

No AI behavior modification is included in v1.3.

Preserved research:

- profile table VA: `0x567388`
- profile size: `0x1D8` / 472 bytes
- 66 valid profiles
- six-template priority table VA: `0x566128`
- priority-template stride: `0x1C8`

Known routines:

- `0x25F750` candidate/effect classifier
- `0x25FEB0` priority/rank helper
- `0x25E5A8` sorting
- `0x26CFB0` scoring
- `0x26E210` evaluator

High-level flow:

`enumerate -> classify -> evaluate -> priorities -> sort/rank -> act`

AI work must remain optional/separate until the normal full playthrough is complete.
