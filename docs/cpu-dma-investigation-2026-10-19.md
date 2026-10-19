# CPU bus/prefetch and IRQ under DMA

Stage4, accepted baseline Copperline4038ec64. Blitter E/BusFree experiment from
stage3 is rejected and reverted; use accepted binary at
`captures/cpu-irq-20261019/candidate2-binary/emulator.exe`.

Leading hypothesis: CPU grant/prefetch timing accounts for the no-start Copper
family. Competitor: IRQ recognition phase. Kind61 crosses NOP,STORE,TST,STOP and
masked readback with CPU INTREQ/unmask sources PORTS,EXTER,COPER, no DMA,
four planes,six planes,and six+Copper32 finite NOOPs.1920 cases; two phases,
four launch pads,two repetitions. Bitplane setup matches stage3. Copper starts
after prelaunch observation. Do not infer electrical IPL edges from handler beam.

Compare exact launch conditions. Raw request visibility additionally requires
all read brackets; a separate launch-qualified access-bracket report retains
read-timing differences as bus evidence. No time shifts. DMA0 checks the accepted
CPU-source fix; masked timing versus IRQ-only PC/count differences discriminates
bus handling from recognition.

V1 STOP continuation offset was corrected by assembled-byte inspection before
hardware use. V2 source26d663f7, ROM SHA cdb43469.1920 valid emulator observations;
STOP PC is ffcd1a.16 repeated emulator cohorts differ only in diagnostic serial
ICR flags. Both independent hardware runs agree on all1920 measured records, with verified
restoration. References `cpu-dma-v2-run{1,2}`; source/configuration/result hashes
are in manifests. Original runs `captures/cpu-dma-20261019/a500-v2-run{1,2}`.
Immutable build `build/cpu-dma-v2`; logs/results under the capture root.

Tools `build_cpu_dma_rom.py`, `compare_irq_stage.py`; byte-boundary, source-decode
and shifted-read acceptance checks in `tests/test_cpu_dma.py`. Relevant Copperline
files: `src/bus.rs`, `src/bus/dma_slots.rs`, `src/cpu.rs`.
Next unresolved question: which DMA/instruction combination first diverges,
and whether a bus-access bracket already differs before IRQ exception entry.

## Confirmed result and boundary

All1920 cases qualify.1810 full matches,110 differences:96 timing differences,
16 diagnostic serial-flag differences (two overlap). All timing differences are
memory-TST with six planes+Copper: handler beam eight CCK early; original stacked
PC and loop count agree. No-DMA,four-plane,six-plane-only,NOP,STORE and STOP timing
controls match. All384 masked read brackets match; no request visibility errors.
This rejects a common IRQ latency change and a universal Copper grant delay as
safe fixes. Preserve the TST/Copper family as a CPU operand/exception timing
constraint; no further emulator patch is accepted in stage4.

Broad trace-v2 hit the control RPC wall timeout while logging beam-poll loops;
it has no valid packet and is explicitly marked unusable. Trace-v3 restricts
logging to operand/vector/stack/IRQ addresses and must be byte-identical before
interpretation. `tools/trace_cpu_dma.py` preserves its flags and verification.
Next discriminating test: TST with chip versus ROM operands and corresponding
MOVE/CMP controls under the same finite Copper burst, before changing core
operand/prefetch or exception sequencing. Relevant upstream core is pinned
m68k3be19f7; do not edit unrelated untracked vendor work. The wider CPU matrix
and stable references are the completed stage4 deliverable; serial buffering
is stage5.

Focused trace-v3 is byte-identical to the untraced1920-case emulator packet.
All1536 IRQ events map to cases by exact count and complete level-sequence
verification, without shifting timestamps. Index `trace-v3/irq-case-index.json`;
representative excerpts `trace-v3/case-61-{0,1,2,3}-24-0-0-0.txt`.
TST operand read in the representative starts at line67,hE1 and crosses the
line-end refresh region; STORE instead waits at line68,h0?h7. This raises a
specific alternative to TST-prefetch ordering: CPU data grants crossing the
line-end refresh slot. A chip/ROM TST plus MOVE/CMP sweep must distinguish these
before imposing a global grant restriction. Stage4 is measured, not fixed.
