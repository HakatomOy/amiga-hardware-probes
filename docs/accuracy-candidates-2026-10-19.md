# Four priority accuracy candidates

Continue in order; preserve original unrelated kind51 working files.

1. **Fixed: CIA serial flag boundary.** Copperline`b487bae1`;1533 extended and369
   short qualified cases match, plus all older stable serial controls.3637 core
   tests, strict Clippy and format pass. See serial-phase investigation/record.
2. **Measured: CPU chip/slow operand timing.** New kind65:960 qualified cases,
   96 differences shared by TST/MOVE/CMP chip and slow operands under six planes
   plus Copper; ROM operands, STOP and raw controls match. Global pre-refresh
   CPU guard rejected (88 repairs,18 regressions,54 lost launch cohorts).
   A revised DRAM-only guard is under test. See CPU operand record and captures.
3. **Prepared: CIA counter/output versus request propagation.** Kind66 samples
   counter,PB6,ICR and Paula INTREQ with independent calibration and PBON-off
   controls. Preflight-v2 was uninformative and rejected before hardware.
   Preflight-v3 meets explicit clear/asserted coverage. No physical run yet.
4. **Pending: four-plane blitter handoff.** Preserve stable64-case early family
   and no-start/read controls. Reassess after bus candidate2; if unresolved,
   vary polling cadence independently of launch to separate observation/grant
   timing from terminal sequencing. Do not revive the rejected global E/BusFree
   change. See prior handoff focus plan.

Commands, evidence and resumable validation use `tools/experiment.py` and
`experiments/workflows/`. Logs/builds stay in ignored captures/build directories;
reviewed hardware packets and provenance are versioned in references.
