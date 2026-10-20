# Transfer-time collision latch readback

Accepted Copperline commit: `2efe86ad` on `fix/a500-hardware-timing`.

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

Eight early differences remain. Do not move collision generation or another
register phase merely to remove those residuals; distinguish the remaining
pixel-output boundary from sampling with a narrower observer first.
