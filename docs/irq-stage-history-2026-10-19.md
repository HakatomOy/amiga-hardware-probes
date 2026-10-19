# Source propagation versus CPU recognition

Leading hypothesis: external CIA routes need an extra source-stage delay.
Competitor: source-bit-specific poll qualification compensates for a CPU sampling
error. Compare CIA-A/PORTS and CIA-B/EXTER with Copper-generated requests for the
same Paula bits and COPER. Use STOP, NOP/DBRA, byte-store/DBRA, memory-TST/DBRA,
and masked INTREQR readback controls, four phase pads and eight event offsets.
A raw-request shift implicates source/latch visibility; recognition-only shifts
implicate polling/encoding downstream. Software timestamps cannot separately
measure the physical IPL pin, so the existing calibrated default stays until a
replacement model is supported across all controls.

Kind56:1600 cases,2 repeats. CIA latch32..39 E clocks; software Copper requests
line66 h60..6e colour clocks. These units are distinct. Primary IRQ handlers at
levels2/3/6 timestamp before register pushes; line70 SOFT level1 wakes STOP if
the primary event is missing. No polling in the measured running loops.

Archive inputs before measuring. Preflight finite completion, exactly one
primary interrupt in ordinary cases, raw source visibility in masked controls,
source hashes and checksums. Compare only exact pre/post release brackets;
report missing brackets and unstable repeats. Do not align traces to fit.

Files: `build_irq_stage_rom.py`, `src/rom/irq_stage_{kernel,observer}.i`.
Existing uncommitted kind51 files belong to earlier work and remain unchanged.
Initial plan; no hardware result or emulator correction claimed yet.


## Current evidence

V4 unaligned:run1 has172 qualified/40 mismatched; run2 has137/37. Two physical
runs agree on158 exact software-request/read cohorts; CIA launch phases did
not overlap between those runs. All captures restore the original live ROM.
V5 alignment-only preflight failed: a Copper request could precede STOP, then
its handler disabled the watchdog before returning into STOP. Never used on HW.
V6 moves primary Copper WAIT to line68 and watchdog to72 and extends masked
settling;1600 emulator and physical cases validate. Run1:637 qualified,
437 matches/200 differences,963 excluded. COPER and EXTER STOP controls match;
PORTS STOP is four clocks early in32 matched cases, CIA STOP generally two
clocks early. These statements compare same-scanline handler observations,
not isolated pin propagation. Software raw v6 reads are before the request;
their agreement does NOT constrain the transition edge. V7 repositions those
masked software reads near the edge; emulator preflight pending.

Origin6 candidate: track Copper-written PORTS/EXTER separately from external
pin-fed requests, retain global6 default and CIA behavior, apply internal poll
lead and arm new software PORTS source edges. Must match STOP AND running
controls before acceptance. Exact patch/executable saved under
`captures/irq-stage-20261019/origin6-binary`. Nothing accepted yet.

The phase-pad metadata describes NOP/EXG instruction lengths; conditional
branch costs also apply. Captured beam brackets are authoritative. The v6
manifest text still says line66/70: its archived staged kernel actually uses
line68/72. Builder metadata is corrected for v7 and later. Do not rewrite the
immutable v6 archive.
