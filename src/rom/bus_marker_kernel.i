; Kind55: +12/+14 beam brackets, +20..34 four INTREQ/DMACONR pairs.
; +16 settled beam/watchdog, +18 settled INTREQ, +36/+38 D endpoints.
bus_marker_trial:
        movem.l d0-d7/a0-a3,-(sp)
        move.w #$7fff,$96(a6)       ; disable all DMA channels
        move.w #$7fff,$9a(a6)       ; disable all interrupt enables
        move.w #$7fff,$9c(a6)       ; clear pending requests
        move.w #2,$02e(a6)          ; COPCON CDANG: Copper may write BLT regs

        lea $10000,a0
        move.w #$dead,d0
        moveq #15,d1
.clear_d:
        move.w d0,(a0)+
        dbra d1,.clear_d
        move.w #$ffff,$44(a6)       ; BLTAFWM
        move.w #$ffff,$46(a6)       ; BLTALWM
        move.w #0,$60(a6)           ; BLTAMOD
        move.w #0,$62(a6)           ; BLTBMOD
        move.w #0,$64(a6)           ; BLTCMOD
        move.w #0,$66(a6)           ; BLTDMOD
        move.l #$10000,$54(a6)      ; BLTDPTH/L
        move.w #$01ff,$40(a6)       ; D-only minterm $ff, all-one fill
        move.w #0,$42(a6)
        move.w #$0041,d5
        tst.w 2(a4)
        beq.s .size_ready
        move.w #$0050,d5
.size_ready:

        ; Exactly two adjacent Copper MOVE slots after the WAIT.
        lea $6000,a0
        move.w #$4261,(a0)+
        move.w #$fffe,(a0)+
        move.w #$009c,d0
        move.w #$8010,d1
        move.w #$0058,d2
        move.w d5,d3
        btst #3,5(a4)
        beq.s .slots_ready
        move.w #$01fe,d2
        moveq #0,d3
.slots_ready:
        btst #2,5(a4)
        bne.s .marker_after
        move.w d0,(a0)+
        move.w d1,(a0)+
        move.w d2,(a0)+
        move.w d3,(a0)+
        bra.s .list_end
.marker_after:
        move.w d2,(a0)+
        move.w d3,(a0)+
        move.w d0,(a0)+
        move.w d1,(a0)+
.list_end:
        move.l #$fffffffe,(a0)

        move.w #$8240,d0            ; master + blitter DMA
        btst #1,5(a4)
        bne.s .owner_ready
        ori.w #$0080,d0            ; Copper only for Copper-launch cases
.owner_ready:
        btst #0,5(a4)
        beq.s .priority_ready
        ori.w #$0400,d0             ; BLTPRI
.priority_ready:
        move.w d0,d2                ; preserve exact DMA/BLTPRI mask across sync
        ; Use a local, fixed sync instead of sync_beam: sync_beam consumes
        ; descriptor phase as an extra delay, which would confound this sweep.
        move.w #$7fff,d7
.sync_leave64:
        move.w $006(a6),d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        bne.s .sync_line64_start
        dbra d7,.sync_leave64
        bra.w .sync_timeout
.sync_line64_start:
        move.w #$7fff,d7
.sync_line64:
        move.w $006(a6),d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        beq.s .sync_hpos_start
        dbra d7,.sync_line64
        bra.w .sync_timeout
.sync_hpos_start:
        move.w #$7fff,d7
.sync_hpos:
        move.w $006(a6),d0
        andi.w #$00ff,d0
        cmpi.w #$0020,d0
        bcc.s .sync_ready
        dbra d7,.sync_hpos
        bra.w .sync_timeout
.sync_ready:
        move.w #$7fff,$9c(a6)       ; clear stale COPER from earlier beam periods
        move.l #$6000,$80(a6)
        move.w #0,$88(a6)
        move.w d2,$96(a6)           ; start Copper/blitter DMA after line64 sync

        jsr $ffca00
        ; Measurement is over. Wait for marker, then settle all D writes.
        move.w #$7fff,d7
.marker_poll:
        move.w $01e(a6),d0
        btst #4,d0
        bne.s .marker_seen
        dbra d7,.marker_poll
        move.w #$ffff,16(a4)
        bra.s .final_words
.marker_seen:
        move.w #$00ff,d7
.settle:
        nop
        dbra d7,.settle
        move.w 6(a6),16(a4)
        move.w $01e(a6),18(a4)
.final_words:
        lea $10000,a0
        move.w (a0),36(a4)
        tst.w 2(a4)
        beq.s .last_1
        move.w 30(a0),38(a4)
        bra.s .done
.last_1:
        move.w (a0),38(a4)
.done:
        move.w #0,$02e(a6)          ; restore restrictive COPCON
        movem.l (sp)+,d0-d7/a0-a3
        rts
.sync_timeout:
        move.w #$ffff,12(a4)
        move.w #$ffff,14(a4)
        move.w #$ffff,16(a4)
        move.w #$7fff,$96(a6)        ; stop Copper/blitter if sync did not qualify
        move.w #0,$02e(a6)
        bra.s .final_words
