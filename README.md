# Amiga hardware probes

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

## Compare captures with a compact report

Use [`compare_captures.py`](docs/capture-comparison.md) to summarize A500,
Copperline, and optional WinUAE RBCP captures before inspecting individual rows.
It reports counts, repeated difference patterns, representative case IDs, and
exact-start CIA/IRQ cohorts. Retrieve specific evidence with `--case` and
`--window`; matching rows do not need manual review. The workflow documents
units, integrity checks, trace inputs, and interpretation limits.

## Build

Requires Python 3.9+, and the Motorola-syntax vasm assembler, `vasmm68k_mot`.
All Amiga program and disk-building source is in this repository. No generated
program binaries or disk images are committed. The optional setup helper downloads
a pinned assembler dependency into ignored `.tools/`; vasm has its own license.

On this Windows machine, with Ubuntu-24.04 WSL and GCC/make installed:

```powershell
python tools/setup_vasm.py --wsl
python build.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot
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
3. During collection the screen is blue. Normal runs take roughly 20â€“40 seconds
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
report themselves as a 68000. Real A500 captures have been collected; emulator verification alone is not
hardware validation.

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
emulator configurations. Standalone ROM hardware measurements are linked below.

## Standalone ROM experiments over One ROM USB

The expanded 68000 ROM harness collects 6,240 CIA and IRQ trials in RAM, then
transfers a checksum-protected capture using RBCP. See
[ROM measurements and capture instructions](docs/rom-measurement.md).
The original ADF build and its capture format are unchanged.

[Hardware findings from the RBCP runs](docs/rom-findings-2026-10-13.md) document
repeatable timer and ICR differences, capture provenance and the ROM footer fix.

[RAM timing-probe measurements on 14 October](docs/rom-golden-findings-2026-10-14.md)
cover repeated FORCE LOAD, stopped/polling blitter duration, DIVU display
contention and Copper polling phase. `build_golden_rom.py` wraps the committed
Copperline RAM programs; `compare_golden_rom.py` validates and compares captures.

Focused standalone ROM matrices for aligned CPU/DMA, observer and interrupt
timing are built with `build_rom.py`. These commands build the native and
Copper-generated STOP/IRQ trials and the line-mode BZERO plus destination-memory
matrix (2,560 rows):

```powershell
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --irq-paths
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --bzero-line
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-logic
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-logic-fine
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-logic-followup
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-pipeline
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-truth-table
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-stage
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-b-hold
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-b-hold-dma
python build_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --line-b-mask
```

`--line-logic` builds kind 25 (3,456 trials): line minterms `$00/$ff/$ca/$f0`,
A data `$0000/$8000`, B data `$0000/$ffff/$1000`, initial C data `$0000/$ffff`,
USEB disabled/enabled, and 1/2/22 pixel lines. It samples DMACONR and beam position
before waiting for BBUSY, then checks the destination OR and selected words after
completion. Every source and destination area is initialized independently.

`--line-logic-fine` builds kind 26 (544 trials) for the measured BZERO discrepancy:
minterm `$CA`, BLTADAT `$8000`, zero C data, B data `$0000/$1000`, USEB off/on,
and 2/22 pixel lines. BLTAPT is initialized to signed `-80`. It samples every
integer NOP delay from 0 through 16 with NOP/EXG phase pads and BLTPRI off/on,
then records the same post-completion memory checks. The combined phase and delay
samples adjacent color-clock readback ages on the A500. Keep this capture separate
from kind 25 because its `BLTAPT` setup is explicitly fixed.

`--line-logic-followup` builds kind 27 (3,360 trials) to isolate input-data and
BLTBDAT-order effects around the kind26 BZERO clears. It fixes minterm `$CA`
and `BLTAPT=-80`, and sweeps A `$0000/$8000/$ffff`, C `$0000/$ffff`, B
`$0000/$0001/$0002/$0004/$8000/$1000/$ffff`, USEB off/on, and 2/22 pixel lines.
It pairs NOP/EXG phase pads with delays of 0 through 4 NOPs. Descriptor repeat
0/1 loads BLTBDAT late/early relative to the other direct custom-register
writes; this is an ordering probe, while the selected B-pattern value remains
the same. Every trial reads complete valid DMACONR and beam position before
waiting for BBUSY, then records the destination OR and selected words.

`--line-pipeline` builds kind 28 (3,060 trials) from 90 explicit presets,
each observed with NOP/EXG phase pads and 0-16 NOP read delays. The 24 core
controls cross A=`$0000/$8000`, minterm `$CA/$CC`, USEB off/on and 1/2/22
pixels over a baseline of B=C=0, USEA+USEC+USED, and BLTAPT=`-80`. Other
presets change one input at a time: A data and shifts `0/1/8/15`, B textures
`0/1/2/$8000/$1000/$ffff` and shifts `0/1/8/15`, C data, all nine minterms
`$00/$ff/$ca/$f0/$cc/$aa/$3c/$5a/$0f`, USEABC masks, USED, SING, SIGN and
BLTAPT values `-80/-1/0/80`. A few B=0 controls repeat with the two BLTBDAT
preseed writes reversed. USEABC mask bits are A=bit 0, B=bit 1, C=bit 2.
The descriptor target is the preset index; its complete configuration and
literal BLTCON0, BLTCON1, BLTAPT and BLTSIZE values are written to the build
manifest. Variant and repeat are zero, phase is the phase pad, and delay is
the read delay.

The first observer reads complete DMACONR and beam position before waiting for
BBUSY. Kind28 has its own fine observer because line-mode DPT advances after
the first pixel. It retains raw DMACONR in `counter`, the post-read beam in
`end_beam`, DPT OR in `icr` and selected DPT words in `irq_beam`, `irq_level`
and the high half of `saved_pc_offset`. CPT OR is in `aux`; selected CPT words
are in the low half of `saved_pc_offset`, `second_counter_or_beam` and
`second_icr_or_level`. `compare_timing_sweeps.py` validates all 3,060 descriptors and
preserves both raw per-delay memory traces alongside the decoded preset.

`--line-truth-table` builds kind 29 (2,560 trials): five explicit A/B/C data profiles, each at 1 and 2 pixels, crossed with every raw 8-bit minterm. It holds USEA+USEC+USED on and USEB off, with observer phase 0 and delay 16, to isolate which minterm truth-table bits the line pipeline encounters. The profile register words are included in the manifest; the kind28 dual-memory observer records the same DPT and CPT raw samples. The comparator requires the complete profile/size/minterm descriptor matrix.

`--line-stage` builds kind 30 (2,380 trials) to distinguish the C word present
before a line pixel from the word fetched for the next pixel. It fixes A data
at `$8000`, B/C data registers at zero, A pointer at `-80`, and line size at
2 pixels. Seven pairs of C source words at `$11000/$11050` are crossed with
USEB off/on and minterms `$04/$08/$40/$80/$48`; NOP/EXG phases and delays
0-16 sample each case with the kind28 dual-memory observer. The manifest
contains each pair of C words and the literal BLTCON0/1, BLTAPT and BLTSIZE
values. Strict comparison requires the complete descriptor matrix.

`--line-b-hold` builds kind 31 (2,930 trials, USEB off); `--line-b-hold-dma`
builds kind 32 (2,930 trials, USEB on). Each crosses every BSHIFT with zero,
each single-bit B texture and `$ffff`, phase EXG, and delays 0/1/2/4/16.
Variant 0 uses A=0/LF=`$CC`; variant 1 uses A=`$8000`/LF=`$CA`. Five
selected profiles repeat with BDAT written at BSHIFT=0 before target BSHIFT,
alongside the standard target BSHIFT-before-BDAT order. The manifest records
texture, shift, USEB, ordering and variant register values, and the strict
comparator checks every descriptor and preserves DPT/CPT raw traces.

`--line-b-mask` builds kind 33 (1,024 trials), holding A=`$8000`, B=C=0 and
LF=`$CA` while crossing ASHIFT and BSHIFT 0-15, USEB off/on and 1/2-pixel
lines. The kind28 line driver uses one EXG-phase, delay-16 observer sample per
literal preset; the manifest retains its BLTCON0/1, BLTAPT and BLTSIZE words.
The strict comparator requires every preset and retains the DPT/CPT trace.

`--line-b-prime` builds kind 34 (1,024 trials), crossing the kind28 line
configuration controls (ASHIFT, BSHIFT, USEB, and 1/2 pixels) with four
normal-B priming modes: none, BLTCON1/BLTBDAT register writes, and a two-word
normal B+D copy with zero or `$ffff` source data. Each trial records the prime
mode and literal line preset in the manifest. The strict comparator requires
the full matrix and preserves the two-memory observer trace.

`--line-word-control` builds kind 35 (1,920 trials) from four A/ASHIFT/LF
profiles, BSHIFT 0-15, USEB off/on, three one-word opcodes (NOP, `MOVEQ #0,D6`,
and `MOVEQ #-1,D6`), and delay lengths 0/1/2/4/16. The phase instruction and
each delay word use the selected opcode; all three are four CPU cycles and
two CCKs. A separate phase-zero observer region records the same raw DPT/CPT
flags and memory readbacks. The manifest stores the literal opcodes, register
controls, and observer slot map, and the comparator requires all descriptors.

