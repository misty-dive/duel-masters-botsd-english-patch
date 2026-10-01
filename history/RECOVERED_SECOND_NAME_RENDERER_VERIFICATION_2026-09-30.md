# Recovered UI82 second-name renderer verification — 2026-09-30

## Scope

This report closes the source-reproducibility gap for the third 677-card raster layer in
`UNPACK.IMG`, chunks `2037..2713`.

## Recovered source

- File: `bosd_build_unpack_second_names_ui82.py`
- SHA-256: `7a38b00174b0a50b0662932a278ec14462851a89e44975c5c5380c34a90ea745`
- Preserved copy: `tools/archaeology/bosd_build_unpack_second_names_ui82_recovered.py`

The script is a semantic renderer, not merely a delta packager. It reads the canonical English card
name, detects/removes the retail Japanese title ramp in each 128×128 indexed TGA, renders the English
name with the game font, requantizes only the measured title band, and emits all 677 replacement
chunks.

## Verified inputs

- Retail `UNPACK.IMG`
  - size: `151,525,376`
  - SHA-256: `179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece`
- v1.3 localized `UNPACK.IMG`
  - size: `151,525,376`
  - SHA-256: `2d3fe1849b18e749fac2a9f496776c2d653c9450d566c9f90fdea216b370ff58`
- v1.3 `FONTLINK.PAC`
  - size: `1,625,600`
  - SHA-256: `bea98d495a42aec887020dd4b8e70f6ca38612d0e23f4af7119e1cdef584fb42`
- Card names: public `data/unpack_card_inventory.csv`, 677 rows.

The historical helper API imported by the recovered script had already been migrated/removed from
the active tree. For the direct archaeological run, a thin compatibility adapter mapped its old
`TGA`, `GameFont`, and `ascii_text` interfaces onto the corresponding Phase 15 shared primitives.
The recovered script itself was not modified.

## Direct recovered-script result

- Rendered chunks: `677`
- Range: `2037..2713`
- Title detector fallbacks: `1` (sequence 623)
- Total changed indexed pixels: `498,467`
- Generated payloads compared against v1.3: `677`
- Byte-identical matches: `677`
- Mismatches: `0`

Ordered concatenation SHA-256 of generated chunks `2037..2713`:

`dea8fa559db96f9cc38bfeddac8996dc27a2c90c3f2fdd28e9ece659f76c0f92`

## Shared Phase 16 migration result

The algorithm was migrated into `botsd.second_names` using:

- `botsd.sda.OuterSDA`
- `botsd.indexed_tga.IndexedTGA`
- `botsd.gamefont.GameFont`
- `botsd.cardfaces.ascii_text`
- `botsd.ui_graphics.update_tga_from_rgba`
- the canonical deterministic second-name patch writer in `botsd.unpack`

The package-native command is:

```bash
python -m botsd unpack-render-second-names RETAIL_UNPACK \
  data/unpack_card_inventory.csv FONTLINK.PAC second_names.zip
```

The migrated renderer again produced the same frozen payload digest and all 677 payloads matched the
v1.3 UNPACK byte-for-byte. The deterministic canonical patch ZIP SHA-256 for the verified inputs was:

`d02af8522264bcfce28677eeb64ff6c053492a25bb5c0e1a4d81264de5617f6e`

A second run through the historical-name compatibility wrapper produced the same ZIP hash.

As an end-to-end application proof, the 677 v1.3 second-name chunks were first replaced with their
retail preimages, producing an otherwise-identical base image with SHA-256
`24c6774702287e9f8b2e081ca9d7cbf6312ac575033e2b603bff6c6800accb46`. Applying the semantic
patch ZIP to that image rebuilt the supplied v1.3 UNPACK byte-for-byte, including the exact final
SHA-256 `2d3fe1849b18e749fac2a9f496776c2d653c9450d566c9f90fdea216b370ff58`.

## Conclusion

The third-card-layer source-reproducibility gap is closed. The accepted v1.3 raster layer can be
regenerated from semantic English card names, verified retail sprites, and the localized game font
without embedding the finished 677 payloads as source data. The published v1.3 release remains
unchanged.
