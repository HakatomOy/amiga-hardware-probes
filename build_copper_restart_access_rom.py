"""Kind92: discriminate restart ownership with immediate CPU read/write controls."""
import argparse
from pathlib import Path
import shutil

import build_init_resource_race_rom as resource
import build_irq_stage_rom as base


def trials():
    return [(92, 3, 14 | (access << 5) | (mode << 8) | (gate_first << 10),
             phase, pad, repeat)
            for gate_first in range(2) for mode in range(3) for access in range(4)
            for phase in range(2) for pad in range(8) for repeat in range(2)]


def transform(stage):
    resource.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #90,(a4)') == 1
    path.write_text(text.replace('cmpi.w #90,(a4)', 'cmpi.w #92,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text()
    # Eight banks, chosen before alignment. All critical opcodes within a
    # gate-order group are identical except the intended read/write operation.
    text = text.replace('andi.w #3,d0\n        lsl.w #2,d0',
                        'andi.w #35,d0\n        lsl.w #2,d0')
    # The base table indexes variant>>5. Gate-first is index32..35, so
    # duplicate bank pointers through that fixed sparse index range.
    anchor = 'dc.l $ffb000,$ffb400,$ffb800,$ffbc00'
    assert text.count(anchor) == 1
    table = [f'${0xffb000 + (index % 4) * 0x200 + (0x800 if index >= 32 else 0):06x}'
             for index in range(36)]
    text = text.replace(anchor, 'dc.l ' + ','.join(table))
    path.write_text(text)
    blocks = []
    for gate_first in range(2):
        for access in range(4):
            address = 0x12000 if access < 2 else (0xdff006 if access == 2 else 0xdff1fe)
            operation = 'move.w (a1),d0' if access in (0, 2) else 'move.w d0,(a1)'
            strobes = ['move.w #0,$88(a0)', 'move.w #$8080,$96(a0)']
            if gate_first:
                strobes.reverse()
            blocks.append(f'''        dcb.b ${0xffb000 + gate_first * 0x800 + access * 0x200:06x}-*,0
restart_access_{gate_first}_{access}:
        move.w #$5555,d0
        movea.l #${address:06x},a1
        move.w 6(a6),12(a4)
        {strobes[0]}
        {strobes[1]}
        {operation}
        move.w 6(a6),d3
        move.w d0,16(a4)
        move.w d3,20(a4)
        move.w #255,d1
.settle_{gate_first}_{access}:
        dbra d1,.settle_{gate_first}_{access}
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
               profile=dict(kind=92, variants='bit3 inert BLTSIZE setup only;bits6:5 access0=chipread,1=chipwrite,2=VHPOSRread,3=NOOPwrite;bits9:8 off/WAIT/active;bit10 COPEN-before-COPJMP',
                            fields={'12': 'launch beam', '14': 'prelaunch COPER',
                                    '16': 'access result or5555', '20': 'post-access beam',
                                    '28': 'settled INTREQ', '30': 'settled beam'},
                            limitations='No blit is launched; exact raw beams, no alignment. Fixed opcode banks selected before alignment.'))