`--line-shift-truth` builds kind 36 (4,096 trials), crossing every raw
8-bit minterm with 15 two-pixel profiles (A=0 or `$8000`, C=0 or `$ffff`,
and BSHIFT 0/1/4/8/15) plus a one-pixel A=0/C=0/BSHIFT=8 control. B data is
zero, USEB is off, and the observer is phase 1/delay 16. Its literal profile
table is included in the manifest; strict comparison requires all profile/
minterm descriptors and retains DPT/CPT readbacks.

`--line-wrap` builds kind 37 (1,152 trials): BSHIFT 0-15, line lengths 1-18,
USEB off/on, and A=0/LF=`$CC` or A=`$8000`/LF=`$CA`, with B=C=0. It samples
DMACONR after a phase NOP plus 96 delay NOPs at FF7000, after all pixels in
the selected line have completed. The manifest and generated table carry all
six literal source/control/size words; the comparator requires every profile.

`--line-c-cross` builds kind 38 (1,536 trials) to test A/C dependence under
the B-only `$CC` minterm. It fixes B=0 and crosses A data `$0000/$8000`,
BSHIFT 0-15, C data
`$0000/$ffff/$8000/$0001/$5555/$aaaa`, USEB/USEC off/on, and 1/2 pixels.
A and D stay enabled, and the existing FF3000 phase-one/delay-16 observer
captures both DPT and CPT readbacks. The manifest records every literal
BLTCON0/1 and BLTSIZE word; strict comparison requires the full matrix. Each
trial retains the standard six-word descriptor, and each preset row records
literal A/B/C data plus the three blitter control/size registers.

