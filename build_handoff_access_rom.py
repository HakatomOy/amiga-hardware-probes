"""Kind74: identical first-read opcode, custom/chip/slow/ROM arbitration controls."""
import argparse
from pathlib import Path
import shutil
import build_handoff_edge_rom as edge
import build_irq_stage_rom as base


def trials():
    return [(74,t,v|(n<<5),p,pad,r) for t in (3,6,9,12) for n in range(6)
            for v in (0,1,2,3,8,9,10,11) for p in range(2)
            for pad in (0,2) for r in range(2)]


def transform(stage):
    edge.transform(stage)
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm'
    p.write_text(p.read_text().replace('cmpi.w #71,(a4)','cmpi.w #74,(a4)'))
    p=stage/'src/rom/blitter_handoff_kernel.i';s=p.read_text()
    s=s.replace('        cmpi.w #6,d0\n        bcs.s .ad_only','        cmpi.w #15,d0\n        bcs.s .ad_only')
    old='''        move.l #$10000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$f80000,d4
.read_address_ready:'''
    new='''        move.w #$a55a,$c70000
        move.l #$dff002,d4
        cmpi.w #6,2(a4)
        bcs.s .read_address_ready
        move.l #$10000,d4
        cmpi.w #9,2(a4)
        bcs.s .read_address_ready
        move.l #$c70000,d4
        cmpi.w #12,2(a4)
        bcs.s .read_address_ready
        move.l #$f80000,d4
.read_address_ready:'''
    assert old in s;s=s.replace(old,new);p.write_text(s)
    p=stage/'src/rom/blitter_handoff_observer.i';s=p.read_text()
    assert s.count('        move.w $02(a6),d0')==8
    p.write_text(s.replace('        move.w $02(a6),d0','        move.w (a1),d0'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    base.build(a.vasm,a.wsl,a.out,rows=trials(),transform=transform,
        profile=dict(kind=74,targets=['3 DMACONR','6 chip destination','9 slow C70000','12 ROM F80000'],
            sources=['CPU AD one-word start / inert-write control'],masks=None,masked_fields=None,
            phases='phase0/1 and launch padding0/2; post-start ROM NOPs0..5 in variant bits7:5',
            event_offset='None: original measured beams retained',watchdog='No outcome-dependent polling',
            launch='pre-start beam; identical MOVE.W (A1),D0 opcode for all first-read sources',
            units='packed beam,word and register bits; no alignment',
            measurement_fields='kind71 except end_beam is first-read word; launch_ref/end_ref/icr are post-first-read/post-status/post-request beams; aux is second DMACONR',
            limitations='Bus/visibility witness,not electrical pin timing. Slow RAM must be present; C70000 is outside copied kernels. No hardware-derived event time is inferred from emulator START.'))
