; Kind50 direct BBUSY pilot. IRQs remain masked throughout.
; +12 last VHPOSR poll before sample, +14 VHPOSR after sample train,
; +16 settled VHPOSR, +18 INTREQR after raw-sample result stores,
; +20..+34 one/eight raw DMACONR words, +36/+38 settled D endpoints.
; Target selects 1/8/16 words. Variant bits: BLTPRI, 8-read train,
; no-blit control. Phase selects line-66 gate hpos $10..$60 in $08 steps.
copper_start_busy_trial:
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
        move.w 2(a4),d0
        cmpi.w #0,d0
        beq.s .size_1
        cmpi.w #1,d0
        beq.s .size_8
        move.w #$0050,d5            ; 1 line x 16 words
        bra.s .size_ready
.size_1:
        move.w #$0041,d5            ; 1 line x 1 word
        bra.s .size_ready
.size_8:
        move.w #$0048,d5            ; 1 line x 8 words
.size_ready:

        ; Copper: wait for line 66 h=$60, set D-only controls, launch (or
        ; NOOP control), then a BFD=0 WAIT and a COPER request marker.
        lea $6000,a0
        move.w #$4261,(a0)+
        move.w #$fffe,(a0)+
        move.w #$0040,(a0)+
        move.w #$01ff,(a0)+
        move.w #$0042,(a0)+
        move.w #0,(a0)+
        btst #2,5(a4)
        bne.s .no_blit_slot
        move.w #$0058,(a0)+
        move.w d5,(a0)+
        bra.s .blit_slot_ready
.no_blit_slot:
        move.w #$01fe,(a0)+
        move.w #0,(a0)+
.blit_slot_ready:
        move.w #$4261,(a0)+
        move.w #$7ffe,(a0)+
        move.w #$009c,(a0)+
        move.w #$8010,(a0)+
        move.l #$fffffffe,(a0)

        move.w #$82c0,d0            ; master + Copper + blitter DMA
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

        ; Gate, bracket and DMACONR reads execute from immutable ROM, so
        ; BLTPRI cannot change CPU instruction-fetch progress during sampling.
        jsr $ffc200
        ; INTREQR is sampled by the ROM observer immediately after its record
        ; stores; the BFD marker poll below determines whether the list finished.

        ; BFD WAIT holds the Copper marker until the blit completes. Poll only
        ; INTREQR here; do not contaminate the pre-completion DMACONR samples.
        move.w #$7fff,d7
.marker_poll:
        move.w $01e(a6),d0
        btst #4,d0
        bne.s .marker_seen
        dbra d7,.marker_poll
        move.w #$ffff,16(a4)        ; explicit invalid end-beam sentinel
        bra.s .final_words
.marker_seen:
        move.w #$00ff,d7
.settle:
        nop
        dbra d7,.settle
        move.w 6(a6),16(a4)
.final_words:
        move.l #$10000,a0
        move.w (a0),36(a4)
        move.w 2(a4),d0
        cmpi.w #0,d0
        beq.s .last_1
        cmpi.w #1,d0
        beq.s .last_8
        move.w 30(a0),38(a4)
        bra.s .done
.last_1:
        move.w (a0),38(a4)
        bra.s .done
.last_8:
        move.w 14(a0),38(a4)
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
