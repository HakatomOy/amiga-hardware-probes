# A500 timing measurements and remaining work, 14-15 October 2026

## Machine and method

The physical test machine was a PAL A500 with 512 KiB chip RAM, 512 KiB slow
RAM, ECS Agnus 8372A and OCS Denise. Measurements used One ROM Fire-40-A,
firmware 0.8.0, USB plugin 0.3.2 and host-control 0.1.6. SEL_C reset the 68000.
The original Kickstart was restored and live-read after the experiments; its
SHA-256 is 9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb.

WinUAE 6.0.3 used A500 Best Compatibility, PAL, ECS Agnus and cycle-exact
68000/memory/blitter with matching memory. Copperline used deterministic
headless runs. The trace tools validate source IDs, checksums, descriptors,
launch phase, timeouts and skipped trials. No RBCP traffic ran in timed kernels.

## Results against A500

The STOP and BZERO candidate executable used for the latest Copperline captures
is the optimized CI-profile binary with SHA-256
97a0b51616eb47bdfd060cb8bd66a2a53ad1ca1b1c4e9242c9858ccf5561dc38. The
candidate preserves the known normal/fill behavior and improves the measured
line BZERO onset, but the line flag is not fully modeled yet.

| Measurement | Trials | WinUAE Best Compatibility | Copperline before latest fixes | Copperline after latest fixes |
| --- | ---: | --- | --- | --- |
| Aligned CPU/DIV and DMA observer tests | 1,792 CPU plus 20,736 masked observer comparisons | Zero elapsed/state mismatches on safe phase-matched rows | CPU: 655 elapsed mismatches; blitter observers had state and endpoint errors | CPU: zero elapsed mismatches on 1,732 safe same-launch pairs; observers match |
| Normal/fill BZERO edges | 4,608 | 20 flag mismatches before the normal/fill correction | 86 before correction | Exact packet match; unchanged by the new line-only change |
| Synchronized STOP IRQ paths | 896 | Zero IRQ-beam or saved-PC mismatches | The final source-phase candidate had 256 native odd-phase cases +2 CCK; other paths exact | Zero mismatches; Copperline packet equals A500 byte-for-byte |
| Line data and BZERO, kind 24 | 2,560 | 872 BZERO mismatches | 956 | 932 |
| Line minterm/BZERO, kind 25 | 3,456 | 74 BZERO mismatches | 74 | 74 |
| Fine line BZERO, kind 26 | 544 | 434 BZERO mismatches | 454 | 450 |
| Line inputs and BLTBDAT order, kind 27 | 3,360 | 624 BZERO mismatches | 652 | 596 |

All four line-mode captures have zero elapsed-beam and destination-memory
mismatches. In every line-mode mismatch in kinds 25-27, A500 has cleared BZERO
while Copperline still reports it set. Setting the line-mode extra visibility
delay to zero improves kinds 24, 26 and 27, with no change in kind 25. Kind 27
is now closer to A500 than WinUAE; kinds 24 and 26 remain closer in WinUAE, and
kind 25 ties. This is a measured partial improvement, not a complete line-mode
BZERO fix.

The kind-22 normal/fill packet remains byte-identical to A500 after both
changes. The combined candidate also matches the 896-record kind-23 A500 IRQ
packet exactly. WinUAE has zero IRQ-beam and saved-PC mismatches in that matrix.
The STOP deadline fix retains the earliest device event in colour clocks and
clamps idle chipset advancement to it, avoiding instruction-budget rounding
past the event. It closes the prior odd-phase +2 CCK residual for these tested
native and Copper sources.

The earlier claim of a six-plane DIVU result 191 CCK early was caused by a
faulty beam conversion that doubled HPOS and by unmatched launch phases. It is
superseded. In the corrected aligned count-64 tests, all compared systems
agree on safe same-launch beam timing. The historical kind-19 multiobserver
captures are not interchangeable with the aligned read-observer sweeps.

## Changes supported by measurements

- MC68000 DIVU/DIVS finish internal computation clocks before final prefetch
  and IPL sampling; MULU/MULS retain their separate sequence.
- Blitter BBUSY and BLIT request readback follow their measured pipeline
  positions. BLTPRI follows actual bus requests.
- 68000 chip-memory transfer sampling occurs at the granted slot before its
  trailing DMA clock.
- STOP idle advancement is bounded by exact CCK device deadlines.
- Normal/fill BZERO keeps its measured three/four-CCK propagation schedule.
  Line-mode BZERO has zero extra visibility delay pending the next experiment.
- Copperline builds check out the first-level m68k submodule. The workflow
  checkout value is submodules: true; recursive fixture checkout is not
  needed for the Copperline dependency.

## Remaining measurements and plan

### 1. Identify the line-mode BZERO pipeline rule

The completed kind-25 to kind-27 matrix varies minterm, A/B/C values, USEB,
line length, read delay, NOP/EXG phase, BLTPRI and BLTBDAT write order. Data and
beam remain exact, but the remaining flag state depends on inputs. The A=0
kind-27 cases match; nonzero A produces the residual for selected B/C/USEB
combinations. Changing BLTBDAT write order, line length or BLTPRI does not
explain it.

Build kind 28 to observe BZERO around each line pixel with both phase offsets.
Vary one source at a time: first nonzero A bit and position, B texture bit and
shift, C value, minterm, USEA/USEB/USEC, SING, SIGN/error accumulator and D
enable. Keep one-, two- and 22-pixel lines. Capture full DMACONR plus launch
and read beams, then destination OR and selected words. Use the kind-27 inputs
as a regression and preflight in WinUAE before another One ROM capture. The
test should establish whether the physical BZERO latch follows an earlier
line ALU/pipeline value than the output written to D. Only move the model's
state update point after that rule is supported by the matrix.

### 2. Extend STOP phase and contention coverage

The 896-row kind-23 matrix now matches exactly. Extend it to sixteen or more
source horizontal phases, 0-31 NOP positions before STOP, one- and two-word
blits, and final-D contention from bitplanes and Copper. Retain native
D-only/copy/fill/line sources, Copper BLIT/COPER/SOFT sources, byte-identical
RAM/ROM handlers and current IRQ levels. Record INTREQ and handler beams
without adding a read to the timed path. Recheck Copper 37/38-CCK parity and
CIA STOP timing.

### 3. Regression and scope

The current candidate passes cargo test --profile ci with 4,081 passed, zero
failed, 43 ignored and the two known Windows-only tests filtered. All 45 golden
screenshots pass. Formatting passes; Clippy passes with six pre-existing
warnings (unused Windows test import/constants and two test closures). After
the kind-28 or broader STOP changes, repeat these checks and inspect save/resume
with in-flight BZERO and IRQ deadlines. Benchmark a fixed deterministic
workload before claiming host-speed effects. Extend timing claims to other
OCS/ECS revisions, AGA, NTSC or CPUs only with matching hardware data.

The detailed measurement methods, capture IDs, hashes and build provenance are
in docs/rom-timing-isolation-2026-10-14.md. Raw captures and ROM images remain
local assets and are not committed.