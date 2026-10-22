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
