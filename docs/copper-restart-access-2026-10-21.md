# Restart access and collision qualification

## Acceptance blocker

The transfer/reload/RGA candidate matches9462 focused cases, but collision
qualification loses pointer22 and Copper28 cases. Original limits199/362 remain
unchanged. No qualified collision value differs; the emulator is not accepted.
Extra unchanged pointer captures in `references/pointer-collision-phase-coverage-v1`
expand exact coverage to292/480, with zero conflicts. This does not waive timing
qualification or justify a CPU exception.

## Discriminating hardware evidence

- Kind92 (`references/copper-restart-access-v1`): all768 emulator inputs excluded
  because the first marker is4 CCK later, even before Copper is enabled. This
  is an unqualified diagnostic, not proof of a MOVEA or reload error.
- Kind93 (`references/copper-restart-prefix-v1`):768/768 match, byte-identical
  hardware repeats,384 independent cohorts. Input precedes the unknown prefix;
  immediate MOVEA and register+twoNOPs, RGA reads/writes and both gate orders agree.
- Kind94 (`references/copper-marker-copy-v1`):96/96 match. Memory-destination
  VHPOSR marker and register+padding control agree inside the measured window.
- Kind95 (`references/copper-restart-fetch-v1`):384 qualified, no invalid,
  missing, excluded, unstable or conflicting cases;364 match,20 differ.
  Identical banks execute from ROM or30000 chip RAM, with a common ROM input
  before venue entry. Only RAM+gate-first+active cases are2 CCK late after
  the strobe pair; every prefix-complete observation matches.

The first three tests reject generic MOVEA/marker corrections and a blanket
read/write reload exception. Kind95 isolates chip-memory fetch arbitration.
Exact builders are archived in `experiments/probe-sources/`; manifests are
`experiments/workflows/copper-restart-{prefix,fetch}.json` and `copper-marker-copy.json`.

## Current hypothesis and rejected patches

A same-clock CPU-strobe barrier repairs none of the20 differences and regresses
8 fetch controls plus16 ROM controls. A blanket pre-refresh read exemption
repairs8 but regresses12 other fetch cases. Both were rejected.
Trace `captures/copper-phase-20261020/restart-fetch-trace-v2` is byte-identical
to its untraced packet. Case95,3,5646,0,2,0 requests RAM word30416 at42:E0,
waits through E1/refresh and receives43:07, before COPJMP at43:0D.
E0 is a Copper lockout reservation, not evidence of a pointer reload or RAM read.

Screen v1 (`captures/copper-phase-20261020/resource-screen-v1`) confirmed its
baseline packet byte-identical. Tracking an actual pre-lockout word repaired8
of20 fetch cases without new measured-field regressions; ROM768 and collision
counts were preserved. An odd-clock COPEN latch had no effect. Neither passed.

Next uncertainty: bad cohorts start their first Copper word atE2; the current
model immediately reads the second at0 across a227-clock line wrap. Healthy
cohorts already fetched beforeE2. Screen v2 tests a full two-CCK spacing only
for the first cold memory transfer, retaining already-primed wrap behavior.
The competing explanation is the preceding actual-word read guard. Four modes
isolate each and their combination against the same strict fetch, ROM and
original collision contracts; no new hardware capture is needed. A result is
accepted only after all qualification gates and broader regressions pass.

Source: Copperline `src/bus.rs`, `src/bus/dma_slots.rs`,
`src/bus/custom_regs.rs`. The selector is experimental and must be removed
before final validation/commit. Recipes and source snapshots are in
`experiments/screens/` and `experiments/patches/`.
Main record: [Init investigation](init-resource-investigation-2026-10-21.md).

## Screen v2 result

Baseline packet is byte-identical. Cold-first-word spacing alone repairs16/20
fetch differences (380/384 match, zero new fields); remaining4 are phase1,
pad3,RAM+gate-first+active, both RGA directions and repeats. The actual-word
guard alone repairs8; combining it with spacing leaves12. Every mode preserves
ROM768; none improves original collision qualification (pointer259/480,
Copper411/800). No mode is accepted. Follow-up trace tests the remaining clock0
COPEN-write boundary, verifying the diagnostic packet against mode2 first.
Tool regression suite:337 passed. All captures remain restored; no fresh HW
run was needed for these emulator screens.
