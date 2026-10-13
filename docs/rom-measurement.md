# Standalone A500 timing ROM and RBCP capture

This ROM harness has completed three physical PAL A500 captures through OneROM
RBCP, as well as matching Copperline runs. See [hardware findings](rom-findings-2026-10-13.md).
Raw results remain under ignored `captures/`; never substitute emulator results
for a hardware capture.

The target is an original-speed 68000 A500 with 512 KB chip RAM. Slow RAM is
detected before using it; its absence produces explicit skipped IRQ records.
The ROM initializes the machine directly, copies its payload into chip RAM,
and runs without Kickstart. It does not access or write any disk.

## Experiments

Each trial starts with interrupts and DMA disabled, both CIAs stopped and their
ICRs acknowledged. The opposite CIA's timer B is loaded with 65535 and started
as a free-running reference. IRQ trials use CIA-B timer B as that reference.
The beam synchronizer waits for line 64 and horizontal position at least 32,
then adds the descriptor's number of NOPs. Launch beam and reference count are
recorded, together with end beam and reference count. These are *software*
timestamps, with the assembly logging instructions included in every trial.

The phase field is an injected NOP count, not a direct electrical E-clock phase
measurement. Beam polling, VPA synchronization and DMA may change its physical
phase. Compare actual timestamps and reference-counter ticks; matching the
phase index alone does not establish identical launch phase. Reference reads
use high/low/high retry to avoid torn 16-bit snapshots.

The timer snapshot is the low byte; all tested latches fit in that byte.
The count read and the end reference snapshot occur at different instructions.
Do not interpret reference_ticks as the exact count-write-to-count-read interval.

| Kind | Trials | Description |
|---|---:|---|
| 1 | 640 | CIA-A/B, timer A/B, START vs START+LOAD, five NOP offsets, eight read delays, two repeats |
| 2 | 320 | One-shot vs continuous, latches 0/1/3/15, five offsets and two repeats |
| 3 | 160 | Stop/restart, LOAD while running, stop/LOAD/restart, high-byte one-shot auto-start |
| 4 | 1280 | Enable mask after start, read near underflow, clear mask, and repeated acknowledgement; eight read delays |
| 10 | 3840 | CIA-A/B, paired CIAs and Copper SOFTINT; STOP/NOP/MOVEM load/MOVEM store/DIVU; chip/slow code; no/one/four bitplanes; sixteen offsets, two repeats |

DMA loads are disabled, one bitplane, or four bitplanes over the same display
window. Timer-only experiments do not enable interrupts. IRQ experiments enable
VERTB as a watchdog; the pending set is cleared immediately before launch.
Three vertical blanks without the expected event mark a timeout. Watchdog
interrupts are excluded from the source event count. Paired trials require both
level 6 and level 2 events. The first source event records its beam, vector
level and exception PC; a second event records its beam and level as well.

All measurement code runs in RAM. IRQ loop kernels are position-independent
and copied unchanged to slow RAM when available. Exception PCs are normalized
relative to the kernel block, making chip/slow comparisons meaningful.

## Build

```sh
python build_rom.py --vasm /path/to/vasmm68k_mot
```

On Windows the existing Ubuntu-24.04 assembler can be used with `--wsl` and
its `/mnt/...` path. Assembly is restricted to 68000 with optimizations off.
`build/rom/a500-timing-rom.bin` is the normal Amiga byte order for emulators.
`build/rom/a500-timing-rom-onerom.bin` is word-byte-swapped for OneROM.
`build/rom/manifest.json` contains the exact trial sequence, source fingerprint,
addresses, payload size and ROM hashes. Source fingerprints canonicalize CRLF
to LF, so a Git checkout on another OS retains the same identity.

The last sixteen ROM bytes contain interrupt vector words 24 through 31 at
`$FFFFF0..$FFFFFF`. They coexist with the RBCP command page, whose reads use
addresses to encode commands and discard the returned data. The first hardware
attempt with a zero-filled footer crashed on its first interrupt despite
correct RAM vectors; its exception capsules are retained separately. Copperline
did not expose that failure in its current autovector path. Do not remove these
ROM words or assume that a successful emulator boot validates ROM bus behavior.

