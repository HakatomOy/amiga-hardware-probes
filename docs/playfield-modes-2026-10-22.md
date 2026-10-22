# A500 paired single/dual playfield collision measurements

## Experiment

Hypothesis: DPF changes odd/even match combination for sprite collisions.
Competing explanation: only visual or timing differences, with identical settled
collision results.512 cases pair DPF off/on with identical constant BPL1/BPL2
data, CLXCON masks/match values, sprite0 presence, DMA, and sampling sequence.
There are four enabled-plane masks, four desired patterns, four plane patterns,
and two repeats. Manual sprite0 is armed after CLXDAT clear on the measured line;
no sprite DMA, Copper, or blitter runs. Other sprites are cleared. All downstream
beams remain in capture files; no trace alignment.

References: `references/playfield-modes-v1/{run1,run2}`. ROM SHA256:
`3a614aba9686ad37d83a210a0016b6ec870e36d1fa07294ba0e4ab0c31d82765`.
PAL A500 stock68000,512KiB chip/512KiB slow; silicon revisions unconfirmed.
Two independently captured packets,256 repeated input cohorts, zero conflicting
collision observations, invalid/missing/excluded cases. Raw packets differ in
uncompared beam metadata; every compared collision value is repeatable. Probe
was retained between captures and original ROM restored once at session end.

## Findings

Across256 single/dual pairs (including repeats), sprite0?PF1 bit1 differs in24.
Sprite0?PF2 bit5 and PF?PF bit0 do not differ solely because of DPF in this matrix.
For sprite collisions, single-mode odd match also requires the even match; dual
mode permits independent odd match. Copperline already matches all512 sprite
bit observations and all512 immediate second samples.

The new test exposes328 PF?PF differences:320 missing assertions and8 spurious
assertions. Live readback was using nonzero visible odd/even pixels instead of
CLXCON matches and skipped single-playfield mode. The initial zero BPLDAT and
later constant DMA samples both contribute to this latched result. Mode pairs
and mask cases must be preserved independently; do not generalize these A500
results to unmeasured modes, planes, sprites, or timing boundaries.

## Files and validation

Builder: `build_playfield_modes_rom.py`; exact entry snapshot:
`experiments/probe-sources/playfield-modes-v1.py`. Workflow:
`experiments/workflows/playfield-modes.json`. Full capture and diagnostic:
`captures/playfield-modes-20261022/hardware-v1`.

Copperline fixture `src/bus/tests/data/a500_playfield_modes.csv` contains256
unique consensus observations, derived from both hardware runs and both repeats.
New tests exercise live PF?PF and sprite matching separately. The active Copperline test pins the sprite matching truth table. Two PF?PF tests
are explicitly ignored as known failures; the strict ROM replay stays enabled.
No collision implementation change is accepted; prior Init work remains separate.

## Reproduction and timing scope

Regenerate the Copperline fixture with
`python tools/playfield_mode_fixture.py captures/playfield-modes-20261022/hardware-v1 --out PATH`.
The exporter rejects missing matrix entries, either missing mode, fewer than two
independent runs/two repeats, or conflicting collision values. It reports12
unique sprite?PF1 mode differences across128 unique pairs (24 when the probe's
two repeats are counted). Both runs have identical paired input markers; run2
also has identical paired clear/read brackets. Run1 has one pair with differing
downstream brackets; its collision bits still agree with the other run/repeats.
This is a settled logic test, not an early-edge timing measurement.

The versioned pre-fix Copperline packet in
`experiments/baselines/playfield-modes-before-fix` makes the required328 repairs
reproducible without committing an emulator executable or ROM image. The strict
workflow requires512 matches and no invalid/excluded/unstable cases and is added
to the main timing acceptance suite's neighbor checks.

## Rejected correction and follow-up

The match-mask-only candidate passed core3682 but replay matched424/512,
leaving88 missing zero assertions and introducing20 field regressions. Earlier
C3 pointer/Copper packets are unchanged; their original qualification blockers
remain. Source counterfactual: `experiments/patches/playfield-modes-rejected-match-only.patch`.
It is **rejected**, not part of the Copperline commit.

