# A500 BZERO bus validation, 16 October 2026

This note records the current One ROM experiments and the independent CPU-bus
captures made with the Rigol logic analyzer. The captures establish the
observed DMACONR bit values and the scope of the address decoder. They do not
identify an internal Agnus latch or prove a C-channel fetch mechanism.

## ROM capture results

The new kind45 controlled-history ROM contains 960 rows and uses six explicit
normal-mode preconditioning choices: no prime, an all-zero A/B/C/D prime,
A-only `$FFFF`, B-only `$FFFF`, C-only `$FFFF`, and all-channel `$FFFF`. Each
choice is crossed with ten line presets, direct versus BBUSY-poll observation,
and eight repeats. The physical A500 capture completed all 960 rows with no
skips or timeouts; BZERO stayed set in every hardware row. All 7,680 raw
DMACONR words match both Copperline and
WinUAE preflights: each comparison has zero flag and whole-word differences.
The A500 `results.bin` SHA-256 is
`68213e27c31971e6b0f2c23bfd4f103f68c656a7dd4f4766b59af75324c1cb84`; the
ROM SHA-256 is `4641874d3cac5c27bccedfd178c31657a362211ce0faf28d36e8003673886347`,
with source ID `9128d07c6c2c7dba7093a277f278950d24979f938879141751162c08e404dd73`.
The final all-`$FFFF` preset's CCP readback confirms the A/B sources retained
their prime values and C contains the selected first word followed by seven
zeros.

An exact kind39-final ROM was also run with the analyzer attached. All 344
records completed, and the current full-field comparison reports 344/344
matching Copperline and WinUAE records. The result hash is
`b288b6701f2e1c9b15aac3ff875996e3981b3fc46ce8dcc38a0a44dd8708d070`; source
ID `41de7726dc64b2448da72f9749e1c3f6c144c643e75e81294d9c50cfc5739c06`.
This current repeat does not erase the earlier retained mismatch report; it
shows that the older observation was not reproduced in this capture.

The exact kind42 capture completed 160 rows and all 1,280 consecutive
DMACONR samples have BZERO set. Its result hash is
`8a1cfb795b06a733802de3a9656462eeb2caae2dd1e1c4892ccfc2e1e60b4cf2`, with
source ID `6817153ba97b5fa6ec4f9768f0e267b854a8d6e84d4a5ce2188ebcb88987a0e1`.
Earlier 15 October kind42 observations retained 896 differences, including
clear readings for C=`$0000/$BFFF` and direct-set/poll-clear behavior for
C=`$FFFF/$FFFE/$FEFF`. Current all-set results and older clear results remain
distinct observations. The A/B/C nonzero-prime matrix was added to test
history explicitly; neither the result nor the subsequent scope captures
isolates reset state, probe loading, or another cause of the earlier mismatch.

The archived kind44 comparison in this repository has 320 trial rows / 2,560
DMACONR sample words. Physical hardware and WinUAE metadata both report
`DENISEID=$FFFF`; this metadata agrees for this capture. Emulator ID
differences in other preflights are machine metadata, not trial-row
differences.

Kind33 hardware captures are available as
`captures/kind33-a500-la-attached/results.bin` (SHA-256
`c5f33adb9c740a60c8c75626c46123a19c1ce022a997e0c1b2ca30b8c79f8221`) and a
repeat as `captures/kind33-a500-la-attached-repeat/results.bin`. Each is 1,024
rows. Against current Copperline, the first capture differs in BZERO on 36 rows
(37 on the warm-reset repeat); against WinUAE it differs on 48 rows (49 on
the repeat). All other trial fields match. In the second A500 run, only row 57 changes between
hardware runs (BZERO set in the first run and clear in the repeat); other
fields and rows are unchanged. Two current Copperline clears, rows 129 and
257 (ASHIFT 2/4, BSHIFT 0, USEB off, 2 pixels), are stable-set on hardware;
the remaining 34 hardware-clear rows disagree with Copperline (emulator set),
and all 48 hardware-clear rows disagree with WinUAE (emulator set). Earlier
accepted hardware captures differ from the first current run in BZERO only on
115 and 117 rows, respectively. Matching Copperline and WinUAE results are under the
`*-current-v1` folders. The row-by-row presets for latest initial/repeat, old
accepted hardware and both emulators are in
`captures/kind33-a500-la-attached/comparison-summary.json`. Emulator Denise-ID
and VPOSR metadata is retained as provenance, not counted as trial-row
differences. These remain row-level observations; they do not by themselves
identify why the clear cases differ.

