# BBUSY/completion bus-pressure experiment

## Question and predictions

Confirmed baseline: A500 retains BBUSY and sees the Copper BFD completion
marker later in repeated, exact-phase cohorts. Read-tail sampling and skipping
the launch clock did not explain it; see `bus-marker-investigation-2026-10-19.md`.

Leading hypothesis: CPU custom-read traffic changes terminal progression or
arbitration differently. Competing explanation: an invariant engine/BFD phase
error. Replace the first and/or second DMACONR read with ROM reads, leaving
later status observations and all marker reads intact. Bus-pressure-dependent
changes support arbitration; an invariant residual supports engine/BFD phase.
Do not select an absolute delay using bracketed CPU observations alone.

## Measurement contract

768 cases: width16, Copper launch, both start-marker orders, BLTPRI off/on,
no-blit controls, three gates, four pressure masks and eight repetitions.
Descriptor delay bits0/1 replace status reads1/3 (zero-based read indices).
Four ROM observers at FFCA00 + mask*200 share instruction layout. A replaced
MOVE.W uses PC-relative ROM data instead of d16(A6): both are four-byte,
nominal twelve-CPU-clock instructions. Actual arbitration costs remain measured
by pre/post beam brackets. The ROM dummy is A55A; comparator ignores those
specific samples and retains later real status reads. No alignment is applied.

Acceptance: valid checksum, unique descriptors, settled expected D words,
start/completion markers present; match exact source/config and recorded
brackets. Cross-repeat cohorts retain hardware case IDs and reject unstable
reference patterns. Counts are candidate observations, not independent HW
trials. Require neighboring profiles and broad regressions before acceptance.

## Artifacts and tools

Local root `captures/bus-pressure-20261019`; immutable build `build/bus-pressure-v2`.
V1 staging failed emulator preflight (observer text shadowed experiment text);
no hardware used that ROM. V2 corrects the local name and is preflighted first.
Builder `build_bus_marker_rom.py --pressure`; typed comparison
`compare_bus_marker.py --cohorts`; safe hardware runner `tools/run_onerom_live.py`.

## Next question

Collect a validated physical run, group results by pressure mask and priority,
and decide whether terminal traffic dependence survives exact-phase comparison.
Only then choose the next emulator change or smaller discriminating probe.

## Pressure result and revised discriminator

Run1 validates/restores. Across masks0/1/2/3 respectively, exact-phase cohort
mismatches are15/18/21/20 of154/164/158/153 comparable candidate observations.
In every mask the completion marker is early; substituted early status samples
are ignored explicitly. No unstable reference group. Removing the status reads
does not remove the completion discrepancy, weakening that traffic hypothesis.

Archived kind50 also shows both busy assertion and deassertion one sample later
on hardware for several widths. New onset profile:2176 cases, widths1/16,
start marker before/after size, both priorities/no-blit controls, requested gates
$20..$60 in steps of4, eight repeats. Retain the same four marker/status pairs.
A matched start marker with later busy assertion supports a launch pipeline
error; matched onset but later completion favors terminal/BFD progression.
No absolute delay is inferred from a sample-index difference.

Onset archive `build/bus-onset-v1`. Its emulator packets/endpoints all validate.
The hardware runner was launched while that preflight was still completing;
validation succeeded. Subsequent dependent commands must be separate calls,
with successful validation checked before the hardware call.

## Onset evidence and corrected interpretation

Run1:1965 phase-qualified candidate observations,1784 matches,181 mismatches.
Thirty-three observations show later hardware busy assertion, while all start
markers match. Independent HW run2 matches all2176 phase-cohort observations
against run1, with zero unstable groups. Both restore reports verify contents
and reset release without errors.

Filtered trace is byte-identical to the untraced packet (SHA256
`e4e6d5c505f712518a9ba53d0de6dfe6c9b34b4b8de6abe856a43dbd04afdba0`).
For case55:1:1:0:0:6/frame1240, CPU status is granted at h101, the Copper writes
size at h102 in its tail, and the returned status at h103 includes the future
start. Thus the onset result alone does NOT prove early engine launch.

Revised candidate: sample only BBUSY before the granted CPU cycle advances,
after arbitration waits. Existing INTREQR sampling remains after that quantum,
other DMACONR phases stay calibrated, and 020 short-bus behavior is unchanged.
The prior rejected sampler was AFTER the granted quantum, so it could not
retain busy when E retired during that clock. Compare both endpoints, marker
residuals, and held-out handoff cases before accepting this distinct candidate.

## Pre-grant candidate rejected; revised write-phase model

The pre-grant sampler repairs the26 Copper busy differences but introduces46
CPU-launch busy differences in variant3, whose observations previously matched.
Completion markers remain wrong (25 in the completion profile;74 in pressure),
with zero start-marker differences. The candidate is reverted and retained as
`captures/bus-pressure-20261019/rejected-pre-grant.patch`. Moving a global read
sample is therefore insufficient; it compensates for the Copper timeline while
breaking the correctly phased CPU timeline.

Next candidate: Copper BLTSIZE data fetch arms a two-clock write strobe before
starting the existing engine, while the CPU path already applies its write
after its completed bus cycle. Keep CPU launch timing and all CPU sample points
unchanged. Retain old busy/zero state until strobe commit; serialize pending
clocks and include them in slot/deadline prediction. This is a hardware-source
write-phase candidate, not a title-specific branch or a change to the body/E/F
cycle counts. It must repair both busy and completion markers, preserve CPU
controls, and pass held-out field-level checks before acceptance.


## Wrap-up and next discriminating experiment

