"""Kind102: locate PF-PF zero match near display/fetch start."""
import argparse
from pathlib import Path
import shutil
import build_playfield_modes_rom as modes
import build_irq_stage_rom as base


def trials():
    return [(102,target,dual,pixel,0,repeat) for target in (4,15)
            for pixel in (0,3) for dual in range(2) for repeat in range(4)]

OBSERVER='''        dcb.b $ffb000-*,0
playfield_zero_burst:
        move.w 6(a6),d3
        move.w #$8300,$96(a6)
.wait:
        move.w 6(a6),d0
        cmpi.w #$4400,d0
        bcs.s .wait
        move.w 6(a6),14(a4)
        tst.w $0e(a6)
        move.w 6(a6),26(a4)
        move.w $0e(a6),d0
        move.w $0e(a6),d1
        move.w $0e(a6),d2
        move.w $0e(a6),d4
        move.w $0e(a6),d5
        move.w $0e(a6),d6
        move.w 6(a6),34(a4)
        move.w d0,20(a4)
        move.w d1,22(a4)
        move.w d2,16(a4)
        move.w d4,18(a4)
        move.w d5,24(a4)
        move.w d6,36(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    modes.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm';p.write_text(p.read_text().replace('cmpi.w #101,(a4)','cmpi.w #102,(a4)'))
    p=stage/'src/rom/blitter_handoff_kernel.i';s=p.read_text().replace('        move.w d4,24(a4)\n','').replace('        move.w d5,36(a4)\n','');p.write_text(s)
    (stage/'src/rom/blitter_handoff_observer.i').write_text(OBSERVER)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vasm',required=True)
    p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    base.build(a.vasm,a.wsl,a.out,rows=trials(),transform=transform,profile=dict(kind=102,
        fields={'20':'sample0','22':'sample1','16':'sample2','18':'sample3','24':'sample4','36':'sample5'},
        limitations='Six destructive CLXDAT reads bracketed by raw beams; no alignment or assumed electrical timestamps. No sprites/Copper/blitter.'))