`references/playfield-zero-burst-v1/{run1,run2}` contains a focused32-case follow-up,
CLXCON0040/C3, zero/all-ones planes, both DPF modes, four repeats. Six destructive
reads bracket fetch/display start. All compared observations are independently
repeatable, with no excluded/missing/invalid cases. The A500 zero match is seen
near that boundary, not solely at the late settled read. However, HW burst
brackets are4423..4451 or4427..4455 versus Copperline442A..4459; sample indexes
must not be aligned or treated as identical grant times. Individual beam/read
brackets are the next discriminator before a display-phase or bus fix.
Zero-burst ROM SHA256:
`c782993fab7a63d1d42a343fff6f0b928bc89450f6e62b9d8276e3e024585be1`.
The measurement used the frozen rejected candidate and records that fact through
its binary hash; it does not qualify that candidate. Both measurement sessions
restored the original ROM once at their stop, with no restoration between repeats.

Final test-only state preserves the original emulator behavior: replay again
reports184 matches/328 PF?PF mismatches, zero newly regressed fields, zero
qualification changes, and no invalid/excluded/conflicting captures. The active
sprite matcher test validates256 consensus rows; two known-failing PF?PF tests
are ignored with explicit reasons. No rejected implementation is committed.

## Final commits and checks

Copperline `52d4060b` commits only the paired tests, consensus fixture and
behavior/known-gap documentation. Final core3680 passed,0 failed,39 ignored
(including the two explicit new PF?PF failures),559 window tests filtered.
Strict Clippy and formatting pass. Probe-tool suite356 passes. Original Init
working changes remain uncommitted and unchanged in behavior. The rejected
collision model is not present in the emulator commit.

## Init isolation and collision follow-up

Unfinished Init timing changes are preserved in Copperline branch
`wip/init-copper-timing`, commit `02318e9e`. Collision work continues from
`fix/a500-hardware-timing` at `52d4060b`, without that prototype. A freshly
built clean binary reproduces184/512 matches and328 PF-PF differences,
with no qualification changes. See `captures/collision-clean-20261022/modes-baseline`.
Kind103 sweeps separately bracketed clear/read intervals and moves DDF/DIW
independently; its contract is `experiments/workflows/playfield-boundary.json`.

The two new captures are versioned as `references/playfield-boundary-v1/run1`
and `run2`:768 cases each, independently stable collision values, no invalid,
missing or excluded cases. One within-packet beam-bracket variation is retained,
not mistaken for a collision-value conflict. The original ROM was restored and
verified when live measurement stopped. The ROM hash is in the workflow and
reference manifests; the exact source builder is `build_playfield_boundary_rom.py`.

For all-ones data, CLXCON0040 (plane1 must be zero) sees a transient assertion
with the standard window and with DDF moved eight CCK later. Moving DIW sixteen
lores pixels later removes it. CLXCON00C3 (both planes must be one) shows the
later nonzero data in both moved controls. DPF alone changes neither pattern.
Thus the zero comparison is window gated, but the data stream follows fetch
timing. Individual raw beam brackets remain available via
`tools/playfield_boundary_report.py PACKET --out windows.csv`; do not align them.

Candidate under validation: use CLXCON match masks in either mode, and place
classic lores DMA PF-PF samples at captured fetch origin plus the BPL1 slot
(seven CCK) and the existing Denise write-effect delay (four CCK). Compare zero
before that stream arrives, only inside DIW. Keep sprite matching and unmeasured
AGA/hires/manual-stream timing unchanged. The experiment constrains a nonempty
zero interval and the independent gates; it does not alone prove a precise
electrical latency. Old pointer/Copper packets and early brackets must still
validate this candidate. A blanket phase shift is not accepted merely because
the settled truth table passes.

That uniform-stream candidate is **rejected**. It repairs328/328 settled cases
(512 matches), improves the bracketed probe314 to670/768 matches, but regresses
three strictly qualified older Copper observations:
`72,1,4,19,0,0`, `72,1,4,21,0,0`, `72,1,4,21,0,1`. The input/read brackets
are identical in those cases; first CLXDAT is missing bit0, second still has it.
The pointer suite retains281 qualified matches. New bracketed cases also gain
60 field regressions, so their aggregate improvement cannot qualify the model.
Source counterfactual: `experiments/patches/playfield-modes-rejected-uniform-stream.patch`.
Binary/reports: `captures/collision-clean-20261022/{modes-candidate-v1,boundary-candidate-v1,candidate-neighbors-v1}`.

