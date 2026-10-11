# Measurement contract and binary format

## Machine ownership

The boot block receives the ROM's open trackdisk I/O request and ExecBase. It
allocates 32 KB of chip RAM for the program, rather than overwriting a presumed
free address. The program allocates 64 KB of chip RAM for results. It blanks the
OS view, waits for the display and blitter, suspends task switching and Exec
interrupts, and uses Exec Supervisor to run the experiment on its own stack.

This is a complete temporary machine takeover, not a multitasking CIA timer
client. CIA resource interrupt-mask shadows are saved and disabled before direct
register access. The two timer-A controls and counter values are saved; other
CIA timer controls, keyboard/port direction registers, and disk mechanics are
not reprogrammed by the tests. Level 1/2/3/6 and TRAP 0 vectors are replaced.

Afterward the vectors, DMA/interrupt enables, system Copper pointer, CIA masks,
timer-A counter/control state and OS view are restored to allow trackdisk writes.
Reloading the saved counters cannot restore unreadable original timer latches or
the elapsed wall-clock period. This is sufficient restoration for the dedicated
boot-and-save workflow, **not** a promise of transparent return to an existing
Workbench session. The program stays on its final status screen until reset.

Disk writes use the original boot device's I/O request: CMD_WRITE, CMD_UPDATE,
CMD_CLEAR, CMD_READ, full-buffer comparison, then TD_MOTOR off. No filesystem is
involved and no disk operation is active during measurement.

## Test matrix

4 sources × 6 kernels × 16 phase settings × 2 repetitions = 768 records.
Order is source, kernel, phase, repetition. All program, stack, result buffer,
and MOVEM data accesses are in chip RAM.

| Source ID | Source | Phase setting |
| --- | --- | --- |
| 0 | CIA-A timer A, level 2 / PORTS | One-shot latch `24 + phase` E-clock ticks |
| 1 | CIA-B timer A, level 6 / EXTER | One-shot latch `24 + phase` E-clock ticks |
| 2 | Copper writes `SETCLR | SOFTINT`, level 1 | WAIT line 64, horizontal `$40 + 2*phase` |
| 3 | Both CIA timer A sources | CIA-A latch `$024F + phase`; CIA-B latch `$01FF` |

Those latch values specify what is programmed, not a claim about the exact
start-to-underflow clock count. The launch timestamp precedes setup and timer
start; instruction listings define the intervening accesses. The two timers
start through consecutive CIA register writes, not simultaneously.

| Kernel ID | CPU sequence |
| --- | --- |
| 0 | Two NOPs, flag check and conditional branch |
| 1 | `MOVEM.L (A0),D1/D3/D5`, flag check and branch |
| 2 | `MOVEM.L D1/D3/D5,(A0)`, flag check and branch |
| 3 | Reload fixed D0 then `DIVU #$4321,D0`, flag check and branch |
| 4 | `STOP #$2000`, flag check, repeat if a second interrupt is expected |
| 5 | `TRAP #0` to an immediate `RTE`, flag check and branch |

Each trial waits for a new raster line 32 with vertical bit 8 clear. Display,
blitter, disk, sprite and audio DMA are off. Copper DMA is enabled only for
source 2. Only the tested interrupt source(s) and VERTB are enabled. VERTB is
a watchdog for missing interrupts, so STOP cannot wait forever. It marks the
record as a timeout and lets the next trial proceed.

Phase settings deliberately move an interrupt relative to instruction execution.
They do not guarantee a particular E-clock phase on every physical run. Beam
launch observations and repetitions must be examined before assuming repeatable
starting phase. This first suite covers DMA-quiet execution and does not yet
exercise active display/blitter contention, every instruction or every CIA race.

## Handler instrumentation

The **first instruction** in each handler reads VHPOSR into a global scratch
word using `MOVE.W 6(A6),d16(A5)`. This is the earliest software observation,
already after interrupt recognition, exception entry, vector fetch and handler
instruction fetch. It is not the time when IPL changed or the CPU sampled it.

The handler then sets SR to `$2700`, saves 14 registers, records the interrupted
SR/PC from the six-byte 68000 exception frame and observes VPOSR/INTREQR. The
selected CIA ICR is read and that interrupt source is acknowledged. No unrelated
CIA ICR is read: doing so would clear pending state and change paired results.
The recorded PC is captured **before** any adjustment made by the STOP handler.
It is normalized by subtracting the allocated program start address.

