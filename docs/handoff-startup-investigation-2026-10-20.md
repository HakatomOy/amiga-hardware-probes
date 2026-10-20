# CPU/blitter startup investigation — 2026-10-20

## Question and evidence

Does the early CPU handoff originate in the BLTSIZE startup pipeline or in
CPU bus recognition? No logic analyzer was connected. OneROM software witnesses
retain exact launch qualification, fixed observations and unaligned packed beams.
The accepted emulator baseline is Copperline `4f625516`.

Two new probes distinguish read-source effects from startup/source-mask effects:

| Reference | Cases | Controls | Baseline differences |
| --- | ---: | --- | ---: |
| `handoff-access-v1` | 1536 | Identical `MOVE.W (A1),D0` from custom/chip/slow/ROM; one-word AD; NOP0..5 | 176 |
| `handoff-startup-v1` | 1152 | One-word D/AD/ABCD; no/four/six-plane DMA; NOP0..3 | 352 |

Both include normal/nasty and no-start controls. Each reference has two
byte-identical A500 runs, with verified restoration after each live substitution.
Metadata records hardware/configuration, ROM/source fingerprints, capture method
and limitations. Silicon revisions remain unconfirmed. No-start/no-display-DMA
controls match. The kind75 observer does **not** enable Copper DMA: no variant
claims otherwise. Slow sentinel `$C70000` lies outside copied probe code.

ROM SHA256:

- Access: `f5d1ba31139af195bb63457999ac8ed0b665f195f28b24a378f0a83fbba8e11d`.
- Startup: `d77a6d9fcf2571c3915f850af0bd4310260d2fe7de5be5ea82e947d6e224adc9`.

## Rejected explanations

An unconditional two-CCK CPU engine delay repairs all200 kind71 differences,
but regresses168 previously matching no-display-DMA cases. It is rejected.

Making normal INIT consume a blitter-eligible slot repairs all200 kind71
differences and all176 independent kind74 differences, preserving all matching
fields in those suites. It also repairs192 cases in kind59/60 focused controls.
However, the new six-plane controls expose456 field regressions across160 cases;
the older512-case neighboring suite exposes72 field regressions across44 cases.
Lower total mismatch counts do not qualify this global rule for acceptance.

## Trace and next question

`captures/handoff-cpu-20261020/status-first-trace-v2` reproduces the accepted
kind71 packet byte-for-byte. Case `71,3,2,0,0,0` has CPU BLTSIZE grant h124,
application h126, INIT h127 under bitplane ownership, A h128, D bubble h130,
E h131, F h132. These are **emulator** scheduling events, not measured A500
electrical edges. The earlier timed-out trace is incomplete and is not evidence.

Use `tools/summarize_handoff_trace.py` for a descriptor-bound file index and
bounded case detail. PAL deltas use227 CCK/line; traces are never aligned.
VHPOSR lacks the upper vertical bit, so the summarizer requires known same or
adjacent lines and rejects ambiguous frame/vertical wraps.
Full comparisons and failed candidates remain under
`captures/handoff-cpu-20261020/`. Workflow manifests and short investigation
records preserve hypotheses and decisions.

Next: distinguish startup eligibility from DMA-dependent CPU grant phase using
the six-plane counterexamples. Do not gate a fix on plane count or accept a
four-plane-only repair. Relevant emulator files are `src/bus/dma_slots.rs`,
`src/bus/custom_regs.rs` and `src/chipset/blitter.rs`.

`startup-trace` also reproduces the accepted kind75 packet byte-for-byte.
Case `75,0,4,0,0,0` grants the first status read at h180; E clears BBUSY at
h181, before the existing h182 read sample. Hardware retains BBUSY for that
observation. This motivates a separate BBUSY-only granted-read experiment,
with original startup and BZERO sampling restored/preserved. It does not
establish that every register shares that data phase.

The BBUSY-only granted-read candidate is also **rejected**: kind75 repairs96
cases but regresses16 previously matching cases and80 fields. Kind71 has16
new busy-field regressions, with no timing repairs. Both emulator prototypes
were reverted; accepted Copperline remains `4f625516`. A successful candidate
build is not an accepted emulator build: use the immutable baseline binary
for subsequent baselines, not the unaccepted executable left in `target/ci`.

## Next discriminating experiment

Leading hypothesis: the CPU/blitter request handoff has a pipeline phase that
the instantaneous `current_slot_needs_bus()` arbitration misses. Competing
explanation: the engine's startup/completion sequence itself is misplaced.
Reduce the reproducer to one-word A-only, AD and D-only blits, matched no-start
controls, four/six-plane DMA and neighboring launches/first-read delays. A-only
removes the terminal D bus request while retaining a source transfer. Compare
custom and chip observations with the same read opcode and retain launch and
post-read beam witnesses. Script the matrix and summarize groups only.

If only USED cases move the CPU read slot, investigate terminal request/grant
handoff. If A-only also moves it, investigate source/start request phase. If
no-start controls move, first isolate the fixed-DMA CPU grant model. No further
blanket timing patch is justified by the present captures. Keep electrical
edge claims open until independently measured; a logic analyzer is optional
for this next software experiment.
