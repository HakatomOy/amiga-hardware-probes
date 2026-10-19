# Ordered A500 accuracy investigations

Baseline: Copperline `1bef46ef`, probes `e8a93ea`. Preserve pre-existing kind51
working files. Use staged builds, immutable captures and compact scripted reports.

1. **Measured: CIA phase/source path.** Per-case independent access brackets;
   underflow versus prelatched ICR mask-enable visibility; STOP/running after
   scheduled Paula unmask. Record hidden-phase exclusions.
   Two repeatable kind57 runs; qualified underflow readback differs, prelatched
   readback matches. See `cia-phase-investigation-2026-10-19.md`; no blanket delay.
2. **Fixed: CPU-written PORTS/EXTER.** INTREQ writes versus INTENA unmask,
   STOP/running controls; extend origin handling only with physical evidence.
   Repeated hardware and held-out STORE/TST:1408 timing repairs,zero remaining
   in1920 qualified cases;3632 core tests pass. See CPU IRQ investigation.
3. **Measured: four-plane blitter handoff.** One family plus no-blit controls;
   distinguish arbitration/sequencer timing, then six-plane/Copper neighbors.
   Stable no-start/read controls isolate blit-active timing; global E/BusFree
   candidate rejected by six-plane neighbors. See handoff focus plan.
4. **In progress: 68000 contention.** Operand/prefetch/IRQ poll controls under DMA,
   supported by #3 bus findings.
5. **Pending: CIA serial buffering.** Drain initial state; active-output writes,
   queued bytes and completion behavior, including repeatability.

For each: competing hypotheses and discriminating test; emulator preflight;
version source/ROM/configuration identity and restoration proof; focused and
neighboring hardware replays plus broad tests before accepting fixes. Update
this record at boundaries and commit useful emulator and probe work.
