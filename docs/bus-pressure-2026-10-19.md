# Copper start pipeline: investigation record

Accepted Copperline fix: `1d0df48a` (`fix/cia-timings`).

## Confirmed facts and implementation

A500 hardware shows later Copper-launched BBUSY deassertion and BFD completion
markers than accepted Copperline `3b43225c`. Pressure substitutions retain the
marker difference. Two independent onset runs agree on all 2176 qualified
observations. A split start path fits the measured data: busy asserts two colour
clocks after Copper size data fetch; engine/zero reset begins after four.
CPU write timing and custom-read sampling remain unchanged. Pending pipeline
clocks serialize, affect predictions, advance without DMA, and drain on forced
completion. These are model phases inferred from bracketed observations.

## References and validation

Versioned captures: `references/bus-pressure-v2-run1`,
`bus-onset-v1-run{1,2}`, `bus-phasepad-v1-run1`,
`bus-phase-entry-v1-run1`, and `bus-phase-completion-v1-run1`. Each manifest
identifies ROM/source/result hashes, configuration, repeatability and capture
method. All physical runs restore the original ROM and verify reset release.

| Split candidate profile | Matches / comparable | Excluded brackets |
| --- | ---: | ---: |
| Marker | 370 / 370 | 14 |
| Completion | 576 / 576 | 64 |
| Pressure | 724 / 724 | 44 |
| Onset | 2175 / 2176 | 0 |
| Phase padding | 653 / 653 | 115 |
| Phase entry | 1551 / 1551 | 241 |
| Dense phase completion | 1543 / 1543 | 249 |
| Held-out Copper busy | 526 / 526 | 2 |

No trace alignment: exact descriptor/configuration and measured beam brackets,
with stable repeated hardware observations. Counts are candidate observations;
hardware observations may be reused. Common onset cohort:1965 eligible,
181 repaired,0 regressions. Held-out common Copper busy:449 eligible,41 repaired,
0 regressions. CPU handoff remains1238 mismatches/2304; BZERO edges4608/4608
match. Detailed reports/logs: `captures/bus-pressure-20261019/split-*`.

Checks:186 probe tests,2766 non-network library tests, production Blitter model,
strict all-target/all-feature Clippy and formatting pass. Held-out CIA output
matches2063 qualified cases (209 different underflow brackets); IRQ kind51
matches67 exact-launch cases (1469 different launches); focused IRQ2212/2212
and divider2560/2560 match. Optimized validation with window tests excluded passes3629 tests,37 ignored,
548 filtered, including all netplay tests. Command:
`python tools/cargo_report.py -- test --locked --profile ci --lib -- --skip video::window::`.
The full optimized library run has4169 passes,43 ignored and two failures:
`video::window::tests::numpad_mapping_stands_in_for_the_missing_gamepad` and
`video::window::scaler::tests::picture_draws_match_the_composed_texture`.
The former assumes no physical gamepad; the latter reports a SharpBilinear
texture difference of3/255. These exercise input/window/GPU paths outside the
changed start pipeline; do not report the full suite as passing. Earlier
unoptimized netplay timeouts disappear in optimized validation. Final core log:
`captures/bus-pressure-20261019/cargo/20261019-141618-a88zvbki`; full-suite log:
`captures/bus-pressure-20261019/cargo/20261019-140951-jebp1wch`.
The phase-control suites are available through `tools/replay_accuracy.py` as
`bus-phasepad`, `bus-phase-entry`, and `bus-phase-completion`, and their new
CLI routes reproduce the above results.

## Rejected explanations

Global grant/pre-grant sampling changes break CPU controls. A parity-only
busy-clear latch breaks seven CPU controls. A single two-clock start delay
leaves early completion; four clocks for both stages delays busy assertion.
Evidence and exact rejected patches remain in the capture root. Trace frame
mapping must derive from its first START; captures have different initial frames.
Four-clock onset trace is byte-identical to its untraced packet.

## Next unresolved question

Only initial onset case `55:0:0:0:0:0` differs in BZERO (HW4000/emulator6000,
read1). Baseline also returns6000 but has a different ending bracket. The ROM
does not prime the initial accumulator. Leading hypothesis: warm-reset retained
hardware state differs from emulator construction; competitor: first-start zero
phase. A deliberately nonzero priming blit before the measurement distinguishes
them: disappearance supports preconditioning; persistence requires a smaller
zero-phase experiment. Do not change reset behavior from this packet alone.
CPU register-handoff is the next separate family; preserve its existing evidence.

## Tools and source

`build_bus_marker_rom.py`, `compare_bus_marker.py --cohorts`,
`tools/replay_accuracy.py`, `tools/trace_bus_marker.py`,
`tools/compare_custom_sampling.py`, and `tools/run_onerom_live.py`.
Copperline: `src/bus/custom_regs.rs`, `src/bus/dma_slots.rs`,
`src/chipset/blitter.rs`, `src/bus/tests.rs`.
Historical hypotheses, discarded candidates and experiment chronology:
[history](bus-pressure-history-2026-10-19.md). The saved four-clock patch in
`experiments/copper-start-strobe-wip.patch` is rejected WIP, not the accepted split.
