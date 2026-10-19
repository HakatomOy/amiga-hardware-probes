# CIA serial output buffering

Stage 5 starts from Copperline4038ec64. Hypothesis: active SDR writes fill a
pending byte without restarting the current transfer. Competitor: restart or
an unbounded queue. Kind63 drains previous serial state, masks CPU/CIA IRQs,
then tests single bytes, active writes at observed underflows4 and4/8, and
an idle write at20. Snapshot/ack at18, a sweep24..48, and56 distinguishes
first completion, pending completion and a possible third completion.

Two independent A500 runs are byte-identical across all320 records. Both live
ROM restorations and reset release verified. References
`serial-buffer-v1-run{1,2}` contain source/ROM/configuration/result identities;
source015b086d, ROM00875ce2, result484d0f3c. Immutable local source/build:
`build/serial-buffer-v1`; captures/logs: `captures/serial-buffer-20261019`.

All cases have identical hardware/emulator write and observation brackets.
Units are observed Timer-A underflows through Timer-B cascade (one edge
delayed), not CPU cycles. No shifts or inferred timestamps. Compare SP bit8;
unrelated Timer-A flags remain available in raw records.

Baseline:160 matches (single/idle controls),160 mismatches (active writes).
Hardware preserves the first completion and produces exactly one additional
completion for either one or two active writes. This rejects restart and a
two-entry pending queue. No third completion occurs after a late second ack.
These observations constrain completion count/timing, not serial payload bits
or which overwritten pending payload appears on SP. No electrical IRQ latency
is inferred from this masked-flag probe.

Tools: `build_serial_buffer_rom.py`, `src/rom/cia_serial_buffer_kernel.i`,
`compare_serial_buffer.py`, `tests/test_serial_buffer.py`. Comparison groups
completion patterns, excludes unequal underflow brackets and unstable cohorts,
reports invalid/missing cases. Retrieve a full case with
`--case 63,0,1,0,32,0`; full results and reports stay in files. Mutation tests
change a flag, remove a record, shift a bracket and introduce conflicting repeats.

Candidate in `Copperline/src/chipset/cia.rs`: one pending SDR byte; active writes
preserve shift progress; completion promotes pending state; direction change
clears both. Old snapshots default to no pending byte. Existing single-byte
sixteen-underflow completion and delayed IRQ-pin handling must remain intact.

Next unresolved question: transmitted payload/overwrite behavior and writes at
the exact byte boundary require pin-level evidence; do not infer them from ICR.

## Candidate and boundary control

The pending-byte candidate repairs147 complete cases, leaves13 differences near
the second completion at observed underflow31, and preserves all160 controls.
No complete-case regression. Do not silently accept the13 residuals as matches.

Discriminating follow-up: distinguish a queued-handoff delay from a first-byte
flag boundary. `--first-boundary` acknowledges at12 and samples single-byte
completion at14..18 (40 cases). Sourcee3e4746f, ROM82c5a49a. Hardware sees SP in
all8 underflow15 samples; Copperline only2.34 matches,6 differences; accepted
baseline and candidate packets are byte-identical. Thus the first boundary also
differs, rejecting a queue-only explanation. Hardware at14 is clear and16..18
set in run1. The independent repeat agrees on39/40 records; one CIA-B latch15
underflow14 SP observation changes at identical brackets. Pooling excludes
that cohort (two candidate repeats):32 matches,6 differences,2 unstable.
All eight underflow15 observations agree. References `serial-boundary-v1-run{1,2}`
retain both packets and the explicit instability annotation. Do not convert these delayed-cascade observation brackets directly into
electrical byte-completion edges. Keep this pre-existing timing family open.
Full evidence under `a500-boundary-v1-run{1,2}`, `boundary-comparison-v1.json`.

Validation:217 probe tests pass, including comparator mutations. Copperline3635
core/network tests pass (37 ignored,548 window tests excluded), strict Clippy
and formatting pass. Cargo stdout/stderr and command exit status are retained
under the capture root. MyST is not installed, so no documentation build ran.
The first CPU/DMA replay at30 emulated seconds was incomplete and rejected;
`cpu-dma-neighbor/invalid.json` marks it unusable, with the standard-duration
replacement in `cpu-dma-neighbor-v2`.

Accepted Copperline commit `a2299b00`. All11 earlier regression packets are byte-identical
to Copperline4038ec64, including2272-case CIA output, IRQ stages, bus, blitter and
4608-case BZERO controls. The1920-case CPU/DMA neighbor is also byte-identical.
`regression/summary.json`, `regression-packet-equivalence.json` and
`candidate1-delta.json` retain summaries. Candidate binary is immutable under
`candidate1-binary/emulator.exe`. No timing-boundary patch was accepted.
