# A500 divider IRQ verification, 15 October 2026

## Result

The physical A500 and WinUAE 6.0.3 Best Compatibility agree on every checked
observable in all 2,560 trials. A second hardware run produces the identical
102,464-byte result packet. The existing m68k computation-before-prefetch
correction remains supported, but full DIVU/DIVS interrupt equivalence is not
yet achieved in Copperline. Do not advertise that correction as complete
cycle-accurate divider IPL timing.

| Checked observable | WinUAE mismatches / 2,560 | Current Copperline mismatches / 2,560 |
| --- | ---: | ---: |
| Actual launch beam | 0 | 0 |
| Saved interrupt PC | 0 | 446 |
| Marker value on interrupt entry | 0 | 34 |
| First handler beam sample | 0 | 446 |
| Final division result | 0 | 256 |
| Final marker value | 0 | 0 |

These are overlapping counts, not independent failures. Copperline has 629
records differing in at least one checked observable. Of its 446 saved-PC
mismatches, 34 cross the DIV/following-marker boundary; the others select
different instructions in the subsequent TST/branch waiting loop. All 256
result mismatches belong to signed `$80000000 / -1`. WinUAE and hardware
preserve `$80000000`; the existing m68k implementation writes zero. This
arithmetic behavior predates the divider-ordering commit.

## Equipment and method

The owner's PAL A500 reports ECS Agnus `$a000`, OCS Denise ID `$ffff`,
512 KiB chip and 512 KiB slow RAM. One ROM Fire 40 A firmware 0.8.0 uses
USB 0.3.2, host-control 0.1.6 and SEL_C for 68000 reset. No scope probes or
external logic traces were used for this experiment. USB/RBCP transfer begins
only after all timed results have been collected in RAM.

The new standalone builder generates kind-20 nonzero operand variants without
changing the legacy variant-zero operand selection. Each trial synchronizes
at line 64, restarts the Copper list, executes the ROM horizontal aligner,
clears any stale BLIT request, and enters the ROM-resident DIVU or DIVS
kernel. A Copper WAIT for line 67, horizontal `$20`, followed by an INTREQ
BLIT write supplies the interrupt. This WAIT is a scheduling reference, not
a claim that the actual IRQ pin changes at exactly that beam coordinate.

Four alignment phases differ by one colour clock. Each phase sweeps 0-63
NOPs before the division. The existing kernel unmasks level 3, executes DIV,
executes a MOVEQ marker, then waits for the handler. The handler records its
first beam read, saved PC and marker before clearing the request. The handler
beam is **not** a measurement of IRQ assertion time. Actual launches match
across every record on the three systems; no pair was excluded. All captures
have zero timeouts/skips, complete headers, matching source IDs/descriptors,
and valid additive checksums.

The matrix contains eight DIVS operands and two DIVU controls, with display
DMA disabled (Copper DMA remains enabled). DIVS operands are 100/3, 100/-3,
-100/3, -100/-3, 0/-3, 100000/-2, `$10000000 / -1`, and `$80000000 / -1`.
100000/-2 exercises signed quotient overflow without early absolute overflow;
the final two exercise early absolute overflow. DIVU uses the first two bit
patterns, interpreting the divisor as unsigned.

WinUAE resolves CPU compatible/cycle-exact/memory-cycle-exact and blitter
cycle-exact to true, CPU speed real, ECS Agnus, PAL, matching RAM, zero cache
and no fast RAM. The exact executable hashes are in each invocation.json.
Copperline uses the existing release executable recorded in its invocation.
No m68k or Copperline CPU implementation was changed for this verification.

## DIVS early IPL sample

WinUAE source calls out a DIVS poll two CPU clocks earlier when dividend >= 0
and divisor < 0, excluding early absolute overflow. The positive 100/3 and
negative-divisor 100/-3 cases have different divider durations, but the
hardware's first delay taking the interrupt before the marker is identical:
`[27, 27, 26, 26]` for phases 0-3, as WinUAE predicts. All other signed operand
and overflow controls also match WinUAE for saved PC and handler beam.

This supports the source-derived early-poll model on this physical A500.
It does not directly observe the CPU's internal IPL latch. Current m68k has
no operand-dependent DIVS early poll. Copperline also differs for ordinary
DIVU and DIVS cases, so adding that special poll alone cannot account for all
34 boundary mismatches or the waiting-loop mismatches. The CPU core and host
IRQ propagation/sample mechanism need to be isolated separately.

## Provenance

Accepted immutable ROM archive: `build/divider-irq-signs-v3`.
Source ID: `5d1558cd75f40b7e947773e4778873a8e8ccf42876309960aed568e3f2261d40`.
Normal-order ROM SHA-256:
`6d4c99841661bc8d7003631c29d063236df7e7442e0064d0e4d031ca0504ab2d`.
The archived manifest includes ROM hashes, exact descriptors, operand metadata
and a source snapshot with file hashes. It contains the pre-capture sources;
later tooling/test edits do not change the measured ROM's identity.

Accepted capture directories under `captures/`:

* `divider-irq-a500-v3`
* `divider-irq-a500-v3-repeat`
* `divider-irq-winuae-v3`
* `divider-irq-copperline-v3`

Both physical packets have SHA-256
`5cdce1ea1730161e0340709f8f5aae1cd623c6f7efc7bbc9a5d9f379cb81ec4e`.
WinUAE packet hash:
`4de766cbe7e08a7ffc328ae086202d49e03268497b4bbc9aa25de2a7d0f60efb`.
Copperline packet hash:
`41603b253d8d7682ffa13ae60e21f014bb1884a040d5aab8403a08570f06eee3`.
Detailed comparisons: `captures/divider-irq-a500-v3-comparison.json` and
`captures/divider-irq-emulator-v3-comparison.json`.

