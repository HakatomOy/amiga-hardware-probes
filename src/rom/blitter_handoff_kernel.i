; Kind49 setup. Called with A4=result record, A5=VARS, A6=CUSTOM.
; D7 (outer descriptor count), A3 (descriptor stream), and A4/A5/A6 survive.
; Source: Toni Wilen's EAB post #1422393 notes that control registers can be
; changed after BBUSY clears while a final D write may still be pending.
blitter_handoff_trial:
        move.w #$2700,sr
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$9c(a6)
        clr.w $42(a6)
        clr.w $70(a6)
        clr.w $72(a6)
        clr.w $74(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        clr.w $60(a6)
        clr.w $62(a6)
        clr.w $64(a6)
        clr.w $66(a6)
        move.l #$12000,$50(a6)
        move.l #$14000,$4c(a6)
        move.l #$16000,$48(a6)
        move.l #$10000,$54(a6)
        lea $12000,a0
        move.w #15,d0
.fill_a: move.w #$aaaa,(a0)+
        dbra d0,.fill_a
        lea $14000,a0
        move.w #15,d0
.fill_b: move.w #$ffff,(a0)+
        dbra d0,.fill_b
        lea $16000,a0
        move.w #15,d0
.fill_c: move.w #$5555,(a0)+
        dbra d0,.fill_c
        lea $10000,a0
        moveq #15,d0
.clear_d: clr.w (a0)+
        dbra d0,.clear_d
        lea $18000,a0
        move.w #8191,d0                 ; zero the full display-fetch footprint
.clear_plane: clr.w (a0)+
        dbra d0,.clear_plane
        move.l #$18000,$e0(a6)
        move.l #$18000,$e4(a6)
        move.l #$18000,$e8(a6)
        move.l #$18000,$ec(a6)
        move.l #$18000,$f0(a6)
        move.l #$18000,$f4(a6)
        move.w #$2c81,$8e(a6)
        move.w #$f4c1,$90(a6)
        move.w #$0038,$92(a6)
        move.w #$00d0,$94(a6)
        move.w #$0200,$100(a6)          ; color on, no bitplanes in DMA mode 0
        clr.w $108(a6)
        clr.w $10a(a6)

        ; Select the BLTCON0 truth table by target channel mode.
        move.w 2(a4),d0
        cmpi.w #3,d0
        bcs.s .d_only
        cmpi.w #6,d0
        bcs.s .ad_only
        move.w #$0fff,d4
        bra.s .control_ready
.d_only:
        move.w #$01ff,d4
        bra.s .control_ready
.ad_only:
        move.w #$09f0,d4
.control_ready:
        move.w d4,$40(a6)
        clr.w $42(a6)

        ; Compute BLTSIZE (height one) and early-read destination before the
        ; ROM alignment path. Target remainder is the width index.
        moveq #0,d2                    ; DIVU needs a clear high word
        move.w 2(a4),d2
        divu.w #3,d2
        swap d2
        andi.w #3,d2
        move.w #$0041,d5
        movea.l #$10000,a0
        tst.w d2
        beq.s .width_ready
        move.w #$0042,d5
        cmpi.w #1,d2
        bne.s .sixteen_words
        addq.l #2,a0
        bra.s .width_ready
.sixteen_words:
        move.w #$0050,d5
        adda.w #30,a0
.width_ready:

        ; Descriptor variant bit 0 is BLTPRI; bits 2:1 select extra DMA.
        move.w 4(a4),d0
        move.w d0,d1
        lsr.w #1,d1
        andi.w #3,d1
        ; In DMA mode 3, restart a ready, finite Copper NOOP list immediately
        ; before the blit; a frame-position WAIT could be stale by launch time.
        cmpi.w #3,d1
        bne.w .no_copper_list
        lea $6000,a1
        rept 32
        move.w #$01fe,(a1)+              ; bounded Copper NOOP burst
        clr.w (a1)+
        endr
        move.w #$ffff,(a1)+
        move.w #$fffe,(a1)+
        move.l #$6000,$80(a6)
.no_copper_list:
        move.w #$8240,d6                ; SET, master DMA and blitter DMA
        btst #0,d0
        beq.s .normal_priority
        ori.w #$0400,d6
.normal_priority:
        cmpi.w #1,d1
        bcs.s .planes_ready
        ori.w #$0100,d6                ; BPLEN
        move.w #$4200,$100(a6)          ; four planes for DMA modes 1 and 2+
        cmpi.w #2,d1
        bcs.s .planes_ready
        move.w #$6200,$100(a6)          ; six planes for DMA modes 2 and 3
.planes_ready:
        ; COPEN is enabled by the observer immediately before BLTSIZE.
        move.w d6,$96(a6)

        ; Align in ROM, then apply phase and the 0..7 NOP launch padding.
        jsr sync_beam
        jsr $fb0000
        move.w 6(a4),d0
        btst #0,d0
        beq.s .phase_done
        exg d0,d1
.phase_done:
        move.w 8(a4),d0
        andi.w #7,d0
        add.w d0,d0
        lea .pad_end(pc),a1
        suba.w d0,a1
        jmp (a1)
        rept 7
        nop
        endr
.pad_end:
        jsr $ffb000
        move.w #$7fff,$96(a6)          ; stop DMA after observer settles
        rts
