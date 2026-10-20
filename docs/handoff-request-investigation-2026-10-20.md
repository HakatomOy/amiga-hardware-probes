# A-only versus destination-enabled handoff — 2026-10-20

## Discriminating test

Leading hypothesis: instantaneous blitter slot ownership misses a CPU/blitter
request pipeline phase, with a contribution from the terminal D request.
Competitor: the source/startup sequence or fixed-DMA CPU grant model is wrong
independently of D. Earlier global INIT and BBUSY sampling changes are rejected;
see `handoff-startup-investigation-2026-10-20.md`.

Kind76 crosses one-word D-only (`01ff`), AD (`09f0`) and A-only (`08f0`)
with no/four/six-plane DMA, normal/nasty priority, no-start, four post-start
delays, neighboring launches and two first-read sources. Custom/chip reads
both use `MOVE.W (A1),D0`. All address selection occurs before ROM alignment.
The2304 descriptors include two repeats; no Copper DMA is enabled.

If only USED cases move the CPU read slot, investigate terminal D handoff.
If A-only also moves it, investigate source/start request phase. No-start
differences require fixing fixed-DMA arbitration before attributing a blitter
effect. Post-read beams are software witnesses, not electrical grant edges.
No traces or observations are aligned to improve agreement.

## Provenance and controls

- Accepted baseline: Copperline `4f625516`, frozen
  `captures/accuracy-round-20261020/pointer-candidate-v2/emulator.exe`.
- Builder: `build_handoff_request_rom.py`; archive `build/handoff-request-v2`.
- ROM SHA256: `862672cd471922140a969f3f16554accae26b5983b04e84efe89aaf10819ff1e`.
- Source ID: `9cc4c4674e33009a3c77aba7f2d29176f716a7cd1286f45c2528ce4249eccc56`.
- Workflow: `experiments/workflows/handoff-request.json`.
- Captures/logs: `captures/handoff-request-20261020/`.

The first assembly attempt hit WSL sandbox access denial; v2 assembled with
authorized WSL access. The first coverage contract incorrectly expected active
four-plane AD samples at this earliest identical-opcode observer. Preflight
showed all clear; no hardware ran under that contract. The next contract
required active and clear six-plane AD first samples (model8/24). Hardware
instead retained busy at all32 first samples, but the second fixed status was
clear. Both originals remain under `baseline-v1`, whose coverage gate failed.
The reviewed contract explicitly checks an active first sample **and** clear
second sample in the same8 earliest cases; both model and both physical packets
pass. `baseline-reviewed-v1` reuses those exact captures, without another live
run or any changed measurement/qualification budget. It also requires A-only and no-start destinations to
remain zero, active AD to settle to `aaaa`, and active D-only to `ffff`.
All data-integrity controls pass in preflight and both hardware packets; the
paired edge-witness contract was reviewed after capture as described above.
Build sources retain unrelated
preexisting unused probe WIP; fingerprints refer to the exact saved snapshot.

## Selective analysis

`tools/summarize_handoff_request.py RUN --out REPORT` counts timing separately
from data/status differences by channel, DMA, first-read source and no-start.
It returns six compact contrast totals and keeps detailed distributions and
representative IDs in REPORT. Beam deltas use227 CCK/line on known same/adjacent
lines, rejecting ambiguous frame wraps; they never shift events.

Use `experiment.py detail RUN --case ID --window 6` for individual evidence.
Relevant emulator paths are `src/bus/dma_slots.rs`, `src/bus.rs`,
`src/bus/custom_regs.rs` and `src/chipset/blitter.rs`.

## Confirmed result

Two A500 packets are byte-identical, with verified restoration after each run;
archived as `references/handoff-request-v1/run1` and `run2`. The reviewed
comparison has2304 cases:1744 match,560 differ; zero missing, excluded,
unstable, conflicting or invalid cases.

| Active channel | Cases | Timing differences | Data/status differences |
| --- | ---: | ---: | ---: |
| A-only | 384 | 96 | 88 |
| AD | 384 | 128 | 120 |
| D-only | 384 | 128 | 112 |

Timing and data counts overlap. All1152 no-start cases match. All384 active
no-display-DMA cases match. For each channel/DMA combination, custom and chip
reads have identical timing distributions. A-only chip reads and settled
destinations remain zero; its data differences are custom status observations.
All AD and D-only settled data controls pass on hardware too.

**A terminal D write is not necessary for the timing mismatch.** A-only retains
64 four-plane and32 six-plane timing differences across the two read sources.
The four-plane witnesses differ by plus/minus2 CCK; six-plane first-read
witnesses can differ by4. Later witnesses near a raster boundary occasionally
produce near-line-length encoded differences: preserve raw VHPOSR pairs and
do not describe those as physical223/229-CCK delays or align them away.

The filtered emulator trace is byte-identical to the baseline packet (SHA256
`68937379d2c592141d344e106a3006a2d872d65dd4e4bca8bd5ef0c325e33c5b`).
Its1152 STARTs are descriptor-bound in `trace-index.json`; custom/chip accesses
are indexed explicitly. Software post-read beams also include contention from
the following beam read; they do not timestamp the preceding transfer alone.
No emulator timing change is justified yet; Copperline remains `4f625516`.

## Next unresolved ordering test

Leading hypothesis: the first source request is misplaced relative to a CPU
transfer under display DMA. Competitor: source ordering is correct and the
later completion/status path produces the discrepancy. Use one-word AD with
a fixed CPU overwrite of A source (`aaaa` to `5555`) at neighboring post-start
delays; settled D reveals which value was fetched. Keep D-only and no-start
controls, exact launch and post-write beams, no/four/six-plane neighbors and
normal/nasty priority. This constrains **relative ordering**, not an absolute
electrical timestamp. A shifted old/new boundary implicates first-fetch/CPU
handoff; correct ordering with wrong status keeps completion/readback in scope.
