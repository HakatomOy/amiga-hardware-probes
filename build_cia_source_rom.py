"""Kind66: calibrated timer counter/PB6/ICR/Paula request observations."""
import argparse
from pathlib import Path
import shutil
import build_cia_phase_rom as phase
import build_irq_stage_rom as base


def trials():
    return [(66,4,s,p,d,r) for s in (0,2) for p in (0,2,4,6)
            for d in range(16) for r in range(5)]


def transform(stage):
    phase.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm';p.write_text(p.read_text().replace('cmpi.w #57,(a4)','cmpi.w #66,(a4)'))
    p=stage/'src/rom/edge_kernel.asm';s=p.read_text();s=s[:s.index('        dcb.b $ffda00-*,0')]
    for address,cia in ((0xffda00,0xbfe001),(0xffdc00,0xbfd000)):
        s+=f'''
        dcb.b ${address:06x}-*,0
        moveq #$19,d7
        btst #2,7(a4)
        beq.s .plain{address:x}
        ori.w #6,d7
.plain{address:x}:
        move.w 6(a6),d2
        move.b d7,${cia+0xe00:06x}
        move.w 6(a6),d3
        move.w d2,12(a4)
        move.w d3,14(a4)
        rept 66
        nop
        endr
        move.w 6(a6),d3
        moveq #0,d0
        move.b ${cia+0x400:06x},d0
        moveq #0,d1
        move.b ${cia+0x100:06x},d1
        move.w $1e(a6),d5
        moveq #0,d7
        move.b ${cia+0x400:06x},d7
        move.w 6(a6),d6
        moveq #0,d4
        move.b ${cia+0xd00:06x},d4
        move.w d0,20(a4)
        move.w d1,22(a4)
        move.w d5,24(a4)
        move.w d3,26(a4)
        move.w d7,28(a4)
        move.w d4,30(a4)
        move.w d6,34(a4)
        rts
'''
    p.write_text(s)


def build(assembler,wsl,out):
    return base.build(assembler,wsl,out,aligned=True,rows=trials(),transform=transform,
        profile=dict(kind=66,targets=['masked observations'],sources=['CIA-A timer','CIA-B timer'],masks=None,
            phases='bit1=EXG; bit2=PBON toggle versus disabled',watchdog='bounded measurement; no CPU interrupt wait',
            units='CIA count/flags and raw packed beam; no shifts',masked_fields=None,
            launch='before/after START+LOAD one-shot; independent PRA calibration before launch',
            fields={'counter':'TA before','icr':'PRB PB6','irq_beam':'INTREQR',
                'irq_level':'sample beam before','saved_pc_offset':'TA after:ICR flags','aux':'sample beam after',
                'end_beam':'independent calibration pre-beam','second_counter_or_beam':'calibration post-beam'},
            limitations='Software counter/PB6/request observations, not simultaneous electrical pin traces'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.vasm,a.wsl,a.out)
