# Copperline PR 810 review follow-up

**Update:** the unfinished CIA/PB/STOP changes have been split from the PR.
See [merge subset and validation](pr810-merge-split.md) for current scope.
The full-head results below are historical evidence.

Review head: `744c367d`; source branch `fix/a500-hardware-timing`.
Review comments: https://github.com/CopperlineHQ/Copperline/pull/810

## First family: STOP event scheduling and accounting

Hypothesis: STOP can oversleep serial completion or CIA events because its
deadline excludes delayed flags/pins and ignores the E-clock remainder.
Competitor: another cap always preempts those events. Test independently
scheduled delayed sources and every divider phase, including deferred device
time. An earlier deadline requires a scheduler correction; unchanged bounds
would reject this explanation. These are consistency tests of existing device
timing; no new silicon behavior is inferred.

Hypothesis: STOP poll alignment advances unaccounted time from an observation
method. Competitor: outer slice accounting already includes it. Test clock and
slice counters during IRQ refresh and dispatch. Refresh should not move time;
dispatch should account for any wait once.

## Review checklist

Pending verification/resolution: CIA IR versus pin after mask clear; zero-latch
TA/TB auto-start; serial STOP deadline; E-clock deadline conversion; STOP poll
accounting; removed BLTPRI destination-order regression; Python/tooling scope;
v1 default/format policy; rendered golden probes; CIA pulse save-state meaning;
MyST lab-note inclusion; unused blitter overlay; CIA per-edge cost; stale Git
dependency allowance; CLXPROBE instrumentation.

Do not treat static-review assertions as hardware measurements. Use existing
qualified captures first; measure new CIA/BLTPRI uncertainties on the connected
A500 with explicit controls. Keep raw logs and review API snapshots in ignored
`captures/pr-810-review/`. Record commits, validation and replies here as each
family is resolved.

## CIA hardware evidence

`references/cia-review-mask-v1`:32 cases, two stable independent runs. Both
chips retain the Paula request after clearing the old timer mask without ICR
acknowledgement, even with the new serial source masked. Explicit ICR ack and
no-old-interrupt controls agree. Correct IR/pin retention together.

Paired auto-start aperture `captures/pr-810-review/cia-zero-hardware-v1`:
288 cases, two runs, no unstable cases. Baseline246 match42 differ. Zero-latch
TB START readback matches; TA is late in18 cases. Latch1 readback is late for
both timers in24 cases. Thus adding a TB carry flag is not supported by this
observer. Leading hypothesis: control START readback, like counter reload,
becomes visible during E-high before the falling-edge commit. Competitor:
internal TA carry lifetime itself is wrong. Test a transfer-only STOP preview,
retaining internal underflow/cascade state, against this aperture and existing
underflow references. Repair of both latch1 and zero cases without cascade
regressions supports the preview; otherwise isolate the carry lifetime.

## Destination restore evidence

`references/pr810-destination-v1`:384 cases, two stable runs;360 match24 differ.
Both BLTPRI settings differ identically: AD NOP1/2 and D-only NOP2 restore to
the last descending destination too late in Copperline. Outside-neighbor,
no-start and preseed controls match. The two destination fields both observe
address10000 (the last descending word), not two independent addresses.

Packet-qualified `captures/pr-810-review/destination-profile-v1` case
`127,3,33,0,0,0`: CPU grant42:87, final blitter D write42:88; trace predicts
5555 thenaaaa, but final emulator RAM is5555. The ordinary CPU RAM write commits
only after the entire grant plus tail, overwriting DMA that ran in the tail.
Leading hypothesis: commit RAM at the existing granted-word transfer callback,
before the trailing free DMA clock. Competitor: the actual grant order is wrong.
Test that change against all384 plus original source-write and handoff suites;
repair without grant-time changes supports commit ordering. Added BLTPRI fences
cannot explain equal priority-off/on failures and would delay CPU writes further.

## Broad STOP qualification check

The corrected scheduler changes127 of1600 original kind56 packets. Exact
historical release cohorts show five CIA-A STOP regressions (86 ->91 total
qualified mismatches); no newly repaired cohorts in this old contract.
Leading hypothesis: the old oversized idle advance compensated for unresolved
CIA source/CPU recognition timing. Competitor: the sparse historical cohorts
do not describe a stable repeatable outcome. Recapture the exact original
`build/irq-stage-v7` ROM twice, retaining all STOP/running/masked controls and
all original descriptors. If fresh exact cohorts agree with old HW, the
scheduler correction is not yet timing-accepted; isolate the upstream boundary.
If they agree with the candidate, preserve both historical and new references
and report the qualification limit. Conflicts are unstable, never matches.

Accounting audit found a competing software explanation: moving the STOP wait
into the CPU slice records one bus CCK but does not add its two CPU clocks to
the dispatch charge. Reconciliation can then credit the poll wait against the
exception's nominal execution time. Compare automatic alignment with an
otherwise identical checkpoint advanced explicitly by one idle CCK: final
device time and handler state must agree, while automatic dispatch reports one
extra bus/CPU CCK. Correct that charge before interpreting the fresh HW outcome.

## Resolution status

Copperline commits: `4226b413` (tooling/dependency scope), `0f20b644`
(documentation inclusion/link corrections), `ae68ce90` (functional corrections,
state migration, two golden probes), `569af24e` (PDF appendices). All15 inline
comments have evidence-backed replies. The PR remains a draft targeting `main`.
Use [the short restart record](../investigations/pr810-review.json) next session.

