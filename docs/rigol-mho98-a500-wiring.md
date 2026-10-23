# Rigol MHO98 to A500: Init bus timing wiring

## Purpose and scope

Prepare this wiring now; leave the experiment run for our next session. We want
to distinguish CPU handshake/wait timing from Copper ownership at the remaining
Init boundary. Use the MHO98's own analog and digital inputs together, so they
share one acquisition timebase. Leave the Saleae clones disconnected.

This mapping assumes a stock **64-pin DIP 68000**. It does not apply to a
PLCC CPU or accelerator. Confirm the CPU package and motherboard revision first.
All connections below are at the CPU; no Agnus, Gary or Denise clips are needed.

## Before attaching clips

1. Switch off and unplug the A500 supply. Switch off the scope before connecting
   its logic-probe assembly; Rigol prohibits hot-plugging that connector.
2. Use the compatible Rigol logic probe (PLA2216 for this family), not bare wires
   into the scope's logic connector. Verify the actual probe's input rating
   allows the A500's 5 V logic before connecting.
3. Identify CPU pin 1 from its notch/dot. Viewed **from above**, with the notch
   at the top, pin 1 is upper left: pins 1–32 run down the left side; pins 33–64
   run up the right side. Do not count from the underside of the board.
4. Attach grounds only to verified motherboard ground, conveniently CPU pin 16
   or 53. Scope BNC grounds are common and normally earth-referenced. **Never
   attach a ground clip to a signal or +5 V** (CPU pins 14 and 49 are +5 V).
5. Use insulated micrograbbers or a suitable DIP test clip. Check every clip
   for adjacent-pin shorts before power-on. Keep flying leads short and support
   them so moving the scope cables cannot pull CPU pins or clips.

## Analog connections

Use compensated **10× passive probes**, DC coupling, scope input **1 MΩ**;
set the scope's probe factor to 10× too. Do not use 50 Ω termination.
Use short ground springs/leads to nearby verified ground.

| Rigol input | Signal | 68000 pin | Purpose |
|---|---|---:|---|
| CH1 | CPU CLK | 15 | CPU clock edges and wait-state counting |
| CH2 | /DTACK | 10 | Bus acknowledgement timing |
| CH3 | E | 20 | Peripheral clock phase/history |
| CH4 | Unconnected | — | Reserved for a later, verified CCK connection |

CCK is not available as a dedicated 68000 pin. CPU CLK is sufficient for this
first handshake measurement; it does **not** independently establish CCK/Agnus
phase. Do not connect CH4 to a guessed motherboard location.

## Digital connections

The names D0–D15 below mean **Rigol channel numbers**, not CPU data-bus pins.
Label the leads before attaching them.

| Rigol input | Signal | 68000 pin |
|---|---|---:|
| D0 | A1 | 29 |
| D1 | A2 | 30 |
| D2 | A3 | 31 |
| D3 | A4 | 32 |
| D4 | A5 | 33 |
| D5 | A6 | 34 |
| D6 | A7 | 35 |
| D7 | A8 | 36 |
| D8 | A20 | 48 |
| D9 | A21 | 50 |
| D10 | A23 | 52 |
| D11 | /AS | 6 |
| D12 | /UDS | 7 |
| D13 | /LDS | 8 |
| D14 | R/W | 9 |
| D15 | /VPA | 21 |

Connect the logic pod's ground leads to verified ground near their signal
groups, using CPU ground pins 16/53 where practical. Follow the pod's grounding
instructions; signal leads alone are insufficient.

## Initial scope setup and checkout

After checking the wiring, power the scope and A500. Leave OneROM connected.

- Enable CH1–CH3 and D0–D15. Set both digital threshold groups to **1.4 V**
  as a starting TTL threshold. Keep the slash signals displayed in their actual
  polarity: low means asserted; R/W high means read, low means write.
- Start around 1 V/div and 200 ns/div, adjusting vertical offsets to show 0–5 V.
  Trigger on CH1 rising near 1.4 V. On a stock PAL A500 expect approximately
  7.09 MHz CPU clock and 0.709 MHz E clock; NTSC rates differ.
- Check clean clock edges, plausible low/high levels and `/AS` pulses before
  attempting the experiment. Stop if attaching a probe prevents normal boot or
  produces obvious ringing/unstable thresholds; fix the connection first.
- For a preliminary timing capture, use Single acquisition and falling-edge
  trigger on D11 (`/AS`) if the trigger menu permits. This is only a wiring
  check, **not** a case-qualified Init capture. Keep acquisition mode Normal;
  avoid averaging or peak-detect processing.
- For the actual experiment we will configure a qualified trigger/window and
  deep memory together. Aim for at least **100 MS/s actual acquisition rate**
  with all selected channels enabled; record the displayed rates and depth.
  Do not assume the headline maximum rate applies to every channel configuration.
- Keep LAN connected and note the scope's IPv4 address (LAN/network settings),
  exact model, firmware, logic-probe model and motherboard revision. LAN is the
  control/export connection; no extra signal wire goes to the PC.

## What this wiring can and cannot identify

A1–A8 identify the low nine address bits of a word access. The three upper bits
help separate the expected ROM, custom-register and RAM regions. We will look
for the enable write at `$dff096`, COLOR00 write at `$dff180` (or COPJMP at
`$dff088`), then VHPOSR reads at `$dff006` within the unchanged observer.

This is a **partial address bus**, not a full address decoder: uncaptured bits
can alias. No CPU data bits are captured. The original ROM's known sequence,
case order and OneROM result packet must establish identity; an ambiguous
sequence is invalid evidence. Do not add marker instructions or change ROM order.
See [the experiment plan](init-bus-phase-capture.md) for the original ROM hash,
case IDs and acceptance rules.

When ready, tell us the wiring is complete and provide the LAN IPv4 address.
We will save the native acquisition plus exported analog/digital samples and
settings under ignored `captures/`, preserving timestamps without aligning away
the timing difference. No measurement needs to be run during wiring.

## Sources checked

- [Motorola/NXP M68000 user manual](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf),
  Figure 11-1, printed page 11-2 (PDF page 171): the 64-pin DIP diagram was
  rendered and visually checked against this table. Local copy: `../MC68000UM.pdf`
  relative to the repository root.
- [Rigol MHO900/MHO98 product and manual downloads](https://www.rigol.com/intl/products/oscilloscope/MHO900.html):
  mixed-signal channel family and compatible logic probe.
- [Rigol MHO900 user guide](https://www.rigol.com/dam/global/downloads/brochures/en/user-manual/oscillosopes/MHO900-UserGuide.pdf),
  Digital Channel chapter: two threshold groups, PLA2216 connection and
  prohibition on hot-plugging the logic-probe connector. Check the MHO98/probe
  manuals for the exact installed accessory and firmware.
