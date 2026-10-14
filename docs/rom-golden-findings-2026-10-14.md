# RAM timing probes over OneROM, 14 October 2026

PAL A500, 512 KB chip + 512 KB slow RAM, ECS Agnus 8372A (VPOSR `$a000`),
OCS Denise (raw ID `$ffff`). OneROM Fire-40-A 0.8.0 with USB 0.3.2 and
host-control 0.1.6; SEL_C resets the 68000. Data collection runs entirely in
RAM, then RBCP transfers a checksummed packet. No RBCP calls occur during
the measurements. Kickstart was backed up and restored with an identical
524288-byte live-ROM SHA-256:
`9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`.

## Reproduce

Build the original ROM harness with `build_rom.py --loads` or `--blits`,
plus the usual `--wsl --vasm /path/to/vasmm68k_mot` arguments. Load uses
1280 descriptors, blitter duration uses 540. Existing `run_rom.py` and
`collect_rom_usb.py` read `build/rom/manifest.json`.

`build_golden_rom.py --copperline ../Copperline --suite timing --repeats 8`
uses the same assembler options and wraps Copperline `timing-test/test.bin`
at its original `$30000`
address. Copy its two ROM files and manifest from `build/golden` into
`build/rom` before running the existing collectors. `--suite blitter
--repeats 16` runs `bltprobe-pace.bin`. Additional suites `divu --repeats 14`
and `copper --repeats 32` vary the final DIVU display plane count and the
Copper polling-loop phase respectively.

The wrapper lives at `$8000`, below the programs' scratch buffers. The
original timing program is intercepted only after its 32 values have been
measured, replacing the first rendering instruction with TRAP #15. The
blitter program's drawbar entry logs raw loop counts after polling, using
TRAP #14, and its final idle branch becomes TRAP #15. That logging changes
the next blit's launch phase; compare the same instrumented ROM on both
machines rather than treating its rendered bars as phase-independent.

For the DIVU sweep, the final row's BPLCON0 immediate is modified in RAM
before each run, cycling through zero to six planes. The Copper sweep replaces
the optimized MOVEQ/SWAP timeout initialization with a JSR to a RAM stub
that restores the same timeout and varies NOP/DBRA delay before polling.
These two diagnostic mutations are additional to the collection hooks.

Compare validated packets with:

```text
python compare_golden_rom.py captures/rom-amiga500-loads1 captures/rom-copperline-loads-after --out loads.json
```

Kind 15 stores an original 32-bit measurement as `(icr << 16) | counter`.
Here `icr` is a data field, not a CIA interrupt register; blitter width is
in `aux`. Kind 16 records live low count in `counter`, fully stopped count
in `aux`. Kind 17 records launch and completion beam positions; target is
D-only / AD fill / line, variant is STOP / normal polling / BLTPRI polling,
and delay is blit height. PAL elapsed time is `227*Δv + Δh`. Reject ambiguous
VHPOSR samples at horizontal wrap before fitting a duration: one sample can
appear a line short even when the blitter and IRQ completed correctly.

## Captures and provenance

Every hardware capture contains `results.bin`, decoded JSON/CSV, USB text,
the capture-time manifest and `source-snapshot.zip`. The archive includes
the exact builder, assembler sources, pinned RBCP includes and generated
ROM. Captures and generated ROMs remain local ignored assets.

| Capture suffix (`rom-amiga500-`) | Records | Source ID |
| --- | ---: | --- |
| golden-timing1 | 256 | `7b7ea959e3b4a932fe4693b4b35d667fd89b4d013affd4d9b74c841c64a8b3bd` |
| golden-blitter1 | 80 | `86a422e5595ae3a2ce04de1415566582ba69fb6348ff8fff0fdb6477faf9e4b3` |
| loads1 | 1280 | `39dd1ae5417db13e3b5b769468067ef712673ffbf0fa51f2b81710e67e8c279c` |
| divu1 | 448 | `0e2e226b0f55b570d3d0e41e5863171081969f6e1d2aee5c5352946556c0b65b` |
| copper1 | 1024 | `ab1d02ab544e9f60f7812132e5c856bd461efcc07a6833a10aebc4056848a093` |
| blits1 | 540 | `fc66d05230da8eb222225e1e1837055e80b8db90f3e95570ac02c23fc9f37a76` |

All 3628 hardware records were received without capture faults, timeouts or
skipped descriptors. Failed early emulator preflights with a wrapper at
`$20000` are not evidence: a measured clear overwrote that wrapper. The
corrected `$8000` layout completed on both emulator and hardware.

## CIA FORCE LOAD while running

The original stopwatch's first row agrees, but later steady rows initially
read three E-clocks too high. Its TAHI write auto-starts a stopped one-shot
timer before CRA `$19`. Copperline applied the three-edge LOAD hold only
on a START transition, so an already-running timer decremented three extra
times after the force reload.

The focused experiment tests both timers of both CIAs, START-only controls
and START+LOAD, five launch phases, sixteen read delays, two repetitions.
All 640 LOAD samples initially read exactly three counts too low. Applying
the same three-edge hold to running LOAD makes **all 640 live and stopped
counter pairs match the hardware exactly**. START-only controls remain
phase-dependent and are not a whole-record equality test.

## Blitter slowdown counter

The 220×22-word D-only clear with a stopped CPU measures 9898–9899 clocks on
hardware and 9902–9904 in Copperline. Its ordinary polling control instead
measures 9923–9934 versus 9876–9890. This isolates most of the discrepancy
to CPU arbitration, rather than a wrong blit slope.

Copperline discarded denied CPU slots when the blitter pipeline was in a
disabled-channel gap or empty destination phase, even if refresh/fixed DMA
had denied the CPU. Counting actual misses independently of blitter phase
makes ordinary polling measure 9925–9935. STOP and BLTPRI control durations are
identical before and after the fix (one launch/completion pair shifts together
by two clocks). The original timing-table clear
also moves into the hardware's phase-dependent range. This is a generic
CPU starvation-counter correction, not a per-blit elapsed-time adjustment.

## Copper polling phase

The original table reports `$643a` on hardware versus `$642c` in Copperline.
After sweeping the polling-loop phase, both machines report the same low
beam values: 38, 40, 44, 51, 58. Frequencies differ, but there is no separate
fixed 14-clock interrupt offset to add. The STOP latency measurements and
busy-poll detection times must not be conflated.

## Remaining constraints

The 64-iteration DIVU row with six bitplanes measures 5015 clocks on hardware
versus 4824 in Copperline. With zero planes, hardware 4526–4530 overlaps
Copperline 4522–4526. A trial moving the DIVU prefetch after its internal
clocks worsened the six-plane result to 4778 and was discarded. This is
a CPU/DMA bus-phase investigation, not evidence for increasing DIVU's
uncontended instruction cycle count.

Small stopped-CPU/fill/line readback differences remain. Their register
access, IRQ-entry and beam-read contributions have not yet been separated
enough to justify changing blitter startup or completion constants. Golden
PNGs remain emulator-generated regression references; these RAM captures
do not validate analogue video output or AGA behavior.

The wrapper and capture tools are MIT licensed. The original RAM test programs
retain Copperline's GPL-3.0-or-later license; generated ROMs contain those
programs and are local build artifacts.