`--line-c-words` builds kind 39 (344 trials). With A=B=0, BSHIFT=4,
LF=`$CC`, and BLTCDAT=0, it places isolated one-hot/zero/all-ones words at
C memory addresses `$11000` and `$11050`, crossing USEB/USEC and 1/2-pixel
lines. Separate controls hold C memory at zero while priming BLTCDAT with
`$ffff/$5555/$aaaa/$8000/$0001`, and hold BLTCDAT at zero for uniform
`$ffff/$5555/$aaaa` memory words. The manifest and literal table record both
C memory words and the independent BLTCDAT value; strict comparison requires
the full matrix.

`--line-c-tomography` builds kind 40 (1,344 trials). It fixes A data at
`$8000`, B at zero, uses the C0 minterm, and crosses all A shifts with zero,
full, alternating, one-hot and one-cold first-C words at 1/2 pixels. The
second C word and BLTCDAT stay zero. Zero/full-word controls cross all
USEB/USEC settings. `--line-c-tomography-shift N` selects BSHIFT 0-15 for
separate repeat ROMs; the shift is included in descriptors and provenance.

`--line-c-onset` builds kind 41 (2,584 trials). It maps phase 0/1 and delay
0-16 across C-first-word zero, full, and one-cold patterns, with A data zero
and `$8000` crossed on the LF=`$CC` cases. Four two-pixel LF=`$0C`/`$C0`
controls use zero/full C words. B and C data registers and the second C word
stay zero. The observer address is `$FF0000 + phase*$2000 + delay*$100`;
`--line-c-onset-shift N` selects BSHIFT 0-15 for separate repeat ROMs. The
kind41 table's third word is A data (CDAT remains zero).

