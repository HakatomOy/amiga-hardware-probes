# ROM timing isolation, 14 October 2026

This note records the focused One ROM measurements behind the timing changes and separates exact phase-matched results from older, phase-mixed timing-table readings. The emulator timing-model discussion is in [Copperline internals: timing](../../Copperline/docs/internals/timing.md); earlier broad RAM results remain in [earlier ROM golden findings](rom-golden-findings-2026-10-14.md).

The final [comparison, fixes and detailed remaining measurement plan](rom-timing-wrapup-2026-10-14.md) updates the intermediate candidate notes below. The synchronized 896-trial STOP matrix now matches A500 exactly; line-mode BZERO remains partially unresolved after kinds 25-27.

## Machine and evidence

The physical test machine was a PAL A500 with ECS Agnus 8372A (`VPOSR=$a000`), OCS Denise (raw ID `$ffff`), 512 KiB chip RAM and 512 KiB slow RAM. The One ROM Fire-40-A was v0.8.0 (USB 0.3.2, host-control 0.1.6); SEL_C reset the 68000. The Kickstart image was backed up and restored byte-for-byte; restored live-ROM SHA-256: `9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`. Results were gathered in RAM and transferred after measurement; RBCP was not called inside timed loops. No AGA or analogue-video claim follows from these captures.

WinUAE reference captures used WinUAE 6.0.3 (2026-03-01), A500 quickstart, Best Compatibility, cycle-exact 68000, PAL, ECS Agnus, matching memory arrangement. Copperline runs used the pinned `tmp/golden-a500-ecs.toml` configuration: A500, 68000, ECS, 512 KiB chip plus 512 KiB slow, no JIT, no audio. The fixed-candidate capture used `target/ci/copperline.exe`, SHA-256 `69f242e04cbc696d04dbc3c38d8b7a55e96fa053641234d0b51b43df772d786b`. The analysis validated both the capture's invocation path/hash and the current on-disk binary hash. An earlier preflight accidentally used `target/release/copperline.exe`, SHA-256 `be0b85e7a67145cc8861bbbc0eab7cb5a75e719ebd81a4e75942583fb423efbb`; it is explicitly a baseline, not evidence about the fixed CI candidate.

## CPU and interrupt ordering

The CPU timing ROM aligns the measurement launch through the ROM alignment routine (`jsr $fb0000`) rather than a variable delay loop. It preserves the trial operands and plane state, and records the complete launch beam coordinate. This phase alignment is a harness improvement; it does not establish correctness for every CPU/DMA phase.

For each count-64 comparison of operand variants 0, 1 and 5 over planes 0-6, only rows with identical full launch beam and safe end-beam samples are compared. There are 168 scheduled phase trials: 162 exact-launch pairs and 6 with unequal launch positions (all six are in plane 5); no exact-launch pair has an ambiguous endpoint. All 162 matched beam-time deltas are zero. The zero-plane controls are 24/24 exact, with both beam elapsed and independently measured CIA elapsed deltas zero. Plane six is 24/24 exact at launch positions H=`$61`, `$65` and `$69`; every matched beam elapsed value agrees. The CIA reference is a separate cross-check, computed as the difference of individually modulo-65536 counter readings. Its launch begins before the alignment call, so it includes alignment setup and has small phase-related spread; it is not the primary elapsed-time observable.

The whole 1,792-row sweep compares planes 0-6, four operands, and counts 1/2/16/64. Exact safe launch pairs have zero beam-time delta for both Copperline (1,732 rows) and WinUAE (1,640 rows); remaining rows do not share an exact full launch coordinate or have unsafe endpoint samples and are excluded from that claim. CPU-aligned source ID is `89893768d65920f312d7fd2b41fc81de847fe72c6ca884360e3c7e216d03190b`, ROM SHA-256 `b95ceff42bcde05e020d597f73668a73db62e2a8a196e1ee627c50f0d890fb4e`, archived source-snapshot SHA-256 `30671646e749cdf5b3a06ffce148524cf78ee45891d29352c9eab46ec06f51f9`; each capture contains 1,792 records and no timeouts or skips.

