#!/usr/bin/env python3
"""Kind61: CPU IRQ/prefetch/operand controls across display and Copper DMA."""
import argparse
from pathlib import Path
import shutil
import build_cpu_irq_rom as cpu
import build_irq_stage_rom as base


def trials():
    return [(61,t,s+8*dma,p,d,r) for dma in range(4) for t in range(5)
            for s in range(6) for p in (0,2) for d in range(4) for r in range(2)]


def transform(stage):
    cpu.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm';p.write_text(p.read_text().replace('cmpi.w #58,(a4)','cmpi.w #61,(a4)'))
    p=stage/'src/rom/irq_stage_kernel.i';s=p.read_text()
    s=s.replace('        move.w 4(a4),d0\n        add.w d0,d0','        move.w 4(a4),d0\n        andi.w #7,d0\n        add.w d0,d0',1)
    anchor='        lea $18100,a1'
    setup="""        lea $18000,a0
        move.w #8191,d0
.dma_clear:
        clr.w (a0)+
        dbra d0,.dma_clear
        move.l #$18000,$e0(a6)
        move.l #$18000,$e4(a6)
        move.l #$18000,$e8(a6)
        move.l #$18000,$ec(a6)
        move.l #$18000,$f0(a6)
        move.l #$18000,$f4(a6)
        move.w #$2c81,$8e(a6)
        move.w #$f4c1,$90(a6)
        move.w #$0038,$92(a6)
        move.w #$00d0,$94(a6)
        clr.w $108(a6)
        clr.w $10a(a6)
        move.w #$0200,$100(a6)
        moveq #0,d6
        move.w 4(a4),d0
        lsr.w #3,d0
        beq.s .dma_ready
        move.w #$8300,d6
        move.w #$4200,$100(a6)
        cmpi.w #1,d0
        beq.s .dma_ready
        move.w #$6200,$100(a6)
        cmpi.w #3,d0
        bne.s .dma_ready
        ori.w #$80,d6
.dma_ready:
        move.w d6,d0
        andi.w #$ff7f,d0
        move.w d0,$96(a6)
        lea $6000,a0
        moveq #31,d0
.dma_copper:
        move.w #$01fe,(a0)+
        clr.w (a0)+
        dbra d0,.dma_copper
        move.l #$fffffffe,(a0)
"""
    assert s.count(anchor)==1;s=s.replace(anchor,setup+anchor);p.write_text(s)
    p=stage/'src/rom/irq_stage_observer.i';s=p.read_text()
    s=s.replace('        move.w 4(a4),d0','        move.w 4(a4),d0\n        andi.w #7,d0',1)
    s=s.replace('        move.w d5,(a0)','        move.w d6,$96(a6)\n        move.w #0,$88(a6)\n        move.w d5,(a0)')
    # Added pre-write strobes move the STOP continuation by ten bytes.
    s=s.replace('move.l #$ffcd10,6(sp)','move.l #$ffcd1a,6(sp)')
    p.write_text(s)


def build(assembler,wsl,out):
    return base.build(assembler,wsl,out,aligned=True,rows=trials(),transform=transform,
        profile=dict(kind=61,targets=list(range(5)),sources=list(cpu.SOURCES),masks=list(cpu.MASKS),
            variants='source0..5 +8*DMA; DMA0=off,1=four planes,2=six,3=six+Copper32 NOOPs',
            phases='0 or EXG selector2; prelaunch brackets authoritative',
            event_offset='prelaunch NOP/DBRA pad0..3',
            launch='+12 pre-write beam;+14 zero; Copper/DMACON strobes after prebeam, then CPU IRQ write',
            watchdog='STOP handler records original PC then resumes after STOP at ffcd1a; bounded preflight',
            units='raw beam/flags/PC; no timestamp shifts',
            limitations='Prelaunch exact cohorts; bus contention and recognition separated by masked/running/STOP controls'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.vasm,a.wsl,a.out)
