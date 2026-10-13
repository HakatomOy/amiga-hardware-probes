# Copperline follow-up fixes, 2026-10-13

Copperline now models the two-stage CIA count-enable pipeline, the high-byte
one-shot LOAD hold, the latched ICR IR bit, ROM-tail interrupt acknowledge
vectors on the 68000 motherboard bus path, and the stock 68000 STOP polling
phase. No title identity checks or new latency tuning constants were added.
The global Paula latency remains six colour clocks.

The original 6240-trial ROM was rebuilt from probe commit 2d838e9 into a separate
folder; its source ID remains
`891dcccda24a94ec28d2de5750408df66f31a9aa4c0605b0fb1edfba9c81c5c4`.
The fixed-emulator packet is `captures/rom-copperline-final-fixed1/results.bin`.
Its comparison against `rom-amiga500-final` is stored alongside it.

| Measurement | Matched fixed-emulator results |
|---|---|
| Fresh START and START+LOAD | 640/640 counter values |
| Stop/restart without LOAD | 40/40 counter values |
| High-byte one-shot auto-start | 40/40 counter values |
| All transition variants | 160/160 counter values |
| Mask-clear ICR IR latch | 320/320 IR bits and counter values |
| All ICR-race variants | 1280/1280 counter values |
| One-shot periods | 160/160 counter values |

Continuous-period snapshots still differ by one count in 30 of 160 trials.
Five differences remain in the 70 pairs having equal reference-timer elapsed
values. Those reference reads do not identify the target timer read's exact
E-clock phase; this data does not yet isolate a remaining timer implementation
error from read-phase differences. These cases are not claimed fixed.

The original ROM's no-DMA chip-code Copper/STOP histogram changes from all
37 CCK to twelve 37 / twenty 38, versus hardware ten 37 / twenty-two 38.
Changed preceding timing can alter the entry phase, so identical histograms
are not the criterion. The focused entry-phase suite supplies that criterion:
all 256 hardware and fixed-emulator phase trials satisfy the same parity rule,
and all 320 STOP-only trials have the same stopped counter decrements.
The single-bitplane and four-bitplane Copper/STOP distributions remain exact
matches to hardware in both chip and slow code: 128/128 latency values.
See [focused measurements](rom-measurement.md#focused-stop-and-cpu-phase-suite).

ROM vector data was separately verified by rerouting hardware level 1 through
ROM word $FFFFF2 to RAM vector 30: all 256 records reach the installed handler
that records level 6. Copperline's end-to-end zero-footer test now reproduces
hardware's illegal-instruction fault at $003020. Its local diagnostic packet
is in `../Copperline/tmp/probe-negative/capture/fault.bin`; its manifest records
the binary patch and fault-capsule breakpoint. This negative case is not a
valid timing capture.

The corrected release executable boots both bundled AROS and Kickstart 1.3.
Kickstart was restored on OneROM; the live ROM SHA-256 is
`9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`.
