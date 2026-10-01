# Reverse-engineered format notes

This document records format facts independently of any single implementation.

## Packed UI DAT archives

Observed archive properties used by `botsd.archive`:

- 32-bit little-endian declared total size at file offset `0`
- bytes `4..7`: `ALL `
- header-size field at `+0x08`; `data_start = 8 + header_size`
- bytes `12..15`: `HDR `
- FILE directory record size: `0x114`
- FILE record name: NUL-terminated ASCII inside a 256-byte field
- record fields at `+0x104`: data-relative offset, stored size, compression flag, next-record size
- payload alignment normally `0x100`
- compression flag `0`: raw
- compression flag `1`: 4 KiB-window LZSS; member blob begins with a 32-bit uncompressed-size prefix

The shared parser preserves member order/names and verifies every rebuilt member by decoding it
again.

## BOTSD UI LZSS

- sliding/ring window: `0x1000` bytes
- initial ring position: `0xFEE`
- match lengths encoded as `3..18`
- flag byte covers eight tokens
- literal token: one byte
- match token: two bytes containing 12-bit ring offset and 4-bit `(length - 3)`

Two encoders exist:

- `botsd.lzss.compress`: fast bounded search, no overlap matches
- `botsd.lzss.compress_optimal`: overlap-capable match search plus dynamic-programming token parse
  for fixed-allocation archives

## ISO9660 assumptions

`botsd.iso9660` uses the primary volume descriptor and standard directory records:

- logical sector size: `2048`
- volume descriptors begin at sector 16
- descriptor identifier: `CD001`
- little/big-endian duplicated 32-bit fields are validated for equality
- directory record extent field: `+0x02`
- directory record file-size field: `+0x0A`
- volume-space-size field in PVD/SVD: `+0x50`

Same-size replacements retain the original extent. Enlarged files are sector-aligned, appended and
retargeted through the directory record; the volume-space-size field is increased accordingly.

## PPF 3.0 profile used by releases

- six-byte prefix: `PPF30\x02`
- 50-byte NUL-padded ASCII description
- image type: BIN (`0`)
- block check: disabled
- undo data: disabled
- each record: 64-bit little-endian absolute offset, 8-bit payload length, payload bytes
- maximum payload per record: 255 bytes

The project does not rely on PPF undo/block-check extensions.

## Card text

The combined card text resource contains:

- 1,682 display-text pointers
- 2,376 master-text pointers
- 4,058 pointers total

The internal retail card database has 673 card identities while the rendered card resource set has
677 entries because the resource inventory contains additional printings/resources.

## Card image layers in UNPACK.IMG

- chunks `677–1353`: 677 full-size printed cards
- chunks `1360–2036`: 677 128×128 thumbnails
- chunks `2037–2713`: 677 secondary 128×128 display/name sprites


The UI75 semantic card-face layout is machine-readable in `botsd/assets/cardfaces_ui75.json`.
Large card resources are one-member packed UI archives inside their fixed outer SDA chunks. The
large indexed texture is 512×512; the printed face occupies x=0..383 and is resampled to 128×128 for
the thumbnail layer. Only declared title/type/rules/flavor rectangles are quantized back into the
original palette. Outer chunk sizes/offsets and inner archive allocations are invariants.

The UI82 second-name patch format is a ZIP containing `manifest.csv` plus `chunks/NNNN.bin`. The
manifest has `chunk`, `retail_sha256`, and `patched_sha256` fields. Creation requires the UI76→UI82
delta to be exactly chunks 2037..2713 and proves the UI76 preimages for those chunks are still retail.

## Release-level values

Do not duplicate release hashes/offsets from this document into code. The authoritative machine-
readable values live in `botsd/release_manifest.json` and are exposed through `botsd.manifest`.


## Semantic visual recipes

The repository intentionally separates editable visual intent from packed UI bytes. JSON recipes
under `botsd/assets/` operate on the decompressed indexed-TGA pixel plane and specify the exact LZSS
encoder used when the member is written back into its fixed archive allocation.

### TCHANGE v1.3

