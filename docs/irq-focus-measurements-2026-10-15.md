# IRQ focus measurement limits

Kind43 target 10 uses `STOP` as its timed instruction. Keep its delay at 40 or
below. With longer delays, the first IRQ can arrive before `STOP` executes;
the CPU then sleeps until Copper raises another IRQ on a later frame, and the
second handler can overwrite the first measurement. Those rows do not measure
the intended instruction window, so the builder omits them and rejects a
target-10 selection with no safe delay. Other targets still use the full
requested delay range.

## Archived target-0 label erratum

The kind43 controller writes `$0010` to INTREQ. That bit is Copper's COPER
request (`$0040` is BLIT), so target 0 is a masked COPER request observed
through INTREQR. The existing `irq-focus-*-v2` and `irq-focus-*-v3` archives
and captures used an incorrect BLIT label in their manifests and descriptions;
they remain immutable and should be interpreted as COPER-request experiments.
The current builder uses the corrected COPER label. This naming correction
does not change the instruction stream or require new captures.

## Physical experiment and result

The PAL A500 (stock 68000, 512 KB chip, 512 KB slow, ECS Agnus, OCS Denise)
ran the `build/irq-focus-v3` archive twice through One ROM / RBCP. Source ID:
`99a1ae36ea4d03e93fbce46b6eefead08fcba4dcc2dbd7b24fd31e9cbcbb68d1`.
All 2,212 compared observations repeat exactly. One incidental VERTB bit in
a masked INTREQR word differs between runs; the observed COPER bit and both
beam brackets agree. The final comparison excludes no rows.

| Suite | Observations | Copperline before mismatches | After | WinUAE Best Compatibility |
| --- | ---: | ---: | ---: | ---: |
| Focused kind43 | 2,212 | 1,774 | 0 | 0 |
| Divider signs v3 | 2,560 | 452 | 0 | 0 |
| Native/Copper STOP paths | 896 | 0 | 0 | 0 measured timing/PC differences |

Copperline now samples raw INTREQR before the CPU transfer's trailing CCK,
qualifies ordinary 68000 polls separately from the STOP deadline, and uses
an explicit memory-TST operand poll (low word for TST.L). The divider and
STOP result packets are byte-identical to hardware. Global latency=4 was a
diagnostic only: it fixed running instructions while breaking STOP cases.

Captures: `irq-focus-a500-v3`, `irq-focus-a500-v3-repeat`,
`irq-focus-copperline-v3-before`, `irq-focus-copperline-v3-fixed2`,
`irq-focus-winuae-v3`. Comparisons: `irq-focus-v3-final-comparison.json`,
`irq-focus-v3-repeat-comparison.json`, `divider-irq-v3-final-comparison.json`.
The intermediate `irq-focus-copperline-v3-fixed1` is excluded because the
executable was replaced during capture; the runner formerly hashed at the
end. It now hashes before launch and rejects changed binaries.

The exact original Kickstart firmware was restored, with matching flash
readback SHA-256
`7faf644f3d33d97075f07d7ffc4c5ca89037e17238cc012ec07e825f1b85638f`.

See the detailed implementation, provenance and next measurement plan in
[the Copperline report](../../Copperline/docs/internals/a500-irq-focus-2026-10-15.md).
Next experiments should separate operand and prefetch contention, broaden
instruction classes, and sweep source set/clear/masking and priority changes.
These end-to-end results do not directly measure Paula's IPL pins.

## Reproduction

Build an immutable archive with `build_irq_focus_rom.py --wsl --vasm PATH
--out build/NEW_NAME`. Run the same archive with `run_rom.py` and
`run_winuae_rom.py`; flash its One ROM-order image through a board/plugin
firmware bundle, reset SEL_C and collect with `collect_rom_usb.py --manifest
build/NEW_NAME/manifest.json`. Preserve and restore original device firmware.
Compare decoded results with `compare_irq_focus.py REF/results.json
CANDIDATE/results.json --out REPORT.json`. The comparator rejects source-ID,
count and descriptor mismatches, and reports unmatched launch/status rows
explicitly. Diagnostic latency overrides must remain labelled diagnostic.
Generated ROMs, captures and machine firmware remain local ignored assets.
