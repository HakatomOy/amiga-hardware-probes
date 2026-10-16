# Kind46 line-mode CPU bus-data control

Kind46 tests whether a CPU write to ordinary RAM immediately after a line-mode
BLTSIZE write changes the early DMACONR BZERO observations. Earlier continuous
RAM measurements reproduced a BZERO clear at ASHIFT=0 and set values at
ASHIFT=2/4 with LF=`$CA`, BSHIFT=0, A=`$8000`, B=C=0 and a two-pixel line.
That result does not support a universal fixed-FFFF wrap rule. One working
hypothesis is that additional evaluation sees a value shared on the CPU data
bus; this experiment varies the CPU-written value while holding the line
sources and opcode/addressing form fixed.

## Matrix and cycle order

The 1,536 descriptors are the full product of 16 ASHIFT values, six CPU words,
two scratch regions, and eight repeats:

| Axis | Values |
| --- | --- |
| ASHIFT | 0 through 15 |
| D3 word | `$0000`, `$FFFF`, `$2000`, `$0800`, `$2800`, `$D7FF` |
| A3 destination | chip `$00018000`; slow `$00C01000` |
| Repeat | 0 through 7 |

The other blitter inputs stay fixed: A data=`$8000`, B data=0, C data=0,
LF=`$CA`, BSHIFT=0, A/C/D enabled, B disabled, BLTAPT=`-80`, and
BLTSIZE=`$0082`. The A and B source areas at `$12000` and `$16000` are cleared
to eight zero words per trial. The C region starting at `$11000` is cleared
through `$110A2` so all strided line words remain zero, and `$11050` is
explicitly cleared as the second C word the line engine may touch. D memory
is cleared separately.
The controller restores these inputs and pointers, configures DMA before
launch, loads the selected word into D3 and the selected destination into A3,
then aligns to the same phase for all rows.

The FF7800 ROM stub saves D7 in A0 and captures the launch beam in A2. Its
first instructions are `MOVE.W D5,(A1)` (the BLTSIZE launch),
`MOVE.W D3,(A3)`, then eight adjacent `MOVE.W $02(A6),Dn` DMACONR reads.
There is no instruction between the CPU RAM write and the first DMACONR read.
Only after the eight words are captured does the stub store metadata and wait
for BBUSY to clear. The beam-alignment routine uses D0/A2 and does not alter
D3/A3; the wrapper test checks both register loads occur before entering the
observer. After the eight reads and BBUSY clearing, the stub reads D memory at
`$10000` and `$11050` into the record's legacy `launch_ref` and `end_ref`
fields. Both must be zero; they are D readbacks in kind46, not timing values.

The descriptor uses the standard six words `(kind, ashift, pattern index,
region index, fixed delay, repeat)`. Region index occupies the phase slot but
the controller saves it on the stack and keeps that slot zero through both
`sync_beam` and the FF7800 measurement. It restores the exact descriptor word
after the observer returns, so region selection does not change launch phase
and the capture retains the original descriptor. The manifest includes every literal pattern, address, line
control, observer offset, and source snapshot hash.

## Emulator checks and limits

`run_rom.py` stops at collection completion and reads back the A/B/C source
areas plus the explicitly cleared second C word at `$11050`. It also checks
the two post-BBUSY D readbacks remain zero and the first word at both scratch destinations;
the final descriptor is D3=`$D7FF`, region slow, so the run must leave `$D7FF`
in both chip and slow scratch words. This confirms the selected data writes
landed and the line source areas stayed zero. It is not a physical-bus
measurement. Copperline and WinUAE captures should be compared using the
strict kind46 descriptor comparator before considering a hardware run.

Chip and slow destinations intentionally change the RAM region. The CPU
opcode, register-direct source and `(A3)` addressing mode remain identical,
but the different memory buses can have different wait/arbitration behavior.
The measurements therefore compare data-word effects within each region and
report region as a separate matrix axis. They cannot by themselves establish
that a CPU bus value is connected to an internal blitter latch, nor distinguish
all hardware paths that could produce the observed BZERO bit.