Earlier `v1`/`v2` bundles are exploratory and superseded. Their Copper setup
allowed a stale pending interrupt, obscuring the intended completion boundary.
A checksum-valid packet is not sufficient to validate an experiment's design.

## Restoration

The installed 720,896-byte firmware was backed up before flashing and restored
at the end. Its flash readback is byte-for-byte identical, SHA-256
`7faf644f3d33d97075f07d7ffc4c5ca89037e17238cc012ec07e825f1b85638f`.
The restored live ROM hash is
`9797dfe08af1e48271528411a41eda20fb03ee3cf387e610ce50eedfb0c457eb`,
matching the previous restored Kickstart reference. The pre/post live reads
differ only in six bytes at offsets `$7fc00..$7fc05`, within the runtime RBCP
back-channel header. The firmware image itself is identical. Backup and
readback files are in `captures/divider-irq-2026-10-15-backup`.

## Reproduction and validation

```powershell
python build_divider_irq_rom.py --wsl --vasm /mnt/c/Users/seppo/amiga/amiga-hardware-probes/.tools/vasm/vasmm68k_mot --out build/divider-irq-new
python run_winuae_rom.py --binary 'C:\Program Files\WinUAE\winuae64_603.exe' --romdir build/divider-irq-new --out captures/divider-irq-winuae-new
python run_rom.py --binary ../Copperline/target/release/copperline.exe --romdir build/divider-irq-new --out captures/divider-irq-copperline-new
python compare_divider_irq.py captures/divider-irq-a500-v3/results.json captures/divider-irq-winuae-v3/results.json captures/divider-irq-copperline-v3/results.json --out captures/divider-irq-comparison-new.json
python -m unittest discover -s tests -q
```

Flash/collect uses the existing procedure in `rom-measurement.md`, supplying
the new ROM directory and its manifest explicitly. The wrapper refuses to
overwrite archives. Its default 2,560-row matrix fits the 64-KiB boot-payload
region as well as the RAM result buffer. Two existing out-of-range BSRs were
converted to absolute JSRs so the enlarged controller still assembles on a
68000; the corresponding source assertion was updated. All 64 Python tests
pass. m68k's four contribution checks passed in the preceding source review.

## Next work before claiming complete accuracy

1. Add focused ordinary-instruction IRQ probes (NOP, EXG, TST/branch and
   MOVEQ) using this same single-event, matched-launch method. Establish the
   actual Copper request timing and separate host IRQ propagation delay,
   ordinary CPU poll timing and handler-entry timing. Do not globally retune
   IRQ latency merely to make DIV pass.
2. Add a CPU/bus regression for DIVS with a nonnegative dividend and negative
   divisor. Model its early IPL sample independently of the final prefetch;
   moving the bus fetch earlier would implement the wrong behavior. The bus
   interface may need an explicit timed-sample event rather than a hold of
   the preceding bus access's IPL value.
3. Fix the pre-existing signed minimum-dividend overflow result separately,
   with an arithmetic/flags test and a hardware CCR capture if exact overflow
   flags are claimed. This experiment validates D0, not division CCR state.
4. Repeat the boundary matrix under bitplane DMA after the no-display-DMA
   IRQ path agrees. Add immediate/memory DIVS, additional divisors/quotient
   bit patterns, divide-by-zero, and final-prefetch bus-fault state as separate
   focused experiments/tests. These paths are not established by this sweep.
5. Keep the existing prefetch-order PR narrowly worded and disclose the
   remaining IPL limitation unless it is resolved and independently verified.

## Follow-up m68k correction and replay

m68k commit `275b2e6` preserves the MC68000 destination and sets overflow for
`$80000000 / -1`, and exposes the two-clock-earlier DIVS poll through an
explicit internal sample-and-hold bus hook. Copperline implements that hook.
The bus prefetch position and total instruction duration remain unchanged.
All four m68k contribution checks pass, including new clocked-bus IRQ tests
for operand signs, addressing modes and interrupt arrivals on each side of
the early sample, plus overflow-result regressions.

Replaying the accepted v3 ROM with the rebuilt Copperline gives zero division
result mismatches in 2,560 identical-launch pairs. Capture:
`captures/divider-irq-copperline-fixed-v3`; comparison:
`captures/divider-irq-a500-v3-fixed-comparison.json`. Packet SHA-256:
`8a1f0991a8b8fec991f7935f4053835ccbad0c955d36904f977d148a2d2b10ae`.
Saved-PC/handler-beam mismatches are 452 (446 before), including 40 DIV/marker
boundary mismatches (34 before). The corrected sign-dependent sample removes
an accidental cancellation in six cases; it does not fix the common
recognition discrepancy. Do not describe the complete Copperline IRQ path
as matching A500 yet. All final marker values still agree. There are no
excluded launches, timeouts or skips.

The waiting-loop TST poll also needs isolation: WinUAE's memory TST handler
polls before the operand read, while m68k's current handler leaves polling
to the final bus access. Separate this from the DIV boundary and host IRQ
propagation before changing general latency. In the next hardware probes,
move SR unmasking outside the timed window and measure Copper INTREQ raw
readback separately from CPU IRQ recognition to discriminate source-event,
poll-phase and visibility-delay differences. Preserve the passing STOP
controls when testing a common IRQ-pipeline correction.
