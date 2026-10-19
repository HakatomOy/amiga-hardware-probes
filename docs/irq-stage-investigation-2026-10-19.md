# IRQ source versus CPU recognition: investigation record

Copperline fix committed as `1bef46ef` (parent `1d0df48a`).

## Findings and correction

Do not remove `DEFAULT_IRQ_LATENCY_CCK`: it remains 6 colour clocks, a combined
recognition calibration rather than an isolated electrical IPL delay.

Paula PORTS/EXTER bit numbers do not identify the request origin. Copper can set
those bits through INTREQ without a CIA pin assertion. Copperline incorrectly
used external-source poll qualification for them; a new Copper PORTS write also
took the immediate unmask path. Track Copper-written origins, arm a normal source
recognition deadline and use internal Paula running-poll qualification. Retain
CIA/pin-fed and unmeasured CPU-written paths. Clear origin on acknowledgement/reset;
serialize it with a backward-compatible default. No new timing constant is fitted.

## Physical evidence

PAL stock 68000 A500, 512 KiB chip+512 KiB slow,ECS Agnus/OCS Denise,OneROM live
substitution. All five physical runs validate and restore their live-ROM backup,
including readback and reset-release verification. Versioned reference packets:
`references/irq-stage-v4-run{1,2}`, `irq-stage-v6-run1`,
`irq-stage-v7-run{1,2}`. Manifests include ROM/source/result hashes and configuration.

Kind56: 1600 cases per ROM. NOP/DBRA, byte-store/DBRA, memory-TST/DBRA, STOP,
and masked INTREQR controls; CIA-A/PORTS,CIA-B/EXTER and Copper-generated
COPER/PORTS/EXTER; four phase selectors,eight source offsets,two repeats.
V7 records raw-request observations near the transition. Units: CIA latch 32..39
E clocks; aligned Copper WAIT line68 h60..6e colour clocks; watchdog line72.
Actual pre/post release brackets must match; masked controls also require all
read brackets. No timestamp shifting or automatic trace alignment.

Independent v7 HW runs agree on all 960 software-request observations. Their
CIA overlap has 22 qualified observations, 6 differences; pooled references contain
25 conflicting CIA-A cohorts. Exact launch brackets therefore do not fully
specify the hidden CIA phase. Conflicting cohorts are excluded when visited.

Pooled stable cohorts visited by the emulator:668/1600 eligible,932 excluded.
Before: 219 differing records; after: 86. Common-cohort delta:133 complete-record
repairs,zero regressions; software timing/visibility differences 134 to0 across
480 qualified software observations. Three software records retain diagnostic
CIA ICR-bit differences. CIA-generated differences are unchanged. V7 first run
shows 6 near-edge CIA INTREQR observations asserted early in Copperline and a
frequent two-clock STOP lead; these are constraints, not an established link delay.

## Validation and tools

Optimized core/network suite: 3630 passed,37 ignored,548 window tests excluded;
new origin snapshot/legacy-default test passes separately. Strict all-feature/
all-target Clippy and formatting pass. 192 probe tests pass, including deliberate
value mutation, missing record, shifted event/bracket and conflicting references.
Ten neighboring packets are byte-identical to accepted `1d0df48a`: CIA outputs,
qualified IRQ,focused IRQ,divider,bus onset/completion/pressure,Copper busy,CPU
handoff and BZERO edges. Existing handoff/initial BZERO differences remain.

Compact replay: `python tools/replay_accuracy.py --binary EXE --config CONFIG
--out NEW_DIRECTORY --suite irq-stages`. Direct comparison:
`python compare_irq_stage.py --hardware references/irq-stage-v7-run1
--hardware references/irq-stage-v7-run2 --candidate CAPTURE --out REPORT.json`.
Reports include grouped differences, representative IDs, first differing fields,
missing/invalid/excluded counts and diagnostic-vs-timing totals. Detailed data:
`captures/irq-stage-20261019/`; accepted candidate prefix `origin6`.

## Next uncertainty and boundaries

Leading hypothesis: CIA request generation/forwarding precedes the hardware
transition. Competitor: an unobserved E-clock/start phase creates the difference.
Before another CIA patch, use an independent phase calibration plus a prelatched
ICR mask-enable control, separating a known pending flag from timer underflow.
A common delay in both controls supports forwarding; an underflow-only shift
implicates timer generation. Phase-dependent changes require tighter conditioning.
Also drain/precondition serial flags before interpreting diagnostic ICR differences.
CPU-written PORTS/EXTER needs its own control before broadening the origin fix.

Copperline files: `src/bus.rs`, `src/bus/custom_regs.rs`, `src/bus/tests.rs`.
Probe: `build_irq_stage_rom.py`, `src/rom/irq_stage_{kernel,observer}.i`,
`compare_irq_stage.py`. [Experiment history](irq-stage-history-2026-10-19.md)
records rejected preflight versions and metadata corrections. V5 never ran on HW.
