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

        include "irq_focus_kernel.i"

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

        dcb.b $fe9000-*,0
line_logic_phase set 0
        rept 2
line_logic_slot set 0
line_logic_delay set 0
        rept 6
        dcb.b $fe9000+line_logic_phase*$1000+line_logic_slot*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifne line_logic_phase
        exg d0,d1
        else
        nop
        endc
        rept line_logic_delay
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
        ifeq line_logic_delay
line_logic_delay set 1
        else
line_logic_delay set line_logic_delay*2
        endc
line_logic_slot set line_logic_slot+1
        endr
line_logic_phase set line_logic_phase+1
        endr

        dcb.b $feb000-*,0
line_logic_fine_phase set 0
        rept 2
line_logic_fine_slot set 0
line_logic_fine_delay set 0
        rept 17
        dcb.b $feb000+line_logic_fine_phase*$2000+line_logic_fine_slot*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifne line_logic_fine_phase
        exg d0,d1
        else
        nop
        endc
        rept line_logic_fine_delay
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
line_logic_fine_delay set line_logic_fine_delay+1
line_logic_fine_slot set line_logic_fine_slot+1
        endr
line_logic_fine_phase set line_logic_fine_phase+1
        endr

; Kind28 gets a private observer so the two line-mode DMA streams are both
; covered. DPT moves to $11050/$110a0 after the first pixel; retain raw ORs
; and samples for DPT=$10000 and CPT=$11000 in unused record words.
        dcb.b $ff0000-*,0
line_pipeline_phase set 0
        rept 2
line_pipeline_slot set 0
line_pipeline_delay set 0
        rept 17
        dcb.b $ff0000+line_pipeline_phase*$2000+line_pipeline_slot*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifne line_pipeline_phase
        exg d0,d1
        else
        nop
        endc
        rept line_pipeline_delay
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
        moveq #0,d2
        lea $11000,a0
        move.w #1023,d0
        or.w (a0)+,d2
        dbra d0,*-2
        move.w d2,34(a4)
        move.w $11000,30(a4)
        move.w $11050,36(a4)
        move.w $110a0,38(a4)
        move.l (sp)+,d2
        move.l (sp)+,d7
        rts
line_pipeline_delay set line_pipeline_delay+1
line_pipeline_slot set line_pipeline_slot+1
        endr
line_pipeline_phase set line_pipeline_phase+1
        endr

; Kind35 keeps the kind28 dual-memory observer and the same aligned sample,
; but replaces every pad word (including the phase word) with one of three
; equal-length, four-cycle CPU instructions. Address = $ff4000 + variant*$1000
; + delay-slot*$100; variant 0/1/2 is NOP/MOVEQ #0,D6/MOVEQ #-1,D6.
line_word_variant set 0
        rept 3
line_word_slot set 0
        rept 5
        dcb.b $ff4000+line_word_variant*$1000+line_word_slot*$100-*,0
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        ifeq line_word_variant
        nop
        else
        ifeq line_word_variant-1
        moveq #0,d6
        else
        moveq #-1,d6
        endc
        endc
line_word_delay set 0
        ifeq line_word_slot-1
line_word_delay set 1
        endc
        ifeq line_word_slot-2
line_word_delay set 2
        endc
        ifeq line_word_slot-3
line_word_delay set 4
        endc
        ifeq line_word_slot-4
line_word_delay set 16
        endc
        rept line_word_delay
        ifeq line_word_variant
        nop
        else
        ifeq line_word_variant-1
        moveq #0,d6
        else
        moveq #-1,d6
        endc
        endc
        endr
        move.w $02(a6),d0
        move.w $06(a6),d1
        move.w d7,12(a4)
        move.w d0,20(a4)
        move.w d1,16(a4)
        bra.w line_word_capture
line_word_slot set line_word_slot+1
        endr
line_word_variant set line_word_variant+1
        endr
        dcb.b $ff6500-*,0
line_word_capture:
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
        moveq #0,d2
        lea $11000,a0
        move.w #1023,d0
        or.w (a0)+,d2
        dbra d0,*-2
        move.w d2,34(a4)
        move.w $11000,30(a4)
        move.w $11050,36(a4)
        move.w $110a0,38(a4)
        move.l (sp)+,d2
        move.l (sp)+,d7
        rts

; Kind37 takes one phase NOP plus 96 delay NOPs before sampling completed
; line blits. The 232-byte body fits its dedicated $ff7000 slot and joins the
; same dual-memory capture as the shorter kind28/35 observers.
        dcb.b $ff7000-*,0
