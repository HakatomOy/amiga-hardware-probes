# CPU overwrite versus A fetch — 2026-10-20

## Question

Leading hypothesis: the first A-source transfer is misplaced relative to a CPU
transfer under display DMA. Competitor: ordering is correct and the discrepancy
lies in completion/status or later observation. The preceding kind76 experiment
excluded a terminal-D-only explanation: A-only still has timing differences.

Kind77 starts a one-word AD blit and overwrites source `$12000` with `$5555`
after zero to three ROM NOPs. Settled D identifies the old `$AAAA` or new value.
An identical store to unused neighbor `$12002` controls bus effects. D-only,
no-start and preseeded-AD `$5555` controls distinguish corrupted captures or
failed writes from a source-fetch race. All address/value selection precedes
the timed launch; the overwrite instruction is always `MOVE.W D0,(A1)`.

The2304 descriptors cross no/four/six-plane DMA, normal/nasty, neighboring
launches and two repeats. This is a **relative ordering witness**, not an
electrical timestamp. Post-write beams include the following beam read's
contention; no event alignment is permitted.

## Reproduction and provenance

- Builder: `build_handoff_race_rom.py`; ROM archive `build/handoff-race-v1`.
- Workflow: `experiments/workflows/handoff-race.json`.
- Source ID: `f9c5d11ba25325b0ad07870a11211c4228bfdb48f509d65fdd0046e50cd98364`.
- ROM SHA256: `073460b6638e860d9390e3dbd2516efa1cffcc9a3edc57cbf87da9efe267553a`.
- Frozen baseline: Copperline `4f625516` in
  `captures/accuracy-round-20261020/pointer-candidate-v2/emulator.exe`.
- Captures and trace: `captures/handoff-race-20261020/`.

Preflight verifies every selected CPU-written word is5555, all1152 no-start
destinations are0, active D-only isffff, preseeded AD is5555, and unrelated
neighbor writes leave ordinary AD ataaaa. Ordinary source races may produce
onlyaaaa/5555, with an old-value witness required. The model currently fetches
old data in all192 ordinary active source-write cases; positive controls prove
that new data can reach D. Hardware must satisfy the same integrity controls.

The filtered emulator trace reproduces preflight byte-for-byte (packet SHA256
`df69d32a78db3b923a78c600b3bae4ae9e006225e856a4477b5e288079f572f9`).
Use `tools/summarize_handoff_race.py RUN --out REPORT` for ordering counts and
bounded changed groups; full traces and matching rows remain file-backed.

Relevant emulator paths: `src/cpu.rs` (CPU stores), `src/bus.rs` (grant/sample),
`src/bus/dma_slots.rs` (ownership), `src/chipset/blitter.rs` (source fetch).
Do not infer a fix from a status-only difference when the destination ordering
matches; any candidate needs kind71/74/75/76 neighbors and broader regressions.

## Hardware result

Both restorations verified. All2304 measurement records agree byte-for-byte
between the two hardware runs; only the boot-time VPOSR snapshot and header
checksum differ (`a000` versus `a001`). Preserve both original headers; do not
claim that the complete packets are byte-identical. Archived references:
`references/handoff-race-v1/run1` and `run2`.

Baseline:1864 matches,440 differences; zero missing/invalid/excluded/unstable
or conflicting cases.64 cases have a destination-order difference;384 have
beam differences (overlap exists). Every destination control matches.

The64 ordering errors copy5555 on hardware andaaaa in Copperline:

- Four planes: earliest overwrite only,8 cases each for normal/nasty.
- Six planes: overwrite delays0,1,2,8 cases each for normal/nasty.
- No-display-DMA, unused-neighbor, no-start, preseeded and D-only controls pass.

This independently establishes an ordering discrepancy, not merely a readback
phase error. In the model's four-plane case `77,3,2,0,0,0`, BLTSIZE grants at
h128, application h130, StartDelay h130 idle, INIT h131 under bitplane DMA,
A fetch h132; CPU overwrite requested h132 waits to h134. The six-plane case
`77,3,4,0,0,0` applies start h178; both h178/179 are bitplane-owned, yet the
internal startup advances and A fetches h180 ahead of the CPU.

## Candidate inference

Both normal startup stages consuming eligible slots predicts A at h134 for
the four-plane launch and h188 for the six-plane launch. CPU overwrite can
then win at the observed earlier delays. This is a generic arbitration rule;
it does not branch on plane count. The earlier INIT-only candidate misses the
first-stage stall and is insufficient evidence for rejecting the two-stage
rule. Keep E/F, CPU grant and RAM commit phases unchanged in this candidate.
Acceptance still requires exact field/qualification preservation across the
independent source-mask, no-DMA, Copper and broader suites.

