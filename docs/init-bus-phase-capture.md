# Original Init observer: bus-phase capture

Use this if software phase controls cannot resolve the original boundary.
For the available Rigol MHO98, use the
[16-digital plus analog wiring guide](rigol-mho98-a500-wiring.md).
Its partial address capture requires sequence qualification; the full 32-channel
mapping below remains the preferred option when that hardware becomes available.
The exact original ROM hash is
`1c00a58ea071deaa624ff16302944b70fd31e91941d939fec9e9f97bd0acb32e`
(`build/dma-master-boundary-v1`). Reordered and VPA probes are controls, not
substitutes for this original experiment.

## Uncertainty

Leading hypothesis: CPU read/write handshake phase or wait recognition differs
under the original immediate-enable/immediate-COLOR00 sequence. Competitor:
unrecorded Copper/DMA history changes the first transaction ownership.

The original case `113,8,1,1,0,0` repeatedly returns hardware 0x4264 versus
emulator 0x4265 at input 0x424d. A reordered, byte-identical observer admits both
outcomes. Capture phase0/phase3 neighbors too; do not select only one outcome.

## Signals and unchanged execution

With 32 channels, capture CPU `A1..A23` (23 channels), plus CPU clock, CCK,
E clock, `/AS`, `/UDS`, `/LDS`, `/DTACK`, and `R/W` (8 channels). The spare
channel can record HSYNC or VPA when useful for raster/E-clock qualification. Address signals identify the original observer and
custom-register accesses without inserting a marker instruction. Eight timing
signals alone reveal handshake phase but make case identification harder.

Confirm the actual A500 revision, pin locations and analyzer configuration
before wiring; this plan specifies logical signals, not a board pinout.
Record the actual sample rate, channel mapping and clock polarity. Aim to
resolve individual CPU clock edges;100 MS/s gives about 14 samples per stock
PAL CPU clock. At 32 channels,200 ms at that rate is about 80 MB before export
overhead; verify the device's supported capture/streaming mode.

Where supported, trigger on the first inert observer instruction fetch at `$ffb100`, retaining
pretrigger context and enough following cases to include phase 1. Otherwise
capture continuously and locate that fetch in the exported address trace. Keep the
original case order and observer bytes. Added GPIO writes, debugger stops or
different instruction forms can change the failing boundary.

## Bounded analysis

Keep the full raw capture and export in ignored `captures/`, with metadata and
ROM hash. Decode bus cycles from `/AS`, address and byte strobes. Associate
descriptor reads/result slots with manifest case IDs; identify `$dff096`,
`$dff180`, and following`$dff006` transactions.

Return only per-case CPU clock counts, wait counts, phase before/after each
transaction, and a short window around the first divergence. Compare the
measured strobe edges against the MC68000 read/write states; do not infer
Amiga RGA ownership from a generic CPU diagram alone. Preserve timestamps and
clock units exactly, without shifting traces to make them match.

If waits differ, repair the grant/return model. If handshake timing agrees but
the reported beam differs, isolate Agnus readback sampling. Missing signal or
case identity is an invalid capture, not a match. See the
[investigation record](../investigations/init-after-bmapen.json) for current gates.
