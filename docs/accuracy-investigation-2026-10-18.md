# Accuracy investigation: current handoff

## Confirmed facts and commits

- Copperline `f2d0a523` fixes CIA batching: PB pulse/toggle state and serial IRQ
  delay now agree with single-edge advancement. No global timing constants
  changed. `11e0f964` supplies the compact Cargo wrapper used by the tools.
- Baseline source was `4694aa3c` on `fix/cia-timings`. Unrelated local work
  remains untouched. No new physical capture was required for the CIA repair.
- Validation: 44 CIA model tests, including a 384-case output matrix; 3,014
  headless core tests passed, five ignored; strict all-target/all-feature Clippy
  passed. The default library suite had 4,160 passes, 43 ignored and the two
  previously documented Windows numpad/scaler failures. Do not claim all pass.
- Hardware replay: kind51 has 67/67 exact-start matches, focused IRQ 2,212/2,212,
  divider 2,560/2,560 (byte-identical packet), normal/fill BZERO 4,608/4,608.

## Reference data and selective tools

`references/` contains seven versioned RBCP packets with capture IDs, test ROM
hashes, hardware/configuration, result hashes and repeatability manifests.
Original OneROM transcripts, ROM archives and run logs remain under ignored
`captures/` and `build/`. Never replace a reference or infer timing from
unmatched starts. WinUAE corroborates; hardware remains authoritative.

- `tools/check_cia_model.py`: quick production CIA-module tests; excludes bus/CPU.
- `tools/replay_accuracy.py`: snapshot executable/config, replay selected suites.
- `compare_copper_busy.py`: kind50 raw sample comparison; status is a sample here.
- `tools/compare_custom_sampling.py`: compare repairs AND regressions on common
  launch cohorts. Detailed evidence: `captures/accuracy-20261018/`.

## Rejected hypothesis

Moving all DMACONR sampling to the 68000 granted slot improves the Copper pilot
from 41 to 23 differences, but introduces 33 BZERO-edge regressions and four
new handoff-record regressions. It is reverted, not committed. Exact candidate,
case IDs, per-field deltas and logs are linked in
[the experiment record](accuracy-experiments-2026-10-18.md).

## Next unresolved question

Physical bus-marker probes now isolate a repeated completion family: BBUSY
clears early and the Copper BFD completion marker is observed early. CPU
read-tail sampling and skipping the launch clock were insufficient; both
candidates are reverted. See
[the bus handoff](bus-marker-investigation-2026-10-19.md) for reference IDs,
source files, bounded traces, rejected hypotheses and the next bus-pressure
experiment. Do not repeat unchanged captures or retune a global delay.
The existing divider/IRQ cases match; broader operand/prefetch contention
needs new physical evidence after this bus question is resolved.

## Follow-up: physical CIA verification, 19 October

F2d batching consistency did not establish physical PB/serial accuracy. New
A500 measurements confirmed pulse polarity, START toggle reset, merged
zero-latch underflows, TA high-byte auto-start carries, and sixteen-underflow
serial completion differences. See
[the current hardware record](cia-hardware-verification-2026-10-19.md) and its
versioned v3/v4 reference packets. Earlier qualified IRQ/divider matches remain
useful neighbors; they do not imply that all CIA behavior matches hardware.