Kind-20 DIV/IRQ observations jointly classify saved PC and a marker written by the instruction following DIV. They show exception entry before that marker when the interrupt arrives during the divide, consistent with the 68000 completing the divide's internal work before its final prefetch/IPL sampling point. The saved PC and marker are the evidence; kind-19's unrelated `irq_level`/`savedpc` fields are not observer writes. These measurements constrain CPU ordering and the tested IRQ case, not every interrupt or bus phase.

## Aligned DMA-observer sweeps

The baseline aligned-channel ROMs test busy, IRQ and memory observers over 3,456 trials each with BLTPRI cleared at trial reset. Each uses the same per-mode source for hardware, WinUAE and the fixed CI build. Comparisons use only meaningful state masks: busy bit `$4000`, IRQ bit `$0040`, and the memory word `$ffff`; elapsed colour clocks are compared as `227 * dV + dH`. The full floating/raw DMACONR value is intentionally not compared. For each hardware-versus-emulator comparison, all 10,368 rows have zero state and timing mismatches. Launch positions are aligned at H=`$42`/`$43`; valid final HPOS values reach approximately `$d0`, safely away from the vertical-wrap ambiguity. These read-observer sweeps are distinct from the earlier kind-19 raw asynchronous observer exploration.

The three mode source IDs and ROM SHA-256 values are:

| Mode | Source ID | ROM SHA-256 | Archived source-snapshot SHA-256 |
| --- | --- | --- | --- |
| busy | `fad8e342ac5f90057737969facd54d568d616502da9423d4d7b7a08cd5fa46b7` | `24289b3fc34ba4baed0d592b4492e47c240ff6c80515895392a4ebdbe527cbb2` | `0108b1ac80926d9f0e61ed87427ca56df42ba5758dfc1cdb318321991248ab0a` |
| IRQ | `ea4481eb8632945cd80d2a4fba4f45f770400401716884e73d79a91ee517c464` | `0d9dd138499572ceabc529b12da6f533a5da41e423438003d3bdf69ff3007efe` | `513c9f2b87000ea7335d7e2e4fb3f57301ba9008d1330d08f3f5a1b0adeb8747` |
| memory | `be743a9aa847ee58749678375b21b8fd5d72adfdef59d646c270726d29c27cd3` | `623647a64b58a9197efd38e7a41f3fc05258bc50c95902f2017ac95734111dc3` | `e0bff75b56fc0ba08a396e031a07126b8024604015a28fad40e5ca1efd7e005d` |

### BLTPRI follow-up in progress

The existing 10,368-row baseline captures keep BLTPRI clear and compare the masked observer state plus elapsed time exactly. The earlier 540-row blitter sweep still showed a +2 colour-clock residual for fill and line cases under BLTPRI. A separate 3,456-row busy-observer ROM now forces DMACON BLTPRI (`$0400`) before each blit launch while preserving the trial's busy observer and aligned launch phases. Its repeat descriptor is 4 (low bits select busy; bit 2 marks BLTPRI on). The immutable ROM bundles are under `Copperline/tmp/timing-isolation/aligned-priority-{busy,irq}-rom`:

| Observer | Source ID | ROM SHA-256 | One ROM-order ROM SHA-256 | Source-snapshot SHA-256 |
| --- | --- | --- | --- | --- |
| busy | `93adfec44fe58ea38aba0e07e81f7949d1eaf519dc6bcc5914d10f2f5d2ccf1f` | `aed3a4b3db7648cd615526e2d1b5999c3d1115b50b6ec3cecbec60d9ec1e626b` | `215355fd63d02f5a92ff9298e4339c5eefa4a6ba105fd866695c322574027f1d` | `50dc611f6b0ab16caefb6d6fc2f091a34fca7e833a3a3fef625d69e40f7eba34` |
| IRQ | `18786132832d8aab99388ce1a1c52fbd12ff01465f40a73d21c71799f07edd53` | `5887ecfb0c0eed192b1a134dad4855363f07689d9fa2bc2aeb5926ebb59f57e2` | `7f75ed93baeaae1b22e59cf11771e45d38963b04ffb47d1dc38c94a78a26aaac` | `dc88298a70cd05acbd7aafbcb7358165ebf8199a820ff96b483a4f72ec541f8c` |