Revised discriminator: kind104 gates CLXCON with a finite Copper list, requiring
the absent plane6 to be one outside the selected interval (0820). The CPU reads
only after the gate closes; INTREQR bit2 witnesses Copper completion. Opening and
closing sweeps, independent DDF/DIW shifts, zero/all-ones pixels and DPF pairs
separate startup gating from a uniform stream delay. Workflow:
`experiments/workflows/playfield-gate.json`. The initial v1 probe was rejected
by emulator preflight because WAIT low bits were malformed and no completion
marker appeared; it never reached hardware. v2 passes all1024 activity controls.

## Gated evidence and narrower model

`references/playfield-gate-v1/{run1,run2}` contains1024 stable cases and
`references/playfield-word-gate-v1/{run1,run2}` contains768. Every completion
witness is set and every second CLXDAT is zero; no invalid, excluded, missing or
conflicting observations. Gate packet pairs are byte-identical; read timestamps
are retained in the word-packet manifests. The latter probe repeats0000,FFFF,
8000 and0001 in both planes. All-ones and isolated first-bit gate thresholds
agree; the isolated last bit appears later. This rejects dropping the start of
the first word as an explanation for the brief zero match.

`tools/playfield_gate_report.py` returns bounded WAIT-sweep strings and file-backed
case IDs. `tools/playfield_gate_fixture.py` validates two independent runs and
both repeats, then exports896 consensus gate cases for Copperline. It refuses
conflicts, missing conditions, failed witnesses and nonzero second samples.

An intermediate model corrected CLXCON's coordinate and added a BPL1-trigger
gate, but retained a four-CCK mask delay and data delay. It matches1020/1024 and
766/768; **all six residuals are the independently shifted DIW control**. The
independent DIW boundary distinguishes the otherwise compensating mask/data
delays. Reports: `captures/collision-clean-20261022/{gate-candidate-v2,word-gate-candidate-v2}`.

Narrower candidate: CLXCON takes two CCK from its bus slot to the comparator;
map that event with the absolute comparator coordinate. The classic lores DMA
stream begins two CCK after the BPL1 slot, enabling comparison one lores pixel
before that data. Preserve the existing CLXDAT read phase. This is a half-CCK
data shift from the old captured-row placement, rather than the rejected2.5-CCK
shift. The pure image renderer and other register classes keep their own
calibration. Validate both gated matrices, settled modes, old pointer/Copper
cases and broad regressions before accepting it. Ungated CPU bursts remain
diagnostic: differing raw read brackets must never be silently aligned.

## Final replay findings

The narrower model matches all1024 gated and768 isolated-bit cases. The older
pointer/Copper suites retain281/438 qualified matches, with no value differences.
All nine broad replay packets (8416 cases) are byte-identical to the clean branch.

Original late-clear matrix:488/512 matches,304 repairs,zero regressions;24
remaining cases all use phase2 and targets8/9/12. Example `101,8,0,2,0,0` has
the same424E entry, but pre-clear443C in Copperline versus4438 on A500. Its
original strict512 floor is untouched and still fails. The original ungated
window sweep is668/768 and remains diagnostic, not a timing conformance pass.

A new experiment moves the matrix clear threshold from4420 to4400, safely
before DDF/startup. `references/playfield-early-clear-v1/{run1,run2}` independently
matches512/512, repairing328 cases against a same-ROM pre-fix baseline without
new fields, qualification changes or excluded/invalid/conflicting observations.
The new experiment is separate; it does not replace the late-clear failure.
Its full consensus collision values also reproduce the original256-row fixture.
Scoped workflow: `experiments/workflows/playfield-early-clear.json`.
Concise handoff: `docs/playfield-collision-fix-2026-10-22.md` and
`investigations/playfield-collision-fix.json`.

Copperline commit `7bbedf58` accepts the scoped correction. Final core3670 pass,
zero failures,37 ignored,559 window tests filtered; strict Clippy/format pass.
Probe tools361 pass. Two older timing fixtures were corrected to stage/query
CLXCON in its absolute comparator coordinate; original bitplane observation
windows were retained. The original late-clear24 failures remain explicit.
