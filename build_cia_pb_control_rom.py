"""Kind69: calibrated pulse/toggle and one-shot/continuous PB6 controls."""
import argparse
from pathlib import Path
import shutil
import build_cia_source_rom as source
import build_irq_stage_rom as base


def trials():
    phases = (0, 2, 4, 6, 8, 10, 12, 14, 20, 22, 28, 30)
    return [(69, 4, s, p, d, r) for s in (0, 2) for p in phases
            for d in range(8) for r in range(3)]


def transform(stage):
    source.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / 'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #66,(a4)', 'cmpi.w #69,(a4)'))
    p = stage / 'src/rom/edge_kernel.asm'
    s = p.read_text()
    for address in (0xffda00, 0xffdc00):
        old = f'''        moveq #$19,d7
        btst #2,7(a4)
        beq.s .plain{address:x}
        ori.w #6,d7
.plain{address:x}:'''
        new = f'''        moveq #$19,d7
        btst #3,7(a4)
        beq.s .oneshot{address:x}
        andi.w #$fff7,d7
.oneshot{address:x}:
        btst #2,7(a4)
        beq.s .plain{address:x}
        ori.w #2,d7
        btst #4,7(a4)
        bne.s .plain{address:x}
        ori.w #4,d7
.plain{address:x}:'''
        assert old in s
        s = s.replace(old, new)
    p.write_text(s)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, aligned=True, rows=trials(), transform=transform,
               profile=dict(kind=69, phases='bit3 continuous; bit4 pulse; bit2 PBON; bit1 EXG',
                            measurement_fields='Kind66 TA/PB6/INTREQ/TA/ICR',
                            limitations='First underflow boundary; no electrical pin recording or exhaustive short-period merging sweep'))
