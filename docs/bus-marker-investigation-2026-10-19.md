# Bus marker investigation, 19 October 2026

## Question and decision rule

Leading hypothesis: Copper BLTSIZE launch scheduling differs. Competing
explanation: busy/zero visibility differs after a correctly scheduled launch,
possibly compounded by CPU register sampling. Marker and status moving together
implicates scheduling/sampling; a matching marker with a status-only mismatch
narrows the status path. CPU launch and no-blit controls prevent fitting only
the Copper pilot. Do not change a global status or IRQ delay from one cohort.

## Probe and units

Kind55 has 896 descriptors: widths 1/16, both launch owners, marker immediately
before/after size, BLTPRI off/on, no-blit controls, fourteen requested beam gates
($40..$74 in steps of four on line 66), and two repetitions.
Copper waits for line66 h$60, then executes the adjacent marker/size MOVEs.
CPU launch executes the same ordered register writes after its observation
gate. NOOP replaces size in controls. Their requested gates are not equivalent
launch timestamps.

The fixed ROM observer at FFCA00 retains pre/post VHPOSR and captures four
alternating INTREQR/DMACONR pairs in D0..D7, without intervening stores. Raw
indices are read positions, not cycle offsets. No inferred offset or trace
alignment is allowed. CPU IRQs are masked. Results +20..34 contain raw samples,
including canonical status/PC slots; +36/+38 are settled D endpoints.

`compare_bus_marker.py` requires matching source IDs and validates checksums,
watchdogs, marker completion, unique descriptors and D endpoints. Compare
raw marker bit4 and busy/zero bits14/13 only on identical recorded pre/post
beam brackets. Different brackets are counted separately. First divergence
is the first differing recorded read, not necessarily the electrical event.

## Reusable tools and local evidence

- `build_bus_marker_rom.py`: isolated source snapshot and immutable build.
- `src/rom/bus_marker_kernel.i`, `bus_marker_observer.i`: setup and observer.
- `compare_bus_marker.py --hardware PATH --candidate PATH --out REPORT`.
  Add `--case 55:0:0:0:0:0` for the complete eight-read surrounding trace.
- `tests/test_bus_marker.py`: changed marker/status, missing row, shifted bracket.
- Archive `build/bus-marker-v1`; capture/log root `captures/cia-hw-20261019`.
- Copperline preflight `bus-marker-copperline-v1`, executable from `3b43225c`.
  All 896 packets validate, with all active/control destination words correct.

The baseline bus differences are unchanged after the CIA correction:
Copper busy 41/449, handoff 1238/2304, normal/fill BZERO 0/4608. The rejected
global DMACONR sampling patch and next CPU experiments remain documented in
`accuracy-experiments-2026-10-18.md`.

## Physical findings and smaller reproducer

Pilot: 103 exact-descriptor/bracket matches, zero mismatches, 793 different
brackets. Grouping across the two repetitions on identical configuration AND
recorded pre/post brackets yields 185 candidate observations: 184 matches and
one busy-only mismatch. No timestamp/read is shifted; the matched hardware
case ID remains explicit. This motivated a smaller width16/BLTPRI sweep at
three gates ($50/$54/$58), sixteen repetitions, both owners, marker orders
and no-blit controls: `build_bus_marker_rom.py --focused` (384 cases).

The focused batch ran twice on A500. Run1: 370 phase-qualified candidate
observations, 344 matches and 26 mismatches. Run2: 367 qualified, 341 matches
and the same 26 mismatches. Both marker orders show first-status BBUSY still
high on hardware and already low in Copperline; the marker reads agree and
no qualified CPU-launch/no-blit observation differs. Run2 also supplies thirteen
exact-descriptor/bracket mismatches, so this is not solely a cross-repeat
cohort inference. BZERO agrees in these traces. Markers already set at the
completion sample do not establish the precise launch edge.

Hardware-to-hardware: 374 phase-qualified candidate observations agree,
zero mismatches/unstable-reference groups, ten without a common bracket.
Cohort counts may reuse a hardware observation and are not independent trial
counts. The stricter same-repeat comparison has fifty matches, zero mismatches,
334 different brackets. All three physical runs restored and verified the
original live ROM and final reset release without errors.

References: `references/bus-marker-pilot-v1`, `bus-marker-focus-v2-run1` and
`run2`. Reports are under `captures/cia-hw-20261019/bus-marker*comparison.json`
and `bus-marker-focus-hw-repeat.json`. Tools pass 181 tests, including an
unstable-reference rejection and exact-phase matching across repetitions.

## Candidate and acceptance conditions

Hypothesis: BBUSY is sampled after the 68000 bus-cycle tail; competing cause:
the sequencer finishes early. Candidate: retain BBUSY at the granted CPU
transfer, leaving sequencer timing, BZERO calibration and IRQ timing intact.
No owner/program-specific branch. This is a scoped sampling correction, not
proof that all DMACONR signals have a complete shared physical pipeline model.
Only accept if it repairs the focused pattern and held-out busy observations
without BZERO, handoff, IRQ or core-test regressions. Otherwise revert and
revise the hypothesis; do not infer a global delay from this one boundary.

## Next unresolved question

Does sampling BBUSY at the granted transfer repair the repeated completion
pattern without new field-level regressions in held-out bus captures? Both
start-marker orders already read high at the divergent completion sample;
that alone does not prove exact Copper start timing. If the candidate fails
held-out checks, preserve/revert it and add an end-marker or external bus trace
rather than extend a global delay. Continue with broader 68000 operand/prefetch
contention only after this bus family has a bounded explanation.

