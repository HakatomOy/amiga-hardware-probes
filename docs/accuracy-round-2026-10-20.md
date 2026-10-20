# A500 compatibility investigation order

Baseline Copperline b8a97ac6. Preserve unrelated kind51 working files.

1. **CPU/DMA and blitter handoff.** Leading hypothesis: the early window
   reflects memory-port release/grant timing. Competitor: early terminal status
   hidden by later reads. Kind71 samples status before its first beam read,
   adding two- and sixteen-word controls. Require busy/clear preflight coverage.
   Status differences at equal observation beams constrain event/readback timing;
   matching status with early beams constrains grant timing. No global E delay.
2. **Copper-driven Agnus register effects.** First audit what the documented
   two-versus-four-CCK distinction actually affects: guest DMA arbitration or
   recorded rendering. Measure a specific observable before retiming either.
   Use matched CPU/Copper writes and inactive-DMA controls.
3. **68000 timing.** Reuse instruction/source matrices after arbitration changes;
   distinguish instruction/prefetch timing from shared-bus scheduling. Design
   new instruction controls only for a remaining qualified mismatch family.
4. **CIA request propagation.** Timer counts/output fixes are separate from
   early Paula request visibility. Reuse kind66/68 evidence; isolate sub-E
   read/input sampling before changing pin delay or CPU recognition latency.

Each family gets focused evidence, neighboring regressions, then broad checks.
Commit justified emulator fixes; version physical packets and concise decisions
in the probe repository. Negative experiments remain useful constraints and
must not be reported as fixes. Existing records and workflow guide remain the
starting points, rather than rereading full historical traces.


## Status-first BLIT request result

Kind71 ROM `50a54642b7a32579e55895460fd8cc0e557022848a1304e1f76a9cc73e2ab22f`
(source `3f8596f74d419cb1185867d62154bf020c7d39b7071c25fccd3080bcb17b3fef`)
has two live runs with verified restoration in `references/handoff-edge-v2/`.
All1536 cases qualify: baseline1328 match/208 differ. Two hundred cases have
changed beam observations; their48 busy-status differences do not isolate a
status edge. Eight sixteen-word AD cases expose late INTREQ.BLIT at identical
observation beams. All no-start controls match.

The candidate changes native BLIT readback from E-start+4 to E-start+3CCK,
reducing recognition pre-age equally so the absolute CPU deadline stays fixed.
It repairs those eight fields without new field/cohort regressions. The200
arbitration differences remain. Neighbor comparisons cover operands, old
CPU/DMA, onset/completion/pressure and handoff/read controls. Two historical
kind50 request snapshots also become hardware matches at identical three-beam
brackets; those older records lack restoration provenance and are corroboration,
not the primary acceptance evidence. `tools/check_native_blit_neighbors.py`
requires every changed field to be that qualified repair and keeps unrelated
fields/BZERO strict. Six Rust tests asserted the superseded request deadline;
their expectations were updated while preserving the absolute CPU deadline.
Acceptance batch: `captures/accuracy-round-20261020/blit-request-acceptance-v2`.

## Copper/display pointer evidence

Kind72 v3 has800 rows,416 qualified matches,22 qualified differences and362
explicit exclusions; no invalid/conflicting cohorts. Positive and negative
controls pass both physical runs (`references/copper-dma-collision-v3/`).
All qualified differences are pointer retargeting, not BPLEN. Raw Copper
BPL2PTL results have lost-write-shaped holes at B2,BA,C2,CA,D2CCK, one before
the modeled selected-plane DMA fetches. A byte-identical observational replay
records the actual Copper write positions. This is evidence for an Agnus
pointer update hazard, not permission to change all Copper render delays.

Kind73 adds BPL2PTH, BPL1PTL, CPU/Copper controls and a settled CLXDAT sample
after the following complete scanline. Its first preflight was rejected:
2A000 test data overlapped RAM code ending2A552. No hardware run used that ROM.
The corrected v2 uses5A000 and explicitly clears BPLCON1. Settled-zero holes
would support genuinely lost writes; settled-one with early-zero would instead
support collision visibility. Retain both families separately.

## CPU and CIA constraints

The old1920-case CPU/DMA matrix has1904 matches and16 differences solely in
handler CIA ICR bit3 (serial diagnostic). Handler beams, saved PCs and loop
counts match. This corpus does not justify a new68000 timing patch; retain the
16 diagnostic differences separately rather than declaring the full matrix fixed.

`tools/cia_request_clock_screen.py` checks the kind68 observational packet is
byte-identical before extracting actual grants. It finds1872 eight-CCK and48
nine-CCK intervals. Nominal eight-clock alias arithmetic is insufficient.
The actual-clock counterfactual has0 differences on2974 available fields for
sixCCK, but2146 fields are unavailable; this does not establish a six-CCK pin
delay. On2826 fields shared by five/six-CCK hypotheses, five has20 differences
and six has0. Six/seven share1554 fields with0 differences each, so this corpus
cannot distinguish them. No field is supported for every delay0..8. These are
hypothesis screens, never aligned comparisons or accepted fixes. Require a
sub-E boundary probe with prelatched/mask-enable controls before a CIA patch.
Detailed screen: `captures/accuracy-round-20261020/cia-actual-clock-screen.json`.
DEFAULT_IRQ_LATENCY_CCK remains6; this is a CPU-recognition model constant,
not a measured isolated CIA propagation delay.


## Accepted BLIT fix and settled pointer follow-up

Copperline `10a0d677` accepts the native BLIT request correction. Broad core
checks, strict all-target/all-feature Clippy and formatting pass after the six
old deadline assertions are updated. Acceptance decision and logs are linked
from `investigations/handoff-edge.json`.

Corrected kind73 v2 ROM is
`89e928cb35641a5e0d5519d6103ebcfc97a2d7ec206fab8feb9ac8a64c013aaf`,
source `6386f8702df804478280c5f0639af82f9a4301d4817512fcfe02d6f1fde28aaf`.
Both new live runs restore/reset successfully and pass all constant controls.
Versioned packets: `references/pointer-collision-v2/run{1,2}`. After adding CPU
write brackets to qualification,480 rows yield244 matches,37 differences and
199 exclusions. No instability/conflicting cohorts;111 candidate rows have
independently repeated exact cohorts (not all281 qualifying rows).

Twenty-four differences include persistent settled loss; thirteen affect only
the early read. Copper BPL2 low and high halves lose at phases0,4,8,12,16;
BPL1 low losses shift to2,6,10,14. This rejects the explanation that all losses
are early collision visibility. The candidate uses a generic same-plane
counter-update window one CCK before DMA, retaining the early-only family.
Exact budgets199 (kind73) and362 (kind72) are frozen before candidate replay.

These builders inherit some generic kind56 metadata labels; their explicit
measurement fields and workflow contracts define kind71/72/73 meanings. The
original source snapshots remain under their build directories. Full-source
hashes include the pre-existing kind51 work; later clean-source builds must
not be relabeled as these historical ROMs.