The 3,456-row hardware-vs-WinUAE reports are `aligned-priority-busy-a500-vs-winuae.json`, `aligned-priority-irq-a500-vs-winuae.json`, and the matching memory report. The reports validate source IDs and trial descriptors, verify the WinUAE 6.0.3 executable hash on disk, and show zero state and timing mismatches. The fixed Copperline build also matches the hardware and WinUAE for all 10,368 priority-on rows across busy, IRQ and memory observers. That gives 20,736 pairwise hardware/emulator comparisons with no masked-state or elapsed-time mismatches. An independent colour-clock sequence model that applies BLTPRI only on actual bus requests reproduces all 3,456 hardware busy-observer samples. These results cover the aligned observer cases; the separate STOP paths still have a small native-IRQ residual described below.

## Corrected DIVU interpretation and remaining scope

A measurement conversion error doubled the low horizontal byte from `$DFF006` even though VHPOSR already reports the colour-clock coordinate used by this PAL elapsed-time calculation. That incorrect conversion could make a sample appear nearly a line short. The corrected formula is `227 * (endV - startV) + (endH - startH)` with wrap/ambiguous endpoints rejected. A redundant two-byte NOP now occupies the same instruction size and cycle budget as the replaced instruction, so the fix does not intentionally shift the launch phase.

Consequently the old six-plane, count-64 DIVU figures (hardware 5015, Copperline 4824) in the earlier findings are superseded: they mixed horizontal-clock conversion and launch phase. A corrected but phase-unmatched legacy line gives hardware 4891, fixed Copperline 4886, and WinUAE readings 4863/4874. These `kind=15`, target-2, variant-31 rows pack the count as `(icr << 16) | counter`; plane is `repeat % 7`. They are not same-launch comparisons and do not demonstrate a residual 5- or 27-colour-clock bug. In the CPU-aligned count-64 plane-six sweep, unsigned DIVU operand 0 normally measures 4763-4767 colour clocks, with the worst result 5102; signed DIVS measures 5249-5257, with the three compared systems reporting identical distributions. The aligned CPU trials are the stronger evidence: plane-six count-64 rows match exact launch phase and beam elapsed time across tested operands. Continue to treat phase-frequency and independent CIA distributions separately from exact per-launch elapsed results.

The earlier kind-19 multiobserver captures expose their own register-read/IRQ/beam sequencing; they are not interchangeable with aligned kind-21 read-observer comparisons. Historical reports and raw captures remain preserved. This is a focused PAL A500/ECS 68000 result, not proof of all chipset revisions, CPU models, display modes or timing phases.

## Reproducible analysis artifacts

Validated capture comparisons and raw records remain as ignored local artifacts in `C:\Users\seppo\amiga\amiga-hardware-probes\captures\timing-sweep-comparisons` and the sibling `captures\rom-*` folders; the large capture binaries are not part of this source change. The fixed CPU comparison is `cpu-aligned-a500-vs-copperline-fixed-ci.json`; the exact launch/count-64 subset is `cpu-aligned-count64-operands-0-1-5-same-launch-a500-vs-copperline-fixed-ci.json`. Aligned mode reports are `aligned-{busy,irq,memory}-a500-vs-copperline-fixed.json` and matching `...-vs-winuae.json`. The comparison tool verifies results metadata/checksum, source ID and descriptors, and for fixed CPU results the executable's invocation and current SHA-256. The portable comparison and matrix tests use generated checksummed packets and temporary manifests, so they do not depend on local captures. Focused validation passes 10 tests; full discovery passes 27 tests with access to the existing captures directory monkeypatched unavailable.

