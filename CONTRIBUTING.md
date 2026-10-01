# Contributing

Please keep changes small, reproducible and reviewable.

- Work on a feature/fix branch rather than editing `main` directly for substantial changes.
- Add or update a regression test for every confirmed bug fix.
- For binary edits, document the preimage, offset/structure, semantic reason and expected output hash.
- Do not commit original ISOs, extracted retail binaries, save states or copyrighted game assets.
- Prefer semantic source transformations over opaque binary payloads when both can reproduce the
  same verified result.
- Import release-level hashes/counts/offsets from `botsd.manifest`; do not duplicate them in new
  scripts.
- Put reusable format logic in `botsd/`; keep `tools/` wrappers thin when historical filenames need
  to remain compatible.
- Keep network/deprecated online work and future AI changes separate from the offline localization.
- Use precise commit messages such as `Use streaming ISO9660 replacement writer`, not `updated`.

Before opening a PR:

```bash
python -m pip install -e '.[dev,graphics]'
ruff check botsd tests
mypy botsd
pytest
```


## Release/version convention

Historical tags are inconsistent (`v1.0` versus `1.1`/`1.2`/`1.3`). Do not rewrite published tags.
Use `vX.Y` for all future release tags and record every public release in `CHANGELOG.md`.

## Localization provenance

Do not mark historical translation rows as `human_reviewed`, `official_terminology`, or
`runtime_verified` simply because the current patch contains them. Preserve existing source/status
metadata and strengthen review state only when there is row-specific evidence. Use
`localization/en/manifest.json` and the provenance exporter as the migration path.

## QA evidence

Keep binary/static verification distinct from runtime verification. Update `qa/regressions.csv` when
a known bug becomes a permanent regression and update the playthrough/save matrices when a real
manual test is performed. Never convert `not_tested`/`static_only` to a stronger state based only on
assumption or a successful build hash.
