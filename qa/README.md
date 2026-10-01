# Runtime QA records

These CSVs turn coverage into versioned project data instead of scattered chat notes. They contain
no game assets.

- `playthrough_matrix.csv` tracks game-area coverage using `not_tested`, `partial`, `complete`, or
  `blocked`.
- `compatibility_matrix.csv` tracks emulator/hardware environments separately from gameplay coverage.
- `save_compatibility.csv` tracks deliberate normal PS2 memory-card compatibility checks separately
  from emulator save states.
- `regressions.csv` is the permanent corpus of known historical bugs and records static/automated
  evidence separately from runtime confirmation.

For every new runtime pass, record the patch version, exact platform/emulator version and whether a
normal PS2 memory-card save was involved. Emulator save states are diagnostic snapshots and must not
be used as evidence of normal save compatibility.

Useful commands:

```bash
python -m botsd qa-summary qa/playthrough_matrix.csv
python -m botsd qa-audit qa
```

CI validates schema/status consistency, but it cannot convert an untested case into a tested one.
