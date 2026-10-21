# Init and Copper/CPU investigation

## Confirmed hardware evidence

A500 was power-cycled before this session. OneROM restores were verified after
all live runs. Hardware remains authoritative; no trace alignment is applied.

- `references/init-resource-race-v1`:600 qualified cases,300 independently
  repeated cohorts; measured fields stable although raw packets differ.
- `references/init-resource-launch-sweep-v1`:606 qualified cases,303 independently
  repeated cohorts; two byte-identical packets, zero invalid, excluded, missing
  or unstable results. ROM SHA256:
  `a32cc59c177a6bb85d7692cec189851de566f671f841ccd65637fa543cf3262f`.
  Exact builder: `experiments/probe-sources/init-resource-launch-sweep-v1.py`.

Both probes pair Copper off, sleeping WAIT and finite active streams, identical
CPU opcodes, source races, inert starts, neighbor and preseed controls. The sweep
covers both launch phases and padding0..7 with NOP0/1/3.

## Supported correction

Classic CPU words transfer before their tail. Copper's second restart phase
owns a DMA slot for pointer reload. Normal bus-free body phases, including the
first D math bubble, must respect the pre-refresh RGA reservation already
required by Init. StartDelay, memory transfers and internal terminal phases
retain distinct rules. Keep the completion predictor consistent with execution.

The launch sweep separates this from CPU-write blocking: all fetched sources
already matched, while64 status mismatches executed math at E1 before refresh.
Fourteen further differences included inappropriate post-refresh Init holds.
Removing write holds and reserving bus-free body phases repairs both groups.

## Rejected models and evidence

Blanket CPU-write Init holds lose152 register witnesses. Restricting that hold
to the preceding Copper second word still fails78/606 sweep cases. No CPU
write-direction field remains. The old Init-as-Bus experiment failed because it
never asserted the bus request; it does not refute a correctly asserted request.
Full chronology: [experiment history](init-resource-experiment-history-2026-10-21.md).

## Validation and next action

`captures/copper-phase-20261020/body-turnaround-controls` matches all3894 focused
cases: access1024, register768, onset384, original resource600, sweep606 and
handoff512, without exclusions or new measured-field regressions. This includes
new hardware evidence and preserved earlier suites; it is not yet broad acceptance.

Source: Copperline `src/bus/dma_slots.rs`, `src/chipset/blitter.rs`,
`src/chipset/copper.rs`, `src/cpu.rs`, `src/bus.rs` and named bus tests.
The final binary preserves all9462 focused cases. Standalone core3676, strict
Clippy, format and331 probe-tool tests pass. Full acceptance stops at collision
qualification losses; remaining CIA/legacy/broad stages have not run in that
acceptance batch. Follow the [restart investigation](copper-restart-access-2026-10-21.md)
before resuming acceptance or committing the emulator. Reuse archived hardware
by default; the new live test resolves a specific reload uncertainty.

## Latest validation boundary

The clean internal-frame restart candidate passes core3679, strict Clippy/fmt,
and reproduces all1664 selected startup/control packets exactly. Experimental
broad screen26/28 contracts pass across23830 cases; original collision phase
qualification still blocks acceptance. New960-case A500 collision diagnostic
shows stable planes-off controls but81 conflicting active-DMA cohorts. See
[controlled collision record](controlled-collision-investigation-2026-10-21.md).
No Copperline commit yet; no hardware session remains active.
