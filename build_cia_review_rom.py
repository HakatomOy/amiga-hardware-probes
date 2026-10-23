"""PR810: stale IR versus a fresh serial request, with masked/ack controls."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base


def trials():
    return [(125, cia, mode, 0, 0, repeat)
            for cia in range(2) for mode in range(4) for repeat in range(4)]


KERNEL = '''
cia_review_trial:
        movem.l d0-d7/a0-a3,-(sp)
        lea $bfe001,a0
        move.w #8,d7
        tst.w 2(a4)
        beq.s .selected
        lea $bfd000,a0
        move.w #$2000,d7
.selected:
        clr.b $e00(a0)
        clr.b $f00(a0)
        move.b #$7f,$d00(a0)
        tst.b $d00(a0)
        move.b #3,$400(a0)
        clr.b $500(a0)
        move.b #$81,$d00(a0)
        cmpi.w #3,4(a4)
        beq.s .no_old
        move.b #$19,$e00(a0)
        move.w #63,d0
.old_wait: dbra d0,.old_wait
.no_old:
        move.w $1e(a6),20(a4)
        move.b #1,$d00(a0)
        cmpi.w #2,4(a4)
        bne.s .no_ack
        tst.b $d00(a0)
.no_ack:
        move.b #$40,$e00(a0)
        move.w #127,d0
.settle: dbra d0,.settle
        move.w d7,$9c(a6)
        move.w #31,d0
.clear_wait: dbra d0,.clear_wait
        move.w $1e(a6),34(a4)
        tst.w 4(a4)
        beq.s .masked
        move.b #$88,$d00(a0)
.masked:
        move.b #$a5,$c00(a0)
        move.b #$51,$e00(a0)
        move.w #511,d0
.serial_wait: dbra d0,.serial_wait
        move.w $1e(a6),36(a4)
        moveq #0,d0
        move.b $d00(a0),d0
        move.w d0,22(a4)
        moveq #0,d0
        move.b $e00(a0),d0
        move.w d0,38(a4)
        clr.b $e00(a0)
        move.b #$7f,$d00(a0)
        tst.b $d00(a0)
        movem.l (sp)+,d0-d7/a0-a3
        rts
'''


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    text = p.read_text().replace('cmpi.w #56,(a4)', 'cmpi.w #125,(a4)')
    text = text.replace('jsr irq_stage_trial', 'jsr cia_review_trial')
    p.write_text(text + '\n' + KERNEL)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=125, targets=['CIA-A', 'CIA-B'],
                            sources=None, masks=None, masked_fields=None,
                            variants='0=SP masked;1=stale IR+SP;2=ICR ack+SP;3=no old TA+SP',
                            fields={'20': 'old INTREQR', '22': 'final ICR',
                                    '34': 'INTREQR after mask clear and Paula ack',
                                    '36': 'INTREQR after serial completion', '38': 'CRA'},
                            limitations='Settled flag/request truth table, not electrical IRQ timestamps.'))