line_wrap_observer:
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),d7
        move.w d5,(a1)
        nop
        rept 96
        nop
        endr
        move.w $02(a6),d0
        move.w $06(a6),d1
        move.w d7,12(a4)
        move.w d0,20(a4)
        move.w d1,16(a4)
        bra.w line_word_capture

; Kind42 reads DMACONR eight times consecutively inside one line blit. The
; launch beam is stored before BLTSIZE; offset 36 is the presample beam, the
; eight raw DMACONR words occupy offsets 20..34, offset 16 is post-read beam,
; and offset 38 is the beam after BBUSY clears. Offset 32 is sample six.
        dcb.b $ff7400-*,0
line_c_read_early:
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),12(a4)
        move.w d5,(a1)
        move.w 6(a6),36(a4)
        move.w $02(a6),d0
        move.w $02(a6),d1
        move.w $02(a6),d2
        move.w $02(a6),d3
        move.w $02(a6),d4
        move.w $02(a6),d5
        move.w $02(a6),d6
        move.w $02(a6),d7
        movem.w d0-d7,20(a4)
        move.w 6(a6),16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.w 6(a6),38(a4)
        move.l (sp)+,d7
        rts

        dcb.b $ff7500-*,0
line_c_read_postbusy:
        move.l d7,-(sp)
        jsr $fb0000
        move.w 6(a6),12(a4)
        move.w d5,(a1)
        btst #6,$02(a6)
        bne.s *-6
        move.w 6(a6),36(a4)
        move.w $02(a6),d0
        move.w $02(a6),d1
        move.w $02(a6),d2
        move.w $02(a6),d3
        move.w $02(a6),d4
        move.w $02(a6),d5
        move.w $02(a6),d6
        move.w $02(a6),d7
        movem.w d0-d7,20(a4)
        move.w 6(a6),16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.w 6(a6),38(a4)
        move.l (sp)+,d7
        rts

; Kind44 starts the line blit after ROM beam alignment. The direct observer
; immediately performs eight DMACONR reads; all beam/result stores follow.
; The poll observer waits for BBUSY to clear before taking the same sequence.
        dcb.b $ff7600-*,0
line_c_activity_direct:
        move.l d7,a0
        jsr $fb0000
        move.w 6(a6),a2
        move.w d5,(a1)
        move.w $02(a6),d0
        move.w $02(a6),d1
        move.w $02(a6),d2
        move.w $02(a6),d3
        move.w $02(a6),d4
        move.w $02(a6),d5
        move.w $02(a6),d6
        move.w $02(a6),d7
        movem.w d0-d7,20(a4)
        move.w a2,12(a4)
        move.w 6(a6),36(a4)
        move.w 6(a6),16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.w 6(a6),38(a4)
        move.l a0,d7
        rts

        dcb.b $ff7700-*,0
line_c_activity_poll:
        move.l d7,a0
        jsr $fb0000
        move.w 6(a6),a2
        move.w d5,(a1)
        btst #6,$02(a6)
        bne.s *-6
        move.w $02(a6),d0
        move.w $02(a6),d1
        move.w $02(a6),d2
        move.w $02(a6),d3
        move.w $02(a6),d4
        move.w $02(a6),d5
        move.w $02(a6),d6
        move.w $02(a6),d7
        movem.w d0-d7,20(a4)
        move.w a2,12(a4)
        move.w 6(a6),36(a4)
        move.w 6(a6),16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.w 6(a6),38(a4)
        move.l a0,d7
        rts

; Kind46 writes D3 to the selected chip/slow address directly after BLTSIZE.
; The following eight CPU reads are adjacent DMACONR accesses; beam/result
; stores and BBUSY polling happen only after the raw sample sequence.
        dcb.b $ff7800-*,0
line_c_bus_data_observer:
        move.l d7,a0
        jsr $fb0000
        move.w 6(a6),a2
        move.w d5,(a1)
        move.w d3,(a3)
        move.w $02(a6),d0
        move.w $02(a6),d1
        move.w $02(a6),d2
        move.w $02(a6),d3
        move.w $02(a6),d4
        move.w $02(a6),d5
        move.w $02(a6),d6
        move.w $02(a6),d7
        movem.w d0-d7,20(a4)
        move.w a2,12(a4)
        move.w 6(a6),36(a4)
        move.w 6(a6),16(a4)
        btst #6,$02(a6)
        bne.s *-6
        move.w 6(a6),38(a4)
        move.w $10000,14(a4)
        move.w $11050,18(a4)
        move.l a0,d7
        rts
