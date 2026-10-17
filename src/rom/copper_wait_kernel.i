; Kind47: Copper-launched 16-word blit and Copper COPER marker.
; Record: +12 launch beam, +16 post-settle beam, +20 DMACONR at IRQ,
; +22 first destination word at IRQ, +24 IRQ beam, +26 IRQ level,
; +28 saved PC, +32 completion/watchdog, +34 event count,
; +36/+38 first/last destination words after settling.
copper_wait_trial:
        movem.l d0-d7/a0-a3,-(sp)
        move.l #copper_wait_irq,$6c
        clr.w WATCHDOG(a5)
        clr.w DONE(a5)
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        lea $10000,a0
        move.w #$dead,d0
        moveq #15,d1
.clear_d: move.w d0,(a0)+
        dbra d1,.clear_d
        lea $12000,a0
        move.w #$aaaa,d0
        moveq #15,d1
.fill_a: move.w d0,(a0)+
        dbra d1,.fill_a
        lea $18000,a0
        moveq #0,d0
        move.w #1023,d1
.clear_planes: move.w d0,(a0)+
        dbra d1,.clear_planes
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #0,$60(a6)
        move.w #0,$62(a6)
        move.w #0,$64(a6)
        move.w #0,$66(a6)
        move.l #$12000,$50(a6)
        move.l #$10000,$54(a6)
        move.w #$4200,$dff100
        move.w #$0038,$dff092
        move.w #$00d0,$dff094
        move.w #$2c81,$dff08e
        move.w #$f4c1,$dff090
        move.l #$18000,$dff0e0
        move.l #$18000,$dff0e4
        move.l #$18000,$dff0e8
        move.l #$18000,$dff0ec
        move.w #2,$02e(a6)       ; COPCON CDANG permits Copper BLT register writes
        ; CPU-launch control preloads the same CON0/CON1 values that Copper
        ; writes below; Copper still performs its two MOVE fetches unchanged.
        btst #5,5(a4)
        beq.s .cpu_con_ready
        move.w 2(a4),d0
        andi.w #1,d0
        beq.s .cpu_con_d_only
        move.w #$09f0,$40(a6)
        bra.s .cpu_con1
.cpu_con_d_only:
        move.w #$01ff,$40(a6)
.cpu_con1:
        move.w #$0000,$42(a6)
.cpu_con_ready:
        ; Finish-sweep size is selected before the Copper/beam timing window.
        btst #6,5(a4)
        beq.s .cpu_size_ready
        move.w 2(a4),d0
        andi.w #$000c,d0
        cmpi.w #$0004,d0
        beq.s .cpu_size_4
        cmpi.w #$0008,d0
        beq.s .cpu_size_8
        cmpi.w #$000c,d0
        beq.s .cpu_size_16
        move.w #$0041,d5
        bra.s .cpu_size_ready
.cpu_size_4:
        move.w #$0044,d5
        bra.s .cpu_size_ready
.cpu_size_8:
        move.w #$0048,d5
        bra.s .cpu_size_ready
.cpu_size_16:
        move.w #$0050,d5
.cpu_size_ready:
        ; Copper list starts at $6000. Wait for line 66, then program the
        ; selected blit, pass through one or two eligible WAITs, and raise COPER.
        lea $6000,a0
        btst #5,5(a4)
        beq.s .initial_wait_selected
        ; Finish-sweep gets an earlier entry than the established CPU-launch
        ; control so its COPER marker cannot precede the CPU blit launch.
        btst #6,5(a4)
        beq.s .cpu_launch_initial_wait
        move.w #$4205,(a0)+
        bra.s .initial_wait_ready
.cpu_launch_initial_wait:
        ; Keep the original CPU-launch control's hpos 0x20 entry unchanged.
        move.w #$4221,(a0)+
        bra.s .initial_wait_ready
.initial_wait_selected:
        move.w 8(a4),d0
        add.w d0,d0
        addi.w #$4261,d0
        move.w d0,(a0)+
.initial_wait_ready:
        move.w #$fffe,(a0)+
        move.w 2(a4),d0
        andi.w #1,d0
        beq.s .d_only
        move.w #$09f0,d1
        bra.s .bltcon0
.d_only:
        move.w #$01ff,d1
.bltcon0:
        move.w #$0040,(a0)+
        move.w d1,(a0)+
        move.w #$0042,(a0)+
        move.w #$0000,(a0)+
        ; The control archive can replace the BLTSIZE MOVE with an equal-size
        ; Copper NOOP pair. The list still fetches the same two words.
        btst #5,5(a4)
        bne.s .no_blit
        btst #4,5(a4)
        bne.s .no_blit
        move.w #$0058,(a0)+
        move.w #$0050,(a0)+
        bra.s .blit_slot_ready
.no_blit:
        move.w #$01fe,(a0)+
        move.w #$0000,(a0)+
.blit_slot_ready:
        ; BFD=0: same eligible beam condition, but also wait for BBUSY.
        btst #6,5(a4)
        bne.s .blitter_wait_fixed
        move.w 8(a4),d0
        add.w d0,d0
        addi.w #$4261,d0
        bra.s .blitter_wait_ready
