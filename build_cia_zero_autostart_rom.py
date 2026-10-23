"""PR810: paired TA/TB high-byte one-shot START readback aperture."""
import argparse
from pathlib import Path
import shutil
import build_irq_stage_rom as base


def trials():
    return [(126, cia, timer, latch, gap, repeat) for cia in range(2)
            for timer in range(2) for latch in (0, 1, 3)
            for gap in range(8) for repeat in range(3)]


def kernel():
    s = 'cia_zero_review_trial:\n        movem.l d0-d7/a0-a3,-(sp)\n'
    s += '        lea $bfe001,a0\n        tst.w 2(a4)\n        beq.s .selected\n        lea $bfd000,a0\n.selected:\n'
    s += '        clr.b $e00(a0)\n        clr.b $f00(a0)\n        move.b #$7f,$d00(a0)\n        tst.b $d00(a0)\n'
    s += '        tst.w 4(a4)\n        beq.s .ta\n        lea $200(a0),a0\n.ta:\n'
    # a0+400/500 is selected timer; control is e00 from original CIA base.
    s += '        lea $e00(a0),a1\n        tst.w 4(a4)\n        beq.s .control\n        lea -$100(a1),a1\n.control:\n'
    s += '        move.b #8,(a1)\n        move.b 7(a4),$400(a0)\n'
    s += '        move.w 8(a4),d0\n        lsl.w #2,d0\n        lea .observers(pc),a2\n        movea.l 0(a2,d0.w),a2\n        jmp (a2)\n'
    s += '.observers:\n' + ''.join(f'        dc.l .gap{g}\n' for g in range(8))
    for g in range(8):
        s += f'.gap{g}:\n        move.w 6(a6),12(a4)\n        clr.b $500(a0)\n'
        s += '        nop\n' * g
        s += '        moveq #0,d0\n        move.b (a1),d0\n        move.w d0,20(a4)\n'
        s += '        move.w 6(a6),14(a4)\n        bra.w .done\n'
    s += '.done:\n        moveq #0,d0\n        move.b (a1),d0\n        move.w d0,22(a4)\n'
    s += '        move.w #31,d0\n.wait: dbra d0,.wait\n        moveq #0,d0\n        move.b (a1),d0\n        move.w d0,34(a4)\n'
    s += '        clr.b (a1)\n        movem.l (sp)+,d0-d7/a0-a3\n        rts\n'
    return s


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    text = p.read_text().replace('cmpi.w #56,(a4)', 'cmpi.w #126,(a4)')
    text = text.replace('jsr irq_stage_trial', 'jsr cia_zero_review_trial')
    p.write_text(text + '\n' + kernel())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=126, targets=['CIA-A', 'CIA-B'], sources=None,
                            masks=None, masked_fields=None,
                            variants='0=TA,1=TB;phase=latch;delay=NOP count',
                            fields={'20': 'first CRA/CRB', '22': 'second CRA/CRB',
                                    '34': 'settled CRA/CRB', '12': 'pre-write beam',
                                    '14': 'post-first-read beam'},
                            limitations='VPA transfer aperture, not direct underflow counting. Paired timers and latch1/3 controls.'))
