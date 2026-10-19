; Kind63. Serial flag completion, qualified by Timer-B cascade counts.
cia_serial_buffer_trial:
        movem.l d0-d7/a0-a3,-(sp)
        move.w #$2700,sr
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        lea $bfe001,a0
        tst.w 2(a4)
        beq.s .selected
        lea $bfd000,a0
.selected:
        move.b #$7f,$d00(a0)
        move.b #$40,$e00(a0)
        move.b #$40,$f00(a0)
        move.b #1,$400(a0)
        clr.b $500(a0)
        clr.b $c00(a0)
        move.b #$51,$e00(a0)
        move.w #511,d0
.drain: dbra d0,.drain
        move.b #$40,$e00(a0)
        rept 32
        nop
        endr
        tst.b $d00(a0)
        move.w 6(a4),d0
        lsl.w #4,d0
        addi.w #15,d0
        move.b d0,$400(a0)
        clr.b $500(a0)
        move.b #$ff,$600(a0)
        move.b #$ff,$700(a0)
        move.b #$51,$f00(a0)
        rept 12
        nop
        endr
        move.b #$a5,$c00(a0)
        moveq #0,d0
        move.b $d00(a0),d0
        andi.w #8,d0
        move.w d0,32(a4)
        move.w #$ffff,12(a4)
        move.w #$ffff,14(a4)
        move.w #$ffff,16(a4)
        move.w #$ffff,18(a4)
        move.b #$51,$e00(a0)
        move.w 4(a4),d0
        beq.s .first
        cmpi.w #3,d0
        beq.s .first
        moveq #4,d1
        bsr.w .wait_uf
        bsr.w .read_uf
        move.w d0,d4
        move.b #$5a,$c00(a0)
        bsr.w .read_uf
        move.w d4,12(a4)
        move.w d0,14(a4)
        cmpi.w #2,4(a4)
        bne.s .first
        moveq #8,d1
        bsr.w .wait_uf
        bsr.w .read_uf
        move.w d0,d4
        move.b #$3c,$c00(a0)
        bsr.w .read_uf
        move.w d4,16(a4)
        move.w d0,18(a4)
.first:
        moveq #18,d1
        bsr.w .snapshot
        move.w d3,20(a4)
        move.w d4,26(a4)
        move.w d0,28(a4)
        cmpi.w #3,4(a4)
        bne.s .second
        moveq #20,d1
        bsr.w .wait_uf
        bsr.w .read_uf
        move.w d0,d4
        move.b #$5a,$c00(a0)
        bsr.w .read_uf
        move.w d4,12(a4)
        move.w d0,14(a4)
.second:
        move.w 8(a4),d1
        bsr.w .snapshot
        move.w d3,22(a4)
        move.w d4,30(a4)
        move.w d0,34(a4)
        moveq #56,d1
        bsr.w .snapshot
        move.w d3,24(a4)
        move.w d4,36(a4)
        move.w d0,38(a4)
        move.b #$40,$e00(a0)
        move.b #$40,$f00(a0)
        tst.b $d00(a0)
        movem.l (sp)+,d0-d7/a0-a3
        rts
.snapshot:
        bsr.s .wait_uf
        bsr.s .read_uf
        move.w d0,d4
        moveq #0,d3
        move.b $d00(a0),d3
        bra.s .read_uf
.wait_uf:
        move.w #2047,d2
.wait:
        moveq #0,d0
        move.b $600(a0),d0
        not.b d0
        cmp.w d1,d0
        bcc.s .ready
        dbra d2,.wait
        move.w #1,32(a4)
.ready:
        rts
.read_uf:
        moveq #0,d0
        move.b $600(a0),d0
        not.b d0
        rts