The grouped emulator preflight is recorded in
[`captures/kind46-a500-v2/bzero-group-analysis.json`](../captures/kind46-a500-v2/bzero-group-analysis.json).

## Emulator preflight, 2026-10-16

The immutable kind46 v2 archive has ROM SHA-256
`3d6fb876bac15bebdac4e6725524ac38bf939f925dd1571d887d62078de37256` and
source ID `5a9cfc28ee9c17a620d259ec73a8b05ce9f0b5f45c72dc26a8f694747dce6317`.
Both Copperline and WinUAE completed all 1,536 rows with no skips or timeouts.
Every launch beam and later beam field matched across emulators. All eight
DMACONR reads in every pair differed by exactly `$2000`: BZERO was set in
WinUAE and clear in Copperline for every ASHIFT, CPU word, region and repeat.
The other sampled bits were identical. Copperline's collection-time checks
confirmed zero A/B/C sources, zero C word at `$11050`, zero D readbacks at
`$10000` and `$11050` on all records, and final `$D7FF` words in both scratch
regions. These are emulator-only checks; they do not establish which emulator
matches an A500 for kind46.

## A500 result, 2026-10-16

The A500 capture `captures/kind46-a500-v2` is complete: 1,536 records, zero
timeouts or skips, with SHA-256
`303a2776216993689ef8c95c5f32afab05abd20f56c898bee44a1fb5332cee3f`.
All launch and later beam fields match the Copperline and WinUAE captures, and
both post-BBUSY D readbacks are zero in every row.

On the A500, BZERO is set in all eight samples only at ASHIFT 2 and 4. This
holds for all six CPU D3 words, both chip and slow scratch destinations, and
all eight repeats: 192 rows or 1,536 set sample words. The other 1,344 rows
have BZERO clear in every sample. The grouped JSON gives each ASHIFT/pattern/
region combination and per-read set counts. Changing the CPU-written word or
scratch region has no observed BZERO effect in this matrix. Copperline falsely
clears the 1,536 A500-positive words; WinUAE falsely sets 10,752 words in the
1,344 A500-negative rows. The emulator disagreements remain BZERO-only.

The A500 pattern points to an ASHIFT-dependent condition, while leaving open
whether BZERO follows a shifted A-data bit or an ASHIFT/counter field. Two
continuous controls were built with the existing scope builder and no source
changes: `build/scope-bzero-a2000-ash0-kind46-control-v1` uses A data
`$2000` at ASHIFT 0; `build/scope-bzero-a0800-ash0-kind46-control-v1` uses
`$0800` at ASHIFT 0. Those words correspond to `$8000` shifted by 2 or 4. If
either produces BZERO set, the data-bit-position hypothesis gains support; if
both clear, an ASHIFT/counter-field dependence remains more likely. The A500
results for both controls are now captured: BZERO remains set after busy
clears, matching the effective A bit positions in the original shifted-data
cases. Raw files are `captures/bzero-scope-2026-10-16/bzero-a2000-ash0-bsh0-ca.bin`
and `bzero-a0800-ash0-bsh0-ca.bin`. This supports effective A-bit-position
dependence rather than a condition solely on the ASHIFT field. A follow-up
checksum-protected matrix should include nonzero B controls and actual output
words to independently verify each alternative ADAT input. The `$2000` control ROM SHA-256 is
`24a94f8952249063f360df441be09cae47a04e861902eb0c270aeefe5778012a`; the
`$0800` control ROM SHA-256 is
`3aac21822dcbb9a4123abd9c7f50216d5fa848a89029bdd7ee9f5bc0382f4e0e`.

The original live Kickstart was restored and read back with SHA-256
`9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`;
SEL_C is released. No additional emulator behavior correction is accepted
from this incidence map alone.
