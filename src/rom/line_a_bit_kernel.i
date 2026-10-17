; Kind48 line-mode BZERO witness: one-hot BLTADAT crosses ASHIFT 0/2/4,
; BLTBDAT 0/ffff, and one/two pixels with USEB off and C zero. The observer
; intentionally writes D3=0 to scratch at $18000 between launch and its eight
; adjacent DMACONR reads, matching the kind46 FF7800 observation sequence.
line_a_bit_trial:
        btst #7,5(a4)
        bne.w line_a_bit_line_hold_trial
        btst #6,5(a4)
        bne.w line_a_bit_history_trial
        btst #5,5(a4)
        bne.w line_a_bit_history_trial
        btst #4,5(a4)
        bne.w line_a_bit_truth_trial
        move.l a3,-(sp)
        move.l d7,-(sp)
        move.w 6(a4),-(sp)
        clr.w 6(a4)
        move.w #$7fff,$96(a6)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.line_a_clear_d: move.w d0,(a0)+
        dbra d7,.line_a_clear_d
        lea $12000,a0
        move.w #15,d7
.line_a_clear_a: move.w d0,(a0)+
        dbra d7,.line_a_clear_a
        lea $16000,a0
        move.w #15,d7
.line_a_clear_b: move.w d0,(a0)+
        dbra d7,.line_a_clear_b
        lea $11000,a0
        move.w #81,d7
.line_a_clear_c: move.w d0,(a0)+
        dbra d7,.line_a_clear_c
        move.w d0,$11050
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$8000,$74(a6)
        move.w #0,$70(a6)
        move.w #0,$72(a6)
        move.w #-280,$64(a6)
        clr.w $62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w 2(a4),d0
        moveq #0,d1
        move.w #$8000,d1
        lsr.w d0,d1
        move.w d1,$74(a6)
        move.w 4(a4),d2
        move.w d2,d0
        andi.w #3,d0
        lsl.w #1,d0
        lsl.w #8,d0
        lsl.w #4,d0
        ori.w #$0bca,d0
        move.w d0,$40(a6)
        btst #2,d2
        beq.s .line_a_bdat_zero
        move.w #$ffff,$72(a6)
        bra.s .line_a_bdat_ready
.line_a_bdat_zero:
        clr.w $72(a6)
.line_a_bdat_ready:
        move.w #$0001,$42(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        lea $58(a6),a1
        move.w #$0042,d5
        btst #3,d2
        beq.s .line_a_size_ready
        move.w #$0082,d5
.line_a_size_ready:
        jsr sync_beam
        move.w 4(a4),d0
        add.w d0,d0
        lea line_a_bit_observer_values(pc),a2
        adda.w d0,a2
        move.w (a2),d3
        move.w 8(a4),d0
        lsl.w #2,d0
        lea line_a_bit_scratch_regions(pc),a3
        adda.w d0,a3
        movea.l (a3),a3
        movea.l #$ff7800,a2
        jsr (a2)
        move.w (sp)+,6(a4)
        move.l (sp)+,d7
        move.l (sp)+,a3
        rts

; Truth-control extension, selected by variant bit 4. The existing kind48
; variant range and instruction path above remain unchanged. Phase temporarily
; carries BSHIFT, but is cleared for both beam-alignment stages and restored
; after the unchanged FF7800 observer call.
line_a_bit_truth_trial:
        move.l a3,-(sp)
        move.l d7,-(sp)
        move.w 6(a4),-(sp)
        clr.w 6(a4)
        move.w #$7fff,$96(a6)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
line_a_truth_clear_d:
        move.w d0,(a0)+
        dbra d7,line_a_truth_clear_d
        lea $12000,a0
        move.w #15,d7
line_a_truth_clear_a:
        move.w d0,(a0)+
        dbra d7,line_a_truth_clear_a
        lea $16000,a0
        move.w #15,d7
line_a_truth_clear_b:
        move.w d0,(a0)+
        dbra d7,line_a_truth_clear_b
        lea $11000,a0
        move.w #81,d7
