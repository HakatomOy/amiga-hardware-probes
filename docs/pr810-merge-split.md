# PR810 merge-ready split

Preserved full investigation head: `d19310f3`, branches
`backup/pr810-before-cia-split-20261023` and `wip/cia-propagation-pb-stop`.
The PR branch remains `fix/a500-hardware-timing`.

## Decision and first test

Hypothesis: separating exact STOP deadline clipping and the disputed early
PB/zero-auto-start boundary work restores the older CIA STOP cohorts without
removing independent serial, timer, IRQ latch or RAM transfer fixes.
Competitor: those changes are coupled more deeply and a shared correction
would regress retained contracts.

First candidate: restore upstream's bulk STOP accounting/scheduling structure,
retain the new serial/pin event horizon and blitter IRQ horizon, defer the PB
transfer preview and TA-specific extra zero-auto-start carry. Keep steady PB
polarity/output behavior and its save-state migration. Keep control/counter
transfer readback where independently verified.

Compare unchanged reference packets against the preserved full head and upstream
main. Test STOP/running/masked controls, serial deadlines, timer START/counter
controls, retained steady outputs and destination/source races. An improvement
in totals cannot hide a lost previously matching field or qualification.
Deferred boundary families remain documented evidence, not acceptance matches.
If retained gates fail, revise the split rather than relaxing qualification.

No new hardware run is planned for this separation: unchanged ROMs and trusted
captures are sufficient unless the split reveals a new measurement uncertainty.

## Candidate replay

Frozen binary SHA-256: `bdd25a780b5da29410527cde5fd4ca5a26f57e39872bdecbf0b04b98074a551a`.

- Kind56:601 matches,67 differences,932 excluded. Against the original
  before-review head:19 repaired cohorts, no lost matching qualified fields.
- Calibrated kind57:968 matches,360 differences,592 excluded;140 repaired
  fields, no lost matches or qualification changes.
- Mask32/32, START288/288, destination384/384 remain matching.
- Fifteen of17 broad replay suite counts are unchanged from full head.
  The other changes are the improved STOP suite and48 deferred kind54
  zero-auto-start underflow brackets (24 on each CIA). These48 are visible
  deferred limitations, not passing cases. CIA-output has2015 matches and257
  exclusions. Ordinary PB and serial qualification is unchanged.

Detailed reports: `captures/pr810-split/{replays,phase-gate,focused-v2}/`.
No captures were repeated and no units or alignment rules were relaxed.

## Branches and validation

- Reduced PR commit: `a213b680` on `fix/a500-hardware-timing`.
- Follow-up: `d8c47e3a` on `wip/cia-propagation-pb-stop`, based on the reduced
  PR and restoring its deferred code/tests/docs. Its source and documentation
  tree matches preserved `d19310f3`; this is investigation work, not accepted fixes.
- Native suite:45 test binaries,4474 passed,131 ignored,2 named window
  exclusions;48 goldens pass. Serial linker retry succeeded.
- Source race2304/2304; fresh IRQ498 matches/13 differences/1089 excluded.
-388 Python tests,strict Clippy,fmt,strict HTML/links and PDF pass.
  Full MyST checks used explicitly approved network access.

The two window exclusions are the existing parallel keypad-map issue and
GPU scaler precision (3/255); an unfiltered pass is not claimed. The four fewer
native tests than the full head are the deferred tests preserved on WIP.

## Upstream comparison and decision

A separate clean worktree built upstream `main` (`a444a636`) with the same
profile/config and immutable ROMs. The reduced branch changes:

| Suite | Upstream | Reduced PR |
|---|---|---|
| IRQ stages (match/different/excluded) |265/403/932|601/67/932|
| Serial buffering |114/320 matches|320/320 matches|
| Serial boundaries |0/38 matches|38/38 matches|
| CIA outputs (match/different/excluded) |584/936/752|2015/0/257|

Both serial-boundary runs exclude the same2 unstable cases. IRQ cohort analysis
finds336 repaired whole cases and no lost completely matching cases. At field
level693 improve and18 formerly matching fields change in already-failing
cases. This is a disclosed limit: overall gains do not imply every individual
field improves against upstream. Against the original before-review PR, the
reduced split has no lost matching fields in these qualified STOP cohorts.

Decision: accept the reduced scope for review, preserve the full experimental
state on WIP, and do not tune the global IRQ latency to mask remaining failures.
No new HW measurements were needed. Further CIA/PB work must resolve its
uncertainty with phase-qualified or electrical controls before merging.

PR810 is now **ready for review** and GitHub reports it mergeable. Both
Copperline branches and the evidence branch `review/pr810-a500` are pushed.
The primary checkout remains on `fix/a500-hardware-timing`; temporary
validation worktrees were removed without deleting either branch.
