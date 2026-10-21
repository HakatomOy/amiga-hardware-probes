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

## WAIT-tail counterfactual rejected

`wait-tail-screen-v1`: mode0 reproduces the parent kind95 packet exactly.
Two internal RGA tail slots plus cold spacing reaches184/192 kind96 and180/192
kind97, but regresses4 and2 previously measured fields respectively. Kind95
falls to332/384, with32 new settling-beam fields (typically4CCK later). Therefore
universally reserving WAIT tails is not an acceptable explanation. Cold-only
control reproduces380/384,168/192,168/192 across kinds95/96/97 with no new fields.

Next revised hypothesis: missing odd phase across short-line E2-to0. Advance no
word on that immediate next even clock; a warm request pipe can still reserve a
dummy slot, while the cold first word has not established that reservation.
This targets the early release only at wrap, leaving normal-line WAIT tails
free. Local WinUAE `custom.cpp:generate_copper` independently separates odd-phase
request progression from even-phase allocation and handles even-to-even dummy
requests; it is corroboration, not HW proof. A separate strictly-next-odd COPEN
sample tests remaining clock0-granted enables. Earlier odd-latch experiment
consumed the same odd clock as the CPU word-End write, not the following one.
Recipe/patch: `wrap-phase-resources-v1`, modes0/2/4/16/20, unchanged strict gates.

## Wrap/gate screen and targeted profile

`wrap-phase-screen-v1`: baseline packet byte-identical. Mode4 all-word spacing
with a warm dummy reservation gives380/384,168/192,178/192 for kinds95/96/97,
zero new fields. Mode16 strictly-next-odd COPEN fixes384/384 kind95 but regresses
8 kind96 and4 kind97 fields. Mode20 combined regresses20 kind95 fields. No
universal enable delay or gap rule accepted.

A packet-qualified single-case profiler now captures full bus slots using a
common observer entry once per trial, skip-count plus exact descriptor check,
and full packet equality afterward. `enable-rom-case-profile-v3` matches the
parent byte-for-byte. Case96,3,1550,0,0,0: COPEN grantC4; IR1C8,IR2CC,WAIT1D0,
WAIT2D4; CPU NOOPD8,VHPOSRDC yields42E1 versus hardware42E2. Slots show bitplanes
throughD7. This rejects reasoning that assumed undocumented fetch locations.
The first register-conditioned profile failed because the control parser treats
string A4 as a hexadecimal number before recognizing a register; the tool uses
verified hit-count selection instead. No emulator debugger patch was made.

Next source-backed hypothesis: `start_pending_copper_frame_if_due` and
`Copper::frame_start` preload a running PC while DMA is disabled. A real pending
address reload on enable could change the whole first-fetch/stop sequence,
explaining short probe and long restart data together. Screen modes32 pending
restart,96 also full restart phase spacing,98 also cold spacing against0; recipe
and exact patch `frame-restart-resources-v1`. DMA-enabled frame starts retain
existing calibration; dormant LC writes preserve the pending live-address load.

## Pending-frame restart screen

Mode32 pending disabled-frame restart reaches376/384 kind95 and184/192 each
kind96/97. It repairs all earlier families except8 RAM cases at phase0pad3 or
phase1pad2, consistently2CCK late;8/4 new settling fields are confined to those
remaining cases. Mode96 with both restart transitions spaced repairs those8,
but introduces earlier RAM cases2CCK early and loses ROM restart controls,
reaching360/384,176/192,176/192. No model accepted.

The transition screen now isolates First-to-reload spacing(bit64) from reload-to-
first-word spacing(bit128). Mode96 is pending-frame plus First spacing only;
mode224 retains both and must reproduce previous96 as a control. Leading
hypothesis: the first bus-free phase needs a full phase edge, while the address
reload primes its following word and retains the existing even-to-even wrap.
This is tested against the exact saved packets rather than inferred row timing.

## Transition membership and packet-qualified boundary traces

First-only spacing mode96 has the same totals376/384,184/192,184/192 as mode32,
but DIFFERENT cases: it repairs the late phase0pad3/phase1pad2 group and makes
phase0pad2/phase1pad1 twoCCK early. Equal counts are not an unchanged result.
Mode224 both-transitions is byte-for-byte checked against prior mode96 below.
Selective traces `pending-ram-pad{1,2,3}-profile-v1` and
`first-spacing-pad3-profile-v1` reproduce their respective packets exactly.

Mode32 pad2: COPEN grantDE, CPU first prefetchE0, address reload0, words2/4/6/8,
CPU second prefetch7, read returns4314 (HW4314). Pad3: COPEN grantE0, address
reload0, same words2/4/6/8, CPU FIRST prefetch7, read4316 (HW4314).
Mode96 pad3 frees0, reloads2, words4/6/8/A, CPU prefetch0 then7/9; read4314.
But pad2 also gains0 for its SECOND prefetch, incorrectly returning4312.

Revised discriminator: COPEN in pad2 was active through an odd sampling phase
before the first restart phase; pad3 was latched at that phase. Retain a dummy
RGA reservation in the wrap gap only for a mature request, without advancing
address reload there. Mode104 adds that reservation to96 using the next-odd gate
clock as an explicit phase boundary, not a case-ID/beam special case. Mode32
and96 are counterfactual controls. No universal WAIT or enable delay is enabled.
The batch tool now reports representative case IDs so moved families are visible
before any detailed trace is requested.

## Frame-origin discriminator

`restart-origin-diagnostic-v1`: unchanged0 and pending-frame32 preserve busy384
and handoff512. First-gap96 and mature-reserved104 each lose64 busy and32 handoff.
`frame-origin-validation-v1` mode360 scopes104 to internal vertical-blank origin,
clears it on CPU COPJMP, and restores all896 controls while preserving768 startup
matches. Baseline packet is byte-identical; generic104 reproduces its failure.
No alignment, field/floor/exclusion change. Three production unit tests encode
live-LC reload, cold/mature short-line gap and CPU-strobe cancellation.

`collision-observation-diagnostic-v1` keeps launch qualification and measures
later brackets instead: pointer242/480 match,238 excluded and no timing mismatch;
Copper396 match,118 bracket mismatches,278 excluded,8 conflicting HW cohorts.
Diagnostic contracts do not replace original acceptance gates. The original
launch marker follows DMA enable/restart and cannot uniquely identify input.

Broad mode104 screen completed most comparisons but was invalid overall: CIA
aperture/clear manifests had empty references. These are harness failures, not
CIA mismatches. Existing references cia-request-aperture-v2 and clear-v2 run1/2
are restored in manifests; frozen mode360 reruns the checks without changing
comparison fields, baseline or thresholds. Full artifacts remain file-backed.

## Completed frame-origin regression screen

Frozen360:26/28 existing contracts pass,23830 total cases. Only original pointer
and Copper collision qualification contracts fail:242/480 and396/800 qualified,
238/404 excluded; no qualified value mismatch. CIA aperture880/1280 and clear
558/640 preserve known400/82 mismatches with zero new fields or qualifications.
Bus-onset preserves1 known mismatch, CPU-DMA16; other exclusions stay unchanged.
Supplemental pointer phase references improve qualification to270/480,210excluded,
zero value mismatch/unstable/invalid; still above original199 exclusion budget.
This is diagnostic evidence, not changed acceptance. Source cleanup and three
unit tests are compiling; production replay and final acceptance remain pending.
