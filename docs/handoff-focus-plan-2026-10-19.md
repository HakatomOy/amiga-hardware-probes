# Blitter handoff: measured, unresolved

Stage3; accepted Copperline baseline `4038ec64`. No blitter patch accepted.

## Confirmed facts

Kind59 AD one-word/four-plane probe:128 valid,all exact launch conditions qualify.
Two independent hardware runs agree on all records. All64 no-start controls
match; all64 blits have handoff timing early, usually2CCK; final data correct.
Kind60 ROM/chip read discriminator:256 valid;128 no-start controls match,128 blits
differ. Busy-sample counts agree and both read paths are early: the immediate
destination read and a missing poll iteration are rejected causes for this family.

Six-plane/Copper neighbors512: two independent hardware runs agree completely.
Baseline248 matches264 differences. Six-plane-only no-start128/128 match;
six-plane+Copper no-start96/128 differ. Some real blits also expose BZERO/poll-count
differences. Keep these families separate.

## Rejected hypothesis

Trace shows terminal E advancing under bitplane DMA. Making E BusFree repairs
all focused64 and read-control128 blit mismatches, but creates16 complete-case
regressions and48 cases with field regressions among neighbors. Reject the global
rule. Source restored clean to4038ec64. Rejected patch:
`experiments/rejected-e-busfree-20261019.patch`; binary/results under
`captures/handoff-focus-20261019/e-busfree-v1/`. Do not reuse as accepted behavior.

## Retrieval and validation

References: `handoff-focus-v1-run{1,2}`, `handoff-read-v1-run1`,
`handoff-read-neighbor-v1-run{1,2}`; hashes/configuration/restoration in manifests.
Build archives have matching names under `build/`. Original baseline executable:
`captures/cpu-irq-20261019/candidate2-binary/emulator.exe`.
`python compare_handoff_focus.py --hardware REF --candidate CAPTURE --baseline OLD
--out REPORT` groups patterns and reports field repairs/regressions with case IDs.
Exact prelaunch brackets only; no time shifts. Wrapped beam registers remain
encoded pairs.208 probe tests include value/removal/shift/conflict/cross-line and
new-field-regression checks. Observational trace is byte-identical to untraced
packet; small excerpt `captures/handoff-focus-20261019/trace-v1/first-case.txt`.

## Next question

Stage4: isolate CPU grants, operand/prefetch and Copper timing using no-DMA,
four/six-plane and Copper controls. No-start Copper evidence constrains CPU-side
behavior independently of blitter sequencing. Relevant source:
`src/bus/dma_slots.rs`, `src/bus.rs`, `src/chipset/blitter.rs` in Copperline;
`build_handoff_focus_rom.py`, `compare_handoff_focus.py` here.
[History](handoff-focus-history-2026-10-19.md) retains detailed hypotheses/results.
