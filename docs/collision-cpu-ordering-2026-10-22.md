# Collision polling and DMA-enable ordering

## Measured uncertainty

The clean rebased branch reproduces the original 24 late-clear failures:
488/512 match. Entry424E is identical, but the clear bracket is443C instead
of A5004438. The loop polls VHPOSR, not CLXDAT: collision state cannot alter
its branch decision. No original acceptance threshold was relaxed.

## Discriminating controls

Kind107 pairs polling with fixed ROM NOP sequences, DMA on/off and DPF pairs.
The first register-source DMACON version adds a dispatcher jump:128/128 match.
Removing the jump still gives no stable differences, but one timing cohort
conflicts across repetitions (126 matches,2 unstable). The register-source
write is shorter than the original immediate write; neither experiment alone
reproduces the original instruction boundary.

The immediate-source version restores that boundary:96 cases,64 matches,
30 stable timing differences,2 unstable. Fixed and DMA-off paths agree.
Sixteen collision-value differences reproduce the original late-clear family.
Conflicting observations remain diagnostic; they are never counted as matches.

Kind108 sweeps16 polling exit thresholds4260..4420 across four launch phases,
DMA on/off and two repeats. Two independent A500 captures have no invalid,
excluded, missing or conflicting observations. Baseline208/256 match;48 differ.
Phases0/2 first differ at4260 by2CCK, while phases1/3 and all DMA-off controls
match. Phase2 later accumulates4CCK drift. Both the final polling value and
the following clear bracket differ, ruling out the clear access alone.

## Candidate and evidence

Hypothesis: classic Agnus samples BMAPEN assertion on an even CCK, at the
fetch-counter step boundary. The current odd-clock start reserves the wrong
partial-unit slots. Round only BMAPEN_SET effects in the classic DDF sequencer;
leave disable, comparator delays, CPU timing and wide-FMODE rules unchanged.
This is a behavioral hypothesis, not an electrical pin measurement.

Primary contract: `experiments/workflows/collision-cpu-enable-even.json`.
Require256/256 stable sweep cases, the original512/512 collision floor, gated
controls, old pointer/Copper and bus/CIA/serial neighbors, then core/Clippy/fmt.
Do not use the unstable immediate/register timing cohorts as acceptance evidence.

Versioned captures: `references/collision-cpu-{clear-dispatch,clear-register,
clear-immediate,poll}-v1/`. Each includes ROM/source hashes and hardware/capture
provenance. Exact historical clear builders are in `experiments/probe-sources/`;
current entry points are `build_collision_cpu_clear_rom.py` and
`build_collision_cpu_poll_rom.py`. Full runs: `captures/collision-cpu-20261022/`.
OneROM restoration was verified at the end of each completed live batch.

The packet-qualified original case profile is `original-case-profile` in that
directory. Retrieve bounded raw slots with `tools/profile_case_window.py`;
the original register trace is also packet-identical, but its full log is large.
Prefer one-case profiles over whole-run register logging.

## Counterfactual results and acceptance boundary

Even-step assertion repairs256/256 sweep cases and all512 original matrix
cases, including the24 residual failures. Gated1024, isolated-bit768 and
early-clear512 controls pass. The immediate diagnostic repairs30 stable cases
and76 fields with no regressions; its2 unstable cases remain unqualified.
Register controls retain126 stable matches/2 unstable; dispatch controls
retain128/128. These distinguish the sampling-phase model from a blanket delay.

Bus onset/completion/pressure, CIA aperture/clear and serial neighbors pass.
The old pointer/Copper collision contracts still block:273/480 and424/800
qualify with zero collision-value mismatches, but207/376 exclusions exceed
the unchanged199/362 budgets. Fresh unchanged-ROM hardware captures will test
whether these missing beam cohorts exist independently; all original evidence
and thresholds remain. This is not acceptance yet.

The expanded pointer evidence qualifies291/480 without value mismatches;
the expanded Copper evidence still qualifies424/800. Neither resolves all
qualification losses, so no further unchanged captures are justified.
The older96-case controlled startup matrix gains80 later timing-field
regressions against the exact pre-patch binary. The initial post-COPJMP
read is already early in that binary; comparisons to a historical prototype
must not attribute that existing difference to this patch.

Kind109 independently crosses initial COPEN with COPJMP versus an inert
COLOR00 write, four launch phases and four repeats, all ROM execution.
`references/dma-restart-boundary-v1` has40 matches,20 stable differences and
4 unstable samples; every finite-Copper witness passes. The packet is identical
before and after the late-enable correction. Inert writes also differ when
COPEN is enabled: COPJMP alone is not the cause. The isolated Init prototype
improves52 matches but retains8 stable differences and4 unstable samples.

Two-plane ownership repeats every four CCK, so the polling sweep cannot
distinguish absolute fetch phases four clocks apart. A new counterfactual
compares tail-based even enable against transfer-based even enable, retaining
an exact baseline variant. Recipe: `experiments/screens/bmapen-transfer-phase-v1.json`.
No temporary selector or incomplete candidate is accepted into Copperline.

## Scoped source correction and next work

Copperline `b40122d4` commits the selector-free even-step enable correction.
Independent-data two/four-plane1024/1024 and nonuniform three-plane256/256
controls reject the early-transfer alternative (920/1024 and128/256).
Production replay matches4352/4352 across the original512 matrix, polling256,
independent-data1024, three-plane256, early-clear512, gate1024 and word-gate768.
Core3675, goldens46, strict Clippy and formatting pass; probe tools364 pass.
This is a scoped source correction, **not full Init/Copper acceptance**. The
failed qualification/timing gates above remain recorded and must be resolved.

