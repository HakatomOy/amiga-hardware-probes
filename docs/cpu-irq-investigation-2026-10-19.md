# CPU INTREQ and INTENA recognition

Stage 2; baseline Copperline `1bef46ef`. Kind58 isolates CPU-written PORTS,
EXTER and COPER, versus unmasking those already-pending software requests.
CIA masks and timers are cleared. NOP/DBRA, STOP and masked readback controls;
four phase selectors, eight prelaunch pads, two repetitions: 1152 observations.

Leading hypothesis: request origin and unmask path require different recognition
qualification. Competitor: ordinary instruction polling explains the differences.
Compare identical pre-write beam conditions, instruction count, handler beam and
original stacked PC. There is deliberately no post-write beam read before STOP;
+14 is zero, not an event timestamp. Masked controls require all read brackets.
No trace shifts. Handler beam remains combined propagation/CPU exception timing.

V1 failed assembly (shared handler constants omitted); v2 emulator preflight did
not complete because an interrupt before STOP could leave STOP stranded. Neither
ran on hardware. V3 failed assembly on a scoped-label reference. V4 relocates
handlers into 128-byte slots. After recording the original PC, a helper returns
STOP cases to the instruction after STOP (fixed 0xffcd10), irrespective of whether
the interrupt arrived before STOP. This prevents a hang without changing the
recorded recognition evidence. V4: 1152 valid emulator preflight cases; A500 capture valid. Only 112 rows
qualify: 40 masked readbacks match, 72 recognition rows differ, 1040 excluded.
V5 adds the established ROM beam-alignment call before the observer; preflight
valid, five repeated cohorts have diagnostic CIA ICR flags differing. The
comparator conservatively excludes these unstable cohorts. Hardware pending. Source `a611f6e5`, ROM SHA starts `462bce30`.

Local build `build/cpu-irq-v4`; captures and reports
`captures/cpu-irq-20261019/`. Tools: `build_cpu_irq_rom.py`,
`compare_irq_stage.py`. Guard and mutation acceptance checks are in
`tests/test_cpu_irq.py`. No emulator behavior has been changed from this probe.

## Aligned hardware result and candidate

V5: all 1152 hardware rows qualify. All 384 masked readbacks match. All 768
recognition rows differ: PORTS STOP is two CCK early and stacks the pre-STOP PC;
EXTER/COPER STOP is two CCK late. NOP controls also differ in PC/loop count.
An independent hardware repeat agrees on all 1152 measured records. Packets have
different header/checksum hashes; raw Agnus metadata is retained in references.
References `cpu-irq-v5-run1` and `cpu-irq-v5-run2`; both restorations verified.

Diagnostic override latency4 repairs COPER running/STOP and EXTER STOP. PORTS
retains its immediate bypass; EXTER running retains its pin-fed no-lead rule.
Candidate: record CPU-written software request origin, use the internal poll lead,
and subtract the measured two-CCK CPU-write reference-phase difference only for
newly exposed software requests. Keep CIA pin-fed request/unmask paths unchanged.
Default asynchronous recognition deadline remains six CCK. Candidate validation
and neighboring replays pending; no accepted emulator change yet.

## Validation boundary

Candidate1 repairs all 768 main timing records; candidate2 limits qualification
explicitly to measured PORTS/EXTER/COPER bits. Main packets are byte-identical
between candidates. Core tests caught the unnecessarily broadened BLIT deadline;
BLIT retains its previous six-CCK deadline in candidate2. This is a scope limit,
not evidence for changing unmeasured request bits.

Held-out neighbor ROM: STORE/DBRA and memory-TST/DBRA, 768 cases. Hardware
qualifies all rows. Baseline has 640 timing differences; candidate has zero.
Five diagnostic ICR serial-bit differences remain. Build archive
`build/cpu-irq-neighbors-v1`, source `5bc142e2`, ROM SHA starts `458056ed`.
Independent hardware repeat pending. Candidate1 broader replay: ten packets
byte-identical to accepted baseline; irq-stages has the same 582 matches,86
differences,932 exclusions. New CIA-phase packet1920 also byte-identical.
Logs/results under `captures/cpu-irq-20261019/`. Final core tests pending.

## Accepted result

Candidate2 passes3632 optimized core/network tests,37 ignored,548 window tests
excluded; strict all-feature/all-target Clippy and formatting pass. Main and
held-out packets are byte-identical to candidate1. Both independent held-out
hardware runs agree on all768 records, with verified restoration. Across1920
qualified main+held-out cases,1408 timing differences are repaired,zero remain;
1910 complete matches and ten diagnostic serial-flag differences. Default IRQ
latency remains6 CCK. Unmeasured CPU-written bits and CIA pin-fed paths retain
prior behavior. See Copperline commit for accepted implementation and snapshot
compatibility tests. Task3 starts from this accepted CPU-source model.
