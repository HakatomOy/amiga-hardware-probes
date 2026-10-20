"""Kind81: CPU overwrite versus Copper instruction-data fetch; no blitter."""
import argparse
from pathlib import Path
import shutil

import build_handoff_copper_race_rom as copper
import build_irq_stage_rom as base


def trials():
    return [(81,t,v|(n<<5),p,pad,r) for t in (0,3,6,9) for n in range(8)
            for v in (12,14) for p in range(2) for pad in (0,1) for r in range(2)]


def transform(stage):
    copper.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    path=stage/'src/rom/experiment.asm'
    text=path.read_text()
    assert text.count('cmpi.w #78,(a4)')==1
    path.write_text(text.replace('cmpi.w #78,(a4)','cmpi.w #81,(a4)'))
    path=stage/'src/rom/blitter_handoff_kernel.i'
    text=path.read_text()
    anchor='        cmpi.w #3,d1\n        bne.w .no_copper_list'
    assert text.count(anchor)==1
    text=text.replace(anchor,'        ; Prepare the same list even in the disabled-Copper control.')
    old='''        move.l #$12000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$12002,d4'''
    new='''        moveq #0,d4
        move.w 2(a4),d4
        divu.w #3,d4
        andi.l #$ffff,d4
        lsl.l #4,d4                  ; target0/3/6/9 selects MOVE0/4/8/12
        addi.l #$6002,d4
        movea.l d4,a1
        move.w #$009c,-2(a1)
        move.w #$8002,(a1)           ; old: DSKBLK; CPU overwrites with SOFT'''
    assert text.count(old)==1
    path.write_text(text.replace(old,new))
    path=stage/'src/rom/blitter_handoff_observer.i'
    text=path.read_text()
    assert text.count('move.w #$5555,d0')==8
    path.write_text(text.replace('move.w #$5555,d0','move.w #$8004,d0'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm',required=True)
    parser.add_argument('--wsl',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    base.build(args.vasm,args.wsl,args.out,rows=trials(),transform=transform,
        profile=dict(kind=81,targets=['MOVE0','MOVE4','MOVE8','MOVE12'],
                     sources=['CPU overwrites selected Copper INTREQ instruction data8002->8004; BLTSIZE always inert'],
                     masks=None,masked_fields=None,
                     measurement_fields='kind78; settled INTREQ bit1=old fetched,bit2=new fetched; COPER bit4=stream complete; aux=stored8004',
                     limitations='Direct CPU/Copper ordering witness, no active blitter. Exact launch cohorts; no pin timestamps or alignment.'))