Logging has a real execution cost. After the first beam read the handler masks
interrupt nesting while recording; the paired test therefore measures two
interrupts with this exact handler between them. There is a small interval
between the first read and the SR write in which a higher-priority interrupt
could enter. The chosen paired latches normally separate the events enough to
avoid this; unexpected ordering/beam observations should be investigated, not
silently treated as independent pin timestamps.

The STOP path redirects the saved return PC to its flag check to handle an IRQ
arriving just before STOP. If the second paired interrupt has not arrived, it
executes another STOP. Other kernels return normally and check a completion flag.
The handlers preserve the interrupted registers. This suite measures MOVEM
timing but does **not** reproduce Voyage's full self-decryption or register-
permuting interrupt handlers, and does not identify any program by name.

## ADF layout

Ordinary 80-cylinder, two-side, 11-sector DD image: 1760 × 512 = 901120 bytes.

| Region | Bytes / sectors |
| --- | --- |
| Boot block | sectors 0–1; 1024 bytes with Amiga end-around-carry checksum |
| Program reservation | sectors 2–65; 32768 bytes loaded to allocated chip RAM |
| Unused | sectors 66–1535 |
| Results | sectors 1536–1663; 65536 bytes |
| Unused | sectors 1664–1759 |

There is no AmigaDOS root block. The boot header's root-block field is conventional
but the loader takes over directly and never requests filesystem mounting.

All saved integers are big-endian. The results region has a 512-byte header,
768 × 64-byte records, then zero padding. Sum all 16384 big-endian longwords
modulo 2^32, including the checksum field: a valid region sums to zero.
This detects accidental corruption; it is not a cryptographic integrity check.

| Header offset | Size | Meaning |
| --- | --- | --- |
| 0 | 8 | ASCII `A5IRQ001` |
| 8 | 2 | Format version = 1 |
| 10 | 2 | Header size = 512 |
| 12 | 2 | Record size = 64 |
| 14 | 2 | Reserved = 0 |
| 16 | 4 | Number of finished records = 768 |
| 20 | 4 | Region size = 65536 |
| 24 | 4 | Record offset = 512 |
| 28 | 4 | Additive checksum |
| 32 | 32 | SHA-256 of normalized assembly sources and build.py |
| 64 | 2 | Initial raw VPOSR / Agnus ID bits |
| 66 | 2 | Initial raw DENISEID (unreliable on OCS) |
| 68 | 2 | Exec AttnFlags |
| 70 | 2 | Exec library version |
| 72 | 2 | Exec library revision (not necessarily the ROM release revision) |
| 74 | 2 | Test matrix complete = 1 |
| 76–511 | 436 | Reserved = 0 |

| Record offset | Size | Meaning |
| --- | --- | --- |
| 0 / 1 / 2 / 3 | 1 each | Source / kernel / phase / repetition IDs |
| 4 | 2 | Status: 0 completed, 1 VERTB watchdog timeout |
| 6 | 2 | Number of recorded test IRQs: 0, 1 or 2 |
| 8 | 2 | VHPOSR at launch synchronization, before source setup |
| 10 | 2 | Reserved = 0 |
| 12 | 20 | Event 1, described below |
| 32 | 20 | Event 2 (paired source); zero when absent |
| 52 / 56 / 60 | 4 each | D1 / D3 / D5 after the kernel returns |

| Event offset | Size | Meaning |
| --- | --- | --- |
| 0 | 2 | VHPOSR read by the first handler instruction |
| 2 | 2 | VPOSR read later, after register saving |
| 4 | 2 | Interrupted SR from the exception frame |
| 6 | 2 | INTREQR read before acknowledging this source |
| 8 | 4 | Interrupted PC relative to program start |
| 12 / 13 | 1 each | CIA-A / CIA-B ICR; `$FF` means deliberately unread |
| 14 | 1 | Interrupt level: 1, 2 or 6 |
| 15 | 1 | Reserved = 0 |
| 16 | 4 | Interrupted D0 |

Do not combine VHPOSR's first timestamp with VPOSR's later vertical-high bit
as though they were an atomic beam read. The current test events are arranged
well before line 256; extending the suite across that boundary needs explicit
handling. Exception PCs can point into loop flag checks, setup, or trap return
code as well as the operation under test; use the exact assembler listing.
