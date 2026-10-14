# Continuous timer isolation with OneROM, 13?14 October 2026

Measurements used OneROM Fire 40 A on the user's real PAL A500, 512 KB chip
and 512 KB slow RAM. All timed code runs in RAM, DMA and interrupts are
masked, and RBCP is used only after collection. The five physical packets
contain 18000 completed trials, with no timeouts or skipped cases.

## What the original +/-1 comparison could not establish

The original kind-2 period probe read a running timer. Its reference interval
starts before timer programming and ends after additional target reads; equal
whole-interval elapsed values do not identify the first target read's E-clock
phase. The new suites freeze references and record underflows, avoiding that
ambiguity. The continuous reload cadence is latch + 1; a stopped counter
follows that arithmetic. The real readout difference occurs at the zero/reload
slot: running synchronized reads return the reload value instead of zero.

The old 160 continuous rows still contain 27 raw +/-1 differences after the
fix, including three pairs with equal old reference intervals. Those are not
used as phase-aligned accuracy tests. The properly bracketed measurements
below have no matched-clock counter discrepancies. No arbitrary +/-1 counter
correction or per-program tuning was added.

## Suites and result contracts

- `--continuous`: 5976 trials. Kind 6 freezes target and two PHI2 references;
  kind 7 uses a same-CIA TB cascade reference; kind 8 adds a non-overflowing
  DIVU (`$0001fedc / $1234`); kind 9 freezes the other-CIA reference immediately
  after the live target read; kind 12 checks one-shot underflows.
- `--modes`: 600 kind-13 trials on both TBs. Variants switch PHI2 to stopped
  CNT, stopped TA, running TA, running TA to PHI2, or stop without changing
  source. `aux` is the last running count; `counter` and word 18 are stopped
  target counts. The old emulator applied source changes two E-clocks early.
- `--pulses`: 1728 kind-14 trials. The repeat field selects START, START+LOAD,
  one-shot START or one-shot START+LOAD. `aux` is the first TB cascade count,
  word 19 the final cascade count, `counter` a live TA count, word 18 the frozen
  TA count, and `icr` the sampled CRA control bits. Early versus late snapshots
  distinguish cascade propagation from a missing or extra underflow.
- `--reads`: 6240 kind-9 trials. Sweep NOP delays 0..63 and 127 on all four
  timers, with latches 1, 3, 15 and 200 and three launch phases, twice each.

All packets keep the established 64-byte header and 40-byte records. For
continuous kinds, `aux` is the frozen paired timer's 16-bit count and word 19
is its second frozen read. Kind 9 retains the live target count in `counter`;
other continuous kinds store a frozen target count there. Word 18 is always
the second/frozen target read. `reference_ticks` uses the frozen other-CIA TB.
Timer B's cascade input is preserved when stopping that reference (`$40`),
so a source change cannot contaminate the underflow count.

An initial 3456-trial suite (`rom-amiga500-continuous1`) intentionally stopped
the cascade reference with `$00`, revealing the input-source pipeline issue.
The refined suite preserves `$40`. Exact source snapshots are archived beside
the physical packets; generated ROMs/firmware and captures remain ignored.

## Hardware and fixed-emulator comparisons

| Hardware capture | Fixed emulator capture | Source ID | Matched E-clock durations | Counter/control mismatches |
|---|---|---|---:|---:|
| rom-amiga500-continuous2 | rom-copperline-continuous-fixed2 | 6db7d85b1393869349e5ba9354ee37c30b46b688d496447461e2ff4a129187e9 | 5975 / 5976 | 0 |
| rom-amiga500-modes1 | rom-copperline-modes-fixed2 | 8e389cda62ed90a2e8eb48d7066c4608257ad771e161dd44045da857b5a1479a | 595 / 600 | 0 |
| rom-amiga500-pulses1 | rom-copperline-pulses-fixed2 | 4a23bb26ce945c6543a139101913a5b721445cf746cf855839395faf3e2c8830 | 1616 / 1728 | 0 |
| rom-amiga500-reads1 | rom-copperline-reads-fixed2 | 08c6f2272feaf8bb72d9138b9f4171d8834a22ea48b7d4a3129e7993b6236942 | 5316 / 6240 | 0 |

Each comparison's JSON report is beside the emulator packet. The validator
requires matching source IDs, lengths, descriptors, checksums and completed
successful trials. It compares samples having equal frozen E-clock duration.
Kind 14 also compares CRA bits 0/3; other kinds compare timer ICR bits 0/1.
Keyboard SP status is excluded from the timing criterion. Different E-clock
durations are reported rather than silently treated as timer errors.

For the dense read suite, all 1560 latch-200 controls yield the same calibration
on each machine: `N = reference_ticks - 13`. The offset 13 is instrument overhead,
not a hardware latency constant. For latch L, calculate internal count
`C = (L - N) modulo (L + 1)`; the transfer reads L when C is zero, otherwise C.
This predicts all 6240 hardware values and all 6240 emulator values independently.
The hardware zero-slot samples are 735 at latch 1, 347 at latch 3 and 60 at
latch 15; every one reads the reload value. Freezing preserves actual zero
counter states, so changing the reload period to suppress zero would be wrong.

The pulse suite shows a one-E-clock delay from TA underflow to TB counting.
For zero START+LOAD, carry is generated on the last LOAD stage; the cascade
receives it one edge later. A plain START has no such LOAD carry. The long
DIVU suite exposes lost latch-zero underflows in batched emulator updates.
The source-transition suite measures two old-source edges after control writes.
The one-shot suite catches pending underflows whose one-shot qualifier was
previously cleared too early by a STOP write.

## Copperline changes and regression checks

Copperline now models the reload readout mux, delayed source/one-shot control
qualifiers, one-edge cascade propagation, zero LOAD carry, complete batched
underflow counts, and one-shot stopping at the first underflow. Pending control
and pulse state are serialized, and STOP predictions include queued cascade
underflows. The Paula latency and CPU STOP polling calibration are unchanged.

The original ROM (`891dccc...`) still matches all 640 fresh-start counters,
160 transitions, 1280 ICR-race counters and 160 one-shot period counters.
Its 128 bitplane-DMA Copper/STOP latency samples still match hardware exactly.
The earlier sparse continuous snapshot comparison is retained with its limitations.

Run a comparison with:

```powershell
python compare_continuous.py captures/rom-amiga500-continuous2/results.bin captures/rom-copperline-continuous-fixed2/results.bin --out comparison.json
```

Kickstart was restored with USB and host-control plugins retained. Its live
512 KiB ROM SHA-256 matches the original:
`9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`.