The v1.2 English texture already contains the required `TURN` and `CHANGE` glyph rasters. The v1.3
recipe clears the old connected region, moves CHANGE upward by 47 pixels, moves TURN left by 32 and
down by 47 pixels, and records the small row-76/77 masks needed to separate the two outlines where
they touched in v1.2. No target TGA or packed archive payload is embedded.

### ACE badge v1.3

The badge recipe stores only an 18x16 palette-index source template using named one-character symbols.
The palette itself continues to come from the user's exact v1.2 `DECK_SRC_DC_P02_TGA`; the builder
changes the configured rectangle and leaves the TGA header, palette, trailer, other members and archive
layout untouched.

## SCRPACK script safety rules

`SCRPACK.SDA` is a packed event/script resource. The complete opcode grammar is not yet formalized,
so tools must preserve unknown commands byte-for-byte unless a command has been specifically
reverse-engineered.

Known v1.3-relevant behavior:

- command positions are resource-relative and translated text can shift later command boundaries
- the `0C/07` probability-branch family contains a destination that must be relocated when its target
  command moves
- a branch target landing inside command/string payload is invalid even if the surrounding byte
  stream still parses superficially
- `#cr0` is an explicit in-string line-break control used by the dialogue renderer
- the confirmed Shop -> Leave bug was caused by a stale branch target landing eight bytes inside a
  translated `cm_tips` command, not by a generic semaphore deadlock

The shared v1.3 regression definitions intentionally encode only the proven same-size edits. A future
SCRPACK parser should first define command lengths/targets formally and add round-trip fixtures before
attempting global rewriting.

## Executable-resident master card text

The executable contains a 2,376-entry master-text pointer table:

- master pointer table VA: `0x444268`
- master text count: `2376`
- pointers resolve C-style CP932/ASCII strings, so every string boundary must have a valid terminator
  before another live pointer/string begins

The externalized combined `LIST_1.BIN` used by the localization contains 1,682 display pointers
followed by 2,376 master pointers. The authoritative counts are machine-readable in
`botsd/release_manifest.json`.

The Aura Pegasus v1.3 regression exists specifically because one embedded English name lacked a NUL
terminator and ran into an unrelated live master-text string.

## Booster-shop executable records

The verified fixed record used by the shop description tooling is:

- base file offset: `0x4FDFF8`
- stride: `0x68`
- `+0x00`: 8-byte pack code
- `+0x08`: `0x50`-byte description area
- `+0x58`: price
- `+0x5C`: image ID
- `+0x60`: pack index
- `+0x64`: pack index

Text writers must never treat the metadata tail as spare string capacity. The historical bug that
produced `0 DP` packs came from violating this boundary.

## Software-keyboard mode byte

The persistent/default keyboard-mode byte used by the v1.3 deck-name fix is exposed through the
release manifest rather than duplicated in new code. For the verified SLPM-65882 executable, mode
`6` selected the full-width Latin path and mode `9` selects the half-width Latin path used by v1.3.

## Combined card-text `LIST_1.BIN`

Retail `COMMON/LIST_1.BIN` begins with 1,683 relative 32-bit little-endian pointers: 1,682 meaningful
display-text entries plus one EOF sentinel. The localized externalized form contains exactly 4,058
relative pointers:

- `0..1681`: display text
- `1682..4057`: the 2,376-entry master card-text table previously resident in the executable

The pointer table is therefore `4058 * 4 = 0x3F68` bytes. Each nonzero logical entry points to a
NUL-terminated CP932 string after the table. Byte-identical strings may share one offset; consumers
must not assume pointer uniqueness.

The externalization executable patch changes the loader loop count to 4,058 and redirects the
card-text singleton's master-table pointer to the appended portion of the relocated LIST resource.
The source build guards the retail executable and patch-site instructions before writing anything.

English text uses CP932-compatible bytes. The project reserves literal byte/character `~` as the
internal stand-in for the added `Ü` glyph; source text must write `Ü`, not a literal tilde.

## `DECK/*.DAT` fixed text fields

The localized hidden deck records have two fixed player-visible text fields before gameplay data:

- `0x06..0x2D`: 40-byte callout field
- `0x2E..0x41`: 20-byte deck-title field
- `0x42..EOF`: deck/card composition and other non-text data; localization must not modify it