## Logic-analyzer observations

The three DMACONR-triggered RG03 captures each contain 250,000 packed logic
samples (1,000,000 bytes). The clock estimate is approximately 7,093,790 Hz,
using the caller-supplied nominal CPU reference of 7,093,790 Hz to translate
the measured D0 period. This is an estimated absolute time scale, not an
independent calibration. The RG03 LA x-increment header was found unreliable;
the decoder validates the actual payload against the point count. The
approximately 1 ns sample interval is derived by applying the nominal
7,093,790 Hz CPU reference to the measured D0 period; CH1 was off, so no
analog-span-derived interval is used.

| Capture | Qualified DMACONR windows | Stable BZERO | BZERO changes within window |
| --- | ---: | --- | ---: |
| `bzero-c0000-b0000` | 20 | high in 18; 2 transition windows | 2 |
| `bzero-c0000-bffff` | 21 | low in 3, high in 2; 16 transition windows | 16 |
| `bzero-cffff-b0000` | 21 | high in 18; 3 transition windows | 3 |

The three low stable samples in the C=`$0000`, B=`$FFFF` capture are a useful
positive control: D13 can be observed low during a qualified DMACONR window,
so these data do not support a permanently high D13 interpretation. The
transition windows are retained as transitions, not classified as stable
flags. Several overlap BBUSY transitions; this timing association alone does
not establish causality. Raw RG03 capture hashes are:

| Capture | SHA-256 |
| --- | --- |
| `address-walking-full.bin` | `59c5320b75c96ba0b3814e099c4b40847e367867216d54de7700b6d5da24edb8` |
| `bzero-c0000-b0000.bin` | `c1beec8580d6e54e36e03620059aff53eb7a5e2ae5f3d20ad6270ae4e0b1e9b4` |
| `bzero-c0000-bffff.bin` | `23188bcff22110d4f00aa947446e6b2f692f4b42f14371bf4362d4a5a694bc7c` |
| `bzero-cffff-b0000.bin` | `02c4411c4bb0c84d8a3e5d8ace68c079f6374d4a19c77a16db48aad6264459dc` |


A separate continuous RAM diagnostic (captures under `captures/bzero-scope-2026-10-16/`) used the same CPU-only two-pixel line blit while the logic analyzer observed repeated DMACONR reads. These are continuous-phase captures, not the standard ROM matrix trials above. The ASM controls were reviewed against physical scope results: ASHIFT 0 produced clear BZERO windows; ASHIFT 2 and 4 produced set BZERO windows. The ASHIFT-0 / B-DMA-on control also produced clear windows. Capture windows and stable/transition counts are:

| Capture | Qualified windows | Stable low | Stable high | Transitions | SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `bzero-ash0-bsh0-ca-bdmaoff.bin` | 21 | 3 | 2 | 16 | `6490e4aa2266a097c200aea24bb9e01f0839aaf94bca93df4932278aa7266f48` |
| `bzero-ash2-bsh0-ca-bdmaoff.bin` | 21 | 0 | 18 | 3 | `0d24eaa673b799058f11aeadc1e495e79b7738ca4c0e4081284a3a6bee924199` |
| `bzero-ash4-bsh0-ca-bdmaoff.bin` | 27 | 0 | 24 | 3 | `dbda875b98f3afa31762caa5c2f01fa4601d191215cd9a2990b26115bbaee8c3` |
| `bzero-ash0-bsh0-ca-bdmaon.bin` | 19 | 2 | 3 | 14 | `78cff5cc8789bf76ecb7ee8a832dd8a384898a96521e5e760307415234bd04fc` |

These captures use the first and last sampled D13 levels across each qualified read window; transition windows are explicitly retained as transitions rather than reduced to a midpoint or a guessed stable value. The corresponding analysis JSON files retain per-window first/last levels and transition offsets. `USEB` on at ASHIFT 0 is a clear control in this capture, with transition windows still present.

The firmware-loading control used `captures/kind42-a500-live-poke`: the prepared normal Kickstart-with-host-control image was byte-identical over all 720,896 bytes to `captures/irq-focus-backup-2026-10-15/flash.bin` (SHA-256 `7faf644f3d33d97075f07d7ffc4c5ca89037e17238cc012ec07e825f1b85638f`). It was flashed and exercised using the same hold-reset/poke/readback/release procedure as kind42. All 160 trial records matched the exact full-firmware-load kind42 capture, including all 1,280 BZERO-set samples; the packet hash is `f266485091270df01b2821919096a1dc55e0a2e95bdb74518e2bc17ef5ba6979` and differs in the header LOF field only. Live-poke readback SHA-256 `9c9b7e4a6c9bbe9fd5ea7f08d8a76e718fe60bcde2561edb495e068299e98b1b` matches the archived swapped ROM. The post-kind33 capture also matches all kind42 trial fields. This controls firmware bytes and the load procedure; cold/probe loading and retained history remain unisolated.

