# Copperline accuracy investigation, 18 October 2026

## Scope and sequence

Work one mismatch family at a time: CIA/IRQ first, then bus arbitration and
68000 instruction/poll behavior. Emulator code and behavioral regression tests
belong in Copperline; plans, comparison tools, run logs and captures stay here.
Do not retune the already measured global IRQ delay without discriminating evidence.

## Confirmed reference evidence

- CIA timer pipeline, ICR latch and running-read findings:
  `continuous-timers-2026-10-14.md` and `copperline-fixes-2026-10-13.md`.
- IRQ/poll regression evidence: `irq-focus-measurements-2026-10-15.md`;
  hardware `irq-focus-a500-v3` and repeat; 2,212 measured observations repeat.
- Kind51 hardware references: `rom-amiga500-cia-cpu-irq-kind51-review3-run1`
  and `run2`, with decoded results under `capture/`. Test ROM SHA-256:
  `5366a95c29ab2b8cf826ed72d6ee5ffe8b8d22b5f9380d7598f517fcf1601198`;
  source ID `416ef5b56e43d6803b82cf3986d81bcf40ae747da13b98d378f43d5130bc139a`.
  PAL A500, stock 68000, 512 KiB chip + 512 KiB slow, ECS Agnus/OCS Denise;
  OneROM USB/RBCP. Preserve invocation and build manifests with each capture.
  Observed launch phases differ between repeats: exact-start cohorts, not
  whole-row equality, determine eligible timing comparisons.
- Latest starting Copperline commit: `4694aa3c`, branch `fix/cia-timings`.
  Its external-source poll rule is already a committed regression fix.

## Current uncertainty: CIA batching

Leading hypothesis: batched E-clock advancement loses timer PB output parity,
pulse duration or delayed IRQ state. Competing explanation: intentional
pipeline staging rather than lost events. Discriminator: clone identical CIA
states, advance N clocks in one call and N calls of one clock, compare complete
serialized state and returned IRQ-edge occurrence. Units are CIA PHI2/E-clock
edges (five stock A500 colour clocks), with no phase alignment or correction.

If states agree, reject this candidate and move to a hardware-constrained IRQ
family. If states differ, isolate fields and repair batching while preserving
single-edge behavior; this does not itself establish new physical pin timing.
Use timer-output modes, one-shot, cascade, ICR-read race and serial completion
as neighboring cases. Replay archived CIA/IRQ ROMs and run broader regressions
before accepting a fix. New hardware is required if the repair needs a new
physical timing assumption rather than preserving an established single-edge model.

## Relevant source and selective evidence

- `../Copperline/src/chipset/cia.rs`: timers, output pins, interrupt latches.
- `../Copperline/src/bus.rs`: batched CIA updates and IRQ deadlines.
- `../Copperline/src/cpu.rs`: CPU poll qualification and end-to-end tests.
- `compare_captures.py`, `compare_continuous.py`, `compare_irq_focus.py`:
  reusable comparisons; inspect summaries before selected cases.
- New run artifacts: `captures/accuracy-20261018/` (ignored, never overwrite).

## Rejected hypotheses and next question

Confirmed: identical tick sequences produced two different results before
the patch. PB pulse mode, latch 1, two-clock batch: PB6 stayed low (191 versus
255 for individual edges). Serial completion on the final edge of a two-clock
batch asserted the pin early, while individual edges retained its one-clock
delay. These reject intentional pipeline staging as the explanation.

The CIA now steps edge-sensitive state until it settles, preserving arithmetic
timer batching otherwise. Both CIAs/timers, pulse/toggle and one-shot modes,
latches 0/1/3/15 and six batch sizes are covered by a 384-case full-state
comparison. A separate ICR-race neighbor and serial completion regression
also compare states. All 44 CIA model tests pass in the fast isolated harness.
No new hardware timing assumption or global IRQ constant was introduced.

