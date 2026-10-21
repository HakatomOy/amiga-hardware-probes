"""Kind90: separate blitter source-fetch ordering from CPU status observation."""
import argparse
from pathlib import Path
import shutil

import build_handoff_stride_rom as stride
import build_irq_stage_rom as base


def trials(launch_sweep=False):
    priorities = (1,) if launch_sweep else range(2)
    nops = (0, 1, 3) if launch_sweep else range(4)
    launches = [(phase, pad) for phase in range(2) for pad in range(8)] if launch_sweep else ((0, 3), (0, 4), (1, 3))
    rows = [(90, 3, 6 | priority | inert | neighbor | (n << 5) | (mode << 8),
             phase, pad, repeat)
            for mode in range(3) for priority in priorities for inert in (0, 8)
            for neighbor in ((0,) if launch_sweep else (0, 16)) for n in nops
            for phase, pad in launches for repeat in range(2)]
    rows += [(90, 6, 6 | priority | neighbor | (mode << 8), 0, 4, repeat)
             for mode in range(3) for priority in range(2)
             for neighbor in (0, 16) for repeat in range(2)]
    if launch_sweep:
        rows += [(90, 3, 7 | 16 | (mode << 8), 0, 4, repeat)
                 for mode in range(3) for repeat in range(2)]
    return rows


def transform(stage):
    stride.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    path = stage / 'src/rom/experiment.asm'
    text = path.read_text()
    assert text.count('cmpi.w #67,(a4)') == 1
    path.write_text(text.replace('cmpi.w #67,(a4)', 'cmpi.w #90,(a4)'))
    path = stage / 'src/rom/blitter_handoff_kernel.i'
    text = path.read_text().replace('move.w #$0fff,d4', 'move.w #$09f0,d4')
    anchor = '        lsr.w #5,d0\n        lsl.w #2,d0'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '        lsr.w #5,d0\n        andi.w #3,d0\n        lsl.w #2,d0')
    old = '''        move.l #$10000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$f80000,d4'''
    new = '''        cmpi.w #6,2(a4)
        bne.s .not_preseeded
        move.w #$5555,$12000
.not_preseeded:
        move.l #$12000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$12002,d4'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    anchor = '        move.l #$6000,$80(a6)'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        move.w #$009c,$607c
        move.w #$8010,$607e       ; active finite stream completion witness
        move.w #$009c,$5ff8
        move.w #$8010,$5ffa       ; WAIT entry witness before sleeping
        move.w #$60a1,$5ffc
        move.w #$fffe,$5ffe
''' + anchor)
    anchor = '        ; Align in ROM, then apply phase and the 0..7 NOP launch padding.'
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''        movea.l #$dff100,a0      ; route critical strobes to inert palette addresses
        move.w 4(a4),d0
        andi.w #$0300,d0
        cmpi.w #$0200,d0
        beq.s .active_copper
        cmpi.w #$0100,d0
        bne.s .copper_mode_ready
        move.l #$5ff8,$80(a6)
        move.w #0,$88(a6)
        move.w #$8080,$96(a6)
        move.w #4095,d1
.wait_entry:
        move.w $1e(a6),d0
        btst #4,d0
        bne.s .copper_mode_ready
        dbra d1,.wait_entry
        move.w #1,32(a4)         ; failed WAIT activity control, not timing data
        movea.l (sp)+,a3
        rts
.active_copper:
        movea.l #$dff000,a0
.copper_mode_ready:
        move.w $1e(a6),14(a4)    ; prelaunch COPER witness; compared with mask16
''' + anchor)
    path.write_text(text)
    blocks = []
    for n in range(4):
        blocks.append(f'''        dcb.b ${0xffb000 + n * 0x400:06x}-*,0
init_resource_{n}:
        move.w #$5555,d0
        move.w 6(a6),12(a4)
        move.w #0,$88(a0)        ; same opcode in all modes, active or inert decode
        move.w #$8080,$96(a0)
        move.w d5,(a2)
        rept {n}
        nop
        endr
        move.w d0,(a1)           ; source or unused neighbor, same opcode
        move.w $02(a6),d1
        move.w 6(a6),d3
        move.w $02(a6),d2
        move.w 6(a6),d5
        move.w d0,16(a4)
        move.w d1,18(a4)
        move.w d3,20(a4)
        move.w d2,22(a4)
        move.w d5,24(a4)
        rept 256
        nop
        endr
        move.w $10000,26(a4)     ; old/new A word, independent of early status
        move.w $1e(a6),28(a4)
        move.w 6(a6),30(a4)
        move.w (a1),34(a4)       ; CPU overwrite must have landed
        clr.w 32(a4)
        rts
''')
    (stage / 'src/rom/blitter_handoff_observer.i').write_text('\n'.join(blocks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', required=True)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--launch-sweep', action='store_true',
                        help='Sweep both launch phases and padding0..7; priority-set source races, NOP0/1/3, with inert and preseed controls')
    args = parser.parse_args()
    base.build(args.vasm, args.wsl, args.out, rows=trials(args.launch_sweep), transform=transform,
               profile=dict(kind=90, launch_sweep=args.launch_sweep,
                            targets=['AD oldAAAA', 'AD preseeded5555 control'],
                            variants='bit0 priority;bit3 inert start;bit4 unused-neighbor write;bits6:5 NOP0..3;bits9:8 Copper0=off,1=settledWAIT,2=active',
                            hypothesis='Startup source-fetch progress depends on Copper state, separately from CPU status observation.',
                            competitor='Source ordering is unchanged; differences belong to CPU read arbitration/visibility.',
                            launch='Same launch/strobe/write opcodes; observer selected before ROM alignment; exact launch qualification.',
                            fields={'12': 'launch beam', '14': 'prelaunch COPER witness', '16': 'overwrite value',
                                    '18': 'status0', '20': 'post-status0 beam', '22': 'status1',
                                    '24': 'post-status1 beam', '26': 'settled old/new destination',
                                    '28': 'settled IRQ', '30': 'settled beam', '34': 'written source/neighbor'},
                            limitations='Software ordering and status witnesses, not electrical edges. WAIT may restart at VBL; entry COPER must be confirmed before launch.'))
