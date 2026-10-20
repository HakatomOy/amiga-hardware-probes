# Blitter handoff: polling cadence and single-read controls

Priority4 follows accepted serial, CPU/Copper refresh and CIA output fixes.
No blitter patch is accepted from this investigation.

## Cadence experiment

Kind67 independently varies0..3 ROM NOPs before every BBUSY sample, retaining
launch-phase/pad, normal/nasty, no-start and ROM/chip-read controls. Two restored
A500 runs agree on all1280 raw records and all640 qualified cohorts overlap
independently. All1280 emulator rows qualify:872 match,408 differ.
References `handoff-stride-v1/run{1,2}`, ROM40e17706, source9a3ad7de.

Four-plane real blits: all64 zero-NOP cases are2CCK early; all192 cases with
one to three NOPs match. Four-plane no-start controls256/256 match. No-DMA
controls256/256 match. Six-plane/Copper families remain separate, including
no-start differences: do not credit their timing errors to blitter completion.
Full grouped results: `captures/handoff-stride-20261019/baseline-v1/cadence-summary.json`.

This rejects a polling-cadence-independent observed offset. It does not rule out
an early terminal event hidden by later polling. The previously rejected global
E/BusFree rule remains rejected because of neighboring regressions.

## Single-read discriminator

Kind70 replaces the outcome-dependent loop with one DMACONR read at0..7 fixed
ROM NOP delays, bracketed by beam reads. No BLTCON0 handoff write occurs. Both
normal/nasty, no-DMA/four-plane and no-start controls are included. Two hardware
runs restore successfully. References `handoff-sample-v2/run{1,2}`;
ROMd146eb2a, source9617a839. Buildv1 overflowed a reserved ROM boundary and was
rejected before hardware; v2 fits eight512-byte observer blocks belowFFC000.

At identical launches:1024 qualify,928 match,96 differ. Differences are solely
the pre-status, post-status and post-request beam readings, consistently2CCK
early for real four-plane blits at delays0..2. No-start controls and delays3..7
match. The first divergent observation precedes the first status sample.

The separate, predeclared read-bracket comparison reuses the same packets:
928 matches,zero register/data differences,96 excluded timing cohorts. The
launch-only report retains those96 differences. No trace alignment or outcome
selection hides them. All emulator first-status samples are already clear:
this test constrains read/grant timing but cannot independently locate the
electrical BBUSY transition. Require active/clear preflight coverage for a
future event-boundary experiment; a longer blit or an earlier observer may help.

## Retrieval and next question

Plans: `experiments/workflows/handoff-{stride,sample,sample-source}.json`.
Reports: `captures/handoff-stride-20261019/{baseline-v1,sample-baseline-v2,source-scope-v2}`.
Representative case: `70,3,2,0,0,0`, retrieved with `tools/experiment.py detail`.
File-backed CPU/blitter diagnostics live in `sample-trace`; verify
`trace-verification.json` confirms a byte-identical packet. The bounded excerpt
`experiments/traces/handoff-sample-first-case-20261020.txt` maps the33rd real blit
to case70,3,2,0,0,0.

Candidate trace at the first four-plane launch: CPU beam access overlaps the
first D pipeline bubble; E runs under bitplane ownership and F follows. This
is emulator scheduling evidence, not a measured hardware microcycle. Simply
reserving D or delaying E has competing arbitration implications; do not patch
one from this trace alone. Next: distinguish terminal memory-port release from
CPU grant/sample phase with an earlier active/clear observer and fixed launch
controls. Relevant Copperline files: `src/bus/dma_slots.rs`, `src/bus.rs`,
`src/chipset/blitter.rs`.
