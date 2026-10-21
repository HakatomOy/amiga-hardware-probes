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

## Startup bracket experiment

`references/collision-startup-v1/{run1,run2}`:96 cases, ROM/RAM, pointer target1,
Copper writer, main/planes-off/positive controls, padding0/1/2/6, four repeats.
ROM SHA256 `b20767df0e05668db07816f3cd3bcb55b57c6d7ec3fd0c5fa79791facb192afa`.
All inputs precede enable on line42. Pre-COPEN beam matches96/96. Immediate
post-COPJMP:40 match,24 stable mismatches,32 unstable. Stable mismatches are ROM
observations two raw colour clocks early in Copperline. All96 early, second and
settled CLXDAT values match. Whole-case strict result:32 matches,32 mismatches,
32 unstable; zero excluded/missing/invalid. No acceptance rule was changed.

The first capture kept the probe loaded. The final capture restored the original
session ROM once, with exact readback and reset release verified. References
identify restoration scope as the session. Prior960-case instability also occurs
within each capture (81/80 cohorts); it was not caused solely by restoring the
normal ROM between captures.

Packet-qualified profiles `collision-startup-{active,off}-profile-v1` reproduce
the same parent packet byte-for-byte. For padding0, both have pre-enable4260,
COPEN grant61 and COPJMP69. Planes-off post-strobe4274 matches HW. Active Copperline
reads4276 versus HW4278; its granted read is71, BPL2 uses6F, BPL1 uses73. VHPOSR
includes the existing3CCK lookahead; these raw register values are not electrical
bus edges. Startup already diverges before the line44 polling loop, so later
collision-latch timing alone cannot explain this family. The observed sequence
includes enable, restart and the following read; it does not uniquely identify
which grant is wrong. No emulator change is justified yet.

Next discriminator: preserve the same pre-enable input and isolate the explicit
COPJMP operation from initial BPL/Copper enable, using fixed opcode controls
selected before alignment. Keep planes-off and ROM controls. If the difference
survives an inert strobe, investigate enable/read arbitration; if only COPJMP
exposes it, investigate restart ownership. Unstable RAM observations still need
an additional phase/state control rather than a fitted delay.

Reusable field-level diagnostic (never acceptance):
`python -m tools.field_stability captures/copper-phase-20261021/collision-startup-hardware-v1 --fields pre_COPEN,post_COPJMP,collision`.
Build entry: `build_collision_startup_rom.py`; workflow:
`experiments/workflows/collision-startup.json`. Tool suite352 passed.
