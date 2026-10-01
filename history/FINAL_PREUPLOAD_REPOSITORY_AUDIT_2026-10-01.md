# Final pre-upload repository audit — 2026-10-01

This audit was run against the cumulative Phase 22 tree before GitHub integration. It is a
repository/tooling audit, not a claim of complete game playthrough coverage.

## Scope

The audit checked the concerns that originally motivated the cleanup: automated testing/CI, licensing,
central manifests, shared package architecture, historical wrapper mapping, semantic-vs-binary
reproducibility, localization separation/provenance, documentation consistency, repository metadata,
and obvious duplicated release constants. Runtime game coverage remains tracked separately in `qa/`.

## Results

### Repository structure and process support

Present and validated:

- GitHub Actions CI
- pytest regression suite
- Ruff and mypy configuration in `pyproject.toml` / CI
- MIT license for project-authored code/tooling with third-party game-content caveats
- `botsd/` shared package and package-native commands
- `pyproject.toml` development/runtime dependency definition
- bug-report and pull-request templates
- contribution, security and supported-revision documentation
- architecture, building, formats, reverse-engineering, history, QA, roadmap and changelog documents
- compatibility-wrapper map with regression coverage

### Central release/configuration data

No 64-character release SHA-256 literals remain in active top-level `botsd/*.py` modules. Release
hashes are loaded from machine-readable manifests/specs. Phase 22 additionally moved the remaining
maintained-code validation copies of the 673/677/1682/2376 resource/text counts and the 2,809 UNPACK
chunk count behind the central release manifest. Human-readable help/docstrings may still state those
figures intentionally.

### Localization separation

`localization/en/manifest.json` covers the checked-in English `.json`/`.csv` language resources. The
final audit found no orphaned language data and no registered local language resource missing from
disk. The manifest/provenance model remains conservative: review status is not upgraded without
evidence.

### Reproducibility

The repository now has semantic source paths for the major release-critical systems migrated during
the cleanup, including the recovered 677-card second-name renderer and the exact retail -> v1.2 ->
v1.3 SCRPACK story pipeline. Published v1.3 hashes remain the frozen verification oracle. Some older
pre-v1.3 production steps outside SCRPACK may still be historical/binary-derived; they should only be
migrated when exact source-level parity can be demonstrated.

### Runtime QA

The QA matrix infrastructure exists, but full playthrough, normal memory-card compatibility, Android
emulator coverage and real-hardware coverage are intentionally not claimed complete. Those results can
be added as the user tests at their own pace.

## Verification results

- `python -m compileall`: PASS
- standalone `pytest`: 138 total / 124 passed / 14 skipped / 0 failed / 0 errors
- SCRPACK golden tests with exact retail and v1.2 components: 9/9 passed
- focused manifest/localization/legacy-map/repository-invariant tests: 14 passed / 2 expected skips
- orphan localization resources: 0
- missing registered local localization resources: 0
- active top-level Python SHA-256 literals: 0
- maintained-code authoritative-count literal findings: 0

Ruff and mypy are configured and run in GitHub Actions, but their executables were not installed in
the local execution environment used for this audit.

## Conclusion

The original repository-maintainability critique is substantially addressed. The remaining material
work is primarily runtime QA and any future, evidence-backed semantic migration of older production
steps—not foundational repository repair.
