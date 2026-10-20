"""Kind67: vary BBUSY polling cadence independently of launch/DMA controls."""
import argparse
from pathlib import Path
import shutil
import build_handoff_focus_rom as focus
import build_irq_stage_rom as base


def trials():
    variants=tuple(range(16))+(18,19,26,27)
    return [(67,3,v|(stride<<5),p,pad,r) for stride in range(4) for v in variants
            for p in range(2) for pad in range(4) for r in range(2)]


def transform(stage):
    focus.transform(stage,read_control=True)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm';p.write_text(p.read_text().replace('cmpi.w #60,(a4)','cmpi.w #67,(a4)'))
    p=stage/'src/rom/blitter_handoff_kernel.i';s=p.read_text()
    anchor='        ; Align in ROM, then apply phase and the 0..7 NOP launch padding.'
    s=s.replace(anchor,'''        move.l a3,-(sp)
        move.w 4(a4),d0
        lsr.w #5,d0
        lsl.w #2,d0
        lea .observers(pc),a1
        movea.l 0(a1,d0.w),a3
'''+anchor)
    s=s.replace('        jsr $ffb000','        nop\n        jsr (a3)\n        movea.l (sp)+,a3')
    s+='\n.observers: dc.l $ffb000,$ffb400,$ffb800,$ffbc00\n';p.write_text(s)
    p=stage/'src/rom/blitter_handoff_observer.i';original=p.read_text()
    original=original[original.index('blitter_handoff_observer:'):]
    blocks=[]
    for stride in range(4):
        body=original.replace('blitter_handoff_observer:',f'blitter_stride_{stride}:')
        body=body.replace('.wait_busy:\n','.wait_busy:\n'+'        nop\n'*stride)
        blocks.append(f'        dcb.b ${0xffb000+stride*0x400:06x}-*,0\n'+body)
    p.write_text('\n'.join(blocks))


def build(assembler,wsl,out):
    return base.build(assembler,wsl,out,rows=trials(),transform=transform,
        profile=dict(kind=67,targets=['AD one word'],sources=['CPU start/inert write'],masks=None,masked_fields=None,
            phases='0/1 launch phase unchanged; cadence encoded in variant bits6:5',
            variants='low5 bits kind60; bits6:5 insert0..3 ROM NOPs before each BBUSY sample',
            event_offset='launch pad0..3',watchdog='4096 busy polls',
            launch='pre-write beam; indirect start address; observer selected before alignment',
            units='packed beam/data/register words; no alignment',
            measurement_fields={'launch_ref':'first clear DMACONR','end_beam':'early data/ROM read',
                'end_ref':'postwrite DMACONR','counter':'handoff beam','icr':'postwrite beam',
                'irq_beam':'final first D','irq_level':'final last D','saved_pc_offset':'INTREQ:final beam',
                'aux':'remaining busy DBRA'},
            limitations='Software observations distinguish poll-phase dependence; no direct final D pin trace'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.vasm,a.wsl,a.out)
