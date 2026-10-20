"""Kind65: TST/MOVE/CMP chip/ROM/slow operands under DMA, STOP/raw controls."""
import argparse
from pathlib import Path
import shutil
import build_cpu_dma_rom as dma
import build_irq_stage_rom as base


def trials():
    return [(65,t,4+8*d+32*m,p,pad,r) for t in range(5) for d in range(4)
            for m in range(3) for p in (0,2) for pad in range(4) for r in range(2)]


def transform(stage):
    dma.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm';p.write_text(p.read_text().replace('cmpi.w #61,(a4)','cmpi.w #65,(a4)'))
    p=stage/'src/rom/irq_stage_kernel.i';s=p.read_text()
    s=s.replace('        lsr.w #3,d0','        lsr.w #3,d0\n        andi.w #3,d0')
    s=s.replace('        lea $18100,a1', '''        lea $18100,a1
        move.w 4(a4),d0
        lsr.w #5,d0
        beq.s .operand_ready
        lea $ffb000,a1
        cmpi.w #1,d0
        beq.s .operand_ready
        lea $c18000,a1
.operand_ready:''')
    p.write_text(s)
    p=stage/'src/rom/irq_stage_observer.i';s=p.read_text()
    s=s.replace('.loop:\n        nop','.loop:\n        tst.w (a1)')
    s=s.replace('        move.b d0,-(a1)','        move.w (a1),d0')
    s=s.replace('.tst_loop:\n        tst.w (a1)','.tst_loop:\n        cmp.w (a1),d0')
    p.write_text(s)


def build(assembler,wsl,out):
    return base.build(assembler,wsl,out,aligned=True,rows=trials(),transform=transform,
        profile=dict(kind=65,targets=['TST','MOVE','STOP','CMP','MASKED'],
            sources=['CPU COPER write'],masks=None,masked_fields=None,
            variants='CPU COPER write4 +8*DMA0..3 +32*operand0chip/1ROM/2slow',
            launch='exact pre-write beam; same finite Copper32 NOOPs as kind61',
            watchdog='STOP guard ffcd1a; bounded preflight before hardware',
            fields={'end_ref':'handler diagnostic or masked settled INTREQR',
                'counter':'IRQ loop count or masked raw0','icr':'IRQ pointer or masked raw1',
                'irq_beam':'handler beam or masked raw2','irq_level':'IRQ level or first read beam',
                'saved_pc_offset':'stacked PC or masked read beam pair','aux':'IRQ count or last read beam',
                'second_counter_or_beam':'final loop count or settled INTREQR',
                'second_icr_or_level':'final pointer or expected source mask'},
            units='raw packed beam words, PC, counts and flags; no alignment',
            limitations='Handler observation combines operand/prefetch/exception timing; not an electrical grant trace'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.vasm,a.wsl,a.out)
