# CIA underflow state and request propagation

Priority3 follows the serial flag and CPU/Copper refresh investigations.
Kind66 measures TA, PB6, Paula request, TA again and ICR, with independent PRA,
launch and observation beam brackets. CPU interrupts remain masked. Two restored
A500 runs agree on all640 measured-value vectors, but their read/launch brackets
differ by1CCK: they are separate phase cohorts, not byte-identical repetitions.
Each has five repeats per descriptor. There are no invalid captures, excluded
emulator cases or conflicting qualified observations. References `cia-source-v3/run{1,2}`;
ROM045adb8f, sourceb0227984; full reports in
`captures/cia-source-20261019/baseline-v3`.

580 matches,60 differences. All TA counters and ICR_TA flags match.40 cases
(20 per CIA; latch35, plain/PBON controls) see an asserted request in Copperline
while hardware is still clear.20 PBON cases (latch34, both CIAs) see PB6 high in
Copperline while hardware is low. These are distinct families: moving the entire
timer counter cannot explain both while preserving direct counter observations.

The software observations constrain visibility, rather than measuring the
electrical /IRQ edge directly. A delayed pin and Paula input sampling remain
competing explanations. Kind68 retains the same TA/PB6/first-request prefix and
adds three request samples, each nominally8CCK later (12-cycle MOVE plus4-cycle
NOP, two CPU clocks per CCK). Exact brackets remain required; no alignment or
selection by the request result. Captured traces must confirm any inferred
interval at a refresh boundary. There is no ICR read during these observations.

PB6 has a separate candidate: E-high readback may expose the impending underflow
just as the existing timer read exposes its reload mux. A valid implementation
must leave the internal counter and continuous physical pin state untouched,
handle pulse and toggle outputs, and preserve stopped/CNT-driven controls.

Relevant files: `build_cia_source_rom.py`, `build_cia_request_rom.py`,
`experiments/workflows/cia-{source,request}.json`; Copperline
`src/chipset/cia.rs` (`read_at_transfer`, `latch_timer_interrupts`), `src/bus.rs`
(CIA pin forwarding).

Kind68:640 qualified cases,447 matches,193 differences,zero conflicts. Both
restorations verified; references `cia-request-v2/run{1,2}`. The diagnostic replay
is byte-identical (`request-trace/trace-verification.json`). Nominal request
spacing is8CCK; actual custom grants at line wrap remain authoritative.
`tools/screen_cia_request_delay.py` screens a counterfactual whole-E event delay
using neighboring one-shot latch values, requiring exact unchanged brackets.
No actual trace is shifted, and this is not fix acceptance. Across pooled1280
observations, zero-delay request vectors differ346 times; a one-E delay differs
26/1200 available vectors (80 unavailable), two-E294/1120. Thus a one-E delay is
closer but insufficient, and moving the entire timer is already contradicted
by matching direct counters. Preserve the electrical-pin vs Paula-input ambiguity.
Next request experiment: directly bracket input recognition at sub-E resolution
and separate read sampling from pin propagation; do not add a global IRQ delay.

## Accepted PB6 outcome

Copperline`b8a97ac6` exposes the impending timer output only during E-high CPU
readback, preserving internal counter/pin/IRQ state. Kind66 repairs20 cases with
zero new field/qualification differences; kind68 independently repairs the same
20 output cases without changing request results.

Kind69 adds pulse/toggle, continuous/one-shot and PBON-off controls.192/576 rows
qualify, covering every192 distinct source/mode/latch/phase combination with
independent exact-cohort evidence;384 other phase rows remain excluded. The
exclusion budget was frozen from the baseline before candidate replay.16 output
cases repair,zero regressions,32 request differences remain. References
`cia-pb-controls-v1/run{1,2}`; ROMeeab46d1, sourced062e325.

The first strict legacy gate flagged95 changed live kind53 PB6 snapshots. These
lack precise E-high qualification:85 appear improved and10 appear worse by raw
row, which is insufficient for timing inference. They are not credited as fixes.
The new calibrated mode controls resolve this uncertainty. The typed gate keeps
all unrelated fields/qualification unchanged and preserves2063 qualified settled
output matches.3136 CIA/IRQ snapshots remain unchanged; serial320 stable and38
boundary cases match (2 unstable excluded).3639 core tests pass,37 ignored,
548 window tests excluded; strict Clippy and formatting pass. Full acceptance:
`captures/cia-source-20261019/pb6-acceptance-v2`.
