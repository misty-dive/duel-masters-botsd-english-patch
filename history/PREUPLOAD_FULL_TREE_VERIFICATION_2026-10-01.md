# Pre-upload full-tree verification — 2026-10-01

This pass replaces the earlier partial 0.22.1 hotfix delivery with one complete cumulative overlay.
The partial archive was unsafe for macOS workflows because replacing its `botsd/` directory could
remove unchanged package modules. The source fixes themselves were retained; delivery is now full-tree.

## Additional correction

- `botsd.cli.cmd_iso_verify_assets` now types its extraction map as `dict[str, str | Path]`, matching
  `verify_hash_manifest` and eliminating the final mypy variance error visible in the complete-tree run.

## Verification performed on the complete tree

- all 50 top-level `botsd` package files present
- every importable `botsd.*` module imported successfully
- `python -m compileall -q botsd localization tests`: PASS
- standalone pytest: 138 total / 124 passed / 14 skipped / 0 failed / 0 errors
- exact SCRPACK golden suite with supplied retail and v1.2 inputs: 9/9 passed / 0 skipped
- localization/package/module inventory checks: PASS

Ruff and mypy executables are not available inside the OpenAI container. The previous user-side
0.22.1 run showed Ruff clean and showed only missing-module import errors after the partial archive
replaced the package directory. All modules are restored here; the one complete-tree mypy error that
was outside the partial archive (`botsd.cli` dict invariance) is fixed in 0.22.2. The intended final
validation remains the repository CI / the user's Python 3.12 environment.

No copyrighted retail binaries are included, and no published patch bytes are changed.