## Controlled implementation results

`start-eligible-only` repairs376 complete cases and1024 fields, with no
regressions. All384 beam differences disappear, leaving exactly64 destination
errors. Source inspection identified a separate cause: normal A/B reads used
RAM snapshotted at BLTSIZE, regardless of the later granted DMA slot. The
rejected INIT-only counterfactual also retains all64 ordering errors and
introduces timing regressions; its lower mismatch count is not acceptance.

`live-start-acceptance` combines both eligible startup stages with live A/B
source reads. All2304 race cases match, repairing440 complete cases and1152
fields without regressions. Registers, E/F, CPU grant and write-commit phases
are unchanged. Legacy serialized snapshot/overlay fields remain loadable but
no longer determine DMA source data; new source vectors are empty. Existing
overlap/save-state tests and new per-fetch latch tests cover A/B behavior.
Direct physical overwrite evidence is for A; B uses the same live-memory DMA
rule and has unit/neighbor regression coverage.

The four independent focused suites also pass exactly: kind75 startup1152,
kind76 A-only/request2304, kind71 status-first1536, kind74 read-source1536.
Together with kind77,8832 focused rows match with no exclusions or invalid
captures. No prior matching field or qualification regresses. Full acceptance
still requires the declared neighbor and broad validation ladder in
`experiments/workflows/blit-start-live.json`; partial checks cannot accept it.

The generic two-stage candidate fails that neighbor gate: Copper-launched
bus-onset/completion/pressure cases lose qualification or regress fields, and
CPU-started Copper-pressure neighbors regress16 fields. It is rejected despite
the8832 focused matches. `neighbor-batch/` retains every failure.

The revised `blit-start-copper` candidate distinguishes the already-calibrated
deferred Copper launch from CPU launch, and tests whether CPU startup can
overlap Copper while still waiting for fixed DMA. The startup mask is applied
identically to live stepping and deadline prediction. A defaulted saved-state
flag preserves old pending-start behavior; serialized legacy source fields
remain loadable. This is an ownership/source rule, not a plane-count or program
workaround. The same full validation ladder must pass before acceptance.

The revised candidate preserves all8832 focused matches and passes all15
reference suites without new field or qualification regressions. Bus completion
and pressure restore their original64/44 exclusions; bus onset retains one
known difference. The older Copper-pressure handoff suite repairs56 cases but
retains208 differences, so broad Copper timing remains unresolved. CPU operands
match960/960; IRQ, collision and CIA suites preserve their known diagnostics.
All5136 legacy BZERO/Copper packets are unchanged from the accepted baseline.

The first core-test compile caught a test-helper `clone()` call on Blitter,
which does not implement Clone. It was replaced by the existing serialization
restore helper; no emulator behavior or captured executable changed. Broad
validation is rerun after this test-only correction. The two CIA saved-reference
contracts now explicitly declare regression purpose and separate records, so
the investigation no-new-evidence guard cannot block unchanged regression work.

Two new unit fixtures initially omitted the ROM's `BLTAFWM/BLTALWM=ffff`
preconditions and produced zero data; both fixtures now set the masks explicitly.
All existing core tests passed in that run. Earlier compile/setup failures stay
in validation retry logs; only the corrected full run can qualify acceptance.
Saved ROM source snapshots include pre-existing unused CIA probe work; do not
relabel captures using hashes from later clean or modified source builds.

## Accepted outcome

Copperline commit `2b100669` implements CPU startup ownership/source rules and
live A/B DMA reads. The final `copper-start-acceptance` run passes all21 declared
checks: fifteen reference suites, legacy replay/packet identity, core tests,
strict all-target/all-feature Clippy, formatting and277 Python tool tests.
Core result:3642 passed,37 ignored,548 `video::window::` tests filtered, no failures.
The8832 focused hardware rows match and5136 legacy packets are unchanged.
Existing exclusion budgets remain64/44 for bus completion/pressure and362/384
for the collision/CIA-control suites. Excluded rows are not credited as matches.
Documentation rendering was unavailable because `myst` is not installed.

Next unresolved family:208 older CPU/Copper-pressure handoff differences (plus
the independent bus-onset difference). Design a focused source-write race with
an explicitly enabled finite Copper stream and an activity witness, rather than
repeating the now-matching no/four/six-plane experiments. Hardware electrical
timing and AGA/A1200 behavior were not established by this PAL A500 experiment.
