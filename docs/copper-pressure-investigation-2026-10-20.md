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

## Access-space result and witness control

Kind79's two physical packets are byte-identical with verified restoration.
All 1,024 cases qualify: 512 no-Copper matches and 512 Copper differences, zero
invalid/unstable/excluded cases. References are
`references/handoff-copper-access-v1/run1` and `run2`; full run:
`captures/copper-race-20261020/access-hardware-v1`.

The no-start custom/chip/slow reads show identical first-post-beam offset
distributions: hardware is 4/6/8 CCK later. ROM reads show 8 CCK in all no-start
cases. These differences are computed only on known same/adjacent PAL lines,
not by subtracting arbitrary packed beam words. A blitter-only fix cannot
explain them; access space alone does not isolate the cause.

Kind80 narrows the common prefix: compare the original memory-to-memory launch
witness with a register-held sample written back after the first post-overwrite
beam. Keep identical NOP0..3, six-plane/Copper and data controls, but reduce to
phase0/pad0 (768 rows). A repair confined to register witnesses narrows the CPU
access/prefetch/writeback phase; differences in both retain general Copper/CPU
grant/request sequencing. Observer modes have distinct descriptors and are never
aligned as equivalent captures. Manifest: `handoff-copper-witness.json`.

## Witness result and rejected startup change

Kind80 has 768 qualified independently repeated rows: 492 matches and276
differences. Decoded records are identical; packet headers differ only by the
boot VPOSR a000/a001 and corresponding checksum. Both restorations verified.
All384 no-Copper cases match. Memory-witness Copper cases have192 beam
differences; register-witness cases have76. Twenty source-order cases differ;
all data controls match. Of96 register/no-start/Copper cases,72 first-post-beams
match and24 are6 CCK late on hardware. References:
`references/handoff-copper-witness-v1/run1` and `run2`.

Counterfactual CPU startup exclusion of Copper repaired18 cases but regressed36,
with152 new wrong fields across54 cases. The focused gate stopped broader checks.
The source changes were reverted and the default CI executable restored to the
accepted binary. Preserve `captures/copper-race-20261020/stall-screen-v1` and
`candidate-stall-copper/source.diff`; do not retry that startup rule unchanged.

## Direct CPU/Copper order and write-turnaround hypothesis

Kind81 removes the blitter entirely. The CPU replaces selected Copper INTREQ
instruction data8002 (DSKBLK) with8004 (SOFT); final flags distinguish old/new
fetches, and COPER witnesses finite-stream completion. Select MOVE0/4/8/12,
NOP0..7, neighboring phases and enabled/disabled Copper,512 rows.

Both A500 packets are byte-identical, with512 qualified rows, no exclusions or
instability and verified restoration. All256 no-Copper rows match. Copper
observation beams differ in256 cases, with16 genuine CPU/Copper ordering errors
at MOVE8,NOP3..6: hardware fetched old data while the model fetched new. Other
instruction positions agree. References: `references/copper-cpu-order-v1/run1`
and `run2`; full run: `captures/copper-race-20261020/order-hardware-v1`.

The existing Copper-to-refresh DRAM turnaround guard applies only to CPU reads
and fetches, exempting writes. A candidate extends it to writes, retaining custom
register, uncontended, AGA and short-cycle exemptions. This is a hypothesis until
validated against direct ordering, kinds78/79/80, the accepted kind77 baseline,
held-out DMA/CPU/CIA/display suites and broad core/tool checks. Contract:
`experiments/workflows/copper-write-turnaround.json`; do not accept a better total
with any new field or qualification regression.

## Counterfactual gates and data-phase evidence

The write-only extension had no effect on the direct kind81 observations. A
revised guard checks the upcoming Copper request on line-end refresh and also
blocks custom-register CPU cycles. It repairs all512 direct beam observations,
but exchanges the original16 data-order errors for16 newly wrong data flags:
496/512 cases match,784 fields repair,16 fields regress. It is **not accepted**.

On kind78 the revised guard repairs464 cases, but introduces16 newly wrong fields
in8 cases. All384 no-start beam differences disappear;288 active beam differences
and16 source-order differences remain. These gates stopped broad validation.
All experimental Rust changes and the default CI executable are restored to
accepted2b100669; frozen counterfactual binaries/patches remain in local captures.

The byte-identical direct trace places8 remaining Copper reads one model CCK
after the CPU grant and8 one CCK before it. A fixed-grant counterfactual moving
CPU write visibility from return(+2CCK) to grant(+0/+1CCK) repairs8 but leaves8;
on the accepted baseline it would introduce8 errors. It cannot justify a
CPU-write-only fix. Source clocks are unchanged; this screen is not trace
alignment or patch validation. `tools/summarize_copper_cpu_order.py` verifies
that the original return-phase prediction reproduces captured model flags before
screening alternatives, and retains all source evidence paths.

Reusing raw first INTREQ fields, all512 read brackets match under the revised
guard;18 early flags differ. Sixteen follow final data-order differences. In two
cases (`81,9,14,1,1,0/1`) final data agrees but HW first flags are0 versus model4.
This leaves Copper data/execution phase **and Paula read-sampling phase** in scope;
matching surrounding beams does not establish an electrical sampling clock.

Kind82 changes the first instruction word (NOP01fe to INTREQ009c) with constant
IR2=8004, otherwise retaining kind81's bounded protocol. Paired opcode/data races
distinguish a shared instruction-word data phase from an IR2-only effect. The
preflight binary is explicitly the unaccepted RGA timing counterfactual, not
HEAD; the hardware reference remains independent of that comparison choice.


## Completed opcode/quiet controls and independent stream indexing

Kind82 completed with512 qualified rows:496 matches,16 opcode-order differences,
and all observation beams matching, against the explicitly unaccepted RGA
counterfactual. References: `references/copper-cpu-opcode-v1/run1` and `run2`.
This is not validation of HEAD or of that rejected candidate.

Kind83 removes display DMA as well as the blitter. Against accepted2b100669,
512 qualified rows contain20 data-order differences (HWnewSOFT, modeloldDSKBLK);
all observation beams match. References: `references/copper-cpu-quiet-v1/run1`
and `run2`. No new bus timing candidate has been accepted.

The byte-identical quiet diagnostic replay includes256 enabled-Copper cases at
all four selected instruction positions. Copper can fetch before the inert CPU
launch witness. The indexer now binds Copper streams independently by COPER
completion order and CPU writes by witness order, with full descriptor-count
checks. It must not drop early-fetch cases or align their clocks.

The current return-phase model reproduces all256 captured final flags before
counterfactual screening. Earlier CPU visibility at grant+0/+1 repairs8 cases,
leaves12, and introduces no quiet-suite regressions. The same change introduced
8 errors in the accepted display-pressure baseline, so a CPU-write-only patch
remains rejected. Across all512 unchanged read brackets,32 first INTREQ samples
differ,12 despite matching final order. Copper data/execution and Paula sampling
remain distinct uncertainties. Detail:
`captures/copper-race-20261020/quiet-order-trace/order-trace-summary.json` and
`write-phase-screen.json`. Physical request/data-phase evidence remains useful;
no logic analyzer is assumed connected.