## Rejected CPU sampling candidate

The BBUSY-only grant sampler leaves all 26 focused discrepancies unchanged.
Held-out busy improves 41->39, but handoff introduces four regressions while
repairing eight (1238->1234), so aggregate improvement is insufficient. BZERO
remains 4608/4608. Core tests and strict Clippy pass but do not override the
physical regressions. Patch saved as `diagnostic-bbusy-transfer.patch` under
the local capture root; all three modified source files were restored before
the next candidate. Full comparison: `busy-sampling-heldout.json`.

## Completion-marker discriminator

The v3 `--completion` profile has 640 Copper-only cases, width16, BLTPRI
off/on, both start-marker orders/no-blit controls, ten gates, eight repeats.
After the size/start-marker slots, append a BFD=0 WAIT and INTREQ.SOFT bit2.
Compare INTREQR bits4/2 (start/completion) against BBUSY/BZERO. This marker
tracks Copper-observed completion independently of CPU status readout.

Two physical runs validate all packets/endpoints and restore successfully.
Hardware-to-hardware exact-phase cohorts:579/579 match,61 without a matching
bracket; strict same-repeat:126/126 match,514 different brackets. Versioned
`references/bus-marker-completion-v3-run1` and `run2` preserve provenance.

Against committed 3b43225c, run1 yields576 phase-qualified observations:
551 matches,25 mismatches; run2 yields545:523 matches,22 mismatches. Every
mismatch combines early BBUSY clear AND early completion marker. Both priority
states/start-marker orders occur. No qualified no-blit control differs. This
rejects CPU read-tail sampling as a sufficient cause and supports completion
scheduling or Copper BFD handling; it is not an inferred absolute cycle delay.

## Scheduler candidate

`src/bus/dma_slots.rs` steps the Copper before deciding whether to clock a
blitter internal cycle. A BLTSIZE MOVE can start an idle blitter and consume
its first startup cycle in the same quantum, unlike a CPU launch. Candidate:
only advance a non-bus blitter cycle if the engine was already running at the
start of the quantum. The launch clock arms state; the next clock begins its
existing pipeline. No extra cycle counter, owner-specific delay or status
constant is introduced. A focused bus test checks the initial/next state on
both normal and line launches. Replay new physical references and all held-out
suites before acceptance.

## Scheduler candidate rejected and bounded trace

The launch-clock candidate changes neither focused trace family: 370 qualified
status observations still have 26 mismatches;576 completion observations still
have 25. The first bus-free body phase absorbs this proposed startup-clock
change, so the hypothesized register-clock ordering does not explain the
measured completion error. Both source files were restored to committed HEAD.
Patch retained as `diagnostic-copper-start-clock.patch`. Its added unit fixture
also failed to reach the launch at its assumed third clock; that diagnostic
fixture is discarded, not reported as passing regression evidence.

`tools/trace_bus_marker.py` explicitly enables the observational BLT/Copper/CPU
read flags after the normal runner sanitizes its environment. It records the
exact flags and requires byte-identical results against the untraced packet.
The completed trace verifies identical SHA256
`c464c57dbe2966bd200fafe25f21899547f0f89bcb4eefcc9fabf932a28e10ef`.
Full log stays in `bus-marker-completion-trace-explicit/run.log` under the local
capture root; it is never printed wholesale. Bounded example:
`mismatching-completion-trace-summary.json`, case 55:1:1:5:0:1/frame99.

In that emulated case, size lands at line 66 h102; final body D at 137, E at 138
concurrent with the CPU status-read grant, terminal D at 139, completion marker
at 144. Hardware retains BBUSY at the second status observation and observes
the completion marker one recorded read later. These are emulated internal
clock locations plus physical sampled words, not measured physical bus edges.

## Current handoff and next discriminating test

Confirmed: repeated A500 busy/completion-marker differences; two insufficient
repairs rejected; committed Copperline remains `3b43225c` with only the verified
CIA correction. Existing IRQ/divider and BZERO baselines remain intact.
All new captures are versioned; complete traces/logs stay file-backed locally.

Leading hypothesis: terminal E/F progression under a concurrent CPU custom read
is wrong. Competing explanation: grant/read sampling or Copper BFD wake phase
is wrong while engine progression is correct. The current beam brackets do
not identify every internal grant, so do not choose an absolute delay from them.
Next smaller test: fixed launch and paired completion marker, deliberately
replace selected custom-register reads with equal-duration ROM traffic and
record independent before/after beam brackets. Vary CPU bus pressure around
terminal completion, preserving no-blit controls and both priorities. If only
bus pressure moves the physical busy/completion pair relative to Copperline,
isolate terminal arbitration; an invariant error suggests engine/BFD phase.
A shared external bus trace would distinguish the remaining grant ambiguity.
No new emulator patch is justified until this produces evidence.

Compact committed counts and hashes: `references/bus-marker-validation.json`.
Final probe-tool suite: 182 tests pass, including typed reference validation.

Final restored build succeeds. `captures/cia-hw-20261019/restored-final` replays
CIA output (2063 qualified matches,0 mismatches), focused bus (26 residual
phase-cohort mismatches), and completion marker (25 residual mismatches),
identical to the accepted CIA baseline. Rejected patches are absent from the
tracked Copperline source; its HEAD is `3b43225c`. Final executable hash and
counts are retained in the compact validation record.
