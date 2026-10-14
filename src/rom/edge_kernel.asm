; SPDX-License-Identifier: MIT
; Fixed-size ROM slots eliminate the post-BLTSIZE jump and chip-RAM writes.
DONE equ 8
EVBEAM equ 0
EVPC equ 4
        org $f90000
edge_index set 0
        rept 48
        dcb.b $f90000+edge_index*$100-*,0
        move.l d7,-(sp)
        move.w 6(a6),d7
        move.w d5,(a1)
        rept edge_index
        nop
        endr
        move.w $02(a6),d0
        move.w $06(a6),d1
        move.w $1e(a6),d2
        move.w $06(a6),d3
        move.w (a0),d4
        move.w $06(a6),d6
        move.w d7,12(a4)
        move.w d0,20(a4)
        move.w d1,16(a4)
        move.w d2,22(a4)
        move.w d3,24(a4)
        move.w d4,34(a4)
        move.w d6,36(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.l (sp)+,d7
        rts
edge_index set edge_index+1
        endr
        dcb.b $f94000-*,0
divu_irq:
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        move.w 6(a6),12(a4)
        move.l d2,d0
        move.w #$2000,sr
        divu.w d3,d0
.after_div:
        moveq #1,d4
.after_marker:
        tst.w DONE(a5)
        beq.s .after_marker
        rts
        dcb.b $f94800-*,0
divs_irq:
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        move.w 6(a6),12(a4)
        move.l d2,d0
        move.w #$2000,sr
        divs.w d3,d0
.after_div:
        moveq #1,d4
.after_marker:
        tst.w DONE(a5)
        beq.s .after_marker
        rts

        dcb.b $fa0000-*,0
single_index set 0
        rept 64
        dcb.b $fa0000+single_index*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        rept single_index
        nop
        endr
        move.w (a0),d0
        move.w $06(a6),d1
        move.w d7,12(a4)
        move.w d0,20(a4)
        move.w d1,16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.l (sp)+,d7
        rts
single_index set single_index+1
        endr
        dcb.b $fb0000-*,0
        include "rom_alignment.i"

        dcb.b $fd0000-*,0
bzero_phase set 0
        rept 2
bzero_delay set 0
        rept 16
        dcb.b $fd0000+bzero_phase*$1000+bzero_delay*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifne bzero_phase
        exg d0,d1
        else
        nop
        endc
        rept bzero_delay
        nop
        endr
        move.w $02(a6),d0
        move.w $06(a6),d1
        move.w d7,12(a4)
        move.w d0,20(a4)
        move.w d1,16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.l (sp)+,d7
        rts
bzero_delay set bzero_delay+1
        endr
bzero_phase set bzero_phase+1
        endr

        dcb.b $fe0000-*,0
irqpath_phase set 0
        rept 2
irqpath_delay set 0
        rept 16
        dcb.b $fe0000+irqpath_phase*$1000+irqpath_delay*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifne irqpath_phase
        exg d0,d1
        else
        nop
        endc
        rept irqpath_delay
        nop
        endr
        ; The interrupt returns to the post-STOP PC. If DONE is still clear,
        ; BNE skips the two-byte BRA; otherwise BRA returns 10 bytes to STOP.
        stop #$2000
        tst.w DONE(a5)
        bne.s *+4
        bra.s *-10
        move.w #$2700,sr
        move.w d7,12(a4)
        move.w 6(a6),16(a4)
        move.w EVBEAM(a5),24(a4)
        moveq #3,d0
        cmpi.w #6,2(a4)
        bne.s *+4
        moveq #1,d0
        move.w d0,26(a4)
        move.l EVPC(a5),28(a4)
        move.w #1,34(a4)
        move.l (sp)+,d7
        rts
irqpath_delay set irqpath_delay+1
        endr
irqpath_phase set irqpath_phase+1
        endr

        dcb.b $fe2000-*,0
irqpath_handler_rom:
        move.w 6(a6),EVBEAM(a5)
        move.l 2(sp),EVPC(a5)
        move.w #$7fff,$9c(a6)
        move.w #1,DONE(a5)
        rte
irqpath_handler_end:

        dcb.b $fe4000-*,0
irqpaths_controller:
        lea irqpath_handler_rom,a0
        lea $18000,a1
        moveq #((irqpath_handler_end-irqpath_handler_rom)/2)-1,d0
.copy_handler:
        move.w (a0)+,(a1)+
        dbra d0,.copy_handler
        move.l #irqpath_handler_rom,d0
        tst.w 4(a4)
        bne.s .handler_selected
        move.l #$18000,d0
.handler_selected:
        move.l d0,$64
        move.l d0,$6c
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$ffff,$72(a6)
        move.w #$ffff,$74(a6)
        clr.w $42(a6)
        clr.w $60(a6)
        clr.w $62(a6)
        clr.w $64(a6)
        clr.w $66(a6)
        move.l #$15000,$50(a6)
        move.l #$16000,$4c(a6)
        move.l #$10000,$54(a6)
        move.l #$10000,$48(a6)
        move.w #$0100,$40(a6)
        lea $15000,a0
        moveq #21,d1
.source: move.w #$ffff,(a0)+
        dbra d1,.source
        move.w #$0056,d5
        move.w 2(a4),d0
        cmpi.w #1,d0
        bne.s .not_copy
        move.w #$09f0,$40(a6)
.not_copy:
        cmpi.w #2,d0
        bne.s .not_fill
        move.w #$09f0,$40(a6)
        move.w #$0012,$42(a6)
        move.l #$1502a,$50(a6)
        move.l #$1002a,$54(a6)
.not_fill:
        cmpi.w #3,d0
        bne.s .not_line
        move.w #$0bca,$40(a6)
        move.w #$0001,$42(a6)
        move.w #-280,$64(a6)
        move.w #120,$62(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$48(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.w #$0582,d5
.not_line:
        move.w 2(a4),d0
        cmpi.w #4,d0
        bcs.s .native
        lea $96(a6),a1
        move.w #$8280,d5
        move.l #$10000,$80(a6)
        move.w #0,$88(a6)
        move.w #$4341,$10000
        move.w #$fffe,$10002
        move.w #$009c,$10004
        move.w #$8040,$10006
        cmpi.w #5,d0
        bne.s .not_coper
        move.w #$8010,$10006
.not_coper:
        cmpi.w #6,d0
        bne.s .copper_end
        move.w #$8004,$10006
.copper_end:
        move.w #$ffff,$10008
        move.w #$fffe,$1000a
        move.w #$8000,$96(a6)
        bra.s .priority
.native:
        lea $58(a6),a1
        move.w #$8240,$96(a6)
.priority:
        btst #2,11(a4)
        beq.s .enable_irq
        move.w #$8400,$96(a6)
        cmpi.w #4,2(a4)
        bcc.s .enable_irq
        move.w #$8640,$96(a6)
.enable_irq:
        move.w #$c040,$9a(a6)
        cmpi.w #5,2(a4)
        bcs.s .target_ready
        move.w #$c010,$9a(a6)
        cmpi.w #6,2(a4)
        bne.s .target_ready
        move.w #$c004,$9a(a6)
.target_ready:
; Match the RAM sync_beam line-64 rendezvous before FB0000 aligns HPOS.
.vleave: move.w 6(a6),d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        beq.s .vleave
.vline: move.w 6(a6),d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        bne.s .vline
        moveq #0,d0
        move.w 6(a4),d0
        andi.w #1,d0
        lsl.w #8,d0
        lsl.w #4,d0
        addi.l #$fe0000,d0
        moveq #0,d1
        move.w 8(a4),d1
        lsl.w #8,d1
        add.l d1,d0
        move.l d0,a2
        jmp (a2)

        dcb.b $fe5000-*,0
bzero_line_phase set 0
        rept 2
bzero_line_delay set 0
        rept 32
        dcb.b $fe5000+bzero_line_phase*$2000+bzero_line_delay*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifne bzero_line_phase
        exg d0,d1
        else
        nop
        endc
        rept bzero_line_delay
        nop
        endr
        move.w $02(a6),d0
        move.w $06(a6),d1
        move.w d7,12(a4)
        move.w d0,20(a4)
        move.w d1,16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.l d2,-(sp)
        moveq #0,d2
        lea $10000,a0
        move.w #1023,d0
        or.w (a0)+,d2
        dbra d0,*-2
        move.w d2,22(a4)
        move.w $10000,24(a4)
        move.w $10050,26(a4)
        move.w $100a0,28(a4)
        move.l (sp)+,d2
        move.l (sp)+,d7
        rts
bzero_line_delay set bzero_line_delay+1
        endr
bzero_line_phase set bzero_line_phase+1
        endr
