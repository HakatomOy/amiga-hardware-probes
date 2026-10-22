"""Kind107: beam polling versus fixed ROM instructions under bitplane DMA."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_modes_rom as modes


def trials():
    return [(107, target, dual | (fixed << 2) | (off << 3), 2, pad, repeat)
            for target in (8, 12) for fixed in range(2) for off in range(2)
            for dual in range(2) for pad in range(4) for repeat in range(2)]


def observer():
    prefix = '''        dcb.b $ffb000-*,0
clear_observer:
        move.w 6(a6),d3
        move.w d7,$96(a6)
        jmp (a3)
'''
    wait = ''.join(f'''        dcb.b ${0xffb100 + pad * 0x80:x}-*,0
poll_{pad}:
        move.w 6(a6),d0
        cmpi.w #${0x4410 + pad * 8:x},d0
        bcs.s poll_{pad}
        bra.w clear_tail
''' for pad in range(4))
    wait += '''        dcb.b $ffb400-*,0
        rept 194
        nop
        endr
        bra.w clear_tail
'''
    # All RAM stores follow the critical clear. Keep the original clear/read
    # sequence; neither path polls CLXDAT. Beam values are raw, never aligned.
    suffix = '''clear_tail:
        move.w 6(a6),14(a4)
        tst.w $0e(a6)
        move.w d6,$144(a6)
.wait_sample:
        move.w 6(a6),d0
        cmpi.w #$44d0,d0
        bcs.s .wait_sample
        move.w 6(a6),26(a4)
        move.w $0e(a6),d0
        move.w 6(a6),34(a4)
        move.w d0,20(a4)
        move.w $0e(a6),22(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''
    return prefix + wait + suffix


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    shutil.copyfile(modes.__file__, stage / Path(modes.__file__).name)
    p = stage / 'src/rom/experiment.asm'
    text = p.read_text()
    assert text.count('cmpi.w #49,(a4)') == 1
    p.write_text(text.replace('cmpi.w #49,(a4)', 'cmpi.w #107,(a4)'))
    setup = '''        move.w #$8300,d7
        btst #3,5(a4)
        beq.s .dma_ready
        move.w #$8200,d7
.dma_ready:
        moveq #0,d0
        move.w 8(a4),d0
        btst #2,5(a4)
        bne.s .fixed_address
        lsl.l #7,d0
        addi.l #$ffb100,d0
        bra.s .address_ready
.fixed_address:
        lsl.l #3,d0
        neg.l d0
        addi.l #$ffb418,d0
.address_ready:
        movea.l d0,a3
'''
    kernel = modes.KERNEL.replace('        jsr sync_beam', setup + '        jsr sync_beam')
    kernel = kernel.replace('blitter_handoff_trial:\n',
                            'blitter_handoff_trial:\n        movem.l d7/a3,-(sp)\n')
    kernel = kernel.replace('        rts', '        movem.l (sp)+,d7/a3\n        rts')
    (stage / 'src/rom/blitter_handoff_kernel.i').write_text(kernel)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(
        observer())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=107, variants='bit0 DPF; bit2 fixed NOPs; bit3 DMA off',
                            fields={'12': 'observer entry', '14': 'pre-clear beam',
                                    '20': 'CLXDAT', '22': 'second CLXDAT',
                                    '26': 'pre-read beam', '34': 'post-read beam'},
                            limitations='Raw VHPOSR words; exact entry qualification; no alignment. '
                            'Two mask targets, constant plane pattern2, transparent sprite. '
                            'Polling thresholds4410/4418/4420/4428; fixed182/186/190/194 NOPs.'))
