; Kind50 fixed-ROM onset observer. Include at FFC200 in edge_kernel.asm.
; D4 holds the requested hpos threshold; variant bit1 selects one/eight reads.
; The full pre-read VHPOSR is retained in A2, post-read VHPOSR in A3.
copper_start_busy_observer:
        move.w 6(a4),d0
        add.w d0,d0
        lea .gate_table(pc),a0
        move.w 0(a0,d0.w),d4
        btst #1,5(a4)
        bne.s .train_poll_start

        move.w #$7fff,d7
.single_poll:
        move.w $006(a6),d5
        move.w d5,d6
        andi.w #$ff00,d6
        cmpi.w #$4200,d6
        bne.s .single_next
        move.w d5,d6
        andi.w #$00ff,d6
        cmp.w d4,d6
        bcc.s .single_ready
.single_next:
        dbra d7,.single_poll
        bra.w .gate_timeout
.single_ready:
        move.w d5,a2
        move.w $002(a6),d0
        move.w $006(a6),a3
        move.w a2,12(a4)
        move.w a3,14(a4)
        move.w d0,20(a4)
        move.w $01e(a6),18(a4)
        rts

.train_poll_start:
        move.w #$7fff,d7
.train_poll:
        move.w $006(a6),d5
        move.w d5,d6
        andi.w #$ff00,d6
        cmpi.w #$4200,d6
        bne.s .train_next
        move.w d5,d6
        andi.w #$00ff,d6
        cmp.w d4,d6
        bcc.s .train_ready
.train_next:
        dbra d7,.train_poll
        bra.w .gate_timeout
.train_ready:
        move.w d5,a2
        move.w $002(a6),d0
        move.w $002(a6),d1
        move.w $002(a6),d2
        move.w $002(a6),d3
        move.w $002(a6),d4
        move.w $002(a6),d5
        move.w $002(a6),d6
        move.w $002(a6),d7
        move.w $006(a6),a3
        movem.w d0-d7,20(a4)
        move.w a2,12(a4)
        move.w a3,14(a4)
        move.w $01e(a6),18(a4)
        rts

.gate_timeout:
        move.w #$ffff,12(a4)
        move.w #$ffff,14(a4)
        move.w $01e(a6),18(a4)
        rts
.gate_table:
        dc.w $0010,$0018,$0020,$0028,$0030,$0038
        dc.w $0040,$0048,$0050,$0058,$0060