New references `dma-warm-restart-v1` distinguish a sleeping Copper from cold
COPEN. Warm inert controls match; explicit restart still differs. The
`dma-master-boundary-v1` control keeps DMAEN high beforehand:8/32 baseline
matches and20/32 prototype matches, with no unstable observations. Thus a
simultaneous master-enable edge alone does not explain cold request timing.

`dma-restart-readback-v1` records three consecutive beam reads before any RAM
stores. Prototype16 match,8 mismatch,8 unstable. Stable restart phase0 stays
early beyond the first read; phase1's first read matches but later reads differ.
Keep those raw sequences and conflicts; do not fit a first-read-only offset.
Exact builders/contracts share each reference's `dma-*` name. Full runs and
prototype comparisons remain in `captures/collision-cpu-20261022/`.

Next: integrate the isolated Init model on top of the source correction,
preserving v1's CPU fixes, and test the new cold/warm/master controls alongside
the existing source/reload/resource sweeps. The prototype itself still fails
these new controls; it is evidence for refinement, not an accepted implementation.


## Init integration after the scoped fix

The accepted branch `fix/more-a500-timing-fixes` remains at `b40122d4`.
Unaccepted integration is checkpointed separately as `6c06be2a` on
`wip/init-after-bmapen-20261023`; the older `wip/init-copper-timing` is preserved.
This integrates the old transfer/reload prototype with current v1 CPU changes.
Core3691 passes, but the existing hardware acceptance gates still fail.

Eight explicit mechanism combinations reject WAIT-tail reuse (20 new fields)
and global end-phase beam sampling (hundreds of fields,768 lost qualifications).
Transfer-time combined DMAEN/COPEN request forwarding improves16 cases across
ten unchanged contracts without new field or qualification regressions. Only
Copper sees that transient request; other master-DMA consumers retain full
register commit timing. It remains an unaccepted prototype. Original pointer
and Copper qualification gates still fail at243/480 and391/800 respectively,
with zero collision-value mismatches; excluded cases are not matches.

New reference `dma-nop-boundary-v1` has64 independently stable cases. It crosses
cold/warm Copper with a COLOR00 write versus four NOPs, both16 uncontended CPU
clocks, with master DMA already enabled. The prototype matches60/64: every NOP
and warm case matches. Only cold custom-write phase1 is late (A5004264 versus
Copperline4265), repeated four times. ROM completion witnesses all pass. This
narrows the next question to write/following-read grant timing, rather than a
blanket beam offset or ROM execution duration. Builder, manifest and reference
share the `dma-nop-boundary` name; probe-tool regression365 passes.

The bounded next screen tests explicit CPU-clock address/data/return phases
against unchanged captures and independent collision controls. The MC68000
manual specifies processor-clock waits, but does not establish Gary/Agnus
DTACK granularity. Recipe: `experiments/screens/init-cpu-clock-phase-v1.json`;
plan: `investigations/init-cpu-clock-phase.json`. Reject local improvements
that introduce timing fields or lose qualification. No sub-CCK model is yet
accepted. Full logs and packet-qualified profiles remain under
`captures/init-after-bmapen-20261022/`; use `tools/profile_case_window.py` for
bounded trace retrieval. OneROM was restored and reset release verified after
the completed NOP hardware batch.


The CPU-phase counterfactual is rejected: baseline2024 matches/40 mismatches,
versus736/560 and768 exclusions for explicit phases. Early beam alone gives
776/520 and768 exclusions; each model retains16 unstable samples separately.
The baseline packet was byte-identical. Source was restored to6c06be2a;
`experiments/patches/init-cpu-clock-phase-v1.patch` preserves the rejected
implementation for audit. This rejects that implementation, not all possible
sub-CCK models. Next discriminate persistent write delay from immediate
write/read turnaround with0..3 trailing NOPs (`dma-write-gap`, kind116).


## Gap and consecutive-read controls

`references/dma-write-gap-v1` (kind116) crosses0..3 trailing NOPs with
write/NOP actor and cold/warm Copper:228 match,16 mismatch,12 unstable,0
excluded/invalid. Gap1 matches all64; gap2 cold/write phase3 and gap3 cold/warm
NOP phase2 expose the same1CCK late read. Unstable cohorts4268/4269 remain
unqualified. All completion witnesses pass. Qualified profiles `profile-gap-
{cold0,cold1,warm3}` have packets identical to their parent; bounded slots show
the stable mismatching reads immediately after a bitplane slot.

`references/dma-gap-readback-v1` (kind117) retains the actor prefix and captures
three consecutive reads before stores:196 match,48 mismatch,12 unstable,0
excluded/invalid. Warm NOP gap3 phase2 is HW426a/4270/4276 versus emulator
426b/4271/4277. Cold write gap1 phase1 first4266 matches, but the following
6c/72 become6d/73. A sampled-value correction alone is insufficient.

An important limit: cold write gap0 phase1 first read is now HW4265, whereas
kind116 measured4264 with the same recorded pre-enable beam. Observer bytes
through the first read are identical; following prefetched instructions differ.
The integer marker does not prove equal sub-CCK phase or all microarchitectural
inputs between ROMs. Keep separate ROM-specific references; never align or
combine away this difference. Both live batches restored the original ROM and
verified reset release. Full instability limits remain unchanged.

Revised counterfactual `init-shared-cpu-phase-v1` tests complete shared CPU
instruction/bus accounting, since the first implementation left classic
whole-CCK instruction reconciliation active after fractional bus accounting.
It compares1- and2-CPU-clock waits, with fixed1/2/1 address/data/return clocks,
against both new read sets and the independent collision floor. No beam-value
exception is introduced. See `investigations/init-shared-cpu-phase.json`.
