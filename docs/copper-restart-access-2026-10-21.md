# Copper restart and initial-enable investigation

## Confirmed evidence

The transfer/reload/Init base matches9462 focused A500 cases. It remains
unaccepted: original collision qualification falls to pointer259/480 and
Copper411/800; limits199/362 excluded remain unchanged. No qualified collision
value differs. Extra pointer phase captures expand coverage but do not waive gates.

Hardware references (two restored runs each):

| Capture | Result against base | What it establishes |
|---|---|---|
| `copper-restart-access-v1` (kind92) | All768 inputs excluded | Unqualified marker design; no MOVEA conclusion |
| `copper-restart-prefix-v1` (kind93) | 768/768 | Prefix, both gate orders, RGA read/write controls agree |
| `copper-marker-copy-v1` (kind94) | 96/96 | No generic memory-marker correction justified |
| `copper-restart-fetch-v1` (kind95) | 364/384 | RAM+gate-first+active family; post-access2CCK late |
| `copper-enable-boundary-v1` (kind96) | 152/192 | Differences persist without a second measured COPJMP |
| `copper-enable-tail-v1` (kind97) | 152/192 | Padding separates early release from late wrap cases |

Kind96 has96 independent repeated cohorts, byte-identical packets and zero
invalid/missing/excluded/unstable/conflicting cases. ROM restoration was verified
twice. Off/WAIT controls all match. Active RAM32 and ROM8 differ. Inherited and
explicit disabled-restart pairs agree in every measured hardware field; this
weakens stale-state explanations but does not electrically identify internal state.

## Rejected patches and retained uncertainty

Same-clock strobe barriers and blanket pre-refresh read exemptions regress
controls. E0 is a lockout reservation, not proof of a pointer reload or RAM read.
A cold first-word two-CCK spacing rule repairs16 kind95 cases and16 kind96 cases
without new measured fields, but leaves4 and24 respectively. A universal COPEN
request delay introduces16 new kind96 fields; combining delay and spacing also
regresses. No candidate is accepted. Temporary selectors, saved experimental
state and the obsolete read-exemption test were removed from Copperline.

Trace packets reproduce their untraced parents exactly:
`restart-fetch-trace-v2`, `cold-read-trace-v1`, `enable-boundary-trace-v1`
under `captures/copper-phase-20261020/`. Detailed chronology, case IDs and
screen matrices: [history](copper-restart-access-history-2026-10-21.md).

## Current discriminator and candidate

The internal-frame-origin candidate (screen mode360) matches all1664 cases:
restart-fetch384, initial-enable192, paired-tail192, busy-onset384 and handoff512.
Zero measured-field regressions, qualification changes, exclusions or invalid
captures. Generic spacing(mode104) matches startup768 but regresses64 busy-onset
and32 handoff controls. Pending-frame alone(mode32) preserves both old controls.
This distinguishes internal vertical-blank restart from explicit CPU COPJMP.

DMA-off vertical blank retains a pending live-LC address reload. Its first phase
must be separated from reload by two CCK even across a short-line wrap. The gap
retains a reservation only when COPEN has passed the next odd sampling phase.
CPU COPJMP cancels internal pending state and retains its validated cadence.
Enabled-DMA frame-start calibration stays unchanged. This is a behavioral model,
not an electrical identification of Agnus internals.

Frozen screen: `captures/copper-phase-20261021/frame-origin-validation-v1`;
recipe/source snapshot: `experiments/screens/frame-origin-validation-v1.json`,
`experiments/patches/frame-origin-validation-v1.patch`. Broader screen:
`frame-origin-regression-v1`. Clean production source has no experiment selector;
core tests are in progress. No emulator commit or final acceptance yet.
Broad screen:26/28 contracts passed across23830 cases; only original collision
qualification contracts fail. CIA aperture/clear preserve400/82 known mismatches
respectively with zero new fields; these are not all-HW-matching suites.

Original collision qualification gates remain unchanged and blocking. A separate
observation-timing diagnostic found pointer exclusions entirely due to missing
launch-phase coverage, and8 conflicting Copper HW cohorts at the same recorded
launch marker. The old marker follows COPEN/COPJMP and is not a clean input.
Supplemental saved pointer runs improve242 to270/480 qualified, with zero
value mismatches, but210 exclusions still exceed the original199 budget.
Do not waive these gates; resolve with better controlled evidence.

CIA aperture/clear regression manifests had empty reference lists; restored their
existing versioned two-run A500 references so they can actually run. Probe-tool
suite347 passed. No hardware run is active; all prior ROM restorations verified.

Main record: [Init investigation](init-resource-investigation-2026-10-21.md).