The old `Remaining constraints` section in [earlier ROM golden findings](rom-golden-findings-2026-10-14.md#remaining-constraints) retains its original numbers as history; this note supersedes its interpretation of the doubled-H-clock CPU/DIVU result.

### BZERO edge matrix (complete)

A kind-22 ROM is archived at `Copperline/tmp/timing-isolation/bzero-edges-rom2`. It samples both BBUSY and BZERO from full DMACONR around the first computed blitter word, with phase gap 2 CCK (`NOP`) or 3 CCK (`EXG`) after BLTSIZE and an additional 0-15 NOP delay. The 4,608 rows cover normal and every fill minterm mask 0-31, line targets 32/33, BLTPRI clear/set, and A-source first-nonzero positions 0/1/4 for A-enabled normal/fill cases. Six targets also run a one-word/one-pixel case to test whether BZERO may outlive engine completion. The comparison groups by target, variant and priority; it requires matching launch beam and reports the BBUSY+BZERO mask (`$6000`) separately from valid full DMACONR bits (`$67ff`). The phase and delay indexes are explicitly zero-extended before address calculation; assembled stubs occupy `$FD0000` through `$FD1F00` in `$100`-byte slots, after the alignment kernel ending below `$FD0000`. Hardware and emulator captures are complete. Before BZERO correction Copperline differs in 86 of 4,608 defined-DMACONR samples; WinUAE differs in 20. The final normal/fill candidate has zero mismatches and its entire packet is byte-identical to hardware (SHA-256 3fc9ac2ef2134a5b03090fefca5d5251e5445c71fbee8c9c2f0759284138e7fe). The broader line-texture experiment below remains a separate limitation.

The first archived bundle `bzero-edges-rom` is retained but superseded: its phase/delay address calculation did not clear register upper words, and target 33 included an unnecessary short variant. Use only `bzero-edges-rom2`, source ID `634599ff1094acc5fd95f87f8ab34264a61a12407ff0577330b2b30f348fc076`; ROM SHA-256 `059112d740325bdb74ca958434e99b44371cdfc095b535b1f32d16a5f9cd4a84`; One ROM-order ROM SHA-256 `88e24139912850ed8546014c18ee6cd77c0c5ebf31db3100554adf5de255cd1c`; source-snapshot SHA-256 `7b85e9b2cce92f753df949e9a228be6235d02415619aa09e2b26db425acefb2d`.

### Native and Copper IRQ STOP paths

The kind-23 ROM is archived at `Copperline/tmp/timing-isolation/irq-paths-rom2`. Its 896 trials cross seven sources (native D-only, AD copy, AD fill, line; Copper INTREQ BLIT, COPER and SOFT), RAM-copied versus ROM interrupt handler, 2- versus 3-CCK phase padding after launch, 0-15 additional NOPs before STOP, and BLTPRI clear/set. The Copper list waits for line 67, HPOS 64 and writes the selected INTREQ source. Before phase alignment, the controller rendezvous with VPOSR line 64, matching the RAM timing probes. Both level-1 and level-3 vectors point to the selected handler during each trial, then the main harness restores its regular vectors. The handler records the beam and 68000 exception-frame PC before acknowledging INTREQ and setting DONE. Hardware and WinUAE have identical launch beams and saved PCs for all 896 trials. Before the exact STOP deadline clamp, the measured candidate matched all three Copper-generated sources and all 256 NOP-phase native cases; the 256 EXG-phase native cases remained two clocks late. The 15 October follow-up below closes this residual in the synchronized kind-23 matrix. The first archived `irq-paths-rom` omitted the line-64 rendezvous and is preserved as exploratory only.

Source ID `e3ed3ab473e1a1f2c2f65d6ad03b33684cbf2eb7aa68f076fb7a75d4cd1a4e0a`; ROM SHA-256 `abfbaf4a5fb6ae20326be1b0e9ff41a2d3667a0923b6db26156d4f15664099db`; One ROM-order ROM SHA-256 `b27800412f3b294a43a2051a11afec28a7afff48425482efb11d1c4ab4176f15`; source-snapshot SHA-256 `f01621c44382ccf4cbcf00e0d5702846118112c3c81f96d95f3381c3eb48dc19`.

### Line-mode BZERO and data (complete; flag semantics unresolved)

The initial kind-24 768-row matrix in `Copperline/tmp/timing-isolation/bzero-line-rom4` showed identical BZERO edges across the three pixel patterns, so it did not establish the generated D-data behavior. The expanded 2,560-row `bzero-line-data-rom` matrix adds B patterns `$0000/$8000/$1000/$0100/$ffff` and toggles whether BLTBDAT is written after BLTCON1. It preserves the USEB-off/on targets, 22-pixel line walk, phase NOP/EXG, 0-31 NOP delays and BLTPRI clear/set. Both BLTAFWM and BLTALWM are reset to `$ffff`, the 1,024-word C/D destination region starts at zero, and USEB-on is written directly as `$0fca` (BLTCON0 is write-only). After BBUSY clears, the capture stores an OR of all 1,024 destination words plus words at `$10000`, `$10050` and `$100a0`; the comparator reports these separately from the `$6000` BZERO/BBUSY mask and `$67ff` valid DMACONR bits. In the decoded report these values are named `destination_or`, `destination_first`, `destination_10050`, and `destination_100a0`. RAM `sync_beam` rendezvous at VPOSR line 64 before ROM horizontal alignment. The reviewed immutable ROM is archived at `Copperline/tmp/timing-isolation/bzero-line-data-rom`; all captures are complete. All 2,560 destination OR reductions and selected words match on all three systems. Hardware BZERO still differs from WinUAE in 872 samples and the initial one-CCK line candidate in 956. The all-zero texture control leaves destination OR zero, yet hardware clears BZERO; BLTBDAT write ordering has no effect. The initial 1-CCK candidate had 956 BZERO mismatches. The 15 October follow-up below records a separate replay with zero extra line visibility delay, reducing this to 932. The earlier `bzero-line-rom` through `-rom4` bundles and their captures remain immutable historical artifacts; `-rom3` used a read-modify-write on BLTCON0 and is exploratory only.

Source ID `e9ca4607f72ec69f6c5728b87feb1398bb594f2748e995f6642981127ea8e019`; ROM SHA-256 `29f4c98a7de30cbe5becc97125bcfba47b629d432bbb1b831e2a02b40cd3c4c8`; One ROM-order ROM SHA-256 `99f83f0a2b2e65baa0acbbe705def000de085f58e5d725f3a2bc95db53f5325a`; source-snapshot SHA-256 `44c57811f9b1c67d135c8dc3d228f41175a88b8a78351ecd242f532699058722`.

Source ID `48a5ad0df58634d0e4bbb9fe731c5173b0077ac646f6a9f8fe72ab55b8f713f4`; ROM SHA-256 `23f86d26089545f05eb5a005547df7b73f609433e2bd3785f84e90c9361fe530`; One ROM-order ROM SHA-256 `274bc69f34c039c2ff195f2fb98a91a1595fd80d58ced61de4e88ed91d66d65b`; source-snapshot SHA-256 `dfa09ea969e5bb5a4c2b93955bf05a042494a9e07bb521e0566852320112d31f`.

## Follow-up One ROM measurements, 15 October 2026

The synchronized kind-23 IRQ experiment was replayed using the exact candidate
binary after correcting a stale-executable provenance mistake in the first
attempt. The verified combined Copperline binary is the optimized CI-profile
build, SHA-256
97a0b51616eb47bdfd060cb8bd66a2a53ad1ca1b1c4e9242c9858ccf5561dc38. All 896
Copperline result records have the same packet SHA as A500:
9c74959d803b60cea0f2823372d2b6e52a4dd896ac005b366846da7bd6c883c0. The capture
has zero timeouts and skips. WinUAE 6.0.3 Best Compatibility reports zero
IRQ-beam and saved-PC mismatches on the same paths. The prior +2 CCK native
odd-phase residual is therefore closed for this tested matrix.

The saved kind-25 through kind-27 A500 captures were replayed on that same
binary. The candidate changes only the line-mode extra BZERO visibility delay,
from one CCK to zero; normal/fill timing remains unchanged. Results:

| Kind | A500 rows | WinUAE BZERO mismatches | Copperline at 1 extra CCK | Copperline at 0 extra CCK | Beam/data mismatches after |
| --- | ---: | ---: | ---: | ---: | ---: |
| 22 normal/fill BZERO | 4,608 | 20 before the normal/fill correction | 0 | 0 | 0; packet SHA equals A500 |
| 24 line data/texture | 2,560 | 872 | 956 | 932 | 0 |
| 25 line minterm/channel | 3,456 | 74 | 74 | 74 | 0 |
| 26 fine line BZERO | 544 | 434 | 454 | 450 | 0 |
| 27 line inputs/BDAT order | 3,360 | 624 | 652 | 596 | 0 |

Every remaining mismatch in kinds 25, 26 and 27 is directional: A500 has
cleared BZERO while Copperline still reads it set. Hardware destination ORs and
selected words match exactly. Kind 27 has no mismatch when A=0; nonzero A has
mismatches for selected B/C/USEB combinations. BLTBDAT write order, 2-vs-22
pixel length, and BLTPRI do not explain the residual in the focused cases.
Changing the line visibility delay improves kinds 24, 26 and 27, but does not
give one rule that explains all line-mode flag behavior. WinUAE remains closer
on kinds 24 and 26; Copperline is closer on kind 27; kind 25 ties.

Source IDs and candidate capture packet SHA-256 values:

| Kind | Source ID | Candidate capture packet SHA-256 |
| --- | --- | --- |
| 22 | 634599ff1094acc5fd95f87f8ab34264a61a12407ff0577330b2b30f348fc076 | 3fc9ac2ef2134a5b03090fefca5d5251e5445c71fbee8c9c2f0759284138e7fe |
| 23 | e3ed3ab473e1a1f2c2f65d6ad03b33684cbf2eb7aa68f076fb7a75d4cd1a4e0a | 9c74959d803b60cea0f2823372d2b6e52a4dd896ac005b366846da7bd6c883c0 |
| 24 | e9ca4607f72ec69f6c5728b87feb1398bb594f2748e995f6642981127ea8e019 | 19d3b947bd0bde64d4585ac98f9fd452d8d5742b390c851922d89958c9c53152 |
| 25 | 31b9aa0cf37222a2b6dca7c1d7cc982beed7543a3012d43a26c9fe1a6a33eaa7 | da9a761f652cc7e8ebcffc54e92e27b7df764e5a7146cf24a9beb953394e3e80 |
| 26 | c340ff9336275a570317fc8f0b83a6ee5d0edb6a034a8365f74edfd8f6f62bd0 | 1b0e033455d7b9ff05cc0fa3a648e030072310e7059af840e42b94c95acebd35 |
| 27 | c610b7ff62314870a21a03dfab5aae8c1ff87ce01578f57c7a2e9a42f6476223 | 90663ecf343e2994c9085ac98f9fd452d8d5742b390c851922d89958c9c53152 |

The detailed line-mode TODO is now kind 28: sample DMACONR at both NOP and EXG
phase offsets around each pixel; vary A-bit position, B texture/shift, C,
minterm, channel enables, SING, SIGN/error accumulator and D enable. Keep
one-, two- and 22-pixel lines and record the beam and destination data. The
measurement should establish whether A500's BZERO latch follows an earlier
line ALU/pipeline value than the value eventually written to D. Change the
state update point only after the matrix identifies a stable rule. The A500
remained on its original Kickstart; live-ROM SHA-256 after restoration remains
9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb.