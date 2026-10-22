"""Kind101: paired single/dual playfield collision truth table on A500."""
import argparse
from pathlib import Path
import shutil
import build_irq_stage_rom as base


def trials():
    return [(101,mask*4+desired,dual | (sprite<<1),pixel,0,repeat)
            for mask in range(4) for desired in range(4)
            for sprite in range(2) for pixel in range(4)
            for dual in range(2) for repeat in range(2)]


KERNEL = '''
blitter_handoff_trial:
        move.w #$2700,sr
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.w #$2c81,$8e(a6)
        move.w #$f4c1,$90(a6)
        move.w #$0038,$92(a6)
        move.w #$00d0,$94(a6)
        clr.w $102(a6)
        clr.w $104(a6)
        clr.w $108(a6)
        clr.w $10a(a6)
        clr.w $110(a6)
        clr.w $112(a6)
        move.w #$2200,d4
        move.w 4(a4),d0
        andi.w #1,d0
        lsl.w #8,d0
        lsl.w #2,d0
        or.w d0,d4
        move.w d4,$100(a6)
        move.w 2(a4),d5
        andi.w #3,d5
        move.w 2(a4),d0
        lsr.w #2,d0
        lsl.w #6,d0
        or.w d0,d5
        move.w d5,$98(a6)
        moveq #0,d1
        moveq #0,d2
        btst #0,7(a4)
        beq.s .plane1_ready
        moveq #-1,d1
.plane1_ready:
        btst #1,7(a4)
        beq.s .plane2_ready
        moveq #-1,d2
.plane2_ready:
        lea $18000,a0
        lea $19000,a1
        move.w #511,d0
.fill:
        move.w d1,(a0)+
        move.w d2,(a1)+
        dbra d0,.fill
        move.l #$18000,$e0(a6)
        move.l #$19000,$e4(a6)
        ; All other sprites are disabled, no sprite DMA is enabled.
        lea $140(a6),a0
        moveq #7,d0
.clear_sprites:
        clr.w 2(a0)
        clr.w 6(a0)
        clr.w 4(a0)
        adda.w #8,a0
        dbra d0,.clear_sprites
        move.w #$4480,$140(a6)
        move.w #$4500,$142(a6)
        moveq #0,d0
        btst #1,5(a4)
        beq.s .sprite_ready
        moveq #-1,d0
.sprite_ready:
        clr.w $146(a6)
        move.w d0,d6
        jsr sync_beam
        jsr $fb0000
        jsr $ffb000
        move.w d3,12(a4)
        move.w d4,24(a4)
        move.w d5,36(a4)
        rts
'''

OBSERVER = '''        dcb.b $ffb000-*,0
playfield_mode_observer:
        move.w 6(a6),d3
        move.w #$8300,$96(a6)
.wait_clear:
        move.w 6(a6),d0
        cmpi.w #$4420,d0
        bcs.s .wait_clear
        move.w 6(a6),14(a4)
        tst.w $0e(a6)
        move.w d6,$144(a6)
.wait_sample:
        move.w 6(a6),d0
        cmpi.w #$44d0,d0
        bcs.s .wait_sample
        move.w 6(a6),26(a4)
        move.w $0e(a6),d0
        move.w 6(a6),34(a4)
        move.w d0,20(a4)
        move.w $0e(a6),22(a4)
        move.w #$7fff,$96(a6)
        clr.w 32(a4)
        rts
'''


def transform(stage):
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm'
    text=p.read_text();assert text.count('cmpi.w #49,(a4)')==1
    p.write_text(text.replace('cmpi.w #49,(a4)','cmpi.w #101,(a4)'))
    (stage/'src/rom/blitter_handoff_kernel.i').write_text(KERNEL)
    (stage/'src/rom/blitter_handoff_observer.i').write_text(OBSERVER)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    base.build(a.vasm,a.wsl,a.out,rows=trials(),transform=transform,
        profile=dict(kind=101,variants='bit0 DPF; bit1 sprite0 opaque; target mask*4+desired; phase constant plane bits',
            fields={'12':'common input','14':'pre-clear beam','20':'CLXDAT sample','22':'immediate second CLXDAT','24':'BPLCON0 programmed value','26':'pre-read beam','34':'post-read beam','36':'CLXCON programmed value'},
            limitations='Settled two-plane lores, manual sprite0, sprite DMA disabled; mask CLXDAT bits0/1/5 separately. Paired DPF changes only one BPLCON0 bit; no Copper or blitter. No timing alignment.'))
