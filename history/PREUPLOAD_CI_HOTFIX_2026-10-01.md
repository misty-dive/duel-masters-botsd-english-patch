# Pre-upload CI hotfix — 2026-10-01

A real macOS development checkout with Python 3.12 and the repository's pinned development
dependencies exposed checks that could not be executed in the earlier standalone environment.

## Findings

- Ruff reported 120 findings. Most were formatting/import-order/modernization-only findings
  (`E501`, `I001`, `UP*`). Correctness findings (unused imports, `zip()` strictness and the overly
  broad exception assertion) were fixed.
- Mypy reported 45 errors in 16 modules. The errors were type-narrowing/interface issues rather
  than binary-logic failures and were corrected without changing release recipes.
- Pytest found two failures:
  1. `font_polish` used a Pillow API unavailable in the pinned Pillow 11.3.0.
  2. The repository-CSV card-text test incorrectly equated the maintained source CSV corpus with a
     frozen byte snapshot of the historical public-v1.2 `LIST_1.BIN`.

## Corrections

- `font_polish` uses the Pillow 11-compatible `Image.getdata()` path.
- Current repository CSVs are required to rebuild and round-trip a valid 4,058-pointer combined
  LIST. Exact public-v1.2 LIST size/hash verification remains in the separate golden-component test
  activated when the published component is supplied.
- Type annotations/narrowing were repaired for SCRPACK, story datasets, FONTLINK mutable pages,
  localization manifests, semantic asset resource paths, JSON geometry tuples, card-source maps,
  full-card source metadata and ISO extraction mappings.
- Ruff's CI profile now focuses on syntax/correctness/unused imports and Bugbear
  (`E4`, `E7`, `E9`, `F`, `B`). Line wrapping/import sorting/modernization-only rules are not
  release gates for the archaeological codebase.

## Local verification in the cleanup environment

- `python -m compileall -q botsd tests`: PASS
- standalone `pytest`: PASS (external/copyrighted golden-input tests skipped as designed)
- semantic FONTLINK glyph round-trip: PASS under Pillow 12.3.0; the chosen API is supported by the
  repository-pinned Pillow 11.3.0 as demonstrated by the original failure mode.
- The exact SCRPACK compiler logic was not changed by this hotfix.

The user's real checkout should rerun:

```bash
ruff check botsd tests
mypy botsd
pytest
```

before committing. That checkout contains the public `data/*.csv` corpus and the exact pinned
development dependency versions, making it the authoritative final pre-commit CI-equivalent check.
