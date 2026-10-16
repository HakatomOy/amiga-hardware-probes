# A500 scope wiring for line BZERO observations, 2026-10-15

The map below is for a standard 64-pin DIP 68000 and 48-pin DIP 5719 Gary. Rev6A/7 reference designators are U1 and U5. Use chip markings and pin numbers; if the packages or markings differ, establish the correct pinout before connecting.

Power down the Amiga while attaching or moving clips; disconnect One ROM USB while doing so if it remains powered. Disconnect every probe from the signal-generator output before connecting to the Amiga. The generator must remain OFF and must not drive the Amiga bus. Connect probe grounds to verified Amiga ground only. Keep leads short and do not bridge adjacent IC legs.

| Rigol input | Signal | Chip pin |
| --- | --- | --- |
| D0 | CPU_CLK | 68000 pin 15 |
| D1 | CPU_AS_N | 68000 pin 6 |
| D2 | CPU_RW | 68000 pin 9 |
| D3 | CPU_UDS_N | 68000 pin 7 |
| D4 | CPU_DTACK_N | 68000 pin 10 |
| D5 | CPU_DATA14 | 68000 pin 55 |
| D6 | CPU_A1 | 68000 pin 29 |
| D7 | CPU_A2 | 68000 pin 30 |
| D8 | CPU_DATA13 | 68000 pin 56 |
| D9 | CPU_A3 | 68000 pin 31 |
| D10 | CPU_A4 | 68000 pin 32 |
| D11 | CPU_A5 | 68000 pin 33 |
| D12 | CPU_A6 | 68000 pin 34 |
| D13 | CPU_A7 | 68000 pin 35 |
| D14 | CPU_A8 | 68000 pin 36 |
| D15 | GARY_REGEN_N | Gary 5719 pin 18 |

Analog CH1 (10X, high impedance, DC) connects to the same CPU data13 node, 68000 pin56. Its ground and both PLA2216 pod ground connections go to Amiga ground; 68000 pins16 and53 are GND. Pin53 is near the data pins and pin16 near the clock. Do not confuse these with VCC pins14/49. Keep CH2-CH4 disabled initially to preserve the calibrated one-analog-channel configuration.

Pin counting is top view with the package notch at the top. For the 64-pin CPU, pin1 is upper left, count down to32 at lower left; pin33 is lower right, count up to64 at upper right. Gary follows the same convention with24 pins on each side. Board rotation does not change numbering.

CPU data13/data14 are BZERO/BBUSY only when reading DMACONR ($DFF002). On all other cycles these are ordinary bus data bits. A1-A8 plus active-low REGEN identify the custom-register offset; AS/UDS/RW/DTACK qualify the read and the valid-data interval. Capturing both data bits allows distinguishing early versus after-busy observations. Low address bits also identify the BLTSIZE write ($DFF058) used for CPU launches. Future Copper-initiated experiments may need a separate external marker; no such marker is wired by this first map.

The chosen calibrated inputs D0/D1/D8 carry clock, AS and BZERO respectively. This wiring deliberately does not collect LDS, all data bits, all CPU address bits, or Agnus DRAM addressing. It cannot expose internal blitter latches or directly identify C DMA fetches.

References: [Motorola MC68000 user manual, Figure11-1 (64-pin DIP)](https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf#page=171); [Commodore A500 Rev6A/7 schematic, sheet2](https://amigawiki.org/dnl/schematics/A500_R6.pdf#page=3). CPU control, data and address pins match both; Gary REGEN is pin18 in the schematic.

This is a wiring plan. After the user connects it, first validate clock and strobes with the normal ROM before loading a measurement ROM. Preserve capture settings and this mapping alongside all captured files.

## Live validation, 16 October 2026

The user installed this wiring and powered the A500 to its Kickstart floppy
screen. Scope capture validates a ~7.094 MHz D0 clock, active CPU strobes,
CH1/D8 data13 consistency, and Gary-triggered reads decoding to INTENAR
($DFF01C) and INTREQR ($DFF01E). Both signal-generator outputs remained OFF;
One ROM USB scan succeeded. No ROM was changed. Evidence and analog
undershoot limitations are in
`captures/a500-scope-validation-2026-10-16/README.md`. This validates the
initial bus observation setup, not a BZERO timing result or every pin's
identity independently.