Stopped at user request. Copperline source is restored to accepted `3b43225c`;
no unverified emulator change was committed. Candidate patch is saved in
`experiments/copper-start-strobe-wip.patch` (four-clock deferred Copper start,
NOT validated). A finite Cargo build may finish with this candidate in
`target/ci`; rebuild accepted source before using that executable. Accepted
snapshot: `captures/cia-hw-20261019/restored-final/emulator.exe`.

Confirmed: onset hardware repeats agree on all 2176 qualified observations.
Pressure substitutions retain the completion discrepancy. Two-clock deferred
Copper start matched pressure 510/510 and marker 281/281 qualified cases;
completion had 23 busy-only differences, onset 58 busy/zero differences, with
zero start/completion marker differences. These are qualified cohorts, not all
raw records. Held-out common-cohort comparison repaired five cases and regressed
none of 322 eligible cases; other handoff differences remain unresolved.

Rejected: pre-grant global status sampling introduced 46 CPU busy differences.
An even-phase busy-clear latch fixed completion but introduced seven CPU-control
errors. Neither is an accepted fix. Evidence and rejected patches remain under
`captures/bus-pressure-20261019/` (`pre-grant-focused`, `strobe-focused`,
`strobe-heldout`, `latch-focused`, and trace directories). Derive trace frame
mapping from the first START: initial frame differs between captures.

Phase controls `a500-phasepad-v1-run1` and `a500-phase-entry-v1-run1` matched
498/498 and 1221/1221 qualified observations, respectively. These are neighboring
controls, not discriminators of the residual mismatch. All physical runs ended
with original ROM restored and readback/reset-release verified.

Next uncertainty: deferred Copper write strobe versus a separate status-observer
phase. Preflight `build/bus-phase-completion-v1` (built only; never run on HW),
then measure dense completion markers and compare unchanged CPU controls. A
consistent marker shift supports launch timing; status-only shifts support the
observer explanation. Compare two- and four-clock candidates against the same
trusted captures, retaining exact beam brackets and excluded-case counts.
Relevant files: `build_bus_marker_rom.py`, `compare_bus_marker.py`,
`tools/replay_accuracy.py`, Copperline `src/bus/custom_regs.rs`,
`src/bus/dma_slots.rs`, and `src/chipset/blitter.rs`. Run neighboring and broader
regressions before accepting any candidate. Detailed logs stay in captures.


## Investigation resumed: dense completion and split-stage candidate

Four-clock full deferred start: marker 370/370, completion 576/576, pressure
724/724 qualified matches; onset 2085/2176 with 91 busy differences (one also
zero). Thus a single full launch delay is insufficient. Dense phase-completion
hardware run1 validates and restores; two-clock candidate has 23 busy-only
mismatches/1344 comparable, four-clock has 1543/1543 matches (249 excluded).
Reference packets and configuration manifests are versioned for phasepad,
phase-entry, and phase-completion. Excluded brackets remain excluded.

Byte-identical four-clock onset trace `strobe4-onset-trace` maps its first
START to frame11. Representative frame12: size data fetch h102; status grant
h103 returns at h105 before busy asserts (four-clock candidate commits at end
h105); HW reports busy without zero. Candidate now separates busy assertion
(two clocks after Copper fetch) from engine/zero reset (four clocks). CPU starts
and all CPU sampling remain unchanged. Compare onset plus terminal probes,
then held-out and broad regression evidence. A failure would reject this split
as incomplete rather than justify another observer compensation.

Probe unit suite: 186 tests pass. Full Cargo headless tests for the prior
four-clock candidate hit long-running network tests and three netplay failures;
inspect compact final diagnostics before attributing these to the bus change.
The earlier wrap-up source-restoration statement describes that boundary only:
work resumed and the candidate is again applied, uncommitted, for validation.


## Split-stage validation

Candidate separates busy assertion at +2 colour clocks from engine/zero at +4
relative to Copper size data fetch; CPU paths are unchanged. Qualified outcomes:

| Profile | Matches / comparable | Excluded brackets | Differences |
| --- | ---: | ---: | --- |
| Marker | 370 / 370 | 14 | None |
| Completion | 576 / 576 | 64 | None |
| Pressure | 724 / 724 | 44 | None |
| Onset | 2175 / 2176 | 0 | First-case BZERO only |
| Phase padding | 653 / 653 | 115 | None |
| Phase entry | 1551 / 1551 | 241 | None |
| Dense phase completion | 1543 / 1543 | 249 | None |

Onset common baseline/candidate cohort:1965 eligible,181 repaired,0 regressed,
0 still mismatched (`split-onset-delta.json`). The one newly eligible initial
BZERO difference is `55:0:0:0:0:0`, hardware4000/candidate6000 at read1. Baseline
also returns6000, but has a different ending bracket. The test does not prime
the initial accumulator; warm-reset retained hardware state versus emulator
construction is the leading explanation, not a confirmed reset rule. Resolve
with deliberate nonzero priming before changing reset behavior.

Held-out Copper busy:526/526 comparable match,2 excluded. Register-handoff
remains1066/2304 matches (1238 existing mismatches). Remaining held-out suite
validation is file-backed under `split-heldout`; do not infer completion of a
suite until its summary is written.

Validation so far:186 probe tests pass including every reference manifest;
2766 headless library tests pass,5 ignored,41 netplay tests explicitly filtered;
strict all-target/all-feature Clippy and formatting pass. The earlier broad
run failed three network disk-change/confirmation timeout tests; a serial
netplay-desktop rerun is pending. A low-feature Clippy invocation also reports
pre-existing frontend-off dead-code/unit-value warnings; full-feature strict
Clippy passes. Logs remain in `captures/bus-pressure-20261019/cargo`.