Evidence: `captures/accuracy-20261018/model/cia-model-1cxrt3xt` (PB failure),
`cia-model-ys3ml9jx` (serial failure), and `cia-model-1ai4s6v2` (44 pass).
The full Copperline pre-fix test executable also reproduced the PB failure:
`captures/accuracy-20261018/cargo/20261018-223211-yddi6dgx`.
One initial isolated-harness TOD failure was a harness constant error (312
instead of Copperline's 313-line frame); the harness now reads the production
constant. It is not emulator evidence. Earlier serial fixture initialization
was corrected to start at count=1 before establishing the failing case.

Next: validate the integrated emulator, replay archived cases and run the
broader regression suite. Then select the next bus/68000 uncertainty using
existing measurement contracts rather than tune a global delay.

Integrated replay now passes (`captures/accuracy-20261018/after-cia-batch`):
67/67 exact-start kind51 cases, 2,212/2,212 focused IRQ cases and
2,560/2,560 divider cases. The kind51 before replay (`before-cia`) has the same
67/67 cohort and the divider packet is byte-identical to hardware. No missing
or invalid rows occur. This validates the measured bus/68000 IRQ paths as
regression neighbors; it is not a claim of universal CPU accuracy.

Four original measurement packets and their provenance are now versioned in
`references/`; original logs remain selectively accessible in `captures/`.

Strict all-target/all-feature Clippy passes without warnings. The default
library suite completed: 4,160 passed, 43 ignored and two known Windows GUI
failures (`numpad_mapping_stands_in_for_the_missing_gamepad` and
`picture_draws_match_the_composed_texture`). Both failures are documented as
pre-existing in Copperline's `docs/internals/a500-irq-focus-2026-10-15.md`;
neither failing module is changed. Full logs:
`captures/accuracy-20261018/cargo/20261018-223826-1ac6dk8i`.
A headless core run is also in progress to separate core evidence from GUI
platform failures. Do not report the default suite as all passing.

The headless `--no-default-features --features control` library run completed:
3,014 passed, zero failures, five ignored. CIA correction committed as
`f2d0a523`; compact Cargo prerequisite committed separately as `11e0f964`.

## Next family: CPU sampling of DMACONR

The archived kind50 BBUSY pilot yields 449 identical pre/post-bracket pairs:
408 raw sample matches, 41 differences, 79 different brackets, no missing or
invalid rows. All comparable no-blit controls match. WinUAE has only 44
comparable pairs (25 active), all matching; it corroborates that subset only.
Report: `captures/accuracy-20261018/kind50-archived-comparison.json`.

Leading hypothesis: DMACONR is sampled after the stock CPU bus-cycle tail
instead of at the granted transfer. Competing explanation: Copper launch or
blitter busy visibility differs independently of sampling. Discriminator:
sample only DMACONR at the already established 68000 transfer point, keeping
CPU duration, beam register sampling and IRQ constants unchanged, then replay
kind50 and neighboring blitter/IRQ references. Improvement confined to the
pilot or regressions elsewhere reject this candidate; consistent improvement
supports a generic transfer correction. No new hardware run is yet justified.

Kind50 overlays +20..+34 with eight DMACONR reads: its `status` field is NOT
a collection status. `compare_copper_busy.py` validates gate/end sentinels
and settled destinations and compares raw samples on exact descriptor plus
pre/post beam brackets. It reports raw register words and sample indices,
never inferred cycles. Equal brackets still do not prove internal slot identity.

### Candidate rejected on held-out measurements

The before/after runs are `captures/accuracy-20261018/before-custom-sample`
and `after-custom-sample`; both snapshot their executable and config. The
common-cohort report is `custom-sampling-delta.json` in the same parent:

| Suite | Common cohort | Before mismatches | After mismatches | Repaired / regressed |
|---|---:|---:|---:|---:|
| Copper BBUSY pilot | 449 | 41 | 23 | 18 / 0 |
| CPU blitter handoff | 2,304 | 1,238 | 1,234 | 8 / 4 |
| Normal/fill BZERO edges | 4,608 | 0 | 33 | 0 / 33 |

The handoff row additionally introduces new BZERO field failures inside
already-mismatching records: first-clear BZERO differences rise from 82 to
202. Final D words remain unchanged. Aggregate improvement therefore does
not justify accepting this change. The exact diagnostic patch is retained at
`captures/accuracy-20261018/diagnostic-dmaconr-transfer.patch`; `src/bus.rs` was
restored byte-for-byte from committed HEAD, after checking no intervening diff.
The global DMACONR sampling hypothesis is rejected as a sufficient repair.
The final normal/fill baseline remains exact across all 4,608 hardware rows.

### Next discriminating experiment and 68000 follow-up

Revised hypothesis: Copper-launched busy/BZERO propagation differs from the
CPU-launched behavior; competing explanation: the two status bits' model
timelines compensate for an underlying sampling error. Use a smaller marker
experiment before another emulator patch: paired Copper lists place a calibrated
INTREQ marker immediately before/after BLTSIZE, plus a no-blit control. Compare
that with CPU-launched BLTSIZE using the same fixed-ROM observer, recorded beam
brackets, first-event-only collection, widths 1/16 and BLTPRI off/on.
Return one grouped summary from the scripted batch, with two repeats.

If marker and busy observations move together, investigate Copper scheduling
or CPU sample position; if the marker agrees and only busy differs, isolate
the blitter status path. A BZERO-only difference requires a separate internal
zero-latch hypothesis, not a busy/IRQ constant change. Bracket ambiguity means
shrink the reproducer or obtain a shared external bus/clock trace; do not align
samples or repeat an unchanged pilot and call that new evidence.

After resolving this bus family, extend the currently passing 68000 IRQ/divider
references with controlled operand-versus-prefetch contention for memory TST,
MOVE/RMW, MOVEM and exception return. Distinguish poll placement from bus grant
delay with independently varied DMA and fixed first IRQ records. Existing 2,560
divider observations already match; no arithmetic or poll patch is justified
by the present dataset. New physical cases are needed for broader timing claims.

## Reusable checks

`python tools/check_cia_model.py --out captures/accuracy-20261018/model`
builds the real CIA source in a small offline harness. Its two external support
definitions are a big-endian word decoder and the production PAL line count;
it deliberately does not cover bus/CPU integration. All artifacts remain here.

`python tools/replay_accuracy.py --binary PATH --config PATH --out NEW_DIRECTORY`
replays three immutable local ROM archives and compares them with their hardware
references. `--suite cia-irq`, `--suite irq-focus`, and `--suite divider-irq`
select focused subsets. It snapshots the executable, records its SHA-256 and
configuration hash, retains full logs, and prints one summary per suite. Exit 2
means a capture/comparison failed; observed differences remain in the reports.