line_a_truth_clear_c:
        move.w d0,(a0)+
        dbra d7,line_a_truth_clear_c
        move.w d0,$11050
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$7fff,$96(a6)
        move.w #0,$70(a6)
        move.w #0,$72(a6)
        move.w #-280,$64(a6)
        clr.w $62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)

        ; Pattern-index target selects the eight measured ADAT words.
        move.w #$8000,$74(a6)
        move.w 2(a4),d0
        add.w d0,d0
        lea line_a_truth_patterns(pc),a0
        adda.w d0,a0
        move.w (a0),$74(a6)
        ; Variant low bits index the literal minterm list. Preserve A/C/D
        ; channel enables from $0b00; USEB stays off.
        move.w 4(a4),d2
        andi.w #7,d2
        add.w d2,d2
        lea line_a_truth_minterms(pc),a0
        adda.w d2,a0
        move.w (a0),d0
        ori.w #$0b00,d0
        move.w d0,$40(a6)
        btst #3,5(a4)
        beq.s .truth_b_zero
        move.w #$ffff,$72(a6)
        bra.s .truth_b_ready
.truth_b_zero:
        clr.w $72(a6)
.truth_b_ready:
        ; Match legacy register history: seed/write ADAT, then BDAT, then the
        ; final BLTCON1 value. Build BSHIFT with legal 68000 immediate shifts.
        move.w (sp),d0
        lsl.w #8,d0
        lsl.w #4,d0
        ori.w #$0001,d0
        move.w d0,$42(a6)
        move.w #$8240,$96(a6)
        lea $58(a6),a1
        move.w #$0082,d5
        jsr sync_beam
        moveq #0,d3
        movea.l #$18000,a3
        movea.l #$ff7800,a2
        jsr (a2)
        move.w (sp)+,6(a4)
        move.l (sp)+,d7
        move.l (sp)+,a3
        rts

; Retained-B history control, selected by variant bits 5+4. Phase selects
; one of seven B-state preconditions and is cleared while beam alignment runs.
; Target BSHIFT is always zero. Prime source words at $18000/$18002 are separate
; from C data; FF7800 writes the $18000 scratch only after target BLTSIZE.
line_a_bit_history_trial:
        move.l a3,-(sp)
        move.l d7,-(sp)
        move.w 6(a4),-(sp)
        clr.w 6(a4)
        move.w #$7fff,$96(a6)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.history_clear_d:
        move.w d0,(a0)+
        dbra d7,.history_clear_d
        lea $12000,a0
        move.w #15,d7
.history_clear_a:
        move.w d0,(a0)+
        dbra d7,.history_clear_a
        lea $16000,a0
        move.w #15,d7
.history_clear_b:
        move.w d0,(a0)+
        dbra d7,.history_clear_b
        lea $11000,a0
        move.w #81,d7
.history_clear_c:
        move.w d0,(a0)+
        dbra d7,.history_clear_c
        move.w d0,$11050
        move.w #$2800,$18000
        move.w #$d7ff,$18002
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        ; Establish the same initial B register value before each prime mode.
        move.w #0,$42(a6)           ; inert normal-mode BSHIFT before BLTBDAT seed
        move.w #0,$72(a6)
        move.l #$11000,$48(a6)
        move.l #$18000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #80,$60(a6)
        move.w #0,$62(a6)
        move.w #-280,$64(a6)
        move.w #80,$66(a6)

        move.w (sp),d4
        cmpi.w #1,d4
        beq.w .history_cpu_2800
        cmpi.w #2,d4
        beq.w .history_cpu_d7ff
        cmpi.w #7,d4
        beq.w .history_no_dma_2800
        cmpi.w #8,d4
        beq.w .history_no_dma_d7ff
        cmpi.w #3,d4
        blo.w .history_prime_settle
        ; Profiles 3/5 fetch $2800 then $d7ff; 4/6 reverse the pair.
        cmpi.w #4,d4
        beq.s .history_reverse_pair
        cmpi.w #6,d4
        bne.s .history_pair_ready
.history_reverse_pair:
        move.w #$d7ff,$18000
        move.w #$2800,$18002
.history_pair_ready:
        move.w #$04cc,$40(a6)       ; B only; A/C/D disabled
        move.l #$18000,$4c(a6)
        cmpi.w #5,d4
        bhs.s .history_line_prime
        move.w #0,$42(a6)           ; normal mode
        move.w #0,$62(a6)           ; BMOD=0
        move.w #$8240,$96(a6)
        move.w #$0042,$58(a6)       ; two normal-mode B words
        bra.s .history_prime_busy
