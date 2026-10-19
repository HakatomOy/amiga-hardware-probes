# Four-plane handoff discriminator

Stage 3, after CPU IRQ acceptance. Leading hypothesis: extra DMA changes CPU
access arbitration, so the observed handoff timestamp differs even without a
blitter. Competitor: the blitter completion/sequencer handoff itself is early.

Use one AD, one-word family, normal and nasty priority, two launch phases,
eight NOP offsets, two repetitions. Pair a real BLTSIZE write with a no-start
write to the inert custom register, preserving the access sequence and active
four-plane display DMA. Select the register address before alignment, then use
the same indirect write instruction for both streams. Expected no-start memory
remains zero; no BLIT completion request. Both still read DMACONR, destination,
write BLTCON0 and record surrounding beams. A single pre-launch beam defines the
comparison condition; no automatic time shifts.

If no-start controls already differ, investigate CPU/chip-bus arbitration before
changing the blitter sequencer. If controls match and only starts differ, isolate
busy-clear/last-write ordering. Repeat the physical capture for stability; use
six-plane and Copper neighbors after understanding this four-plane family.
Keep detailed traces file-backed and inspect the first divergent bus access.

## First result

Baseline4038ec64. Kind59 v1:128 valid, all exact launch conditions qualify;
64 no-start controls match,64 real-blit cases differ. Handoff beam is consistently
two CCK early, both priorities. Final data all correct. Some later beam samples
straddle the horizontal/vertical register wrap; retain encoded values rather than
subtracting packed words. Independent repeat pending. Source3dce7f26, ROM SHA
starts eb3badf8. `build/handoff-focus-v1`, `captures/handoff-focus-20261019/`.

Next discriminator: retain the final BBUSY poll count, and compare the immediate
chip destination read with an equivalent ROM read. Equal poll counts with a
difference confined to the chip read would implicate handoff/arbitration rather
than a missing busy-poll iteration. Preserve the real destination final check.

## Poll/read discriminator

Both independent kind59 captures agree on all128 records. Kind60 read control:
256 valid, exact launch all qualify,128 no-start controls match,128 blit cases
are early. ROM and chip-read variants have the same timing pattern; all busy
sample counts agree. Therefore the immediate destination read and a missing
poll iteration are rejected explanations for this family. File-backed trace is
byte-identical to untraced packet; first-case excerpt is `trace-v1/first-case.txt`.
It shows E advancing under Bitplane at149, final D150, CPU DMACONR read152.

Candidate hypothesis: terminal E should require a bus-free clock; competitor:
CPU grant-phase handling near completion. Try E as BusFree, require focused,
six-plane/Copper and no-DMA controls before acceptance. Candidate is unaccepted
WIP in Copperline `src/chipset/blitter.rs`; immutable accepted baseline remains
4038ec64 and binary `captures/cpu-irq-20261019/candidate2-binary/emulator.exe`.

Six-plane/Copper baseline:512 valid,all qualify,248 matches264 differences.
Six-plane-only no-start128/128 match; six-plane+Copper no-start96/128 differ,
so the latter has an independent CPU/Copper access-timing family (stage4).
Six-plane real blits also expose busy-poll-count and BZERO differences; keep
those visible. Do not demand a blitter-only patch repair no-start Copper cases,
but require zero regressions in them. Neighbor source39dcb22d; SHA7bae564b.

## Rejected candidate and boundary

E as BusFree repairs all64 focused kind59 mismatches and all128 kind60 four-plane
mismatches, with zero regressions there. Six-plane/Copper:16 complete repairs but
16 complete regressions;40 cases have repaired fields,48 have regressed fields.
Therefore reject the global E rule. Patch saved as
`experiments/rejected-e-busfree-20261019.patch`; Copperline source restored clean
to4038ec64. Do not revive the candidate based only on its four-plane result.

The independent512-case neighbor hardware repeat agrees on every measured record;
both restorations pass. References `handoff-focus-v1-run{1,2}`,
`handoff-read-v1-run1`, `handoff-read-neighbor-v1-run{1,2}`. Sources and hashes are
in each manifest; detailed traces/reports stay under the capture root. Comparator
mutation, missing-record, shifted launch, cross-line grouping, conflict and field
regression checks pass (208 Python tests). Beam grouping computes small same-line
H deltas only; wrapped register observations remain encoded pairs, never shifted.

Stage3 is measured, not fixed. Next unresolved question (stage4): which CPU grant,
operand/prefetch or Copper access phase accounts for the no-start Copper family,
and does that mechanism also explain the blit handoff observations? Test controlled
CPU instruction/read streams under no DMA, four/six planes and Copper before any
further sequencer patch.
