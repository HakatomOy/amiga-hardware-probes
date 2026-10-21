# Init resource investigation

## Question and controls

Separate blitter source-fetch ordering from CPU status observation before
changing Init again. Kind90 pairs identical critical opcodes across Copper
off, a settled sleeping WAIT and an actively restarted finite stream. Source
overwrite/unused-neighbor, real/inert BLTSIZE, BLTPRI, NOP0..3, neighboring
launch slots and preseeded-source controls total600 cases. COPER witnesses
prove WAIT entry and finite active-stream completion.

## Confirmed hardware facts

`references/init-resource-race-v1/run1` and `run2` cover300 independently
repeated cohorts and all600 rows, with zero invalid, excluded, unstable or
missing results. Packets differ in unmeasured raw bits, so do not call them
byte-identical. Both OneROM restorations verified. All200 cross-mode launch
cohorts have identical launch beams; no alignment is applied.

Off and sleeping-WAIT observations agree. Hardware changes fetched source
between modes in24/48 real source-race cohorts; the current word-End candidate
predicts only4. It matches400/600 complete cases; all200 active-mode rows
differ, including inert starts. Therefore Init alone cannot explain this family.
`tools/summarize_init_resource.py` reports grouped source/status observations.

## Ownership hypothesis

The byte-identical emulator trace shows case90,3,526,0,4,0 granting the inert
CPU write at42:D0 while the Copper completes its second restart phase there.
The CPU source overwrite follows atD9; hardware's later observations are6 CCK
later. Test reserving the reload phase against CPU/blitter, while leaving the
first restart phase free. Distinguish it from a global Init/read delay using
the inert controls and existing source/register suites.

An audit also corrects a historical conclusion: the earlier `reserve-candidate`
changed Init's class to Bus but left `current_slot_needs_bus()` false. No owner
then advanced Init. Its destination-control failure rejects that implementation,
not a correctly asserted Init reservation. Any genuine reservation must keep
request, grant, sequencer advancement, CPU yielding and completion prediction
consistent. Do not repeat the stalled implementation.

## Evidence paths and next check

Full files: `captures/copper-phase-20261020/init-resource-hardware-v1`,
`init-resource-preflight-v1`, and `init-resource-trace-v2` (packet identity
verified). Builder: `build_init_resource_race_rom.py`; exact archived source:
`experiments/probe-sources/init-resource-race-v1.py`.

Next: replay the restart-ownership candidate against kind90 and the previously
repaired quiet/access/register cases. Fix inert ownership before attributing
remaining real-start differences to Init. No emulator acceptance yet.

## Reload reservation result

The reload-ownership candidate preserves quiet512/512, access1024/1024 and
register768/768. Handoff neighbors improve392 to472 matches with zero new
fields. Kind90 improves400 to532: every fetched source matches and every inert
case matches. Remaining68 differences are status0 and later beam observations,
with48 new fields in16 real, priority-set, zero-NOP cases. It is not accepted.

Next discriminating change: hold only Init during a CPU-owned clock, without
delaying the CPU grant. Leave StartDelay and all body bus-free rules unchanged.
The earlier broad CPU-freeze screen changed all BusFree phases and therefore
does not reject this narrower resource distinction. Compare kind90 status/data,
kind89, kinds79/80 and handoff neighbors before broader acceptance. No BBUSY,
IRQ-latency or trace-alignment constant changes.