.history_line_prime:
        move.w #1,$42(a6)           ; line mode, BSHIFT=0
        move.w #2,$62(a6)           ; BMOD=2
        move.l #-80,$50(a6)         ; APT for line algorithm, A DMA disabled
        move.w #-280,$64(a6)        ; AMOD for line algorithm
        move.w #80,$60(a6)          ; CMOD for line algorithm, C DMA disabled
        move.w #80,$66(a6)          ; DMOD for line algorithm, D DMA disabled
        move.w #$8240,$96(a6)
        move.w #$0082,$58(a6)       ; two line-mode pixels
.history_prime_busy:
        btst #6,$02(a6)
        bne.s .history_prime_busy
        bra.s .history_prime_settle
.history_cpu_2800:
        move.w #$2800,$72(a6)
        bra.s .history_prime_settle
.history_cpu_d7ff:
        move.w #$d7ff,$72(a6)
        bra.s .history_prime_settle
.history_no_dma_2800:
        move.w #0,$42(a6)           ; normal mode before loading raw BLTBDAT
        move.w #$2800,$72(a6)
        bra.s .history_no_dma_line_start
.history_no_dma_d7ff:
        move.w #0,$42(a6)           ; normal mode before loading raw BLTBDAT
        move.w #$d7ff,$72(a6)
.history_no_dma_line_start:
        move.w #1,$42(a6)           ; line mode, BSHIFT=0
        move.w #$00cc,$40(a6)       ; all DMA channels disabled
        move.w #$8240,$96(a6)
        move.w #$0082,$58(a6)       ; two pixels; no source fetches
        bra.w .history_prime_busy
.history_prime_settle:
        rept 16
        nop
        endr

        btst #6,5(a4)
        bne.w .history_normal_target
        ; Reinitialize the target inputs and line geometry without disturbing
        ; the primed B shifter/BDAT. A/C/D setup is common to every prime arm.
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #0,$70(a6)
        move.w #$8000,$74(a6)       ; seed ADAT as in the truth-control history
        move.w 2(a4),d0
        add.w d0,d0
        lea line_a_truth_patterns(pc),a0
        adda.w d0,a0
        move.w (a0),$74(a6)
        move.w 4(a4),d2
        andi.w #3,d2
        add.w d2,d2
        lea line_a_history_minterms(pc),a0
        move.w (a0,d2.w),d0
        ori.w #$0b00,d0             ; A/C/D enabled; B DMA remains off
        move.w d0,$40(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)       ; restore target B pointer after DMA prime
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #0,$62(a6)           ; restore target BMOD after line-mode prime
        move.w #-280,$64(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        bra.s .history_target_bdat_order

.history_normal_target:
        ; One-word normal-mode B-to-D hold control; only D DMA is enabled.
        move.w #$01cc,$40(a6)
        move.w #0,$62(a6)           ; BMOD=0
        move.l #$16000,$4c(a6)      ; restore B pointer after DMA prime
        move.l #$10000,$54(a6)
        move.w #0,$66(a6)           ; DMOD=0

        ; Order 0 writes target BDAT before CON1, order 1 after, order 2 skips.
.history_target_bdat_order:
        move.w 4(a4),d2
        lsr.w #2,d2
        andi.w #3,d2
        cmpi.w #0,d2
        bne.s .history_con1_first
        move.w #0,$72(a6)
.history_con1_first:
        btst #6,5(a4)
        bne.s .history_normal_con1
        move.w #1,$42(a6)           ; target BSHIFT=0 regardless of prime phase
        bra.s .history_con1_ready
.history_normal_con1:
        move.w #0,$42(a6)           ; normal-mode target
.history_con1_ready:
        cmpi.w #1,d2
        bne.s .history_order_ready
        move.w #0,$72(a6)
.history_order_ready:
        move.w #$0082,d5            ; line-history target: two pixels
        btst #6,5(a4)
        beq.s .history_size_ready
        move.w #$0041,d5            ; normal-history target: one D word
.history_size_ready:
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        lea $58(a6),a1
        jsr sync_beam
        moveq #0,d3
        movea.l #$18000,a3
        movea.l #$ff7800,a2
        jsr (a2)
        move.w (sp)+,6(a4)
        move.l (sp)+,d7
        move.l (sp)+,a3
        rts

