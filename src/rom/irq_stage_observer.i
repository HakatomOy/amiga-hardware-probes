; SPDX-License-Identifier: MIT
; Addresses fixed independently of variable trial payload size.
ISBEAM equ 0
ISLEVEL equ 2
ISPC equ 4
ISCOUNT equ 10
ISLOOP equ 20
ISPTR equ 22
ISICR equ 26
irq_stage_observer:
        cmpi.w #4,2(a4)
        beq.s .masked
        move.w 18(a5),d0
        ori.w #$c004,d0
        move.w d0,$9a(a6)
.masked:
        cmpi.w #0,4(a4)
        bne.s .not_a
        move.b #$81,$bfed01
.not_a:
        cmpi.w #2,4(a4)
        bne.s .phase
        move.b #$81,$bfdd00
.phase:
        btst #0,7(a4)
        beq.s .p2
        nop
.p2:
        btst #1,7(a4)
        beq.s .release
        exg d0,d1
.release:
        move.w #$8280,$96(a6)
        move.w #0,$88(a6)
        move.w 6(a6),12(a4)
        cmpi.w #0,4(a4)
        bne.s .release_b
        move.b #$19,$bfee01
        bra.s .released
.release_b:
        cmpi.w #2,4(a4)
        bne.s .dummy
        move.b #$19,$bfde00
        bra.s .released
.dummy:
        move.w #0,$1fe(a6)
.released:
        move.w 6(a6),14(a4)
        moveq #127,d1
        moveq #$5a,d0
        cmpi.w #4,2(a4)
        beq .raw
        move.w #$2000,sr
        cmpi.w #2,2(a4)
        beq .stop
        cmpi.w #3,2(a4)
        beq .tst
        cmpi.w #1,2(a4)
        beq .store
        bra .nop
        dcb.b $ffcc00-*,0
.nop:
        nop
        dbra d1,.nop
        bra .done
        dcb.b $ffcd00-*,0
.store:
        move.b d0,-(a1)
        dbra d1,.store
        bra .done
        dcb.b $ffce00-*,0
.tst:
        tst.w (a1)
        dbra d1,.tst
        bra .done
        dcb.b $ffcf00-*,0
.stop:
        stop #$2000
        bra .done
        dcb.b $ffd000-*,0
.raw:
        rept 48
        nop
        endr
        move.w 6(a6),d4
        move.w $1e(a6),d0
        move.w 6(a6),d5
        move.w $1e(a6),d3
        move.w 6(a6),d6
        move.w $1e(a6),d7
        move.w 6(a6),d2
        move.w d0,20(a4)
        move.w d3,22(a4)
        move.w d7,24(a4)
        move.w d4,26(a4)
        move.w d5,28(a4)
        move.w d6,30(a4)
        move.w d2,34(a4)
        rept 128
        nop
        endr
        move.w $1e(a6),36(a4)
        move.w 18(a5),38(a4)
.done:
        move.w #$2700,sr
        rts

        dcb.b $ffd900-*,0
irq_stage_level1:
        move.w 6(a6),ISBEAM(a5)
        move.l 2(sp),ISPC(a5)
        move.w d1,ISLOOP(a5)
        move.w a1,ISPTR(a5)
        move.w #1,ISLEVEL(a5)
        addq.w #1,ISCOUNT(a5)
        move.l d0,-(sp)
        moveq #0,d0
        move.w d0,ISICR(a5)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.l (sp)+,d0
        rte

        dcb.b $ffd940-*,0
irq_stage_level2:
        move.w 6(a6),ISBEAM(a5)
        move.l 2(sp),ISPC(a5)
        move.w d1,ISLOOP(a5)
        move.w a1,ISPTR(a5)
        move.w #2,ISLEVEL(a5)
        addq.w #1,ISCOUNT(a5)
        move.l d0,-(sp)
        moveq #0,d0
        move.b $bfed01,d0
        move.w d0,ISICR(a5)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.l (sp)+,d0
        rte

        dcb.b $ffd980-*,0
irq_stage_level3:
        move.w 6(a6),ISBEAM(a5)
        move.l 2(sp),ISPC(a5)
        move.w d1,ISLOOP(a5)
        move.w a1,ISPTR(a5)
        move.w #3,ISLEVEL(a5)
        addq.w #1,ISCOUNT(a5)
        move.l d0,-(sp)
        moveq #0,d0
        move.w d0,ISICR(a5)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.l (sp)+,d0
        rte

        dcb.b $ffd9c0-*,0
irq_stage_level6:
        move.w 6(a6),ISBEAM(a5)
        move.l 2(sp),ISPC(a5)
        move.w d1,ISLOOP(a5)
        move.w a1,ISPTR(a5)
        move.w #6,ISLEVEL(a5)
        addq.w #1,ISCOUNT(a5)
        move.l d0,-(sp)
        moveq #0,d0
        move.b $bfdd00,d0
        move.w d0,ISICR(a5)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.l (sp)+,d0
        rte
