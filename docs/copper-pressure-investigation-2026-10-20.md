# Copper-pressure CPU/blitter ordering

## Question and controls

Continue the 208 older CPU/Copper-pressure handoff differences after Copperline
`2b100669`. Kind78 extends the accepted source-write race with explicitly enabled
Copper DMA: 32 NOOPs, an INTREQ COPER completion marker and an end-of-list WAIT.
Compare six planes with/without Copper, normal/nasty priority, NOP0..3, source
versus unused-neighbor overwrite, AD old/preseeded-new and D-only/no-start
controls. Exact recorded launch beams qualify comparisons; no trace alignment.

The initial 3,072-descriptor matrix exceeded the 64-KiB boot segment. The 1,536-row
matrix keeps six-plane/Copper discrimination and every data control; previous
versioned kind77 captures cover no/four-plane neighbors. The failed build stays
local; the successful immutable build is `build/handoff-copper-race-v2`.

## Confirmed evidence

- Two physical packets are byte-identical; both OneROM restorations verified.
  Versioned references: `references/handoff-copper-race-v2/run1` and `run2`.
- All 1,536 cases are qualified, with zero missing, invalid, excluded or unstable
  cases. All 768 no-Copper rows match; all 768 Copper rows differ in beam fields.
- 384 of those timing differences are no-start controls. Consequently a
  blitter-only completion/startup explanation cannot explain the broad family.
- Sixteen AD race destinations differ: normal priority/NOP1 copies old AAAA on
  hardware but new 5555 in the model; nasty/NOP0 has the opposite ordering.
  Each group has eight cases. D-only, preseeded and neighbor controls match.
- A byte-identical diagnostic replay has Copper transfers overlapping all
  384/384 enabled real blits. Settled COPER witnesses completion on hardware;
  this is not a pin-level capture proving exact hardware transfer clocks.

Full run: `captures/copper-race-20261020/hardware-v2`; compact ordering report:
`ordering.json`. The verified emulator trace and bounded overlap report are in
`captures/copper-race-20261020/trace-v2`.

## Next discriminating experiment

Kind79 reads custom/chip/slow/ROM with the identical `MOVE.W (A1),D0`, under the
same witnessed Copper stream, AD/no-start, priorities and NOP0..3. The hypothesis
is CPU access-space arbitration; the competitor is blitter-specific completion.
Dependence in no-start controls narrows the CPU grant/readback rule; active-blit
only differences retain the blitter pipeline explanation. Do not tune a startup
delay or IRQ constant from the aggregate beam offset.

Manifest: `experiments/workflows/handoff-copper-access.json`. Preflight checks
settled AD/no-start destinations, slow/ROM read positives and Copper completion.
Further measurements and candidate validation must update the short records.
