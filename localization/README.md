# Localization data architecture

The v1.3 repository predates a clean language-pack split. Release-critical English CSVs therefore
remain under `data/` so historical build paths are not broken.

`localization/en/manifest.json` is the non-destructive mapping layer for both the historical CSVs
and the semantic JSON language resources already checked into the repository. Schema v2 records
IDs, translated fields, optional source guards and explicit review metadata without copying text into
a second source. `localization-audit` also rejects orphaned `.csv`/`.json` resources under the
language directory so new language data cannot silently bypass provenance coverage.

Future localization work should separate:

1. **Language-independent game tooling** in `botsd/`: archive formats, ISO handling, text-table
   extraction/reinsertion, font encoding, validation and patch generation.
2. **Language-specific content** under `localization/<language>/`: translated strings, terminology,
   review state and provenance.

## Translation review states

Use explicit evidence-backed states:

- `unreviewed` — inherited/imported text with no row-level review record
- `machine_draft` — machine/AI-assisted draft awaiting human review
- `human_reviewed` — reviewed for meaning/readability in context
- `official_terminology` — wording/name follows an official English Duel Masters source
- `community_established` — established community reference where no official English source exists
- `runtime_verified` — checked in the actual game UI/context

The current manifest defaults to `unreviewed`. Existing legacy source/status columns are preserved
but are not silently promoted into one of the stronger states above.

## Commands

```bash
python -m botsd localization-audit localization/en/manifest.json --root .
python -m botsd provenance-export localization/en/manifest.json \
  --root . --output local/provenance_en.csv
```

The v1.2 SCRPACK story corpus now has translation-only editable datasets under `localization/en/`:
`story_dialogue_v12.csv` contains the 9,499 dialogue commands whose English text differs from
retail, and `story_choices_v12.csv` contains all 293 `0x1F03` menu-choice commands. The 82 dialogue
commands that are identical to retail are deliberately omitted and left untouched by the builder.
Extracted Japanese retail story text is not checked into the repository. The manifest also covers
the already-separated deck/shop/static-label/executable-residual/UI-polish/WAIT/v1.3-maintenance
JSON resources and the frozen v1.3 `ACE` badge pixel template. Remaining cleanup is in older
binary-only production stages rather than manifest visibility for these files.

## Shared translation-processing code

The historical card-rule and flavor-import scripts are now compatibility entry points only:

- `botsd.ruleswrap` owns the measured 24-cell Card Info wrap model and the invariant that new line breaks replace existing spaces without changing encoded string length.
- `botsd.flavor` owns printing-specific flavor selection, verified card-identity joining, mojibake cleanup and CP932/extended-glyph validation.

These modules process the existing release-critical CSVs in place or into explicit outputs; they do not duplicate the translation corpus into a second source of truth.

## Story corpus extraction

`botsd.storytext` can now derive a complete story-text review catalog directly from a legally
obtained retail SCRPACK and a translated SCRPACK. It assigns stable IDs from chunk/command ordinals
instead of treating binary offsets as localization IDs. This is the migration path for the older
v1.0-v1.2 story corpus without checking a duplicate dump of extracted retail script text into the
repository.
