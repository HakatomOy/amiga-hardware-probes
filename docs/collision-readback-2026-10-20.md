# Transfer-time collision latch readback

Current accepted Copperline commit: `dec76065` on `fix/a500-hardware-timing`.
All eight remaining qualified early differences are repaired;719/719 comparable
cases match. The561 excluded cohorts remain excluded.

## First milestone: `2efe86ad`

Leading hypothesis: CLXDAT was sampled and cleared after the CPU cycle tail,
so a later collision leaked into the preceding transfer. Competitor: all early
visibility differences originate in display-data output rather than the read.
The patch uses the existing granted-transfer sampler, retaining both words of a
long custom-bus read. INTREQR retains its phase; other registers, DMA grants,
CPU cycle length and accelerated-path behavior are unchanged.

Saved physical reference replays, with exact qualification:

| Sweep | Before | After | Repairs | New field/qualification regressions |
| --- | --- | --- | --- | --- |
| kind73 pointer,480 rows |268match/13different/199excluded|276match/5different/199excluded|8|0|
| kind72 Copper/display,800 rows |422match/16different/362excluded|435match/3different/362excluded|13|0|

Exclusions are not matches. Baseline is accepted pre-rebase2b100669; its sources
are retained in the backup branch. A fresh frozen replay establishes the kind72
baseline, rather than crediting the earlier pointer fixes to this patch.
References: `references/pointer-collision-v2/` and
`references/copper-dma-collision-v3/`. Experiment contracts:
`experiments/workflows/collision-sample-pointer.json` and
`collision-sample-copper.json`. Frozen artifacts, comparisons and full checks:
`captures/collision-sampling-20261020/`.

Focused and neighboring native blit, operand/CPU-DMA IRQ, onset/completion/
pressure, handoff and legacy BZERO/Copper packet gates pass without new fields
or lost qualification. Full CI core:3664passed,37ignored,559window tests filtered;
strict all-target/all-feature Clippy and formatting pass. A targeted Rust test
checks a real sprite collision during the CPU tail, retaining it for the next
byte/word/long read with CLXDAT in either long-word position.

At the first milestone eight early differences remained. The follow-up below
resolves them without shifting rendering or DMA grants.


## Final boundary correction: `dec76065`

Leading hypothesis: the replay cursor used the render-write anchor rather than
the absolute pixel comparator, while CLXDAT sampled after its granted clock.
Competitor: the actual fetched data or pointer landing was early.

The verified observational trace reproduces the accepted pointer packet exactly.
All five pointer residuals first latch from DMA word0 on the current scanline43,
not from a preceding line or a manual BPLDAT event. Typical read: grantH40,
old end sampleH41. The window and sprites use `x=4H-2*0x62`; H40 maps tox60,
and DIW81 starts atx62 during that clock. The render-write anchor$28 is a
separate domain. Combining the proper pixel cursor with transfer-start CLXDAT
sampling excludes this later pixel. INTREQR/RAM read phases, DMA grants,
rendering and source write events retain their existing timing.

Two rejected counterfactuals are preserved under `experiments/counterfactuals/`:
oneCCK earlier sampling alone and a fourCCK cursor delay alone each repaired
zero hardware cases; the latter also broke the bus-tail collision test.
Do not retry either alone. Detailed source evidence:
`captures/collision-aperture-20261020/pointer-latch-sources.json`.

Results against saved independent A500 references:

| Sweep | Before | After | New field/qualification regressions |
| --- | --- | --- | --- |
| kind73 pointer |276match/5different/199excluded|281match/0different/199excluded|0|
| kind72 Copper/display |435match/3different/362excluded|438match/0different/362excluded|0|

A new absolute-DIW regression requires both coordinate and sampling corrections.
Seventeen graphical fixtures now observe the same pixel columns at the proper
absolute beam clock; all expected collision bit values remain unchanged. The
separate bus-tail test uses a sprite atPOS83 and a read starting at absoluteH41.
Complete bus suite:445passed. Complete CI core:3665passed,37ignored,559window
filtered. Strict all-target/all-feature Clippy, Rust formatting, focused/neighbor
hardware and legacy packet gates pass. MyST is unavailable locally, so the docs
site/PDF builds were not run.

A paired five-run CI-profile process benchmark, with warmup and alternating
before/after order, gives medians0.7938s and0.7909s (ratio0.9963). Spreads overlap;
no slowdown is resolved in this workload. This includes startup and does not
establish release performance. Full pinned hashes/logs:
`captures/collision-aperture-20261020/benchmark-ci/report.json`.

## Additional hardware apertures and limitations

Kind86 v3 captures1440 complete rows,895 with matching timing brackets; the
remaining545 fail exact source/observation conditioning. Replaying the correction
on those895 comparable rows repairs38 whole cases and50 fields, withzero new
field or qualification regressions:895match/0different/545excluded. The
zero-exclusion matrix gate intentionally remains failed; do not claim all1440
validated. References: `references/collision-aperture-v3/run1` and `run2`.
The root builder is restored to that captured source version; historical v3/v7
builder copies are in `experiments/probe-sources/` (restore the original basename
for reproduction). The diagnostic replay contract disables only old transition
coverage for a saved-data replay; it does not launch hardware, change exact
qualification or relax the exclusion budget.

Kind86 v7 qualified only360 planes-off controls, with1080 exclusions. Its active
rows are not evidence of agreement. Original references remain archived under
`references/collision-aperture-v7/`. Later observer revisions were blocked in
software preflight: missing transition/positive coverage, or the initial cursor
preservation bug. No hardware was run for those failed preflights.

The kind87 short-pulse prototype also failed preflight controls and was discarded
from the public tools; exact code/logs remain locally in
`build/collision-pulse-v3/source_snapshot/` and
`captures/collision-aperture-20261020/pulse-hardware-v3/`. This is not a confirmed
hardware or emulator finding. A future full pulse matrix needs an informative
observer and matching brackets before it can extend this fix's validation scope.