Retail source fields decode as CP932. The current English replacements are ASCII and are NUL-padded
inside the same allocations. A replacement must leave at least one NUL terminator byte inside its
field. `localization/en/deck_text.json` stores the source guard and English value separately from the
binary patch implementation.

## FONTLINK / DPAC font archive

`FONTLINK.PAC` begins with `DPAC`, followed by a little-endian entry count and alignment. The verified retail archive has 453 directory entries and alignment `0x40`. Each directory entry is 24 bytes: a 16-byte NUL-terminated ASCII name, a 32-bit stored size and a 32-bit absolute archive offset.

Font member streams begin with the expected uncompressed size, followed by 16-bit tokens. A zero token terminates the stream. Tokens with a non-zero high five-bit length encode a back-reference with an 11-bit distance; other tokens encode a literal run. ASCII glyph pages begin with four 16-bit values: width, height, bytes-per-glyph and a reserved zero. The verified half-width pages use 12×24 4bpp cells, or 144 bytes per glyph.

`botsd.fontlink` contains the shared parser/codec and the semantic construction of the reserved English `Ü` glyph used by the localization font patch.

## Indexed TGA editing rules

BOTSD UI textures handled by the cleanup use color-mapped TGA type 1, 8-bit pixel indices, and a
24- or 32-bit palette. `botsd.indexed_tga.IndexedTGA` preserves the original header, palette, image
orientation and trailer; ordinary edits replace only the indexed pixel plane. Palette indices are
interpreted relative to the TGA color-map first-entry value rather than assuming zero in shared
code.

Static-label and residual-graphic builders declare allowed rectangles. Regression helpers compare
the original and rebuilt top-down index planes and fail if a changed pixel escapes those boxes. UI
archive member replacement is fixed-allocation: member offsets and archive length are preserved,
and every non-target member must decompress byte-identically.

## Outer SDA container (`UNPACK.IMG`)

The top-level card-resource container begins with:

- `0x00`: ASCII `sda\0`
- `0x04`: little-endian declared total byte size
- `0x08`: little-endian chunk-count `N`
- `0x0C`: `N` little-endian absolute chunk offsets

Chunk `i` occupies `offset[i] .. offset[i+1]`; the final chunk extends from the last offset through
EOF. The public retail/UI76/UI82 card builds preserve the complete offset table and total size.
`botsd.sda.OuterSDA` validates monotonic/in-range offsets and supports streaming chunk reads/hashes.
The UI82 second-name layer is chunks `2037..2713` inclusive (677 chunks).

Each chunk is an 18,432-byte indexed 128×128 TGA with a 32-bit palette. The recovered English
renderer edits only title band `(0,2,128,15)`; title-ramp detection examines rows `3..13`. It groups
near-identical RGB palette entries across alpha levels, prefers ramp members unused below the title,
and uses a conservative top-dominant fallback for the one known shared-ramp card (sequence 623).
TGA header/palette/trailer bytes are immutable. The accepted v1.3 concatenated payload digest for
chunks 2037..2713 is
`dea8fa559db96f9cc38bfeddac8996dc27a2c90c3f2fdd28e9ece659f76c0f92`.


## Executable-resident Card Info rule/race table

The historical UI76 Card Info build uses the 2,376-entry master pointer table at VA `0x444268` and
a 65-entry race pointer table at VA `0x4436D8`. Only master rows whose role contains `rules` are
repacked by this stage. Non-rule master pointers are a hard invariant. The accepted stage also uses
verified zero slack at `0x46A5AC..0x470000` after conservative pointer/memory-reference guards, plus
a small race overflow pool at `0x470080..0x470400`. These values are versioned in
`botsd/assets/cardinfo_ui76.json` rather than duplicated through active code.
## UI76 whole-card source manifest

