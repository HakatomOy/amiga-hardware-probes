# A500 IRQ probe disk

A standalone, reproducibly built bootable ADF for measuring interrupt behavior
on an unaccelerated Amiga 500 with a 68000. It buffers measurements in chip RAM,
then writes them to reserved sectors of the **same disk image**, flushes the
trackdisk cache, invalidates it, and reads the data back before declaring success.
FlashFloppy's normal writable ADF support is sufficient. No Workbench disk,
filesystem, Amiga SDK, commercial compiler, or included Kickstart is needed.

This collects software observations, not electrical pin traces. The measurements
can constrain an emulator's CIA, Paula and 68000 interrupt timing together. They
do not by themselves distinguish every internal propagation delay or prove that
one constant latency is correct for all instructions. The IRQ handlers and their
logging instructions are part of the experiment and must run unchanged in the
emulator. See [the measurement contract](docs/measurement.md).

## Build

Requires Python 3.9+, and the Motorola-syntax vasm assembler, `vasmm68k_mot`.
All Amiga program and disk-building source is in this repository. No generated
program binaries or disk images are committed. The optional setup helper downloads
a pinned assembler dependency into ignored `.tools/`; vasm has its own license.

On this Windows machine, with Ubuntu-24.04 WSL and GCC/make installed:

```powershell
python tools/setup_vasm.py --wsl
python build.py --wsl --vasm /mnt/c/Users/seppo/amiga/a500-irq-probe/.tools/vasm/vasmm68k_mot
python -m unittest discover -s tests -v
```

The setup helper prints the build command for the actual checkout path. On Linux:

```sh
python3 tools/setup_vasm.py
python3 build.py --vasm .tools/vasm/vasmm68k_mot
python3 -m unittest discover -s tests -v
```

An existing native Windows assembler also works:

```powershell
python build.py --vasm C:/path/to/vasmm68k_mot.exe
```

The output is `build/a500-irq-probe.adf` (901120 bytes). `build/manifest.json`
records the source fingerprint, image hash and program size; the assembler
listings contain the relative instruction addresses used in saved exception PCs.
Assembly is restricted to the 68000, with optimization disabled explicitly.
Use the pinned assembler revision for identical binaries across machines.

## Run on your A500 / Gotek

1. Keep the generated ADF as a clean master. Copy it to the Gotek's USB drive
   under a new name, such as `IRQ-A500-RUN1.adf`.
2. Make that image writable: disable FlashFloppy write protection and ensure
   the USB storage/image is writable. Select it in DF0, then reset the A500.
3. During collection the screen is blue. Normal runs take roughly 20–40 seconds
   including loading and disk I/O. Disk writes happen only after collection.
4. Amber means writing; purple means reading the results back. A green screen
   saying **RESULTS SAVED AND VERIFIED** means the bytes were read back correctly.
   A red error screen means failure; it does not indicate a successful capture.
5. Wait for the Gotek/USB activity to become idle, then power off the A500
   before removing the USB drive. Copy that modified ADF back to your PC.
6. Repeat with a fresh copy of the master, preserving each previous capture.

Use a dedicated copy of this test image. It is a raw boot disk, **not an AmigaDOS
volume**: do not format it, run disk-repair tools on it, or expect Workbench to
show a results file. Rebooting it overwrites its previous measurements. It does
not write to other disks or hard drives, and the reserved result area cannot
overlap the boot loader or program.

The intended target is an original-speed 68000 A500 with at least 512 KB chip
RAM, Kickstart 1.3, and PAL or NTSC video. CPU models indicated as 68010 or later
in Exec AttnFlags are rejected. Disable accelerators/turbo modes even if they
report themselves as a 68000. Actual hardware/FlashFloppy execution still needs
your first run; emulator verification is not hardware validation.

Record the A500 board revision, Agnus/Denise/CIA markings where known, PAL/NTSC,
memory expansions, Kickstart, and FlashFloppy version in your capture label.
The program stores raw chip ID registers and the Exec version itself; OCS
Denise's ID register can float and cannot identify its revision reliably.

## Extract and compare

```powershell
python results.py extract captures/IRQ-A500-RUN1.adf --out captures/a500-run1 --label "PAL A500; board ...; CIA ...; 512K chip + 512K slow; KS1.3; FF ..."
python results.py extract captures/IRQ-A500-RUN2.adf --out captures/a500-run2 --label "same hardware, second run"
python results.py compare captures/IRQ-A500-RUN1.adf captures/IRQ-A500-RUN2.adf --out captures/hardware-repeat.json
```

Extraction produces JSON and CSV. It rejects missing, incomplete, unsupported,
or checksum-damaged results. Comparisons require identical source fingerprints.
Timeouts are saved as observations and counted; a green disk-success screen does
not mean every interrupt arrived. Check the extraction's timeout count.

## Run the identical disk in Copperline

Supply your own ROM and executable; neither is copied into this repository.
The runner creates a new writable image and explicit OCS/68000 configuration,
runs 45 emulated seconds, saves a screenshot, validates all records, and checks
that the guest modified only the reserved result sectors. It refuses to replace
an existing capture. It removes inherited debug/IRQ latency overrides from the
child process so the default run uses Copperline's default interrupt timing.

```powershell
python run_copperline.py --exe ../Copperline/target/release/copperline.exe --rom "H:/Amiga_HW/byteswapped_roms/Kickstart v1.3 rev 34.5 (1987)(Commodore)(A500-A1000-A2000-CDTV).bin" --out captures/copperline-default
python results.py compare captures/IRQ-A500-RUN1.adf captures/copperline-default/capture.adf --out captures/hardware-vs-copperline.json
```

Use `--slow 0` for a machine without the trapdoor expansion. Match the actual
hardware's configuration when interpreting measurements. Use `--video NTSC` for
an NTSC machine (the runner defaults to PAL). `--irq-latency 2` is available only as a
diagnostic experiment; it is **not a proposed hardware-correct value**.

For useful evidence, first compare repeated hardware runs, then repeated
emulator runs, then compare hardware with the emulator. A full record comparison
includes beam phase and data-dependent instruction state; inspect the differences
instead of reducing them to a single latency number.

`--write-protected` runs a negative storage test: the image must stay unchanged
and the screenshot should show the red error screen. It is not a timing capture.

## Project layout

- `src/boot.asm`: Kickstart boot block; dynamically allocates chip RAM and loads
  the position-independent program with the existing boot I/O request.
- `src/probe.asm`: takeover, timing kernels, IRQ recording, hardware restoration,
  result writes/readback, and screen status.
- `build.py`: generated constants, original status font, checksummed boot block,
  ADF layout, source fingerprint and manifest.
- `results.py`: validation, JSON/CSV extraction, record-by-record comparisons.
- `run_copperline.py`: deterministic emulator verification of a fresh image.
- `tests/test_formats.py`: disk layout and capture integrity tests.
- `tools/setup_vasm.py`: optional pinned assembler installation.

References: [FlashFloppy ADF write support](https://github.com/keirf/flashfloppy/blob/master/src/image/adf.c),
[Amiga Exec Supervisor contract](https://amigadev.elowar.com/read/ADCD_2.1/Includes_and_Autodocs_2._guide/node059D.html),
[vAmiga interrupt hardware experiments](https://github.com/dirkwhoffmann/vAmiga/issues/274).

See [local validation results](docs/validation.md) for the tested build and
emulator configurations. Hardware reference results remain to be collected.
