# CPU operand memory and refresh

Priority2 follows accepted CIA serial fixb487bae1. Physical baseline uses the
immutable a2299b00 executable; the serial change does not alter this source path.

Kind65 crosses TST/MOVE/CMP chip18100,ROMffb000 and slowc18000 operands, four DMA
modes, two phases/four pads, and STOP/masked controls.960 cases,all qualify.
Two independent physical runs agree on every raw record (packet headers differ),
with both restorations verified. References `cpu-operand-v2/run{1,2}`;
source117b5238, ROMead12d28. Build `build/cpu-operand-v2`, results/logs
`captures/cpu-operand-20261019/baseline-v2`.

864 matches,96 differences: all TST/MOVE/CMP chip or slow operands with six
planes plus Copper. Handler beam is8CCK early within the same line; PC,loop
count and all other compared fields match. ROM operands,STOP/masked and simpler
DMA controls match. This rejects a TST-only or common IRQ-latency explanation.

Rejected rules, with patch/binary/case reports retained:

- Global stock CPU pre-refresh guard:88 repairs,18 value regressions,54 lost
  launch cohorts. `refresh-candidate-v1`, rejected-global-pre-refresh patch.
- DRAM read/write guard, registers exempt:88 repairs,12 full/24 field regressions,
 48 lost cohorts. `dram-candidate-v2`, rejected-dram-readwrite patch.
- Unconditional DRAM read/fetch guard:912 qualified matches,88 repairs,no value
  regressions but48 lost cohorts. This remains rejected; exclusions are not
  repairs. `read-candidate-v3`, rejected-unconditional-read patch.

Byte-identical baseline/candidate diagnostic traces prove that a control's
recording write at record772+12 ($478ec) requests at v42,hE1. Baseline grants
hE1; read/write candidate delays to next-line h0 (2CCK wait), shifting the next
INTREQ write from h10 to h12. This explains the control regression. Trace index
`trace-selection.json`; first operand excerpt `operand-first-case.txt` maps
case65,0,28,0,0,0 by all768 IRQ events. Its read starts at v43,hE1 amid the
finite Copper stream. No timestamp shift or trace outcome alignment was used.

Current hypothesis: DRAM read turnaround after preceding Copper ownership
overlaps final refresh; uncontended reads and writes keep their phase. Competitor:
another CPU/arbitration phase rule. Candidate is constrained by all960 controls,
held-out1920 IRQ-source cases and baseline-qualified bus/handoff neighbors.
If it still regresses, preserve the constraint and design a smaller direct-read
reproducer rather than piling on address/instruction exceptions.

Files: `build_cpu_operand_rom.py`, `tools/trace_cpu_dma.py`, `tools/experiment.py`;
Copperline `src/bus.rs`, `src/bus/dma_slots.rs`, `src/bus/tests.rs`.
Accepted Copperline346f0585. All960 focused cases match:96 repairs,zero field
or qualification regressions. The1920-case CPU/DMA matrix and bus onset2176,
completion640,pressure768,handoff896 cases preserve every baseline field/cohort;
legacy BZERO/Copper packets are unchanged. Existing64/44 excluded completion/
pressure rows remain exclusions. Core tests332.61s,strict Clippy and formatting
pass. Acceptance: `captures/cpu-operand-20261019/copper-candidate-v4`.
Next: measure other ownership/video-standard boundary controls before extending
this constrained PAL result.