The UI76 production mapping is exported as `UI76_WEBP_MAPPING.csv`. It records sequence/resource identity, verified English name/set mapping, selected database printing, source class/URL/file/hash/dimensions, palette color count, compressor result/headroom, and the large/small UNPACK chunk numbers. Public/pinned source selection lives in `botsd.card_sources`; project-only scan-style exceptions are described by an `exception-dir/manifest.csv` with `resource_key`, `internal_id`, `english_name`, `source_class`, `image_file`, `image_sha256`, and `provenance`. No source images are embedded in the Python package.

## DUELPTS shared-number atlas repair

The Issue #2 target is `DUELPTS_SRC_G_P00_TGA` inside `DUELPTS.DAT`. The accepted repair is represented by `botsd/assets/duelpts_issue2.json`: rows 357..384 contain the shared digit strip, while the English `LEFT` raster must begin at row 385. The builder validates the original damage signature before changing pixels, which prevents the fix from being applied to an unrelated archive revision.

## SCRPACK.SDA script command framing

`SCRPACK.SDA` uses the same outer `sda\0` offset-table container described above. Script-bearing
chunks examined for the v1.3 maintenance pass are fully parseable as consecutive commands with no
inter-command gap:

```text
u16 opcode
u16 payload_size
u8  payload[payload_size]
```

The next command begins exactly `4 + payload_size` bytes after the current command header. A valid
chunk consumes its fixed SDA chunk allocation exactly. This is important for localization because
translated payloads can change individual command lengths while leaving command *ordinals* stable.

### `0x070C` probability branch

The three retail/v1.2 probability branches relevant to the maintenance bugs have payload size 12.
The fields needed by the maintained parser are:

```text
+0x00  u16 opcode = 0x070C
+0x02  u16 payload_size = 12
+0x06  u32 probability (10 in the three known cases)
+0x0A  u32 target, relative to the start of the containing SDA chunk
```

The target must equal the start of a command in the same chunk. Retail targets were command
boundaries, but three translated v1.2 branches retained those old numeric offsets after earlier
commands changed size. v1.3 maps each retail branch to its intended command ordinal and resolves the
current translated offset from the parsed stream.

### `0x1D03` dialogue command

For the verified story-dialogue form used by the World's Balance fix:

```text
+0x00  u16 opcode = 0x1D03
+0x02  u16 payload_size
+0x04  6 bytes of command metadata
+0x0A  u16 encoded text length
+0x0C  CP932/ASCII text of the declared length; if shorter than the command allocation, the remaining bytes are zero padding
```

The semantic writer changes only the length field and text/padding area; the command header, payload
size, following command boundary, and outer SDA layout remain unchanged.


### Stable story-text identity

For localization/review purposes, an opcode `0x1D03` text resource is identified as:

`SCRPACK chunk index + command ordinal`

rather than by its physical byte offset. A canonical textual form is
`scrpack.<three-digit-chunk>.<four-digit-command>`, e.g. `scrpack.123.0646`.

This identity was verified across the complete retail and public-v1.2 SCRPACK pair: all 9,581
`0x1D03` commands pair at the same chunk/command ordinal even where English text changes command
sizes and shifts later physical offsets. File offsets remain useful diagnostics but are not stable
localization keys.
## Localization manifest schema v2

`localization/<language>/manifest.json` supports three dataset forms:

- `csv` (default): ordinary header-based rows; schema-v1 manifests remain readable.
- `json_records`: a JSON array of record objects selected by optional dotted `records_path`.
- `json_mapping`: a keyed JSON object; `$key` selects the map key and `$value` selects a scalar value.

`text_fields` may remain a list when logical field names equal source columns/selectors, or be an
object mapping provenance field names to selectors. `source_fields` can associate a different source
selector with each translated field. Optional `review_status_field` and `notes_field` preserve
explicit evidence already present in a language record. Review values are restricted to the shared
review-status vocabulary.

The audit also treats every `.csv` and `.json` file directly under `localization/<language>/` as a
language resource and requires it to be registered, except the manifest itself.
## ACE badge language pixel recipe

`localization/<language>/ace_badge_v13.json` stores one semantic badge record with a human-readable
label and an indexed-symbol row template. `botsd/assets/ace_badge_v13.json` maps those symbols to the
verified palette indices and declares the destination rectangle/compression allocation. This split
keeps language content out of binary-layout metadata while preserving exact published pixels.
