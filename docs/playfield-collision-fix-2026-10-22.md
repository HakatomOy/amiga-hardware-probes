# A500 playfield collision correction

## Result and scope

Copperline's unfinished Init work is isolated on `wip/init-copper-timing` at
`02318e9e`. The collision correction remains on `fix/a500-hardware-timing`.
Accepted collision commit: `7bbedf58`.
It uses CLXCON match values in both playfield modes, models the initial zero
comparison and captured lores data placement, and gives match-register writes
their own two-CCK comparator delay and absolute coordinate. CPU read timing is
unchanged. Gated first/last-bit tests distinguish this model from the rejected
uniform four-CCK delay. Other image-rendering calibration remains separate.

## Hardware evidence and validation

Each new reference has two independent A500 captures and two repeats per case.
Every finite-Copper completion witness passes; second samples are zero.

| Reference | Cases | Corrected replay |
| --- | ---: | ---: |
| `playfield-gate-v1` | 1024 | 1024 matches |
| `playfield-word-gate-v1` | 768 | 768 matches |
| `playfield-early-clear-v1` | 512 | 512 matches;328 pre-fix differences repaired |

No exclusions, invalid captures or conflicting collision observations in those
suites. Nine older suites,8416 cases, retain byte-identical packets, including
281 qualified pointer and438 qualified Copper collision cases. Existing CIA,
bus and startup quality gaps are preserved, not counted as matches.

## Remaining uncertainty

The original `playfield-modes.json` still fails its unchanged512-match floor:
488 match and24 mismatch. All remaining cases use plane pattern2; Copperline's
clear bracket is443C instead of A5004438 for the same424E observer entry. The
clear crosses the brief zero interval. The earlier-clear experiment independently
validates logic without concealing this failure. Ungated burst/window diagnostics
also retain CPU timing differences; do not align their samples or fit a blanket
IRQ or collision delay. Next: identify the first CPU/DMA grant difference in that
specific polling/clear cohort. A smaller startup pulse remains a competitor.

## Reuse

- Run `tools/experiment.py run experiments/workflows/playfield-early-clear.json`
  with a new `--out` path for scoped focused/neighbor/broad validation.
- `tools/playfield_gate_report.py PACKET --out REPORT.json` returns bounded
  sweep patterns; detailed case IDs stay in the report.
- `tools/playfield_gate_fixture.py GATE_RUN WORD_RUN --out FIXTURE.csv` exports
  the896 consensus cases, rejecting missing repeats, conflicts or failed controls.
- Short restart record: `investigations/playfield-collision-fix.json`. Detailed
  findings/rejected models: `docs/playfield-modes-2026-10-22.md`. Full logs and
  immutable executables: `captures/collision-clean-20261022/`.

All live sessions ended with original-ROM restoration verified. The documented
scope covers measured classic lores DMA behavior; AGA, hires, manual bitplane
and sprite-edge timing require their own hardware evidence.

Final checks:3670 Rust core tests pass,37 ignored and559 window tests filtered;
strict Clippy, formatting and361 probe-tool tests pass. MyST is unavailable on
this machine, so documentation HTML/PDF builds were not run.
