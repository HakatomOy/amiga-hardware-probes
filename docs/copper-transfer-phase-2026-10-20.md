# CPU–Copper transfer phases

## Evidence and uncertainty

Continue from [the pressure investigation](copper-pressure-investigation-2026-10-20.md).
The accepted baseline is Copperline `dec76065`. Saved kinds81/83 distinguish
display-pressure and quiet CPU overwrites of Copper instruction data. Model
trace positions describe grants, not measured electrical edges. One CCK is
two stock 68000 clocks; the granted word ends at grant+1 CCK and the CPU
bus tail returns at grant+2. No traces or reference cohorts are aligned.

## Restart and transfer screens

- CPU COPJMP used an immediate PC reload, unlike the existing two-phase
  Copper-issued restart. Reusing those phases repairs16 quiet cases, leaving4,
  but introduces8 display-pressure ordering errors. Reject restart alone.
- Adding the upcoming Copper/line-end refresh guard yields504/512 pressure
  matches, but8 new ordering fields. Quiet remains508/512. Reject together.
- Earlier RAM visibility alone repairs4 remaining quiet cases but regresses4.
  The captured COPEN grant parity distinguishes them: moving enable from
  grant+2 to grant+1 exposes an earlier even Copper restart phase only for odd
  grants. The paired, fixed-grant screen predicts256/256 quiet data flags;
  this prediction is not patch validation.
- The resulting transfer candidate matches512/512 quiet,512/512 pressure,
  512/512 opcode and192/192 new startup controls. However, kind78 gains16
  incorrect destination fields across8 cases and kind79 gains32 incorrect
  busy-status words. Reject pending blitter-startup discrimination. Kind77
  source controls match2304/2304.

Detailed rejected binaries, patches, traces and comparisons are under
`captures/copper-phase-20261020/`. The `jump-*` and `transfer-*` runs preserve
their individual conclusions; do not infer acceptance from a focused pass.

## New A500 startup/steady control

Kind88 compares immediate COPJMP/COPEN with a Copper already enabled before
CPU alignment, released by `WAIT $42a1,$fffe`. Both use the same finite MOVE
stream and COPER completion witness, MOVE0/4/8, NOP0..7 and EXG phase controls.
Stored8004 and old/new outcomes are required before hardware execution.
Clear prior-frame requests at the CPU synchronization point.

References `references/copper-steady-order-v2/run1` and `run2` contain192
qualified cases with byte-identical packets, independently repeated cohorts
and verified OneROM restorations. Baseline:174 matches,18 mismatches; immediate
82/96, settled92/96. Four settled data-order errors rule out startup alone.
There are no excluded, unstable, missing or invalid cases. Exact source is
archived under `experiments/probe-sources/copper-steady-order-v2.py`.

## Reuse and acceptance

`tools/summarize_copper_cpu_order.py` binds CPU witnesses and Copper streams
independently for both quiet and contended traces, including fetches preceding
the CPU witness. `--screen-enable-phase --all-instructions` requires diagnostic
coverage of COPJMP/COPEN and a byte-identical packet. Screens retain source
clocks and report both repairs and regressions.

`experiments/workflows/copper-transfer-acceptance.json` combines the focused
races with held-out handoff, bus, collision, CIA, serial and legacy references,
then core/tool tests, strict Clippy and formatting. Gate individual fields and
qualification as well as whole cases. The next question is whether blitter
Init needs a free DMA clock while StartDelay can still overlap Copper.


## Resolution selected by the clock sweep

The initial free-clock Init correction fixes all kind78/79 cases, but kind80
register witnesses retain72 differences. Reserving Init as a bus transfer fails
a destination control and is rejected. The eight-variant sweep retains exact
cohorts and verifies its default control byte-for-byte against the frozen
parent. Only the unchanged CPU-grant rule with a pre-refresh Init guard matches
all768 kind80 cases; all seven alternatives fail. Full screen:
`captures/copper-phase-20261020/clock-screen-v1/screen.json`.

The selected production model keeps CPU ownership accounting unchanged. Init
cannot advance into the upcoming Copper/refresh RGA turnaround, just as it
cannot overlap a Copper fetch. The completion predictor already treats the
Copper line-end lockout as occupied. StartDelay remains eligible alongside
Copper; this is not a blanket startup delay. Experimental environment branches
are removed from the clean binary. The clean acceptance run is
`captures/copper-phase-20261020/acceptance-clean-v1`; do not call it accepted
until its focused, neighboring and broad gates complete.


The full-DMACON transfer candidate loses12 previously qualified kind73
collision cases (269 matching,211 excluded versus281/199); it is rejected,
not accepted with a raised exclusion budget. The selected refinement stages
only COPEN at transfer. Bitplane/audio/blitter enable delivery and their
observers retain their established write phase. A new clean acceptance run
must preserve the focused repairs and all original collision qualifications.


## Held-out CPU strobe control

The COPEN-only candidate repairs all7360 primary ordering/handoff rows but
introduces four kind61 masked read-beam differences and sixteen kind60 poll
fields. These are separate families: masked saved_pc_offset/ux encode
beam words here, not a stacked PC or IRQ count. The earlier source/recognition
controls retain their results; DEFAULT_IRQ_LATENCY_CCK remains6.

