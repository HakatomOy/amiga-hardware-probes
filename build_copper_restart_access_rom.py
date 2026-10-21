"""Kind93: discriminate restart ownership with immediate CPU read/write controls."""
import argparse
from pathlib import Path
import shutil

import build_init_resource_race_rom as resource
import build_irq_stage_rom as base


def trials():
    return [(93, 3, 14 | (access << 5) | (mode << 8) | (gate_first << 10) | (setup << 11),
             phase, pad, repeat)
            for setup in range(2) for gate_first in range(2) for mode in range(3) for access in range(2)
            for phase in range(2) for pad in range(8) for repeat in range(2)]


def transform(stage):
    resource.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #90,(a4)') == 1
    path.write_text(text.replace('cmpi.w #90,(a4)', 'cmpi.w #93,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    # The unknown prefix is inside the measured window. Select its address
    # before alignment, then compare MOVEA immediate with register+two NOPs.
    text = text.replace('andi.w #3,d0\n        lsl.w #2,d0',
                        'andi.w #97,d0\n        lsl.w #2,d0')
    anchor = 'dc.l $ffb000,$ffb400,$ffb800,$ffbc00'
    assert text.count(anchor) == 1
    table = [f'${0xffb000 + (((index >> 6) & 1) * 4 + ((index >> 5) & 1) * 2 + (index & 1)) * 0x200:06x}'
             for index in range(98)]
    text = text.replace(anchor, 'dc.l ' + ','.join(table))
    anchor = '        ; Align in ROM, then apply phase and the 0..7 NOP launch padding.'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        move.l #$dff006,d4
        btst #5,5(a4)
        beq.s .restart_address_ready
        move.l #$dff1fe,d4
.restart_address_ready:
''' + anchor)
    path.write_text(text)
    blocks = []
    for setup in range(2):
        for gate_first in range(2):
            for access in range(2):
                bank = setup * 4 + gate_first * 2 + access
                address = 0xdff006 if access == 0 else 0xdff1fe
                operation = 'move.w (a1),d0' if access == 0 else 'move.w d0,(a1)'
                prefix = f'movea.l #${address:06x},a1' if setup == 0 else 'movea.l d4,a1\n        nop\n        nop'
                strobes = ['move.w #0,$88(a0)', 'move.w #$8080,$96(a0)']
                if gate_first:
                    strobes.reverse()
                blocks.append(f'''        dcb.b ${0xffb000 + bank * 0x200:06x}-*,0
restart_access_{bank}:
        move.w 6(a6),d2         ; input anchor precedes the unverified prefix
        move.w #$5555,d0
        {prefix}
        move.w 6(a6),d3         ; measure prefix, rather than qualify it away
        {strobes[0]}
        {strobes[1]}
        {operation}
        move.w 6(a6),d5
        move.w d2,12(a4)
        move.w d3,18(a4)
        move.w d0,16(a4)
        move.w d5,20(a4)
        move.w #255,d1
.settle_{bank}:
        dbra d1,.settle_{bank}
        move.w $1e(a6),28(a4)
        move.w 6(a6),30(a4)
        clr.w 32(a4)
        rts
''')
    (stage / 'src/rom/blitter_handoff_observer.i').write_text('\n'.join(blocks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(), transform=transform,
               profile=dict(kind=93, variants='bit3 inert BLTSIZE setup only;bit5 access0=VHPOSRread,1=NOOPwrite;bits9:8 off/WAIT/active;bit10 COPEN-before-COPJMP;bit11 register+twoNOP address setup instead of immediate',
                            fields={'12': 'input beam before prefix', '14': 'prelaunch COPER',
                                    '16': 'access result or5555', '18': 'prefix-complete beam', '20': 'post-access beam',
                                    '28': 'settled INTREQ', '30': 'settled beam'},
                            limitations='No blit is launched; exact raw beams, no alignment. Fixed opcode banks selected before alignment.'))