Upstream `main` advanced to `a444a636` during review. Merge `d19310f3` resolves
three runtime-state conflicts by retaining both STOP poll phase and upstream JIT
bank state, including save and restore. The pushed PR is conflict-free.

| Comment | Evidence / change |
|---|---|
| CIA IR/pin desync | Both chips retain request after mask clear;32/32 new cases match corrected latch/pin behavior. |
| TA/TB zero one-shot |288/288 paired aperture cases match transfer-only decrement-stage START preview; no unsupported TB carry flag added. |
| Serial STOP deadline | New `next_event_ticks` includes serial flag and external-pin lag; library and standalone CIA regressions pass. |
| Removed BLTPRI fence | New D-side384/384 and existing source-side2304/2304 match RAM-at-transfer correction; no priority-only fence restored. |
| E-clock deadline | Divider remainder/deferred clocks included; CIA STOP compatibility check remains open. |
| STOP accounting | Refresh no longer moves time; dispatch owns wait and CPU/bus charges. Explicit-idle/checkpoint test added. |
| Python/tooling scope | Copperline wrapper/instruction changes removed in4226b413; wrapper/tests retained here. |
| Branch policy | Draft PR retargeted to `main`; default remains6, not used to hide timing differences. |
| Golden coverage | Two rendered boundary probes added;48 total goldens pass after visual verification. |
| CIA save-state meaning | Explicit high-pulse fields, CIA chunk v2, registered v1 migrations and pin-level/expiry tests. |
| MyST notes |14 supplementary pages registered hidden; strict HTML/link check and PDF build passed. Formatting/local link fixes in0f20b644. |
| Blitter overlay | Legacy fields retained, new tracking disabled, no map inserts; obsolete policy tests removed, legacy-state/live-RAM tests retained. |
| CIA batching | Skip quiet spans between underflows/serial/pin events; pipeline and pulse boundaries still step exactly. |
| Stale Git dependency | Restored upstream deny policy and corrected crates.io comment in4226b413. |
| CLXPROBE | Both temporary hot-path logging blocks removed. |

Validation logs stay under `captures/pr-810-review/`. Earlier commands selecting
`--bin copperline` ran CLI tests only; they are not emulator-library acceptance.
The explicit `--lib -- --skip window::` run passed3679 tests,37 ignored,
559 window tests filtered. Unfiltered library execution exposed two window
failures: keypad mapping (passes alone, fails in the parallel suite) and a GPU
scaler comparison (3/255 difference). These are recorded, not counted as passes;
the native suite is also run with just those two exact test names excluded.
That run passes4230 library tests,43 ignored,2 filtered, and all other enabled
native binaries except three `--run` integration tests initially blocked from
writing the user's Documents directory. Those three pass when retried with
temporary portable mode inside the workspace; the marker is removed afterward.
The48 golden tests pass on the final executable. Strict Clippy/fmt, HTML/link
checks and the PDF including all14 supplementary articles pass.

After merging current `main`, the complete native run passes4478 tests across
45 binaries (131 ignored,2 named window exclusions,0 failed); library4265
passed,43 ignored. It uses temporary portable mode so all integration boot
volumes stay inside the workspace, and removes that marker afterward. Both
strict documentation builds and Clippy pass on the merge. The three new
hardware-reference families still match32/32,288/288 and384/384 on the merged
executable. Earlier17-suite replay numbers are preserved as pre-merge evidence.
The complete17-suite baseline/candidate replay has identical counts except the
open original kind56 CIA-A STOP timing family. Exclusions and historical raw
differences remain explicit; these runs are not claimed as17 all-matching suites.

The START aperture alone cannot establish TB's hidden adjacent-underflow count.
Hypothesis: TA and TB zero auto-start share the measured two-edge output pulse;
competitor: TB actually emits only the single LOAD-carry pulse. Run kind128,
paired PB6/PB7 pulse-width apertures on both CIAs with latch0/1/3 and the same
NOP gaps as kind126. A zero-only TB pulse mismatch supports adding its pending
carry; matching pulse widths reject that change. Nonzero pulse mismatches instead
require refining transfer phase. Do not infer internal symmetry from shared names.

Kind128 result:224 matched,37 stable pulse differences,27 unstable cases across
two hardware runs, no missing/invalid packets. Instability exceeds the declared
budget, so this is rejected as acceptance evidence. Both timers show an early
zero-latch pulse at gap1 that the emulator misses; TA also has late pulse
differences, and nonzero pulse samples differ. Preserve
`references/cia-review-zero-pulse-v1`; qualify E/CPU phase or capture the actual
PB6/PB7 pulse with the scope before changing TB carry state.

The independently E-phase-calibrated kind57 replay has829 matches,499 existing
differences,592 excluded cases both before and after the STOP correction.
All previously matching qualified fields remain matches (zero field regressions
or qualification changes).280 already-wrong fields change their values; this is
not an accuracy fix for CIA propagation. Kind56 retains five extra mismatches
in its beam-only cohorts, reproduced as four extra mismatches on fresh captures.
Keep this explicitly open in the review; the corrected event cap must not be
advertised as a complete CIA/CPU timing repair. `DEFAULT_IRQ_LATENCY_CCK` remains6.

Final new-reference replay:32/32 mask cases,288/288 START-aperture cases and
384/384 descending destination races. Existing source-race2304/2304 passes.
Logs and packet-qualified traces remain in `captures/pr-810-review/`; reference
packets and manifests are versioned under `references/`. Original ROM images
and OneROM backup/control files remain ignored. Every live session above ended
with verified original-ROM restoration and reset release.