`--line-c-read-sequence` builds kind 42 (160 trials): five first-C words
crossed with A data zero/`$8000`, early/post-BBUSY observers, and eight
repeats. Each observer reads DMACONR eight times consecutively during one
two-pixel line blit. In the standard 40-byte record, the eight samples occupy
word offsets 20-34 (sample six is at offset 32, normally named `status`),
launch beam is at 12, post-read beam at 16, presample beam at 36, and the beam
after BBUSY clears at 38. The early and postbusy stubs are at `$FF7400` and
`$FF7500`; their layout and literal C presets are recorded in the manifest.

`--line-c-activity` builds kind44 (320 trials): the same five first-C words
and two A-data values cross unprimed versus fully A/B/C-primed state, direct
versus BBUSY-poll observation, and eight repeats. Both observer modes use
phase 0 and the same launch beam. The primed control performs an eight-word
normal A/B/C/D blit from zero-filled source words to a separate destination,
then restores ADAT and C-first-word inputs for the line blit. The direct
observer reads DMACONR immediately after BLTSIZE; the poll observer waits for
BBUSY to clear first. Both retain the eight raw reads at offsets 20-34,
launch beam at 12, post-sequence beam at 36, endpoint at 16, and postbusy beam
at 38. `build_line_c_activity_rom.py` archives the immutable ROM and a source
snapshot. The headless runner also reads back the A/B/C input words through
CCP at `collection_done` for this kind.

`build_line_c_history_rom.py` builds kind45 (960 trials): the same ten first-C/A
presets cross six normal-mode history conditions (`none`, explicit all-zero,
A-only `$FFFF`, B-only `$FFFF`, C-only `$FFFF`, and all channels `$FFFF`),
direct versus BBUSY-poll observation, and eight repeats. For each non-`none`
condition, the controller writes eight literal words to each A/B/C source and
performs the same eight-word `$0FCA` normal blit used by kind44. It then clears
the prime destination, restores C memory to the selected first-C word followed
by seven zeros, restores the ADAT/CDAT line inputs, and uses the unchanged
kind44 observer stubs. A/B source words remain at their selected prime values
for CCP verification after collection. `--patterns` accepts a comma-separated
subset of the six names; the default is the complete 960-row matrix. The build
archive contains its manifest, ROM image, and hashed source snapshot.

`build_line_c_bus_data_rom.py` builds kind46 (1,536 trials): ASHIFT 0-15 is
crossed with six literal CPU D3 words (`$0000/$FFFF/$2000/$0800/$2800/$D7FF`),
chip `$18000` versus slow `$C01000` scratch, and eight repeats. The line-blit
inputs are fixed at A=`$8000`, B=C=0, LF=`$CA`, BSHIFT=0 and two pixels. At the
same ROM-aligned point in every trial, FF7800 writes D3 to `(A3)` immediately
after BLTSIZE, then reads DMACONR eight times without an intervening
instruction. The runner verifies zero A/B/C source memory and the final
`$D7FF` word at both scratch addresses through CCP. After the eight samples
and BBUSY clears, the observer also reads D words at `$10000` and `$11050`
into the record's legacy `launch_ref`/`end_ref` fields; both must remain zero.
Build and preflight into
new directories:

```powershell
python build_line_c_bus_data_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --out build/line-c-bus-data-kind46-run
python run_rom.py --binary ../Copperline/target/release/copperline.exe --romdir build/line-c-bus-data-kind46-run --out captures/rom-copperline-line-c-bus-data-run
python run_winuae_rom.py --binary "C:/Program Files/WinUAE/WinUAE.exe" --romdir build/line-c-bus-data-kind46-run --out captures/rom-winuae-line-c-bus-data-run
python compare_timing_sweeps.py captures/rom-winuae-line-c-bus-data-run captures/rom-copperline-line-c-bus-data-run --out captures/kind46-copperline-winuae-run.json
```

The physical A500 capture has not been run for kind46. See
[`line-c-bus-data-experiment.md`](docs/line-c-bus-data-experiment.md) for the
control rationale and comparison limits.