; Held-B shifter validation, selected by variant bit 7. Load raw BLTBDAT in
; normal mode, then clock the line shifter with every DMA channel disabled.
; The following normal one-word B-to-D target tests raw-pattern/BSHIFT/length
; combinations and the same three BLTBDAT/CON1 write orders.
line_a_bit_line_hold_trial:
        move.l a3,-(sp)
        move.l d7,-(sp)
        move.w 6(a4),-(sp)
        clr.w 6(a4)
        move.w #$7fff,$96(a6)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.hold_clear_d:
        move.w d0,(a0)+
        dbra d7,.hold_clear_d
        move.w d0,$11050

        ; The E0..EB cohort enables only C DMA during the line prime. Use a
        ; separate zero buffer at $14000; it is outside the payload at $20000,
        ; observer scratch at $18000, and the existing source/destination areas.
        btst #4,5(a4)
        bne.s .hold_c_buffer_ready
        lea $14000,a0
        move.w #127,d7              ; 128 words / 256 bytes for line stepping
.hold_clear_c:
        move.w d0,(a0)+
        dbra d7,.hold_clear_c
.hold_c_buffer_ready:

        ; Raw B word is loaded under normal CON1 before the line BSHIFT is set.
        move.w #0,$42(a6)
        move.w 2(a4),d0
        add.w d0,d0
        lea line_a_hold_b_patterns(pc),a0
        adda.w d0,a0
        move.w (a0),$72(a6)

        ; A/B/D DMA stay off; C is selected per cohort. BLTDPT is moved to
        ; an isolated sink for C-enabled line primes, whose datapath can write D.
        move.l #-80,$50(a6)         ; APT
        move.w #-280,$64(a6)        ; AMOD
        move.w #0,$62(a6)           ; BMOD
        move.w #80,$60(a6)          ; CMOD
        move.w #80,$66(a6)          ; DMOD
        move.l #$18000,$4c(a6)      ; BPT is unused with B DMA disabled
        move.w 4(a4),d0
        andi.w #3,d0
        add.w d0,d0
        lea line_a_hold_bshifts(pc),a0
        move.w (a0,d0.w),d1
        lsl.w #8,d1
        lsl.w #4,d1                 ; legal 68000 shifts form BSHIFT << 12
        ori.w #1,d1
        move.w d1,$42(a6)
        move.w #$00cc,$40(a6)       ; A/B/C/D DMA all disabled
        btst #4,5(a4)
        bne.s .hold_prime_mode_ready
        move.l #$14000,$48(a6)      ; C source for the C-DMA cohort
        move.l #$15000,$54(a6)      ; safe D sink during the line-prime phase
        move.w #$02cc,$40(a6)       ; C DMA only; minterm still passes B
.hold_prime_mode_ready:
        move.w #$8240,$96(a6)
        lea $58(a6),a1
        move.w (sp),d5              ; saved phase is the line-prime pixel count
        lsl.w #6,d5
        ori.w #2,d5
        move.w d5,$58(a6)
.hold_prime_busy:
        btst #6,$02(a6)
        bne.s .hold_prime_busy
        rept 16
        nop
        endr

        ; Normal one-word target has B DMA off and writes only D[0].
        move.w #$01cc,$40(a6)       ; D enabled; LF=CC passes held B
        move.l #$10000,$54(a6)
        move.w #0,$62(a6)
        move.w #0,$66(a6)
        move.w 4(a4),d2
        lsr.w #2,d2
        andi.w #3,d2
        cmpi.w #0,d2
        bne.s .hold_con1_first
        move.w #0,$72(a6)
.hold_con1_first:
        clr.w $42(a6)               ; target is normal mode, BSHIFT=0
        cmpi.w #1,d2
        bne.s .hold_order_ready
        move.w #0,$72(a6)
.hold_order_ready:
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        lea $58(a6),a1
        move.w #$0041,d5            ; one normal-mode D word
        jsr sync_beam
        moveq #0,d3
        movea.l #$18000,a3
        movea.l #$ff7800,a2
        jsr (a2)
        move.w (sp)+,6(a4)
        move.l (sp)+,d7
        move.l (sp)+,a3
        rts

line_a_history_minterms:
        dc.w $00f0,$00cc,$0040,$00ca

line_a_bit_observer_values:
        dc.w 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
line_a_truth_patterns:
        dc.w $8000,$4000,$2000,$1000,$0800,$0400,$2800,$2801
line_a_truth_minterms:
        dc.w $0000,$00ff,$00f0,$00cc,$0033,$00aa,$0040,$00ca
line_a_hold_b_patterns:
        dc.w $0001,$8000,$a55a,$1248
line_a_hold_bshifts:
        dc.w 0,1,7,15
line_a_bit_scratch_regions:
        dc.l $18000













