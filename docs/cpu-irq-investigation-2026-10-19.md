# CPU-written IRQ recognition: accepted

Copperline `4038ec64`; preceding baseline `1bef46ef`. Stage2 is complete.

## Confirmed result

CPU INTREQ writes and INTENA unmask of software-pending PORTS,EXTER,COPER
need a two-CCK earlier reference deadline and the internal instruction-poll lead.
The old PORTS immediate bypass was early; EXTER/COPER were late. Qualification
is limited to these measured bits and stock68000 bus timing. BLIT, other
unmeasured CPU-written bits, and CIA pin-fed paths retain prior behavior.
`DEFAULT_IRQ_LATENCY_CCK` remains6. Snapshot loading accepts the preceding
Copper-only origin field and missing-field legacy states.

Main probe1152: NOP/DBRA,STOP,masked INTREQR; held-out768: STORE/DBRA,TST/DBRA.
All1920 cases qualify by exact launch/read brackets. Timing differences1408?0;
1910 complete matches,ten diagnostic CIA serial-flag differences. Both independent
physical runs agree on all measured main and held-out records; restorations pass.
No timestamp shifts. Handler beam combines source/CPU exception timing.

## Evidence and validation

References: `cpu-irq-v5-run{1,2}`, `cpu-irq-neighbor-v1-run{1,2}`. Manifests retain
ROM/source/result hashes, raw machine metadata and restoration proof. Main source
`20ff6520`, ROM `edcd6716`; held-out source `5bc142e2`, ROM `458056ed`.
Immutable builds: `build/cpu-irq-v5`, `build/cpu-irq-neighbors-v1`.
Detailed logs/reports/binaries: `captures/cpu-irq-20261019/`; accepted executable
`candidate2-binary/emulator.exe`. 3632 optimized core tests pass,37 ignored,548
window tests excluded; strict Clippy+fmt pass;201 probe tests pass. Ten prior
replay packets and new CIA-phase1920 packet are byte-identical; source-stage IRQ
results unchanged. A broader BLIT deadline change was caught by core tests and
removed before acceptance.

## Commands and next boundary

`python build_cpu_irq_rom.py --wsl --vasm PATH --out NEW [--neighbors]`.
`python compare_irq_stage.py --hardware REFERENCE --candidate CAPTURE --out REPORT`.
`tools/run_irq_latency_sweep.py` preserves explicit diagnostic overrides separately.
Sources: Copperline `src/bus.rs`, `src/bus/custom_regs.rs`, `src/bus/tests.rs`;
probe `build_cpu_irq_rom.py`, `compare_irq_stage.py`.

DMA operand/prefetch/IRQ controls are stage4. The CIA fresh-underflow difference
is separate. [Experiment history](cpu-irq-history-2026-10-19.md) records rejected
preflights, the scope correction and full validation chronology.
