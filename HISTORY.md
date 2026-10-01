# Project history

The project evolved through internal checkpoints named UI55/UI75/UI76/UI81/UI82 and several
versioned one-off scripts. Those names describe development chronology, not the intended long-term
architecture.

They are retained where necessary so old handoffs and build records remain understandable, but new
shared code should use functional names under `botsd/`.

## Cleanup Phase 22 — final pre-upload consistency pass

Phase 22 did not change the translation release. It reconciled a handful of stale architecture/build
statements with the Phase 16–21 reality, centralized the remaining maintained-code copies of
authoritative card/text/UNPACK counts, and added a final repository audit record before GitHub
integration.


## Cleanup Phase 20 — ACE raster source separation

Phase 20 moved the accepted v1.3 `ACE` badge template from `botsd/assets` to the English language
package while preserving the exact indexed pixels. It also repaired the legacy-tool map's Markdown
structure and made the mapping regression require exact table-row coverage. No release binary was
changed.


## Cleanup Phase 19 — unified localization provenance

Phase 19 extended the localization manifest from CSV-only metadata to the JSON language resources
already driving deck/shop/UI maintenance. It added orphan-resource detection and preserved explicit
per-record review evidence without changing any game binary or release patch. It also fixed package
version metadata drift by tying `botsd.__version__` to the same release value tested against
`pyproject.toml`.


## Public releases

### v1.0

Initial public English translation release.

### v1.1

Maintenance release addressing booster-shop metadata corruption and several Records/Options/Deck UI
presentation issues.

### v1.2

Corrected the shared duel-number atlas after the English `LEFT` label edit damaged digits 6–9.

### v1.3

Post-v1.2 QA maintenance release:

- Aura Pegasus unterminated-name repair
- three SCRPACK probability-branch relocations, including Shop → Leave
- keyboard default changed to half-width Latin mode 9
- CHANGE TURN geometry correction
- confirmed World's Balance dialogue wrap repair
- Deck Builder `切` badge localized as `ACE`

See `CHANGELOG.md` for the concise release list and `REVERSE_ENGINEERING.md` for technical causes.


## Post-v1.3 repository cleanup

Phase 21 completed the SCRPACK story source path. Using the exact retail archive, the maintained
compiler now rebuilds command streams with variable-size dialogue/choice payloads, consumes or
releases trailing zero-command padding, and relocates the five proven historical target-bearing
opcode families. The generated v1.2 SCRPACK is byte-identical to the frozen public v1.2 component;
feeding it through the existing semantic v1.3 maintenance stage produces the exact public v1.3
SCRPACK. The three stale `0x070C` probability targets are intentionally preserved by the v1.2
compiler because that historical defect is part of the frozen v1.2 baseline and is repaired by v1.3.

Phase 20 separated the exact English `ACE` badge raster template from language-independent binary
geometry while preserving the 288 indexed pixels byte-for-byte, and repaired the historical-tool map
so every retained top-level compatibility script is represented by a real table row.

Phase 19 unified CSV and JSON localization resources under the provenance manifest, added orphan
resource detection, preserved evidence-backed review status, and added a regression keeping package
version metadata synchronized.

Phase 18 finished a small but persistent wrapper/configuration cleanup: the reserved-English `Ü`
FONTLINK recipe is machine-readable, its retail hash is no longer duplicated in a historical script,
FONTLINK/keyboard checkpoint stages have package-native commands, and the legacy tool map is now
coverage-tested against every top-level compatibility script.

Phase 17 moved the older SCRPACK story baseline from a generated review catalog into maintained
translation-only language data. Stable command IDs drive 9,499 changed dialogue translations and
all 293 menu-choice commands; extracted Japanese retail story text stays outside the repository.
Phase 21 subsequently proved those datasets as an exact retail-to-v1.2 compiler input.

The cleanup deliberately preserves historical filenames while moving active logic into `botsd/`.
Phase 3 is the point where the final v1.3 visual maintenance fixes stopped depending on opaque packed
XOR deltas: CHANGE/TURN is now described as a layout transform and ACE as a small indexed-pixel source
template. Historical release hashes did not change.
