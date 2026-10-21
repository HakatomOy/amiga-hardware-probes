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

## Next discriminating question

Kind97 repeats are byte-identical,96 independent cohorts, both restores verified,
no exclusions or conflicts. Off/WAIT controls match. Padding three NOOPs before
the final WAIT removes some3/4-CCK-early RAM reads; wrap cases remain2-CCK-late.
The leading hypothesis is two internal WAIT-tail RGA phases, including the final
WAIT that currently stops at decode. Competing explanation: CPU grant/release
recognition causes the early reads. Screen `wait-tail-resources-v1` isolates
WAIT-tail ownership and cold first-word spacing against kinds95/96/97; unchanged
mode must reproduce its parent packet. A repair without new fields supports the
resource model; lost controls reject it. This screen is not broad acceptance.
Do not add another universal delay. Reuse existing captures for all unchanged tests.

Builders: `build_copper_{restart_access,restart_fetch,marker_copy,enable_boundary}_rom.py`;
exact snapshots: `experiments/probe-sources/`. Strict workflows and explicit
counterfactual recipes: `experiments/workflows/`, `experiments/screens/`.
Emulator sources: `src/bus{.rs,/dma_slots.rs,/custom_regs.rs}`, `src/chipset/copper.rs`.
Post-screen clean core3676 passed,37 ignored,559 window tests filtered; fmt and
341 probe-tool tests passed. Broader acceptance remains blocked; no emulator
commit or speed claim. Main record: [Init investigation](init-resource-investigation-2026-10-21.md).
