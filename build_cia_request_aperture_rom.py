"""Kind84: odd/even request-read aperture after unchanged CIA timer/PB reads."""
import argparse
from pathlib import Path
import shutil

import build_cia_request_rom as request
import build_irq_stage_rom as base


def trials():
    return [(84,4,s,p,d,r) for s in (0,2) for p in range(8)
            for d in range(16) for r in range(5)]


def transform(stage):
    request.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    path=stage/'src/rom/experiment.asm'
    text=path.read_text()
    assert text.count('cmpi.w #68,(a4)')==1
    path.write_text(text.replace('cmpi.w #68,(a4)','cmpi.w #84,(a4)'))
    path=stage/'src/rom/edge_kernel.asm'
    text=path.read_text()
    anchor_a='        dcb.b $ffda00-*,0'
    anchor_b='        dcb.b $ffdc00-*,0'
    prefix, bodies=text.split(anchor_a,1)
    a,b=bodies.split(anchor_b,1)
    blocks=[]
    for address,old,cia,body,gap in ((0xffda00,0xffda00,0xbfe001,a,'nop'),
                                    (0xffdc00,0xffdc00,0xbfd000,b,'nop'),
                                    (0xffde00,0xffda00,0xbfe001,a,'exg d2,d2'),
                                    (0xffe000,0xffdc00,0xbfd000,b,'exg d2,d2')):
        old_gap=f'        move.b ${cia+0x100:06x},d1\n        move.w $1e(a6),d5'
        assert body.count(old_gap)==1
        body=body.replace(old_gap,f'        move.b ${cia+0x100:06x},d1\n        {gap}\n        move.w $1e(a6),d5')
        body=body.replace(f'.plain{old:x}',f'.plain{address:x}')
        blocks.append(f'        dcb.b ${address:06x}-*,0'+body)
    path.write_text(prefix+'\n'.join(blocks))
    path=stage/'src/rom/irq_stage_observer.i'
    text=path.read_text()
    for cia,plain,odd in (('a',0xffda00,0xffde00),('b',0xffdc00,0xffe000)):
        old=f'.fast_timer_{cia}:\n        jmp ${plain:06x}'
        new=f'''.fast_timer_{cia}:
        btst #0,7(a4)
        bne.s .odd_aperture_{cia}
        jmp ${plain:06x}
.odd_aperture_{cia}:
        jmp ${odd:06x}'''
        assert text.count(old)==1
        text=text.replace(old,new)
    path.write_text(text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm',required=True)
    parser.add_argument('--wsl',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    base.build(args.vasm,args.wsl,args.out,aligned=True,rows=trials(),transform=transform,
        profile=dict(kind=84,sources=['CIA-A TimerA','CIA-B TimerA'],masks=None,masked_fields=None,
                     phases='bit0=NOP2CCK vs EXG-self3CCK after PB6;bit1=existing launch EXG;bit2=PBON toggle control',
                     measurement_fields='kind68 TA/PB6/four INTREQ snapshots and independent PRA/launch/read brackets',
                     limitations='Actual grants,not nominal spacing,decide sub-E timing. No ICR read until cleanup. Pin propagation versus Paula sampling may still require electrical observation.'))
