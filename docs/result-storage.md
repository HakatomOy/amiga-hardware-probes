# Results storage and cache policy

## Files are sufficient

Keep the authoritative data in files. Current access is primarily by experiment,
capture ID and hash; a database would add migrations, backup and consistency work
without removing the need to preserve binary packets and logs. If cross-run
queries become slow, add a disposable SQLite index derived from manifests. Do
not make that index the sole source of evidence. No database is required now.

| Location | Contents | Retention |
|---|---|---|
| `references/ID/` | Reviewed A500 `results.bin` and provenance `manifest.json` | Versioned in Git; immutable; add a new ID for changed evidence |
| `captures/RUN/` | Frozen executable/configuration, local ROM archive, candidate/HW packets, comparisons, traces, full logs | Local and ignored; preserve accepted/rejected evidence; back up independently |
| `captures/.experiment-cache/` | Command/replay reuse entries and derived `evidence/` packets | Disposable acceleration; never the only copy of accepted evidence |
| `investigations/*.json` | Confirmed facts, references, rejected hypotheses and next question | Versioned, short restart knowledge |
| `docs/` | Measurement contracts and detailed interpretation | Versioned |
| `build/` | Generated ROMs and source snapshots | Local and ignored; source-matched archives are needed for replay |

For example, the latest blitter acceptance is under
`captures/handoff-race-20261020/copper-start-acceptance/`; its short record is
`investigations/blit-start-copper.json` and interpretation is in
`docs/handoff-race-investigation-2026-10-20.md`. These local directories are not
published by a Git commit. Keep backups of needed archives; do not commit ROM
images, private hardware backups or control tokens. `archive` publishes reviewed
measurement packets and metadata to `references/`, not the whole run directory.

## Separate cache layers

1. **Build/command reuse:** opt-in manifest `cache`, explicit input globs and
   output files. The runner hashes inputs, argv, working directory, environment,
   launcher and Python entry script, then verifies output hashes. Declare all
   imported helpers, toolchain/configuration inputs and assets; undeclared
   dependencies cannot be detected automatically. Failed commands are not reused.
2. **Emulator replay:** opt-in `reuse_preflight`. The key binds frozen binary,
   config, ROM/source identity, duration, capture/decoder versions and explicit
   `replay_inputs`. Declare external configuration assets and helper dependencies.
   Packet hashes, metadata, descriptors, status and coverage are checked again.
   Comparison/report edits do not require another identical emulator replay.
3. **Derived evidence:** `evidence` hashes input summaries, reports and contracts,
   analyzer/comparator code, baseline case files when supplied, and output budget.
   Entries are atomically written and payload hashes checked. Corruption rebuilds
   this report cache; `--refresh` forces regeneration. Cached reports never grant
   permission to skip capture checks, hardware restoration or validation tiers.

Changing reference data, qualification, units or comparison rules requires a new
comparison, not a new hardware capture when the existing packet remains suitable.
Never reuse hardware measurements across different ROM hashes or configurations
by relabeling them. Hardware is repeated for stability, new tests or ambiguity.

Do not delete historical runs merely because a cache exists. Clear disposable
cache entries only when idle; retain references and investigation provenance.
