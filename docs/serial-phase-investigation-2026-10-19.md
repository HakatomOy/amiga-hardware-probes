# Serial flag visibility phase

Baseline Copperlinea2299b00. Kind64 separates serial flag visibility from
delayed Timer-B cascade observation using direct TA/ICR/TA counter brackets.
Single byte acknowledges atUF12, queued byte atUF18; sample14..16 or30..32,
then ack again at56. All CPU/CIA interrupt masks remain disabled.

V1:384 cases,52 qualified differences,317 matches,15 excluded; zero conflicting
reference cohorts. All differences persist with direct TA counts well before
the next reload. Two live runs restore/readback successfully. References
`serial-phase-v1/run{1,2}`; sourcef0a1d586, ROM4cc886e9. Reference profile labels
were corrected to replace irrelevant inherited kind56 defaults; raw packets and
the original build archive remain unchanged.

Rejected immediate-half-clock15 candidate:52 repairs but10 complete regressions
immediately after the underflow. The workflow stopped before broader tests.
Patch `experiments/rejected-serial-halfclock15-20261019.patch`; binary and full
comparison `captures/serial-phase-20261019/candidate-v1`. Source restored before
testing a separate E-clock pipeline; no rejected binary is an accepted baseline.

Revised hypothesis: serial event at half-clock15 plus fixed E-clock flag pipeline;
competitor: timer-period-dependent completion/reload16 or observation artifact.
V2 adds latches63/127 and16 pads to latches15/31.1536 cases:1156 matches,
377 differences,3 exclusions,zero conflicting qualified cohorts. References
`serial-phase-v2/run{1,2}`; sourcefc2f88b0, ROM4d9e690b. Exact qualification
includes direct TA counts, TB brackets and actual SDR-write brackets.

`tools/screen_serial_delay.py` screens hypotheses, not executable fixes. Among
2871 hardware observations across two runs satisfying its transfer assumptions,
only four E-clocks gives zero predicted flag errors among delays0..8.201 observations
are excluded for possible reload or a non-six-E-clock TA bracket. The assumption
is symmetric TA/ICR/TA transfers three E-clocks apart; no trace alignment occurs.
Actual compiled replay and held-out neighbors remain mandatory.

Current candidate keeps16-underflow byte period/queue promotion, emits an event
at half-clock15 and clocks a separate four-E-clock SP-flag pipeline. It preserves
the additional existing one-E-clock IRQ-pin delay. New state must survive saves
and batching; old snapshots must deserialize without losing an in-flight flag.

Source/tool paths: `build_serial_phase_rom.py`, `tests/test_serial_phase.py`,
`tools/experiment.py aggregate`; Copperline `src/chipset/cia.rs`. Full captures,
builds, command logs and `delay-screen-v2.json` remain under
`captures/serial-phase-20261019` and `build/serial-phase-v{1,2}`.
Next question: does the compiled four-E-clock pipeline remove all qualified
differences without regressions in previous serial/CIA/IRQ controls?

## Accepted outcome

Compiled pipeline:1533/1533 qualified V2 cases match,377 repairs,zero regressions,
3 unchanged exclusions. Held-out V1:369/369 match,52 repairs,zero regressions,
15 unchanged exclusions. Older serial-buffer320/320 and serial-boundary38 stable
cases match (2 unstable excluded). Earlier CIA-output2063 qualified observations
still match; CIA-IRQ and IRQ-stage records are unchanged.3637 core tests pass,
37 ignored,548 window tests excluded. Strict Clippy and formatting pass after a
nonfunctional return-binding cleanup. Validation resume reuses frozen evidence;
original Clippy failure/logs remain retained. Full plan/result: `acceptance-v2`.
Next unresolved question is payload/pin behavior at exact direction/write edges;
the measured flag-boundary family is fixed. Continue priority2 operand arbitration.