Moving classic CPU COPJMP address decode to the granted word Start repairs
all four masked controls: strobe-cpu-dma has1904 matches and the16 pre-existing
serial-status differences. COPEN remains sampled at word End. The read and
write strobe paths share restart phases; disabled pointer writes must preserve
a pending restart. This refinement still needs the full acceptance matrix.

Next discriminating test: clear normal-blit BBUSY on entry to E while keeping
register release, final D and interrupt stages unchanged. If kind60 first-poll
errors repair without losing independent BBUSY controls, the visibility stage
is implicated; otherwise reject it and revisit engine progress.


The early-BBUSY candidate is rejected: kind79 introduces four busy-word
regressions; kind60 still retains the sixteen extra polls and gains more field
regressions. The CPU COPJMP Start candidate is also rejected despite repairing
kind61: collision pointer qualification falls to259/480, Copper to411/800.
Do not raise exclusion budgets. The next candidate delivers COPJMP at word End
so its internal phases cannot consume the CPU-owned slot. Grant parity controls
and the unchanged collision contracts distinguish this from address Start.


Word-End COPJMP restores both collision contracts (pointer281/199, Copper439/361)
and retains kind61's1904 matching rows. Current candidate: strobe-end-candidate.

The byte-identical kind60 trace rules out a one-clock busy drop as the cause
of case60,3,6,0,4,0: first DMACONR grant is67:07 while Init advances in that
same CPU clock; A is67:09, E67:0c and F67:0d. Hardware's first poll is clear.
A discriminating next model is an RGA-only Init interlock: custom accesses
wait for Init, while RAM accesses can overlap. Reserving all chip-bus cycles
previously failed the destination control. This is distinct from changing
completion/IRQ stages or the entire CPU-yield rule. It needs kind60 plus the
kind79/80 access-space witnesses and held-out gates. Alternative explanation:
BBUSY assertion itself is delayed, so first clear does not prove completion.


The RGA-only Init interlock repairs16 extra poll fields but introduces112
kind79 field regressions (32 cases), plus8 kind60 fields; kind80 stays768/768.
Reject it despite a passing core test run. Reverted from production source.

The next hardware probe kind89 preserves kind60's exact launch prefix and
first status opcode, then uses fixed observations rather than polling. It pairs
AD1/AD16, six-plane/Copper pressure, priority, inert starts, chip/ROM first
reads and neighboring launch slots (384 rows). The finite Copper's last MOVE
raises COPER. Settled AD destination and activity are mandatory controls.
An observed clear-to-busy transition in AD16 would distinguish startup
visibility from completed-blit observation. No transition alone is not proof
of completion; retain early/final destination witnesses and raw statuses.

Operator confirmed A500 power cycle and OneROM connection on2026-10-21.
A new128-case known-good blitter control is being collected twice before
kind89. Keep its session metadata with the captures; do not silently replace
older references or claim a power cycle invalidates a trustworthy baseline.


## Clean-session busy-onset evidence

Post-power-cycle control:128/128 matching, two byte-identical packets,64
independently repeated cohorts, both restorations verified. Packet equals the
older handoff-focus run2; this does not support invalidating that baseline.
References: `references/blitter-post-powercycle-control-20261021`.

Kind89:384 qualified, zero invalid/excluded/unstable, two byte-identical
packets,192 independently repeated cohorts, both restorations verified.
References: `references/handoff-busy-onset-v1`; exact builder archived under
`experiments/probe-sources/handoff-busy-onset-v1.py`. No observed clear-to-busy
transition in either run. Every initial-clear case had nonzero final-D data
by the later early-last-D read. This does not locate the first-clear edge or
prove an unobserved interval absent. The delayed-assertion hypothesis is not
supported by this probe. `tools/summarize_busy_onset.py` reports raw sequences
and representative IDs without inventing event alignment.

Accepted HEAD matches208/384; word-End candidate290/384, but22 new measured
fields prevent acceptance. AD16 also exposes an untouched first source/destination
and BZERO where HW has data. Next hypothesis: Init may share Copper IR1's
memory fetch, but not IR2's register/data phase. Test live and cloned completion
scheduling together against kind60,79,80,89 and all held-out gates. Alternative:
a separate CPU read/arbitration delay; do not change IRQ latency or BBUSY drop.

## Rejected Init fetch-phase models

Both phase models repair poll fields but fail independent controls. Allowing
IR1 overlap leaves16 new kind79 fields,136 kind80 fields and6 kind89 fields.
Allowing IR2 leaves16 new kind79 fields,4 kind60 fields and6 kind89 fields;
kind80 has712 matches instead of the previously repaired768. Reject both and
remove their production code and prototype tests. Frozen candidate binaries,
source logs and four-suite reports remain in `ir1-init-controls` and
`ir2-init-controls` under the investigation capture directory.

The old-baseline delta alone did not reject kind80's lost recent repairs.
The primary preservation suites now declare `comparison.min_matches` equal
to their complete qualified matrices, in addition to unchanged field and
qualification gates. A712/768 result cannot pass as preservation. Floor
validation and rejection tests cover this rule; `run` and `resume` share it.

Current production working tree is restored to word-End COPJMP with Init
excluded from Copper clocks. It remains unaccepted:16 extra poll fields in
kind60 and22 new fields in kind89 require a smaller arbitration reproducer.
No Init model or emulator timing change has been committed from this task.