`build_copper_wait_rom.py` builds kind47 (1,024 trials) to test whether Copper
BLTSIZE writes made during chip-bus activity delay observable blitter startup.
It crosses 16-word D-only constant-one and A-to-D copies, one or two identical
already-eligible Copper WAITs with BFD clear, BLTPRI, quiet ROM versus chip-read
CPU traffic, optional four-plane DMA, two CPU instruction paths, eight WAIT
horizontal positions and two repeats. The CPU runs a fixed 512-iteration ROM
loop while the Copper reaches line 66; the pre-marker interval contains no
DMACONR polling. The COPER handler stores its first VHPOSR sample, then DMACONR,
the first destination word and saved PC; after 256 NOPs the program records the
first and last destination words. The standard 40-byte record is documented in
the archived manifest. This is a discriminating experiment, not a hardware
finding; compare Copperline and WinUAE runs with an A500 capture before changing
emulator behavior.

The `--unrolled` builder option produces the same 1,024 descriptors with
variant bit 3 set. It replaces the DBRA traffic loop with 512 ROM NOPs for the
quiet case or 256 fixed chip-memory reads for the traffic case. Both ROM blocks
span the line 66 launch window without a loop branch and are checked byte for
byte against the embedded kernel in the immutable archive.

The additional `--no-blit` option sets variant bit 4 and keeps the same 1,024
rows. Copper writes a two-word `$01fe,$0000` NOOP pair in the BLTSIZE slot;
the WAITs, later COPER marker, and instruction-fetch positions are unchanged.
Those rows check the list/observer baseline with no blitter launch and should
leave both sampled destination endpoints at `$dead`. Combine it with
`--unrolled` to retain the branch-free CPU paths.

The `--cpu-launch --unrolled` control builds the same 1,024 descriptors with
variant bit 5 set and bit 4 clear. CPU code preloads the selected BLTCON0/1;
Copper keeps the same setup MOVE slots but replaces its BLTSIZE slot with the
same two-word NOOP. Copper enters a fixed line 66 hpos `$20` wait, then reaches
the BFD-clear WAIT at `$60 + 2*delay`. The CPU polls line 66 to hpos `$30`,
records the pre-write VHPOSR at record byte `+14`, and starts the same 16-word
blit with a CPU BLTSIZE write before continuing through the unrolled quiet or
chip-read path. This isolates who starts the blit while retaining the Copper
WAIT wakeup and COPER marker. The measured CPU launch position is the key check:
it must precede the BFD WAIT target while the blitter is still busy. This mode
requires `--unrolled` and cannot be combined with `--no-blit`.

The `--finish-sweep --unrolled` follow-up uses kind47 variant bits 6/5/3 and
2,048 rows. Target bits 3..2 select one, four, eight, or sixteen words; target
bits 1..0 retain D-only/A-to-D mode and one/two Copper WAITs. Copper's BFD-clear
WAIT is fixed at line 66 hpos `$60`; descriptor delay now selects zero through
seven NOPs in the CPU launch stub. Finish-sweep enters from an earlier Copper
WAIT at line 66 hpos `$04` and gates the CPU launch at hpos `$10`, keeping its
COPER marker behind the CPU launch. The stub runs
the selected NOP/EXG phase path and pad, samples VHPOSR into D2 immediately
before `MOVE.W D5,$58(a6)`, and then follows the unrolled quiet or chip-read
path. The controller stores D2 at record byte `+14` after masking interrupts,
so there is no prelaunch chip-RAM result store. The manifest records width,
BLTSIZE encoding, launch pad, phase path, and field offsets; this distinguishes
short blits that finish before hpos `$60` from wider blits still active there.

