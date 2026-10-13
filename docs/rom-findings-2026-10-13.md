# A500 ROM probe findings, 13 October 2026

Three physical captures completed through OneROM RBCP: **18,720 records total,
zero timeouts and zero skipped trials**. Each capture contains 6,240 trials,
with two repeats per parameter combination. The source-matched Copperline
captures also completed with zero timeouts/skips. This validates the transport
and executed scenarios; it does not prove every CIA or CPU timing case.

Hardware: PAL A500, original-speed 68000, 512 KB chip + 512 KB slow RAM,
OneROM Fire 40 A firmware 0.8.0, USB 0.3.2 and host-control 0.1.6.
Board and CIA silicon revisions remain unconfirmed. The final raw chip reads
were VPOSR `a000` and DENISEID `ffff`.
The raw DENISEID may float on OCS and is not a reliable revision identifier.

## Captures and reproducibility

- `captures/rom-amiga500-run2/` and `captures/rom-amiga500-run3/`: independent
  resets of the first corrected measurement ROM, source fingerprint
  `58e1f88f66d2fa1d6e4799b6f2f9bed034c28dc845d4428a67591fcd47ca7746`.
- `captures/rom-copperline-final1/`: matching emulator baseline.
- `captures/rom-amiga500-final/`: final build with canonical LF source hashing;
  measurement instructions are unchanged, while the embedded source ID changed.
- `captures/rom-copperline-final2/`: source-matched final emulator baseline.
- Final source fingerprint: `891dcccda24a94ec28d2de5750408df66f31a9aa4c0605b0fb1edfba9c81c5c4`.
- Normal-order ROM SHA-256: `605d02f74099fba36e431fecabc13f553e9bb798c136244638cf1bfe56b3d175`.
- Final hardware result SHA-256: `5aa0a4ffd62e3804848eba93d954c47929625b85f4e8337fdc2640efddacfd62`.
- Final emulator result SHA-256: `25d2ef44f1151960183ccc0879c9d697fa7f43f1ea028cbc3f53ad028d1edad2`.

Each successful folder holds the raw USB transcript or emulator RAM capture,
validated binary, JSON/CSV records and its build manifest. Comparisons are in
`copperline-comparison.json` and `.md`. The run3 folder also has the independent
hardware repeat comparison. A source snapshot for the initial corrected build
is retained in the run2 folder. Generated binaries, logs and captures are ignored
by Git; they include private machine-specific material and are not distributable
source assets.

## Repeatable discrepancies and next investigations

| Observation | Physical A500 | Copperline | Evidence |
|---|---|---|---|
| Fresh START/START+LOAD timer snapshots | Reference values | All 640 counter snapshots match per capture | Both CIAs, both timers, multiple NOP/read delays; all three runs |
| Stop/restart without LOAD | Counter 8 | Counter 10 | All 40 transition records per capture; discrepancy remains on matching reference-tick subsets |
| High-byte one-shot auto-start | Counter 35 | Counter 34 | All 40 records per capture; reference ticks match exactly |
| ICR read after interrupt-mask clear | IR bit 7 remains set | IR bit 7 cleared | All 320 records per capture; counter/source behavior otherwise observed separately |
| Copper/STOP, DMA off, chip code | 37 CCK in 10 samples, 38 in 22 | 37 CCK in all 32 | Identical distributions across all three captures |

Counter differences use countdown values: a larger emulator value means fewer
decrements occurred before the snapshot. Two missing decrements are consistent
with an unmodeled stop/count-enable pipeline, but this stop/restart experiment
alone does not isolate stop latency from restart behavior. A stop-only delay
sweep would distinguish those mechanisms. The high-byte result constrains
auto-start/load staging. The ICR result constrains the latched IR readback after
mask changes; it does not measure the electrical IRQ pin's deassertion edge.
Other ICR bits can include keyboard serial activity, so IR-bit comparisons are
reported separately from equality of the entire ICR byte.

The Copper/STOP result exposes a one-CCK geometry/phase residual that the older
ADF probe did not: that older probe measured 37 for all 32 phases. Do not simply
increase the global IRQ delay to fit this new geometry. CPU recognition/poll
phase and the ROM acknowledge path need separate tests. These captures use
OneROM; extrapolating its ROM-bus observations to every board/ROM setup requires
additional confirmation.

Continuous period tests also contain +/-1 counter differences around reload.
Raw NOP phase indices are not exact electrical E-clock phase labels. The
reference timer snapshots include their own CIA read cycles, and launch/IRQ
beam reads at horizontal 0/1 are excluded from elapsed-error statistics because
of wrap ambiguity. Use the full instruction sequence and matched metadata,
rather than treating whole-record equality as an accuracy score.

## Hardware-only ROM bring-up failure

The initial ROM had zeros in its final sixteen bytes. It passed emulator
collection but the physical A500 crashed on its first CIA interrupt. Valid RBCP
fault capsules showed illegal execution at `$003020`, with correct RAM vectors
and kernel bytes. Supplying interrupt vector words 24 through 31 at
`$FFFFF0..$FFFFFF` resolved the failure; all subsequent full captures succeeded.
The original failed attempt and two diagnostic capsules remain separate under
`captures/rom-amiga500-run1/`, `rom-amiga500-fault-debug/` and
`rom-amiga500-fault-debug2/`. They are not counted as timing captures.

Copperline's current `CpuBus::interrupt_acknowledge` supplies an autovector.
Its successful run of the zero-footer ROM therefore did not validate the
physical ROM interrupt-acknowledge data behavior seen on this OneROM-equipped
A500. This is a distinct compatibility observation, not a reason to retune CIA
latency constants.

## Checks and final device state

- Twelve probe tests pass, including incomplete/corrupt-frame rejection,
  fault-capsule rejection, trial coverage and interrupt footer checks.
- The final ROM rebuild after LF-normalizing the source is byte-identical.
- Both final hardware and emulator packets pass checksum, source ID, length,
  completion and descriptor-order checks.
- Kickstart 1.3 was restored with USB/RBCP plugins and SEL_C reservation retained.
  Its live 512 KiB image matches the original SHA-256
  `9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`.

The new build and capture tools are documented in [ROM measurements](rom-measurement.md).
No Copperline timing changes are made by this probe extension; the measurements
identify specific follow-up fixes and the tests needed to validate them.
