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

## Next discriminating screen

Mode2 diagnostic trace `captures/copper-phase-20261020/cold-read-trace-v1`
reproduces its packet byte-for-byte (SHA25622c122c14534e32071de05da701f5e7dde9ed8663daf4921d962132a6b2cec06).
Remaining case95,3,5646,1,3,0: COPEN grant43:0, latch1, return2; first Copper
read2 denies CPU, followed by refresh3, Copper4,refresh5,Copper6, CPU7.
Screen v3 distinguishes a two-CCK COPEN request lead-in from cold transfer
spacing. Its bit1 now means lead-in, bit2 retains spacing; archived v2 remains
unchanged. Baseline0, lead-in1 and combined3 are compared; spacing2 was already
measured. All strict acceptance rules remain active. This is a hardware-derived
request-pipeline hypothesis, not permission to special-case the failing case.

## Screen v3 rejection and live experiment

COPEN two-clock lead-in alone matches376/384 (12 repairs, no new measured
fields); combined with cold spacing matches360/384 and regresses20 fields.
All ROM768 controls pass; collision counts remain unchanged. Reject both
universal timing rules. Copperline experimental selector and its extra state
were removed; archived patches retain exact counterfactual source. Base
transfer/reload/Init changes remain uncommitted pending acceptance.

Kind96 (`build_copper_enable_boundary_rom.py`, workflow `copper-enable-boundary`)
is a smaller discriminator:192 cases, inherited versus explicit disabled-restart
seed, ROM/RAM venues, off/WAIT/short active stream,phase0/1,pad0..3,repeated.
The measured second COPJMP is replaced with an inert NOOP, so initial stream
ownership and early COPER are observed before any restart can erase evidence.
Input remains in common ROM; active stream starts with INTREQ then parks.
Emulator preflight passed all six off/WAIT/active entry/settled activity checks.
Two live A500 repeats started under the normal restoration-verified workflow:
`captures/copper-phase-20261020/enable-boundary-hardware-v2`.
Hardware outcomes must pass controls/repeatability before interpretation.

## Held-out enable screen

Kind96 baseline152/192; cold spacing168/192 without new fields; lead-in156/192 with16 new fields; combined156/192 with16 new fields. All original qualification limits retained.

## Kind97 paired-tail A500 evidence

`references/copper-enable-tail-v1`:192 qualified cases,96 independent cohorts,
two byte-identical hardware packets; no invalid/missing/excluded/unstable/conflict,
both restorations verified. Base152match40difference. Off/WAIT controls agree.
Short versus three-NOOP tails retain identical first COPER and observer banks.
ROM phase0pad0 first sample stays42E2; padded post-sample beams shift with the tail.
RAM phase0pad0 short HW4311/base430D; padded HW4312/base4312.
RAM phase0pad1 short HW4314/base4311; padded HW4314/base4314.
RAM phase0pad2 short HW4314/base4315; padded HW4314/base4316.
Thus early release and late startup form separate families; a universal delay
cannot repair both. Exact compact cohort table can be regenerated from the
versioned packets and `enable-tail-hardware-v1/cases.json`.

Next counterfactual: WAIT-tail RGA ownership on both internal phases, including
final WAIT (base stops immediately at decode), independently of cold first-word
spacing. Recipe/patch `wait-tail-resources-v1`. Baseline must reproduce frozen
kind95 packet exactly. No emulator patch accepted before held-out controls.
