# CIA phase and source-path investigation

Baseline: Copperline `1bef46ef`. Stage 1 of the ordered accuracy roadmap.

## Question and controls

Does the previously early CIA request reflect source forwarding or an unspecified
E-clock phase? Kind57 independently brackets a CIA-A PRA read before releasing
the source. Fresh Timer-A underflow is compared with a prelatched timer flag.
For the latter, raw streams enable the CIA ICR mask; recognition streams enable
that mask while Paula stays masked, then Copper unmasks INTENA at a fixed beam.
NOP/DBRA and STOP distinguish instruction recognition from request readback.

Require identical descriptors except repeat, calibration brackets, release
brackets and (for masked streams) every read bracket. No timing shifts. Beam
words are encoded line/horizontal coordinates, not linear cycle counts.

## Confirmed facts

V2: 768 valid observations per run. Hardware and emulator calibration reads start
at 0x4252. Both have post-read values 0x4265..0x4269, but their phase sequence
starts differently; same-index calibration comparisons match zero times.
Two physical runs differ in that initial phase. Among 384 qualified hardware
comparisons all measured values agree; 384 have no identical bracket. The pooled
hardware does not yet qualify any of the v2 emulator rows. A blanket IRQ delay
cannot be justified from these unqualified rows.

V3 expands repetitions from two to five to sample the phase nuisance parameter,
without selecting by interrupt outcomes. Emulator preflight: 1920 valid cases,
zero conflicting cohorts. First hardware run: 1920 valid; 1328 qualified, 829 exact matches, 499
differences, 592 excluded, zero conflicting cohorts. All 320 direct prelatched
mask-enable raw readbacks match. Fresh-underflow raw streams have 40 cases
(20 per CIA) with the third INTREQR sample already asserted in Copperline
but still clear on hardware. Fresh-underflow STOP: all 280 qualified rows differ,
usually two colour clocks early. Prelatched recognition is not a universal
control match: CIA-A STOP is early in 32 qualified rows, CIA-B STOP matches
all 32. Those controls use Paula unmask, not a new CIA pin assertion; do not
interpret them as a measured common CIA propagation delay. Independent physical
repeat is byte-identical across all 1920 cases. References: `cia-phase-v3-run1`
and `cia-phase-v3-run2`. Both OneROM restoration checks pass. The experiment
resolves the hidden-phase ambiguity for the qualified fresh-underflow family,
but does not distinguish an early internal timer event from an early IRQ pin
transition; that needs simultaneous timer-output/readback controls. Do not add
a global delay from this evidence. Task 2 now isolates CPU request/unmask paths.

## Evidence and retrieval

Local immutable builds: `build/cia-phase-v2`, `build/cia-phase-v3`, including
staged assembly. Full logs, captures and JSON reports:
`captures/cia-phase-20261019/`. V2 source ID starts `c1fc0ef5`; v3 `92d6ba55`.
Each OneROM run saves its ROM hashes, checksum-protected packet and readback
verified restoration record. Silicon revisions remain unconfirmed; machine is
PAL stock-68000 A500, 512 KiB chip and 512 KiB slow RAM.

Build: `python build_cia_phase_rom.py --wsl --vasm PATH --out NEW_DIRECTORY`.
Compare: `python compare_irq_stage.py --hardware REFERENCE --candidate CAPTURE
--out REPORT.json`; repeat `--hardware` to pool runs, excluding conflicting
cohorts. Calibration summaries and representative case descriptors are in JSON.

## Relevant files and next question

`build_cia_phase_rom.py`, `build_irq_stage_rom.py`, `compare_irq_stage.py`;
Copperline `src/bus.rs` DeviceClock and CIA VPA access, `src/chipset/cia.rs` IRQ
pin pipeline. The independent calibration must qualify source/recognition
comparisons before proposing a source-propagation or CPU-recognition change.