The full address walk has 70 selected custom-bus windows. Its decoded low
offset sequence repeatedly includes `$080`, `$100`, `$002`, `$004`, `$008`,
`$010`, `$020`, `$040`, `$080` and `$100`, consistent with the wired A1-A8 walking pattern
and Gary custom-register qualifier. It establishes operation of the sampled
low address mapping over these captures, not the full 24-bit address.

## Decoder scope and provenance

The RG03 wiring uses D0 for CPU clock; D1-D4 for AS, R/W, UDS and DTACK; D5
and D8 for CPU data14 and data13; D6-D7 and D9-D14 for address A1-A8; and D15
for Gary REGEN. The decoder selects windows with AS_N, REGEN_N, UDS_N and
DTACK_N active, then requires R/W and the sampled low address to remain stable.
It labels an offset-$002 read as a DMACONR read. It does not wire LDS_N, A0,
or upper address lines, so full-address qualification and independent
confirmation of both byte lanes are unavailable. UDS and known ROM word-read
opcodes support interpreting these as word reads; the decoder's window label
alone is not evidence of transfer width. Only D13 and D14 are sampled data
bits, and only during the qualified window. There is no direct observation of
internal blitter state or Agnus DMA channel fetches.

The BZERO bus captures used the validated digital wiring and Rigol MHO98
settings recorded in `captures/bzero-scope-2026-10-16/*-scpi.json`: 1M requested acquisition depth (250,000 LA points, 1,000,000 packed bytes), 20 us/div, 1.4 V digital thresholds, and both generator outputs OFF. CH1 was disconnected for these captures. The earlier separate
analog validation in `captures/a500-scope-validation-2026-10-16/README.md`
used CH1 on data13 and records analog excursions and threshold-agreement
limits; those analog observations are historical setup validation, not part
of the BZERO bus acquisition. Probe loading was not isolated against an
unprobed control, nor were cold boot, reset and retained-state conditions
independently crossed in this set of measurements.
Consequently, the different ROM and scope observations should be treated as
repeatable capture facts, not a diagnosis of their cause.

The v4 standalone address/BZERO archives remain immutable and unchanged. Their
original manifests hash the authored assembly, boot assembly, and (for BZERO)
pattern configuration, but do not separately snapshot the generated
`rom_layout.i` that supplies `PAYLOAD_BYTES` to the boot assembly. The current
builders now include that generated layout in each new source snapshot and
manifest input hashes. This provenance improvement does not retroactively
change or rebuild the archived v4 ROMs.

As a separate build-size check, the legacy builder assembled kind29
`--line-truth-table` and kind30 `--line-stage` in fresh isolated scratch copies
after kind46 was added. Kind29 produced 62,380 bytes (2,560 rows); kind30
produced 60,220 bytes (2,380 rows). Both fit below 64 KiB and produced 512 KiB
boot ROMs. The corresponding pre-kind46 measurements were 62,076 and 59,916
bytes, respectively, so the added controller code increased each payload by
304 bytes. Earlier pre-kind46 checks recorded kind37 `--line-wrap` at 45,180
bytes (1,152 rows) and the default 6,240-row matrix at 106,236 bytes; those
two sizes were not rebuilt in this final check. The default is above 64 KiB but
below the builder's 128 KiB payload copy window: the payload starts at
`$20000`, the results start at `$40000`, and the builder enforces
`payload_bytes < $20000`. No existing build archive was overwritten.

## Reproduction commands

Choose fresh archive and analysis paths; the builders reject existing output
directories, and the capture analyzer writes only to its requested JSON path.

```powershell
python tools/build_bus_address_rom.py --out build/scope-address-reproduction
python tools/build_scope_bzero_rom.py --c-pattern zero --b-data ffff --out build/scope-bzero-c0-bffff-reproduction
python tools/analyze_bzero_bus.py captures/bzero-scope-2026-10-16/bzero-c0000-bffff.bin --nominal-cpu-reference-hz 7093790 --output captures/bzero-scope-2026-10-16/bzero-c0000-bffff-reproduction.json
```
