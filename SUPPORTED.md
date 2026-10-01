# Supported game revision and environments

## Game revision

The patch and release tooling support the Japanese PlayStation 2 release:

- **Game:** Duel Masters: Birth of the Super Dragon
- **Serial:** `SLPM-65882`
- **Clean ISO size:** `3,080,880,128` bytes
- **Clean ISO SHA-256:** `f3108b9b5edaf4feda55ec393f37a8263fb833e25baa2bb5213459439e826a96`

Release-critical tools fail closed when hashes/sizes do not match the expected revision. Alternate
regions, re-dumps, pre-patched images and modified executables are not implicitly supported.

The machine-readable release values live in `botsd/release_manifest.json`; this document should not
be used as a second source of constants in code.

## Patch upgrade inputs

The v1.3 maintenance/release builder also recognizes the exact public v1.2 maintenance components
and official v1.2 full PPF. Their hashes are stored in the release manifest and are verified before
any output is emitted.

## Emulator / hardware status

Compatibility evidence is tracked in `qa/compatibility_matrix.csv` and must name an exact emulator
or hardware environment when a test is performed. PCSX2 is the primary development environment;
real-PS2 and Android/NetherSX2 coverage remain separate QA items rather than assumed compatibility.

Normal PS2 memory-card save compatibility is tracked independently in `qa/save_compatibility.csv`.
PCSX2 save-state compatibility is not evidence for or against normal memory-card compatibility.