Faults produce a separate checksum-protected `A5FAULT1` capsule containing the
exception vector, registers, raw stack, trial descriptor, live RAM vectors,
kernel bytes and variables. The collector writes `fault.bin` and `fault.json`
and fails explicitly. It never treats a fault capsule as completed measurements.

The pinned, unchanged MIT-licensed 68k RBCP library is in `vendor/rbcp`.
`src/rom/rbcp_config.s` is its Amiga terminal configuration. Neither generated
ROMs nor commercial ROM images are committed.

## Physical capture

Program the swapped ROM as a 27C400, with `force_16bit=true`, the USB and
host-control plugins, and `--reserve-pin sel_c`. Use `--reset-host sel_c` only
when that pin is physically connected to the reset line.

```sh
onerom firmware program --board fire-40-a \
  --slot file=build/rom/a500-timing-rom-onerom.bin,type=27C400,force_16bit=true \
  --plugin usb --plugin host-control --reserve-pin sel_c --reset-host sel_c
python collect_rom_usb.py --onerom /path/to/onerom --out captures/hardware-run1
```

Collection takes about 125 seconds on PAL, followed by USB transfer. The
screen is blue during collection, green during transmission and cyan after
successful transfer. Red is a CPU exception, magenta a transport failure.
The USB receiver must be open during transmission. It retains the raw transcript
and requires BEGIN/END framing, a matching source fingerprint and descriptor
sequence, a completed header and a valid additive 32-bit checksum. It rejects
partial or corrupted output and reports timeouts/skips rather than hiding them.

RBCP begins only after the full capture is buffered. USB transfer cannot change
the measurements already collected. Installing the host-control plugin does
not turn ordinary Kickstart into a measurement or terminal program.

## Emulator capture and result format

```sh
python run_rom.py --binary /path/to/copperline --config matched.toml --out captures/emulator-run1
python rom_results.py captures/hardware-run1/usb.txt --transcript --out captures/extracted --manifest build/rom/manifest.json
```

The emulator runs the same normal-order ROM and stops at `$020010`, immediately
after collection and checksum construction, before any RBCP command. Its RAM
capture is read through the control protocol. An exact PC breakpoint combined
with frame-based execution avoids slow per-instruction socket polling.

The 64-byte big-endian header is magic `A5RBCP01`, version and record size,
record count, total byte length, additive checksum, 32-byte source hash, raw
VPOSR, raw DENISEID, slow-RAM availability, and completion flag. Sum every
big-endian 32-bit word modulo 2**32: a complete capture sums to zero.

Each 40-byte record has twenty words:

`kind target variant phase delay repeat launch_beam launch_ref end_beam end_ref
counter icr irq_beam irq_level pc_hi pc_lo status aux second_counter_or_beam
second_icr_or_level`.

For timer kinds, target 0/1/2/3 selects CIA-A TA/TB, CIA-B TA/TB. Variant is
the table's mode index. Kind 2 uses delay as its latch; other timer kinds use
delay as post-write NOP count. For IRQ kind 10, target selects CIA-A, CIA-B,
paired CIA or Copper; variant selects the kernel in table order; delay bits
0-1 select DMA 0/1/2 and bit 2 selects slow code. Status 0 is normal, 1 timeout,
2 skipped due to unavailable slow RAM. IRQ aux is the source event count;
its final two words contain the last source event's beam and level. Timer
aux is INTREQR for kind 4; its final words are second counter and ICR snapshots.

Beam values require horizontal-wrap care; a naive subtraction at horizontal
0 or 1 may cross the pipelined beam register's wrap ambiguously. Results are
software observations, not direct IRQ/IPL pin traces or proof of every internal
latency. Controlled CNT-pin experiments and running LOAD's complete internal
pipeline are not inferred from these PHI2 tests.
