; Kind49 critical observer. BLTEN deliberately stays active after BLTCON0=0 so
; the blitter may retire an already-pending final D write. Software samples are
; observations of register/memory visibility, not timestamps of the chip event.
        dcb.b $ffb000-*,0
blitter_handoff_observer:
        move.w 6(a6),12(a4)             ; launch VHPOSR
        move.w 4(a4),d3
        andi.w #6,d3
        cmpi.w #6,d3
        bne.s .copper_not_started
        move.w #0,$88(a6)               ; point Copper at the prepared NOOP list
        move.w #$8080,$96(a6)           ; enable COPEN immediately before launch
.copper_not_started:
        move.w d5,$58(a6)               ; BLTSIZE starts the one-line blit
        move.w #4095,d3                ; bounded BBUSY poll, about 4096 samples
.wait_busy:
        move.w $02(a6),d0               ; DMACONR, BBUSY bit 14
        btst #14,d0
        beq.s .first_clear
        dbra d3,.wait_busy
        move.w #1,32(a4)                ; bounded poll timed out
        bra.w .capture_timeout
.first_clear:
        move.w (a0),d2                  ; immediately read final D word
        move.w #0,$40(a6)               ; next register update: BLTCON0=0 (D off)
        move.w d0,14(a4)                ; store first clear sample after the write
        move.w d2,16(a4)
        move.w $02(a6),18(a4)           ; first post-write DMACONR
        move.w 6(a6),20(a4)             ; beam observed just after the write
        move.w 6(a6),22(a4)             ; post-write beam sample
        rept 256
        nop
        endr
        move.w $10000,24(a4)
        move.w (a0),26(a4)              ; same last destination sampled at first clear
        move.w $1e(a6),28(a4)           ; INTREQR, including BLIT request
        move.w 6(a6),30(a4)             ; settled beam
        clr.w 32(a4)                    ; completed
        rts
.capture_timeout:
        move.w d0,14(a4)
        move.w 6(a6),22(a4)
        move.w $10000,24(a4)
        move.w (a0),26(a4)
        move.w $1e(a6),28(a4)
        move.w 6(a6),30(a4)
        rts
