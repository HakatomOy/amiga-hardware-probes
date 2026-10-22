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
New tests exercise live PF?PF and sprite matching separately. A scoped live
PF?PF correction is under validation; existing Init changes remain separate.

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
