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

## Init overlap controls

Holding Init on every CPU grant improves kind90 to564/600 but loses120
access-space matches and152 register-witness matches. Holding only CPU writes
preserves1024/1024 access cases and matches384/384 busy-onset cases, but still
loses152 register-witness matches. Neither rule is acceptable.

The reload-only register trace is byte-identical to its untraced packet
(`reload-witness-trace-v1`, SHA256
`25dba4aaa89ca6ddd38cc254b7e4d539bd8742e3caec8c848a78de7c4b76dddc`).
Bind its starts with `tools/summarize_handoff_trace.py`. For example,
case80,0,135,0,0,0 advances Init on CPU write43:07, three clocks after MOVE43:04;
cases80,3,164,0,0,0 and80,3,36,0,0,0 require write overlap without active Copper.
All72 active-Copper regressions whose Init overlaps CPU occur three clocks
after a MOVE. In contrast, kind90 case90,3,519,0,4,0 overlaps Init/write42:DD
one clock after MOVE42:DC. These are emulator trace contexts, not direct
measurements of internal hardware signals.

Next hypothesis: the preceding Copper second-word/register phase conflicts
with Init during a CPU write. Competitor: any CPU write conflicts. Restrict
the experimental hold to a preceding Copper owner with completed instruction
and running state; retain read and first-word overlap. Require kinds79/80,
89/90 and handoff controls before accepting or broadening the change.

The second-word restriction preserves1024 access and768 register witnesses,
matches384/384 onset cases, and retains472/512 handoff neighbors without new
fields. Kind90 matches556/600 but still introduces12 fields in four cases:
90,3,519,0,3,0 and its repeat/source-neighbor partners. Their Init write42:DD
follows IR1 atDC, unlike the neighboring launch which follows a MOVE there.
The successful kind80 CPU/Init overlaps occur after refresh at43:07 or43:0B.
Thus a line-end/startup sampling explanation remains viable; do not add a
special hpos condition from these two launch positions.

`experiments/workflows/init-resource-launch-sweep.json` discriminates these
explanations with both phases and padding0..7, identical opcodes, off/WAIT/
active modes, inert starts, NOP0/1/3 and preseed controls. Both initial408-case
and600-case preflights were rejected before hardware because the target3
neighbor-write control was absent. Both did exercise old/new source outcomes;
the initial interpretation of the coverage error was incorrect. The revised
606-case ROM restores repeated target3 neighbor controls in every Copper mode.
Core tests also caught a missing serialization exclusion for the transient
write-direction flag; corrected with `serde(skip)`, retaining old state format.
No emulator acceptance yet.

## Hardware sweep resolves the distinction

`references/init-resource-launch-sweep-v1/run1` and `run2` are byte-identical:
606 qualified cases,303 independently repeated cohorts, zero invalid, excluded,
unstable or missing results. Both OneROM restorations verified. ROM SHA256:
`a32cc59c177a6bb85d7692cec189851de566f671f841ccd65637fa543cf3262f`.
Exact builder: `experiments/probe-sources/init-resource-launch-sweep-v1.py`.

The second-word CPU-write rule matches528/606, with every fetched source and
inert case correct. Trace `init-launch-ir2-trace-v3` is byte-identical to the
untraced emulator packet. Of78 differences,64 execute math D at42:E1 before
Copper/refresh;14 execute math after refresh, including inappropriate Init
holds at43:07. Thus the preceding-MOVE write rule is rejected.

Remove CPU write-direction tracking and hold bus-free normal body phases in
the same pre-refresh RGA reservation as Init; leave StartDelay, memory transfers
and internal terminal phases separate. This candidate matches all600 original
resource cases, all606 sweep cases,1024 access cases,768 register witnesses,
384 onset cases and512 handoff neighbors, with zero new fields. Paths:
`captures/copper-phase-20261020/body-turnaround-controls`. Next: make the cloned
completion predictor honor the same phase-specific reservation, then validate
the final binary across the full acceptance workflow. No emulator acceptance
until those checks pass.