The hypothesis was prompted by [Toni Wilen's EAB discussion](https://eab.abime.net/showpost.php?p=1426048),
WinUAE's developer. The ROM encodes a new measurement and does not copy WinUAE
implementation code.

The kind51 CPU/CIA probe compares matched NOP and `MOVE.B D0,-(A1)` loops from
ROM or CHIP RAM, interrupted by CIA-A Timer-A/PORTS, Copper COPER, or the
CIA-B Timer-A/EXTER route. `compare_cia_cpu_irq.py` compares the WinUAE and
Copperline captures by descriptor and exact captured VHPOSR both before source
start (`+14`) and immediately after it (`+12`); its report keeps rows with
unmatched observed start phases out of the primary comparison and lists
cross-phase matches separately as exploratory. The review1 and review2 captures
passed the record/status checks. The review3 CIA-B EXTER extension has two
versioned A500 captures in `references/cia-irq-kind51-review3-run1` and `run2`;
only 99 descriptor pairs share both observed start samples, and all 99 match.
Other start phases are not equivalent timing evidence. The EAB discussion motivated the separate
BZERO/blitter hypothesis above, not this IRQ matrix. WinUAE,
developed by Toni Wilen, and its cycle-exact CPU/CIA behavior provide an
independent comparison and diagnostic reference for kind51; no WinUAE
implementation code was copied.

`build_line_a_bit_rom.py` builds kind48 (1,536 trials) to measure line-mode BZERO behavior across all 16 one-hot BLTADAT bits, ASHIFT 0/2/4, BLTBDAT 0/$FFFF with USEB disabled, and one/two-pixel lines with C=0. Each trial records eight immediate DMACONR reads and the post-busy words at `$10000` and `$11050`. The shared FF7800 observer also writes zero to its `$18000` scratch word between launch and those reads; the archive manifest records that observer write. This is a measurement matrix, not a hardware finding.

The opt-in `--truth-control` mode preserves those legacy rows and uses a separate
kind48 marker-bit path for 2,048 new trials. It crosses eight literal ADAT
patterns, minterms `$00,$ff,$f0,$cc,$33,$aa,$40,$ca`, BLTBDAT `$0000/$ffff`,
and BSHIFT 0/1 over two pixels. C DMA remains enabled from zeroed C memory,
while B DMA stays off. BSHIFT is stored in the descriptor's phase word but
cleared during beam alignment; BLTADAT is seeded with `$8000` before the
selected pattern, and BLTBDAT is written before the final BLTCON1 value, matching
the legacy register history. The shared FF7800 observer and 40-byte record
remain unchanged. The archive manifest labels the new descriptor encoding,
patterns, minterms, exact register-write order, and the `$CA`/BSHIFT-0
reproduction cases around effective A bits 13 and 11.

The opt-in `--history-control` mode adds 2,016 kind48 trials to distinguish
retained BLTBDAT/shifter history from the final CPU register-write order. It
crosses A patterns `$8000,$2800,$2801`, the line-function minterms
`$f0,$cc,$40,$ca`, seven B-state preconditions (no extra prime, CPU BDAT
`$2800/$d7ff`, or normal/line-mode B-only DMA fetches of `$2800/$d7ff` in both
orders), and three target BDAT write orders (before CON1, after CON1, or
skipped), with eight repeats. DMA primes run to BBUSY clear before the target
setup; the target always uses BSHIFT 0. The history mode has its own descriptor
marker and minterm table, while the legacy and truth-control paths remain
separate. The manifest records the prime registers, fetch words, target
ordering, and shared observer sequence. This is a proposed discrimination
experiment, not a hardware finding.

The separate `--normal-history-control` mode adds 168 rows using the same seven
B-state primes and three BDAT/CON1 write orders, followed by a normal-mode
one-word B-to-D copy (`BLTCON0=$01cc`, `BLTCON1=0`, `BLTSIZE=$0041`) with B DMA
disabled and D DMA enabled. The source is fixed to the `$cc` B function. The
second observed destination remains zero because this target writes only one
word. This control tests whether a value fetched into B during line-mode
priming is retained for a subsequent normal-mode operation; its results must
be interpreted separately from the line-mode history matrix.

The opt-in `--normal-history-no-dma-control` mode adds 48 rows for two further
prime profiles: CPU-load BLTBDAT with `$2800` or `$d7ff` while CON1 is normal,
then start a two-pixel line-mode blit with `BLTCON0=$00cc`, leaving A/B/C/D DMA
disabled. After BBUSY clears, each trial uses the same one-word normal-mode
`$01cc` B-to-D target and the same before/after/skipped BLTBDAT write control.
The source-memory contents do not matter because no channel fetches during the
prime. This isolates line-mode shifter history from B-channel DMA fetches.

The opt-in `--line-hold-matrix` mode adds 1,152 held-out cases: four raw
BLTBDAT words (`$0001,$8000,$a55a,$1248`), BSHIFT values `0,1,7,15`, line-prime
lengths of one to three pixels, and the three target BDAT/CON1 write orders,
with eight repeats. Each prime loads BLTBDAT in normal mode, then runs line
mode with `BLTCON0=$00cc` so no DMA channel fetches. The target is a normal-mode
one-word B-to-D copy. The A500 capture shows that a one-pixel skipped-write
prime retains `shift_combine(0, raw, BSHIFT, false)`; for two or three pixels it
retains `ROR(raw, (BSHIFT - (pixels - 1)) & 15)`. Writing zero before target
CON1 instead uses `shift_combine(raw, 0, (BSHIFT - pixels) & 15, false)`, while
writing zero after CON1 produces zero. These measured rules and their capture
provenance are recorded in the manifest. Emulator candidate counts remain
provisional; see [`docs/a500-b-hold-2026-10-17.md`](docs/a500-b-hold-2026-10-17.md).

The separate opt-in `--line-hold-c-dma-matrix` repeats those 1,152 tuples with
C DMA enabled during the line prime (`BLTCON0=$02cc`). It fetches zeros from a
256-byte buffer at `$14000`; the first line-prime D write goes to `$15000`, and
later line D writes follow the C pointer into `$14050/$140a0`. The normal-mode
target resets D to `$10000`, and the observer is unchanged. Its A500 capture
matched the all-DMA-off matrix in all 1,152 first-D words; the second D word was
zero throughout. Source ID `1b1847727efe84edb602a69fc9f78d6e01f9caa7fa38321549875b83173aa327`,
packet SHA-256 `4decda1716cd77cf4c2943f3e80fe2f758472bbc4a7186a52fb78099a9e2b73a`.

For direct bus observation, `tools/build_bus_address_rom.py` and
`tools/build_scope_bzero_rom.py` create immutable, source-snapshotted 512 KiB
ROM archives. Always choose a new `--out` directory; builders refuse to
replace an existing archive. The analyzer parses RG03 captures and writes
decoded custom-register windows and raw sample provenance:

```powershell
python tools/build_bus_address_rom.py --out build/scope-address-new
python tools/build_scope_bzero_rom.py --c-pattern zero --b-data ffff --out build/scope-bzero-new
python tools/analyze_bzero_bus.py captures/bzero-scope-2026-10-16/bzero-c0000-bffff.bin --nominal-cpu-reference-hz 7093790 --output captures/bzero-scope-2026-10-16/bzero-c0000-bffff-new-analysis.json
```

The analyzer's CPU-time scale is estimated from the nominal reference; the
RG03 LA time-increment header is not trusted. Wiring and interpretation limits
are documented in [`a500-bzero-bus-validation-2026-10-16.md`](docs/a500-bzero-bus-validation-2026-10-16.md).

The experiment records the full literal pattern table and all assembler inputs
in the immutable archive's `manifest.json` and `source_snapshot/manifest.json`.
The runner checks final A/B/C memory against the final trial descriptor, so the
default ordering ends on all-`$FFFF` and verifies both retained A/B patterns.

Archive each generated ROM and its source snapshot before collecting hardware
data. Compare validated hardware and emulator capture folders with:

```powershell
python compare_timing_sweeps.py captures/rom-amiga500-irq-paths2 captures/rom-copperline-irq-paths2 --out captures/irq-paths-a500-vs-copperline.json
```

The analyzer checks RBCP checksums, matching source IDs/descriptors and exact
launch positions. Kind 24 additionally compares the destination OR reduction
and three selected words after blitter completion. See
[`rom-timing-isolation-2026-10-14.md`](docs/rom-timing-isolation-2026-10-14.md)
for provenance, comparison limits and current findings.

The final [comparison and detailed remaining measurement plan](docs/rom-timing-wrapup-2026-10-14.md) records verified fixes, incomplete native IRQ/line BZERO work, and the restored Kickstart hash.

## Divider IRQ verification

The [15 October A500/WinUAE divider IRQ verification](docs/divider-irq-verification-2026-10-15.md) records two identical physical One ROM captures, full WinUAE agreement, remaining Copperline boundaries, and reproduction commands. Build with `build_divider_irq_rom.py`; compare decoded captures with `compare_divider_irq.py`.
