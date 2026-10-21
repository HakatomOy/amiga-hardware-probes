# Controlled collision input investigation

## Confirmed evidence

References: `references/controlled-pointer-collision-v1/run1` and `run2`.
ROM SHA256 `baa48e2d374de0f478a0c5b196e84a989f448710f1f8ebebc1f27804ea1e17dd`.
PAL A500 stock68000,512KiB chip/512KiB slow; silicon revisions unconfirmed.
Both OneROM restorations verified.960 cases: identical ROM/RAM observers,
three pointer targets, CPU/Copper writers and main/planes-off/zero/positive
controls. The common-ROM input precedes COPEN/COPJMP; all later beam brackets
are outputs. No trace alignment or weakened original acceptance contract.

Every input is on line42, before the scheduled line44 event. Comparison:
132 matches,666 mismatches,162 unstable,0 excluded/missing/invalid.480 input
cohorts repeat independently, but81 have conflicting downstream observations.
80 conflicting cohorts execute from RAM and1 from ROM; all use active bitplane
DMA. All72 planes-off cases match. Raw packets are not identical. These are
versioned diagnostic captures, **not a trustworthy baseline for fitting a fix**.

## Rejected interpretation and next experiment

A common pre-enable input removes missing phase coverage but does not uniquely
constrain later timing. It does not establish a collision-value bug. Leading
hypothesis: initial CPU/bitplane arbitration differs before the old line44
polling marker. Competitor: the initial sequence agrees and a later polling or
display-fetch phase causes the difference. Use a smaller ROM/RAM matrix with
planes-off/active/positive controls and raw observations immediately before
COPEN and after COPJMP. Preserve the common input as the qualifier and measure
both new brackets. Early divergence implicates startup; agreement until later
implicates ongoing DMA/polling. Conflicting repeats require further probe
refinement, not another emulator patch.

Builder: `build_controlled_collision_rom.py`; exact built sources are in
`build/controlled-pointer-collision-v3/source_snapshot`. Archived entry builder:
`experiments/probe-sources/controlled-pointer-collision-v1.py`. Workflow:
`experiments/workflows/controlled-pointer-collision.json`. Full traces and logs:
`captures/copper-phase-20261021/controlled-pointer-hardware-v1`.

Initial preflight caught an A3 descriptor-pointer clobber before any hardware
run. The corrected probe preserves A3 and completes all960 records. Regression
tests cover descriptor pairing, preserved A3 and input-before-enable structure.