.blitter_wait_fixed:
        move.w #$4261,d0
.blitter_wait_ready:
        move.w d0,(a0)+
        move.w #$7ffe,(a0)+
        move.w 2(a4),d0
        andi.w #2,d0
        beq.s .one_wait
        btst #6,5(a4)
        bne.s .second_wait_fixed
        move.w 8(a4),d0
        add.w d0,d0
        addi.w #$4261,d0
        bra.s .second_wait_ready
.second_wait_fixed:
        move.w #$4261,d0
.second_wait_ready:
        move.w d0,(a0)+
        move.w #$7ffe,(a0)+
.one_wait:
        move.w #$009c,(a0)+
        move.w #$8010,(a0)+
        move.l #$fffffffe,(a0)
        ; BLTPRI is a DMACON bit. The high-priority case keeps the same
        ; operand and instruction sequence and changes only this control bit.
        move.w #$82c0,d0
        btst #0,5(a4)
        beq.s .priority_ready
        ori.w #$0400,d0
.priority_ready:
        btst #2,5(a4)
        beq.s .dma_ready
        ori.w #$0100,d0
.dma_ready:
        move.w d0,$96(a6)
        move.w #$c030,$9a(a6)
        lea $58(a6),a1
        jsr sync_beam
        move.w 6(a6),12(a4)
        move.l #$6000,$80(a6)
        move.w #0,$88(a6)
        ; The conditional path explicitly executes NOP or EXG before the loop.
        btst #6,5(a4)
        bne.s .phase_ready
        tst.w 6(a4)
        beq.s .phase_nop
        exg d0,d1
        bra.s .phase_ready
.phase_nop:
        nop
.phase_ready:
        move.w 4(a4),d3
        andi.w #$006a,d3         ; retain unrolled/read and CPU-launch mode bits
        move.w #$01ff,d7
        move.w #$7fff,$9c(a6)    ; discard prior VERTB/other requests before unmasking
        move.w #$2000,sr
        jsr $ff7900
        move.w #$2700,sr
        btst #6,5(a4)
        beq.s .cpu_timestamp_ready
        move.w d2,14(a4)          ; store sampled beam only after IRQs are masked
.cpu_timestamp_ready:
        tst.w DONE(a5)
        beq.s .wait_event
        bra.s .after_event
.wait_event:
        stop #$2000
        tst.w DONE(a5)
        beq.s .wait_event
.after_event:
        move.w #$2700,sr
        move.w #$00ff,d0
.settle:
        nop
        dbra d0,.settle
        move.w 6(a6),16(a4)
        tst.w DONE(a5)
        bmi.s .timed_out
        clr.w 32(a4)              ; standard status 0 means successful capture
        bra.s .status_ready
.timed_out:
        move.w #1,32(a4)          ; standard status 1 means watchdog timeout
.status_ready:
        move.l #$10000,a0
        move.w (a0),36(a4)
        btst #6,5(a4)
        beq.s .last_word_default
        move.w 2(a4),d0
        andi.w #$000c,d0
        cmpi.w #$0004,d0
        beq.s .last_word_4
        cmpi.w #$0008,d0
        beq.s .last_word_8
        cmpi.w #$000c,d0
        beq.s .last_word_16
        move.w (a0),38(a4)
        bra.s .last_word_ready
.last_word_4:
        move.w 6(a0),38(a4)
        bra.s .last_word_ready
.last_word_8:
        move.w 14(a0),38(a4)
        bra.s .last_word_ready
.last_word_16:
        move.w 30(a0),38(a4)
        bra.s .last_word_ready
.last_word_default:
        move.w 30(a0),38(a4)
.last_word_ready:
        move.l #irq3,$6c
        move.w #0,$02e(a6)
        movem.l (sp)+,d0-d7/a0-a3
        rts


copper_wait_irq:
        move.w 6(a6),EVBEAM2(a5)  ; capture beam before touching CPU registers
        move.l 2(sp),EVPC(a5)     ; save exception PC before pushing registers
        movem.l d0-d1/a0,-(sp)
        move.w $01e(a6),d0        ; INTREQR
        btst #4,d0
        beq.s .watchdog
        move.w EVBEAM2(a5),24(a4)
        move.w #3,26(a4)
        move.w $002(a6),20(a4)    ; DMACONR
        move.w $10000,22(a4)      ; first destination word at the IRQ
        move.l EVPC(a5),28(a4)
        addq.w #1,34(a4)
        move.w #$0010,$9c(a6)
        move.w #$0010,$9a(a6)
        move.w #1,DONE(a5)
        bra.s .irq_exit
.watchdog:
        move.w #$0020,$9c(a6)
        addq.w #1,WATCHDOG(a5)
        cmpi.w #3,WATCHDOG(a5)
        bcs.s .irq_exit
        move.w #-1,DONE(a5)
.irq_exit:
        movem.l (sp)+,d0-d1/a0
        rte
