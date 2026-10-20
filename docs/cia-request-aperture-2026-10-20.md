# CIA request aperture and clear controls, 20 October 2026

## Confirmed boundary

The initial kind84 two-repeat run was repeatable but all512 candidate rows were
excluded by unchanged calibration/launch/read qualification. Hardware post-PRA
read beams differ from the same candidate descriptors; no delay inference is
valid from that packet. `qualification-audit-v1.json` preserves raw pairs.

Five repeats per condition cover all E-clock cohorts:1280 qualified rows,
880 matches and400 early request differences; zero excluded, unstable, invalid
or missing rows. Timer count and PB6 measurements match. Two physical runs and
verified OneROM restorations are archived in
`references/cia-request-aperture-v2/run1` and `run2`.
ROM SHA256:8bd9950a8db196bf191725f96d68465bc8b17dc7b7575b9a901f84fef165c01c.
The comparator uses exact independent PRA, launch and observation brackets.

A diagnostic replay reproduces the candidate packet byte-for-byte. Its four
request reads are8CCK apart. The neighboring-latch counterfactual uses actual
grant clocks,5CCK per E tick and no trace shifts. Across both physical packets,
6CCK gives0 differences on6080 available fields;4160 are unavailable/ambiguous.
On5760 common fields,5CCK has160 differences versus0 for6CCK. On3360 common
fields,7CCK has160 differences versus0 for6CCK. Common support across all nine
delays is zero, so pairwise comparisons matter. These are repeated-reference
field counts, not unique fixed cases or acceptance results. Full screen:
`captures/cia-aperture-20261020/clock-screen-v2.json`.

This constrains effective request visibility. It does not locate the electrical
CIA output edge separately from Paula input/read sampling. Keep
DEFAULT_IRQ_LATENCY_CCK=6 and the measured STOP/running recognition controls.
Do not add another blanket six-CCK CPU delay.

## Clear control

Kind85 compares destructive ICR and nondestructive PB reads, then identical
Paula PORTS/EXTER acknowledge, NOP/EXG aperture and four request reads. The first
640-row sweep qualified fully but never encountered an enabled pending ICR;
it is not evidence for cancellation. References remain under
`references/cia-request-clear-v1/`; treat its snapshot-only serial-bit residuals
separately from timer request timing.

The revised latch24..39 sweep requires both ICR0 andICR81 in the destructive
bank during preflight before hardware. Manifest:
`experiments/workflows/cia-request-clear.json`. The next question is whether a
request survives source clear and Paula acknowledgement, not another replay of
the already-established early visibility pattern.


The revised clear sweep qualifies all640 rows:558matches,82differences, no
excluded/unstable/invalid/missing rows. There are320 destructive-read cases,
including200 with hardware ICR81 and120 without enabled assertion. All200
asserted cases remain clear in all four INTREQ observations after ICR clear
and Paula ack. All320 nondestructive PB controls observe a request. Both
physical restorations verified; references:
`references/cia-request-clear-v2/run1` and `run2`. ROM SHA256:
96b6abf3471e6de52480525187475facc016759dfe22cae424343c22b0dfb644.
Use `tools/summarize_cia_clear.py` to query this classification. It explicitly
marks probes without asserted ICR/control coverage as nondiscriminating.

This rules against an uncancellable delayed reassertion in the measured
clear/ack windows. It does not identify every possible shorter pending pulse,
prove a pin timestamp from bit7, or locate CIA output versus Paula sampling.
Any future forwarding-stage candidate must cancel/withdraw appropriately,
preserve software-written/shared PORTS/EXTER sources, avoid adding another CPU
recognition delay, preserve STOP deadline prediction and save-state behavior,
and pass the saved CIA/IRQ/bus suites before acceptance. No CIA latency patch
is accepted by this investigation.


Provenance note: the kind85 v2 builder source is preserved in commit `cdb25b1`.
Its inherited `irq_stage.event_offset` manifest text incorrectly says latch32;
the snapshotted assembly and experiment contract use latch24. The original
capture manifests/hashes remain immutable. The current builder overrides that
metadata for future builds; do not relabel an old ROM with a new source hash.
