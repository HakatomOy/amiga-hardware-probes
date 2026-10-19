# Experiment workflow validation

Implementation: `tools/experiment.py`; instructions: `AGENTS.md` and
`experiment-workflow.md`; runnable contract: `experiments/workflows/serial-buffer.json`.

The seven process improvements are represented by:

1. One manifest-driven build/preflight/reference-or-hardware/comparison/validation batch.
2. Explicit duration, case count, completion, descriptor, status, hash, unit and
   qualification checks before a capture can enter comparison.
3. Automatic repairs/regressions/unchanged differences/exclusions and pattern deltas;
   a strict record-preservation gate for neighboring packets.
4. File-backed logs and stage-completion events with a bounded final summary.
5. Ordered validation tiers, immutable executable/ROM/configuration snapshots,
   fingerprinted command caching and opt-in deterministic preflight reuse.
6. Required hypotheses, competitors, discriminating outcomes, evidence-backed
   decisions and a stop on repeated evidence without a revised hypothesis/test.
7. A maintained short investigation record and bounded restart export, with full
   traces and history retrieved selectively from files.

## Evidence

The real local run `captures/workflow-serial-20261019-v1` completed through the
neighbor tier against saved, versioned A500 measurements. It reproduced320 cases:
307 matches,13 known boundary differences,147 full repairs relative to the pre-fix
baseline, zero regressions, zero exclusions/invalid cases. CIA output, CIA IRQ and
IRQ-stage neighbors replayed successfully and their records were unchanged against
the accepted baseline. The recorded decision is preserve the remaining constraint,
not accept another emulator patch. The current investigation record points here.

Latest-source runs `captures/workflow-latest-20261019-v2` and `v3` reproduced the
same results; v2 performed preflight and v3 reused the verified immutable packet.
The separate temporary investigation record avoids replacing the full neighbor
validation record with a partial smoke run. A restart export is approximately3KB.

`tests/test_experiment.py` verifies changed values, removed records, shifted
qualification and trace events, conflicting references, source/provenance/incomplete
capture rejection, duration selection, ordered validation and early failure gates,
build-cache invalidation, binary-dependent replay reuse, original-error retention,
actual exit status, bounded timeout cleanup, explicit hardware selection,
independent repeats, restoration provenance, reference archiving and refusal of
partial/stale acceptance. Hardware integration uses injected fixtures in tests.

No new physical measurements or emulator code changes were needed for this tooling
work. Broad Copperline recompilation was intentionally avoided: executable inputs
did not change. All229 Python repository tests pass, including12 workflow tests. Full
command logs and machine-readable summaries remain under the capture directories.
