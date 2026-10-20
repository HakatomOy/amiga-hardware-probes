# Four priority accuracy candidates

Continue in order; preserve original unrelated kind51 working files.

1. **Fixed: CIA serial flag boundary.** Copperline`b487bae1`;1533 extended and369
   short qualified cases match, plus all older stable serial controls.3637 core
   tests, strict Clippy and format pass. See serial-phase investigation/record.
2. **Fixed: CPU/Copper refresh handoff.** Copperline`346f0585`;all960 focused
   hardware cases match,96 repairs,zero field/qualification regressions.1920
   CPU/DMA and bus/handoff neighbors preserve baseline evidence;3638 core tests,
   Clippy and format pass. See CPU operand investigation.
3. **Fixed output readback; request propagation remains open.** Copperline
   `b8a97ac6`:20 PB6 repairs plus independent request/control sweeps,2063 settled
   output checks and3639 core tests pass. Early Paula requests remain separate;
   whole-E screening leaves counterexamples. See CIA source investigation.
4. **Narrowed: blitter/CPU handoff window.** New1280-case cadence and1024-case
   single-read A500 batches isolate96 early beam observations before the first
   status sample.928 exact-read-time register/data cases match;96 timing cohorts
   remain unresolved. No blitter patch accepted. Next observer must sample both
   busy/clear states before choosing terminal or CPU phase changes. See
   `docs/handoff-stride-investigation-2026-10-19.md`.

Plans use `experiments/workflows/`, short records `investigations/`. Full logs,
traces and immutable ROM/source snapshots stay in ignored captures/build paths;
reviewed hardware packets/provenance are versioned in references. The source
fingerprint includes every staged ROM source, including pre-existing kind51
working files; use the saved source_snapshot for exact historical rebuilds.
A clean current build may have a different fingerprint and requires its own
matching reference, rather than relabeling an old capture.
