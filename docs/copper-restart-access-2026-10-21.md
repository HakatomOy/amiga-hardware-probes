# Restart access and collision qualification

## Unresolved distinction

The combined transfer/reload/RGA candidate matches all9462 focused cases, but
full acceptance stops at collision qualification: pointer259/480 with221
excluded versus the preserved199 limit; Copper411/800 with389 excluded versus
362. No qualified collision measurement differs. Do not raise these budgets,
align traces or commit the emulator candidate as accepted.

The old captures have sparse polling phases:198 independently repeated pointer
cohorts and235 Copper cohorts. Repeating the unchanged pointer ROM twice adds
valid evidence in `references/pointer-collision-phase-coverage-v1`; both restores
verified. Combining original and new packets gives292 matches,188 excluded,
zero measurement conflicts/mismatches and206 independently repeated candidate
cases. This improves coverage but does not establish restart cycle timing.

## Discriminating test

`build_copper_restart_access_rom.py` and
`experiments/workflows/copper-restart-access.json` isolate reload arbitration
without a blitter. Fixed ROM banks perform an immediate chip read/write or
VHPOSR read/NOOP write after COPJMP/COPEN, with either gate order. Copper off,
sleeping WAIT and active finite streams, both launch phases and padding0..7,
two repeats:768 cases. Qualification is the exact pre-strobe beam. Measurements
are access result, first post-access beam and fixed-loop settled witnesses.

Hypothesis: reads and writes differ in reload ownership when COPEN precedes
COPJMP. Competitor: current ownership is correct and only collision polling
cohort coverage moved. Same-launch post-access discrepancies identify an actual
cycle error; full agreement supports the coverage explanation. Require seeded
RAM and finite-Copper activity controls before hardware.

Preflight passed; live repeat pair is running in
`captures/copper-phase-20261020/restart-access-hardware-v2`. Next: inspect only
grouped access-kind/gate-order timing differences after repeatability checks.
Relevant emulator code: `src/chipset/copper.rs`, `src/bus/dma_slots.rs`,
`src/bus/custom_regs.rs`. Main record:
[Init investigation](init-resource-investigation-2026-10-21.md).
