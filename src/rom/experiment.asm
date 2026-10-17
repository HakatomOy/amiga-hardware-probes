; SPDX-License-Identifier: MIT
; Legacy timing kernels and data reside in RAM; edge sweeps use immutable ROM
; alignment/measurement stubs where recorded. No RBCP commands run in collection.
        include "rom_layout.i"
        include "rbcp_config.s"
        include "rbcp_defs.s"
CUSTOM equ $dff000
VARS equ $3000
RESULT equ $40000
REF equ $3020
CONTROL equ $3024
LOREG equ $3026
HIREG equ $3028
ICRREG equ $d00
EVBEAM equ 0
EVLEVEL equ 2
EVPC equ 4
DONE equ 8
EVCOUNT equ 10
EVBEAM2 equ 12
EVLEVEL2 equ 14
WATCHDOG equ 16
EXPECT equ 18
RUNBASE equ $302c
PIPE equ $3030
STREAM_PTR equ $3034
STREAM_END equ $3038
        org $20000
probe_entry:  bra.w main
        dcb.b $10-(*-probe_entry),0
collection_done:
        move.l #RESULT,$3080
        move.l #RESULT+64+TRIAL_COUNT*40,$3084
        move.w #$0f0,CUSTOM+$180
        jsr stream_results
        move.w #$0ff,CUSTOM+$180
.idle:  stop #$2700
        bra.s .idle
main:
        lea CUSTOM,a6
        lea VARS,a5
        movea.l #fault_vectors,a0
        lea 8,a1
        moveq #45,d1
.vectors: move.l a0,(a1)+
        adda.w #14,a0
        dbra d1,.vectors
        move.l #irq1,$64
        move.l #irq2,$68
        move.l #irq3,$6c
        move.l #irq6,$78
        move.l #$c00000,a0
        move.l (a0),d0
        move.l #$5a6996a5,(a0)
        cmpi.l #$5a6996a5,(a0)
        seq slow_present
        move.l d0,(a0)
        tst.b slow_present
        beq.s .no_slow
        movea.l #kernels,a0
        lea $c00000,a1
        move.w #(kernels_end-kernels)/2-1,d0
.slow_copy: move.w (a0)+,(a1)+
        dbra d0,.slow_copy
.no_slow:
        movea.l #header,a0
        lea RESULT,a1
        moveq #15,d0
.header: move.l (a0)+,(a1)+
        dbra d0,.header
        move.w 4(a6),RESULT+56
        move.w $7c(a6),RESULT+58
        move.b slow_present,d0
        andi.w #1,d0
        move.w d0,RESULT+60
        lea RESULT+64,a4
        movea.l #trials,a3
        move.w #TRIAL_COUNT-1,d7
.trial:
        move.w #$2700,sr
        bsr quiet
        lea (a4),a0
        moveq #9,d0
.zero:  clr.l (a0)+
        dbra d0,.zero
        moveq #5,d0
        lea (a4),a0
.desc:  move.w (a3)+,(a0)+
        dbra d0,.desc
        clr.w DONE(a5)
        clr.w EVCOUNT(a5)
        clr.w WATCHDOG(a5)
        clr.w EVBEAM(a5)
        clr.w EVLEVEL(a5)
        clr.l EVPC(a5)
        clr.w EVBEAM2(a5)
        clr.w EVLEVEL2(a5)
        cmpi.w #10,(a4)
        beq .interrupt
        cmpi.w #21,(a4)
        beq .channels
        cmpi.w #22,(a4)
        beq .channels
        cmpi.w #23,(a4)
        beq .irq_paths
        cmpi.w #24,(a4)
        beq .bzero_line
        cmpi.w #25,(a4)
        beq .line_logic
        cmpi.w #26,(a4)
        beq .line_logic_fine
        cmpi.w #27,(a4)
        beq .line_logic_followup
        cmpi.w #28,(a4)
        beq .line_pipeline
        cmpi.w #29,(a4)
        beq .line_truth
        cmpi.w #30,(a4)
        beq .line_stage
        cmpi.w #31,(a4)
        beq .line_b_hold
        cmpi.w #32,(a4)
        beq .line_b_hold
        cmpi.w #33,(a4)
        beq .line_pipeline
        cmpi.w #34,(a4)
        beq .line_b_prime
        cmpi.w #35,(a4)
        beq .line_word_control
        cmpi.w #36,(a4)
        beq .line_shift_truth
        cmpi.w #37,(a4)
        beq .line_wrap
        cmpi.w #38,(a4)
        beq .line_wrap
        cmpi.w #39,(a4)
        beq .line_wrap
        cmpi.w #40,(a4)
        beq .line_wrap
        cmpi.w #41,(a4)
        beq .line_wrap
        cmpi.w #43,(a4)
        beq .irq_focus
        cmpi.w #42,(a4)
        beq .line_c_read_sequence
        cmpi.w #44,(a4)
        beq .line_c_activity
        cmpi.w #45,(a4)
        beq .line_c_history
        cmpi.w #46,(a4)
        beq .line_c_bus_data
        cmpi.w #47,(a4)
        beq .copper_wait
        cmpi.w #48,(a4)
        beq .line_a_bit
        cmpi.w #49,(a4)
        beq .blitter_handoff
        cmpi.w #50,(a4)
        beq .copper_start_busy
        cmpi.w #20,(a4)
        beq .divirq
        cmpi.w #19,(a4)
        beq .edges
        cmpi.w #18,(a4)
        beq .cpu
        cmpi.w #17,(a4)
        beq .blits
        cmpi.w #16,(a4)
        beq .loads
        cmpi.w #14,(a4)
        beq .pulses
        cmpi.w #13,(a4)
        beq .modes
        cmpi.w #6,(a4)
        beq .continuous
        cmpi.w #7,(a4)
        beq .continuous
        cmpi.w #8,(a4)
        beq .continuous
        cmpi.w #9,(a4)
        beq .continuous
        cmpi.w #12,(a4)
        beq .continuous
        cmpi.w #5,(a4)
        beq .stop_only
        bsr timer_trial
        bra.w .recorded
.channels:
        bsr channels_trial
        bra.w .recorded
.irq_paths:
        bsr irq_paths_trial
        bra.w .recorded
.bzero_line:
        bsr bzero_line_trial
        bra.w .recorded
.line_logic:
        bsr line_logic_trial
        bra.w .recorded
.line_logic_fine:
        bsr line_logic_trial
        bra.w .recorded
.line_logic_followup:
        bsr line_logic_trial
        bra.w .recorded
.line_pipeline:
        bsr line_pipeline_trial
        bra.w .recorded
.line_truth:
        bsr line_truth_trial
        bra.w .recorded
.line_stage:
        bsr line_stage_trial
        bra.w .recorded
.line_b_hold:
        bsr line_b_hold_trial
        bra.w .recorded
.line_b_prime:
        bsr line_b_prime_trial
        bra.w .recorded
.line_word_control:
        bsr line_pipeline_trial
        bra.w .recorded
.line_shift_truth:
        bsr line_shift_truth_trial
        bra.w .recorded
.line_wrap:
        bsr line_wrap_trial
        bra.w .recorded
.irq_focus:
        jsr irq_focus_trial
        bra.w .recorded
.line_c_read_sequence:
        jsr line_c_read_sequence_trial
        bra.w .recorded
.line_c_activity:
        jsr line_c_activity_trial
        bra.w .recorded
.line_c_history:
        jsr line_c_history_trial
        bra.w .recorded
.line_c_bus_data:
        jsr line_c_bus_data_trial
        bra.w .recorded
.copper_wait:
        jsr copper_wait_trial
        bra.w .recorded
.line_a_bit:
        jsr line_a_bit_trial
        bra.w .recorded
.blitter_handoff:
        jsr blitter_handoff_trial
        bra.w .recorded
.copper_start_busy:
        jsr copper_start_busy_trial
        bra.w .recorded
.divirq:
        bsr divirq_trial
        bra.s .recorded
.edges:
        bsr edges_trial
        bra.s .recorded
.cpu:
        bsr cpu_trial
        bra.s .recorded
.blits:
        bsr blits_trial
        bra.s .recorded
.loads:
        bsr loads_trial
        bra.s .recorded
.pulses:
        bsr pulses_trial
        bra.s .recorded
.modes:
        bsr modes_trial
        bra.s .recorded
.continuous:
        bsr continuous_trial
        bra.s .recorded
.stop_only:
        bsr stop_only_trial
        bra.s .recorded
.interrupt:
        bsr interrupt_trial
.recorded:
        move.w #$2700,sr
        bsr quiet
        adda.w #40,a4
        dbra d7,.trial
        move.l #TRIAL_COUNT,RESULT+12
        move.l #64+TRIAL_COUNT*40,RESULT+16
        move.w #1,RESULT+62
        lea RESULT,a0
        move.l #((64+TRIAL_COUNT*40)/4)-1,d1
        moveq #0,d0
.sum:   add.l (a0)+,d0
        subq.l #1,d1
        bpl.s .sum
        neg.l d0
        move.l d0,RESULT+20
        jmp collection_done
quiet:
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9a(a6)
        clr.b $bfee01
        clr.b $bfef01
        clr.b $bfde00
        clr.b $bfdf00
        move.b #$7f,$bfed01
        move.b #$7f,$bfdd00
        tst.b $bfed01
        tst.b $bfdd00
        move.w #$7fff,$9c(a6)
        move.w #$0200,$100(a6)
        rts
; Target 0/1 = CIA-A TA/TB, 2/3 = CIA-B TA/TB. Other CIA TB is reference.
select_target:
        lea $bfe001,a0
        move.l #$bfd000,REF
        move.w 2(a4),d0
        cmpi.w #2,d0
        bcs.s .cia_a
        lea $bfd000,a0
        move.l #$bfe001,REF
.cia_a: andi.w #1,d0
        beq.s .ta
        move.w #$600,LOREG
        move.w #$700,HIREG
        move.w #$f00,CONTROL
        bra.s .ref
.ta:    move.w #$400,LOREG
        move.w #$500,HIREG
        move.w #$e00,CONTROL
.ref:   move.l REF,a1
        move.b #$ff,$600(a1)
        move.b #$ff,$700(a1)
        move.b #$11,$f00(a1)
        rts
read_reference:
        move.l REF,a1
.again: moveq #0,d0
        move.b $700(a1),d0
        move.b $600(a1),d1
        cmp.b $700(a1),d0
        bne.s .again
        lsl.w #8,d0
        move.b d1,d0
        rts
sync_beam:
.leave: move.w 6(a6),d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        beq.s .leave
.line:  move.w 6(a6),d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        bne.s .line
.hpos:  move.w 6(a6),d0
        andi.w #$ff,d0
        cmpi.w #$20,d0
        bcs.s .hpos
        move.w 6(a4),d0
        bsr delay
        rts
delay:
        lea delay_end(pc),a2
        add.w d0,d0
        suba.w d0,a2
        jsr (a2)
        rts
        rept 64
        nop
        endr
delay_end: rts
; STOP-only: freeze a running continuous timer, sweep delay before reading.
; aux is the last running counter snapshot; counter/second_counter are stopped reads.
; Reload an already-running timer. Variant 0 is START only (control);
; variant 1 is START+LOAD. Counter is live low byte, aux is frozen count.
; Blitter duration: target D-only/AD fill/line; variant STOP/nice-poll/nasty-poll.
; Raw VHPOSR endpoints plus independent CIA-B timer B. No doubled hpos.
; target=plane count; variant=normal/zero/overflow DIVU, MULU, 126-clock NOP/EXG.
; ROM-resident snapshot stream: no chip-RAM opcode fetches during the blit.
; target=D-only/AD copy/AD fill/line/software IRQ; variant=words or pixels.
; A Copper interrupt inside one ROM-resident divide identifies its IPL poll.
; All normal USE masks and all D-enabled fill masks. One observable per run.
channels_trial:
        lea $10000,a0
        lea $15000,a1
        lea $16000,a2
        moveq #63,d0
.clear: clr.w (a0)+
        move.w #$ffff,(a1)+
        move.w #$ffff,(a2)+
        dbra d0,.clear
        cmpi.w #22,(a4)
        bne.s .sources_ready
        move.w 2(a4),d0
        cmpi.w #32,d0
        bcc.s .sources_ready
        btst #3,d0
        beq.s .sources_ready
        move.w 4(a4),d1
        andi.w #$00ff,d1
        beq.s .sources_ready
        cmpi.w #16,d0
        bcs.s .ascending_sources
        lea $1502a,a0
        bra.s .zero_sources
.ascending_sources:
        lea $15000,a0
.zero_sources:
        subq.w #1,d1
.zero_source:
        clr.w (a0)
        cmpi.w #16,2(a4)
        bcc.s .descending_source
        addq.w #2,a0
        bra.s .next_source
.descending_source:
        subq.w #2,a0
.next_source:
        dbra d1,.zero_source
.sources_ready:
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        clr.w $42(a6)
        clr.w $60(a6)
        clr.w $62(a6)
        clr.w $64(a6)
        clr.w $66(a6)
        move.l #$15000,$50(a6)
        move.l #$16000,$4c(a6)
        move.l #$17000,$48(a6)
        move.l #$10000,$54(a6)
        move.w 2(a4),d0
        andi.w #15,d0
        lsl.w #8,d0
        cmpi.w #22,(a4)
        bne.s .normal_minterm
        ori.w #$00f0,d0
        bra.s .store_minterm
.normal_minterm:
        ori.w #$00ff,d0
.store_minterm:
        move.w d0,$40(a6)
        move.w 4(a4),d5
        cmpi.w #22,(a4)
        bne.s .variable_size
        move.w #$0056,d5
        move.w 4(a4),d0
        btst #8,d0
        beq.s .size_ready
        move.w #$0041,d5
        bra.s .size_ready
.variable_size:
        ori.w #$40,d5
.size_ready:
        lea $1002a,a0
        cmpi.w #16,2(a4)
        bcs.w .configured
        cmpi.w #32,2(a4)
        bcc.s .line
        move.w #$0012,$42(a6)
        move.l #$1502a,$50(a6)
        move.l #$1602a,$4c(a6)
        move.l #$1702a,$48(a6)
        move.l #$1002a,$54(a6)
        lea $10000,a0
        bra.w .configured
.line:
        move.w #$0bca,d0
        cmpi.w #33,2(a4)
        bne.s .not_b
        ori.w #$0400,d0
.not_b:
        move.w d0,$40(a6)
        move.w #$0001,$42(a6)
        move.w #-280,$64(a6)
        move.w #120,$62(a6)
        move.l #-80,$50(a6)
        move.w #$8000,$74(a6)
        move.w #$ffff,$72(a6)
        move.l #$10000,$48(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        cmpi.w #22,(a4)
        bne.s .variable_line_size
        move.w #$0582,d5
        move.w 4(a4),d0
        btst #8,d0
        beq.s .line_size_ready
        move.w #$0042,d5
        bra.s .line_size_ready
.variable_line_size:
        move.w 4(a4),d5
        lsl.w #6,d5
        ori.w #2,d5
.line_size_ready:
        lea $10000,a0
.configured:
        cmpi.w #22,(a4)
        bne.s .priority_setup
        cmpi.w #32,2(a4)
        bcc.s .priority_setup
        move.w #$ffff,$74(a6)
.priority_setup:
        btst #2,11(a4)
        beq.s .priority_off
        move.w #$8400,$96(a6)
.priority_off:
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        cmpi.w #34,2(a4)
        bne.s .not_software
        lea $9c(a6),a1
        move.w #$8040,d5
.not_software:
        move.w 10(a4),d0
        andi.w #3,d0
        tst.w d0
        bne.s .not_busy
        lea $02(a6),a0
.not_busy:
        cmpi.w #1,d0
        bne.s .selected
        lea $1e(a6),a0
.selected:
        btst #0,7(a4)
        beq.s .even
        exg d0,d1
        bra.s .phase
.even: nop
        nop
.phase:
        cmpi.w #22,(a4)
        bne.s .primary_stub
        moveq #0,d0
        move.w 6(a4),d0
        andi.w #1,d0
        lsl.w #8,d0
        lsl.w #4,d0
        addi.l #$fd0000,d0
        moveq #0,d1
        move.w 8(a4),d1
        lsl.w #8,d1
        add.l d1,d0
        bra.s .stub_ready
.primary_stub:
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        addi.l #$fa0000,d0
.stub_ready:
        move.l d0,a2
        jsr (a2)
        rts
divirq_trial:
        tst.w 4(a4)
        bne divirq_sign_trial
        move.l #divirq_handler,$6c
        move.l #$12345678,d2
        move.w #$789a,d3
        cmpi.w #1,2(a4)
        bne.s .not_zero
        moveq #0,d2
        moveq #1,d3
.not_zero:
        cmpi.w #2,2(a4)
        bne.s .operands
        moveq #-1,d2
        moveq #1,d3
.operands:
        moveq #0,d4
        lea $6000,a0
        move.l #$4141fffe,(a0)+
        move.l #$009c8010,(a0)+
        move.l #$fffffffe,(a0)+
        move.l #$6000,$80(a6)
        move.w #0,$88(a6)
        move.w #$8280,$96(a6)
        move.w #$c010,$9a(a6)
        bsr sync_beam
        lea $f94000,a0
        cmpi.w #3,2(a4)
        bne.s .selected
        lea $f94800,a0
.selected:
        jsr (a0)
        move.w #$2700,sr
        move.w 6(a6),16(a4)
        move.l d0,20(a4)
        move.l #irq3,$6c
        rts
; Nonzero kind-20 variants are the signed-divider IPL boundary experiment.
; Keep operands and controller setup outside the ROM-aligned timed kernel.
divirq_sign_trial:
        move.l #divirq_handler,$6c
        moveq #0,d0
        move.w 4(a4),d0
        subq.w #1,d0
        lsl.w #3,d0
        lea divirq_sign_operands(pc),a0
        move.l 0(a0,d0.w),d2
        move.w 4(a0,d0.w),d3
        moveq #0,d4
        lea $6000,a0
        move.l #$4321fffe,(a0)+
        move.l #$009c8010,(a0)+
        move.l #$fffffffe,(a0)+
        move.l #$6000,$80(a6)
        move.w #0,$88(a6)
        move.w #$8280,$96(a6)
        move.w #$c010,$9a(a6)
        bsr sync_beam
        move.w #0,$88(a6)
        jsr $fb0000
        move.w #$0010,$9c(a6)
        lea $f94000,a0
        cmpi.w #3,2(a4)
        bne.s .selected
        lea $f94800,a0
.selected:
        jsr (a0)
        move.w #$2700,sr
        move.w 6(a6),16(a4)
        move.l d0,20(a4)
        move.w d4,38(a4)
        move.l #irq3,$6c
        rts
; Eight-byte entries: signed 32-bit dividend, 16-bit divisor, padding.
divirq_sign_operands:
        dc.l 100
        dc.w 3,0
        dc.l 100
        dc.w -3,0
        dc.l -100
        dc.w 3,0
        dc.l -100
        dc.w -3,0
        dc.l 0
        dc.w -3,0
        dc.l 100000
        dc.w -2,0
        dc.l $10000000
        dc.w -1,0
        dc.l $80000000
        dc.w -1,0
irq_paths_trial:
        jsr $fe4000
        move.l #irq1,$64
        move.l #irq3,$6c
        rts
bzero_line_trial:
        lea $10000,a0
        move.w #1023,d0
.clear_line: clr.w (a0)+
        dbra d0,.clear_line
        lea $16000,a0
        move.w 4(a4),d1
        andi.w #$00ff,d1
        beq.s .line_pattern_zero
        cmpi.w #1,d1
        beq.s .line_pattern_one
        cmpi.w #4,d1
        beq.s .line_pattern_four
        cmpi.w #8,d1
        beq.s .line_pattern_eight
        move.w #$ffff,d1
        bra.s .line_pattern_ready
.line_pattern_zero:
        moveq #0,d1
        bra.s .line_pattern_ready
.line_pattern_one:
        move.w #$8000,d1
        bra.s .line_pattern_ready
.line_pattern_four:
        move.w #$1000,d1
        bra.s .line_pattern_ready
.line_pattern_eight:
        move.w #$0100,d1
.line_pattern_ready:
        move.w d1,(a0)
        btst #0,4(a4)
        bne.s .line_bdat_ready
        move.w d1,$72(a6)
.line_bdat_ready:
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$0bca,$40(a6)
        cmpi.w #33,2(a4)
        bne.s .line_b_off
        move.w #$0fca,$40(a6)
.line_b_off:
        move.w #$0001,$42(a6)
        btst #0,4(a4)
        beq.s .line_control_ready
        move.w d1,$72(a6)
.line_control_ready:
        move.w #-280,$64(a6)
        clr.w $62(a6)
        move.l #-80,$50(a6)
        move.l #$16000,$4c(a6)
        move.l #$10000,$48(a6)
        move.l #$10000,$54(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.w #$8000,$74(a6)
        move.w #$0582,d5
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9c(a6)
        move.w #$8240,$96(a6)
        btst #2,11(a4)
        beq.s .line_priority_ready
        move.w #$8640,$96(a6)
.line_priority_ready:
        bsr sync_beam
        lea $58(a6),a1
        moveq #0,d0
        move.w 6(a4),d0
        andi.w #1,d0
        lsl.w #8,d0
        lsl.w #5,d0
        addi.l #$fe5000,d0
        moveq #0,d1
        move.w 8(a4),d1
        lsl.w #8,d1
        add.l d1,d0
        move.l d0,a2
        jmp (a2)
; Kind 25 uses disjoint initialized chip-RAM sources and direct writes to all
; write-only blitter registers. Descriptor variant bits select minterm (0-1),
; A data (2), B source data (3-4), initial C data (5), and size (6-7).
; Target 32/33 selects USEB off/on. The first two observer reads occur before
; waiting for BBUSY to clear; destination memory is sampled only afterward.
line_logic_trial:
        move.l d7,-(sp)
        cmpi.w #27,(a4)
        bne.s .bdat_seed_ready
        move.w #$0001,$42(a6)
        move.w #$ffff,$72(a6)
.bdat_seed_ready:
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.clear_d: move.w d0,(a0)+
        dbra d7,.clear_d
        lea $11000,a0
        moveq #0,d0
        btst #5,5(a4)
        beq.s .c_ready
        move.w #$ffff,d0
.c_ready:
        move.w d0,$70(a6)
        move.w #1023,d7
.fill_c: move.w d0,(a0)+
        dbra d7,.fill_c
        move.w 4(a4),d3
        move.w d3,d1
        cmpi.w #26,(a4)
        beq.s .fine_b_index
        cmpi.w #27,(a4)
        beq.w .followup_b_index
.b_index_general:
        lsr.w #3,d1
        andi.w #3,d1
        bra.w .b_index_ready
.fine_b_index:
        andi.w #1,d1
        lsl.w #1,d1
        bra.w .b_index_ready
.b_index_ready:
        beq.s .b_zero
        cmpi.w #1,d1
        beq.s .b_full
        move.w #$1000,d1
        bra.s .b_ready
.b_zero: moveq #0,d1
        bra.s .b_ready
.b_full: move.w #$ffff,d1
.b_ready:
        cmpi.w #27,(a4)
        bne.s .b_fill_memory
        btst #0,11(a4)
        beq.s .b_fill_memory
        move.w d1,$72(a6)
.b_fill_memory:
        lea $16000,a0
        move.w #1023,d7
.fill_b: move.w d1,(a0)+
        dbra d7,.fill_b
        move.w d3,d0
        cmpi.w #26,(a4)
        beq.s .fine_minterm
        cmpi.w #27,(a4)
        beq.s .fine_minterm
        andi.w #3,d0
        bra.s .minterm_ready
.fine_minterm:
        moveq #2,d0
.minterm_ready:
        add.w d0,d0
        lea .line_minterms(pc),a0
        move.w 0(a0,d0.w),d0
        move.w #$0b00,d2
        cmpi.w #33,2(a4)
        bne.s .b_enable_ready
        move.w #$0f00,d2
.b_enable_ready:
        or.w d2,d0
        move.w d0,$40(a6)
        move.w #$0001,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        ; In line mode BLTAPT ($50) is the signed error accumulator, not a
        ; source pointer. Pin it identically for both line-logic matrices.
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        cmpi.w #27,(a4)
        bne.s .legacy_bdat
        btst #0,11(a4)
        bne.s .bdat_ready
        move.w d1,$72(a6)
        bra.s .bdat_ready
.legacy_bdat:
        move.w d1,$72(a6)
.bdat_ready:
        moveq #0,d0
        cmpi.w #26,(a4)
        beq.s .fine_a_data
        cmpi.w #27,(a4)
        beq.s .followup_a_data
        btst #2,5(a4)
        beq.s .a_ready
        move.w #$8000,d0
        bra.s .a_ready
.fine_a_data:
        move.w #$8000,d0
        bra.s .a_ready
.followup_a_data:
        move.w d3,d0
        lsr.w #3,d0
        andi.w #3,d0
        add.w d0,d0
        lea .line_a_patterns(pc),a0
        move.w 0(a0,d0.w),d0
.a_ready:
        move.w d0,$74(a6)
        move.w d3,d5
        cmpi.w #26,(a4)
        beq.s .fine_size
        cmpi.w #27,(a4)
        beq.s .followup_size
        lsr.w #6,d5
        andi.w #3,d5
        cmpi.w #0,d5
        bne.s .size_not_one
        move.w #$0042,d5
        bra.w .size_ready
.size_not_one:
        cmpi.w #1,d5
        bne.s .size_twenty_two
        move.w #$0082,d5
        bra.s .size_ready
.size_twenty_two:
        move.w #$0582,d5
        bra.w .size_ready
.fine_size:
        btst #1,5(a4)
        beq.s .fine_size_two
        move.w #$0582,d5
        bra.s .size_ready
.fine_size_two:
        move.w #$0082,d5
        bra.s .size_ready
.followup_size:
        btst #6,5(a4)
        beq.s .fine_size_two
        move.w #$0582,d5
        bra.w .size_ready
.size_ready:
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        btst #2,11(a4)
        beq.s .line_priority_ready
        move.w #$8640,$96(a6)
.line_priority_ready:
        bsr sync_beam
        lea $58(a6),a1
        moveq #0,d0
        move.w 8(a4),d0
        cmpi.w #26,(a4)
        beq.s .fine_delay_ready
        cmpi.w #27,(a4)
        beq.s .fine_delay_ready
        cmpi.w #0,d0
        beq.s .delay_ready
        cmpi.w #1,d0
        beq.s .delay_one
        cmpi.w #2,d0
        beq.s .delay_two
        cmpi.w #4,d0
        beq.s .delay_four
        cmpi.w #8,d0
        beq.s .delay_eight
        moveq #5,d0
        bra.s .delay_ready
.delay_one: moveq #1,d0
        bra.s .delay_ready
.delay_two: moveq #2,d0
        bra.s .delay_ready
.delay_four: moveq #3,d0
        bra.s .delay_ready
.delay_eight: moveq #4,d0
.delay_ready:
        bra.w .delay_scaled
.fine_delay_ready:
.delay_scaled:
        lsl.w #8,d0
        moveq #0,d1
        move.w 6(a4),d1
        andi.w #1,d1
        cmpi.w #26,(a4)
        beq.s .fine_phase_offset
        cmpi.w #27,(a4)
        beq.s .fine_phase_offset
        lsl.w #4,d1
        bra.s .phase_scaled
.fine_phase_offset:
        lsl.w #5,d1
.phase_scaled:
        lsl.w #8,d1
        add.l d1,d0
        cmpi.w #26,(a4)
        beq.s .fine_stub_base
        cmpi.w #27,(a4)
        beq.s .fine_stub_base
        addi.l #$fe9000,d0
        bra.s .stub_base_ready
.fine_stub_base:
        addi.l #$feb000,d0
.stub_base_ready:
        move.l d0,a2
        jsr (a2)
        move.l (sp)+,d7
        rts
.line_minterms:
        dc.w $0000,$00ff,$00ca,$00f0
.followup_b_index:
        andi.w #7,d1
        add.w d1,d1
        lea .line_b_patterns(pc),a0
        move.w 0(a0,d1.w),d1
        bra.w .b_ready
.line_b_patterns:
        dc.w 0,$0001,$0002,$0004,$8000,$1000,$ffff
.line_a_patterns:
        dc.w 0,$8000,$ffff
; Kind 28 uses a compact, generated preset table (three words per entry).
; target is the zero-based preset index; phase is NOP/EXG; delay selects one
; of the 17 existing fine observer slots. variant/repeat remain zero.
line_pipeline_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.clear_d: move.w d0,(a0)+
        dbra d7,.clear_d
        moveq #0,d0
        move.w 2(a4),d0
        move.w d0,d1
        lsl.w #2,d0
        add.w d1,d1
        add.w d1,d0
        lea line_pipeline_presets(pc),a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        ; Explicit BLTBDAT preseed pair in both orders. The final selected B
        ; value is installed below, just before the operation is armed.
        btst #14,d5
        bne.s .seed_zero_first
        move.w #$ffff,$72(a6)
        clr.w $72(a6)
        bra.s .seed_done
.seed_zero_first:
        clr.w $72(a6)
        move.w #$ffff,$72(a6)
.seed_done:
        ; A data and A shift (table patterns: 0000, 8000, 0001, ffff).
        move.w d3,d0
        andi.w #3,d0
        add.w d0,d0
        lea .pipeline_a(pc),a0
        move.w 0(a0,d0.w),$74(a6)
        ; B texture and shift; fill chip source so both DMA and data-register
        ; paths receive the same repeated word texture.
        move.w d3,d1
        lsr.w #6,d1
        andi.w #7,d1
        add.w d1,d1
        lea .pipeline_b(pc),a0
        move.w 0(a0,d1.w),d1
        move.w d1,$72(a6)
        lea $16000,a0
        move.w #1023,d7
.fill_b: move.w d1,(a0)+
        dbra d7,.fill_b
        ; C texture and its source memory.
        move.w d4,d2
        andi.w #3,d2
        add.w d2,d2
        lea .pipeline_c(pc),a0
        move.w 0(a0,d2.w),d2
        move.w d2,$70(a6)
        lea $11000,a0
        move.w #1023,d7
.fill_c: move.w d2,(a0)+
        dbra d7,.fill_c
        ; Compose A shift, USEA/B/C, USED and one of nine minterms.
        move.w d5,d0
        andi.w #$00ff,d0
        move.w d4,d1
        lsr.w #2,d1
        andi.w #7,d1
        lsl.w #8,d1
        lsl.w #1,d1
        or.w d1,d0
        move.w d4,d1
        btst #5,d1
        beq.s .d_disabled
        ori.w #$0100,d0
.d_disabled:
        move.w d3,d1
        lsr.w #2,d1
        andi.w #15,d1
        lsl.w #8,d1
        lsl.w #4,d1
        or.w d1,d0
        move.w d0,$40(a6)
        move.w d3,d1
        lsr.w #8,d1
        lsr.w #1,d1
        andi.w #15,d1
        lsl.w #8,d1
        lsl.w #4,d1
        btst #8,d5
        beq.s .sing_ready
        ori.w #$0002,d1
.sing_ready:
        btst #9,d5
        beq.s .sign_ready
        ori.w #$0040,d1
.sign_ready:
        ori.w #1,d1
        move.w d1,$42(a6)
        move.w d5,d0
        lsr.w #8,d0
        lsr.w #2,d0
        andi.w #3,d0
        lsl.w #2,d0
        lea .pipeline_errors(pc),a0
        move.l 0(a0,d0.w),$50(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #$10000,$54(a6)
        move.w d5,d0
        lsr.w #8,d0
        lsr.w #4,d0
        andi.w #3,d0
        beq.s .size_one
        cmpi.w #1,d0
        beq.s .size_two
        move.w #$0582,d5
        bra.s .size_ready
.size_one: move.w #$0042,d5
        bra.s .size_ready
.size_two: move.w #$0082,d5
.size_ready:
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        cmpi.w #35,(a4)
        beq.w .word_control_observer
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        moveq #0,d1
        move.w 6(a4),d1
        andi.w #1,d1
        lsl.w #5,d1
        lsl.w #8,d1
        add.l d1,d0
        addi.l #$ff0000,d0
        move.l d0,a2
        bra.w .observer_ready
.word_control_observer:
        ; Kind35 delay values map onto five private ROM slot indices.
        moveq #0,d0
        move.w 8(a4),d0
        cmpi.w #0,d0
        beq.s .word_delay_zero
        cmpi.w #1,d0
        beq.s .word_delay_one
        cmpi.w #2,d0
        beq.s .word_delay_two
        cmpi.w #4,d0
        beq.s .word_delay_four
        cmpi.w #16,d0
        beq.s .word_delay_sixteen
        moveq #0,d0
        bra.s .word_delay_ready
.word_delay_zero: moveq #0,d0
        bra.s .word_delay_ready
.word_delay_one: moveq #1,d0
        bra.s .word_delay_ready
.word_delay_two: moveq #2,d0
        bra.s .word_delay_ready
.word_delay_four: moveq #3,d0
        bra.s .word_delay_ready
.word_delay_sixteen: moveq #4,d0
.word_delay_ready:
        lsl.w #8,d0
        moveq #0,d1
        move.w 4(a4),d1
        lsl.w #8,d1
        lsl.w #4,d1
        add.l d1,d0
        addi.l #$ff4000,d0
        move.l d0,a2
.observer_ready:
        jsr (a2)
        move.l (sp)+,d7
        rts
.pipeline_a: dc.w 0,$8000,$0001,$ffff
.pipeline_b: dc.w 0,$0001,$0002,$8000,$1000,$ffff
.pipeline_c: dc.w 0,$ffff,$8000,$aaaa
.pipeline_errors: dc.l -80,-1,0,80
.pipeline_minterms: dc.w $0000,$00ff,$00ca,$00f0,$00cc,$00aa,$003c,$005a,$000f
        include "line_pipeline.i"
; Kind29 target selects one of five input profiles and 1/2-pixel size;
; variant is the raw 8-bit minterm. It uses the kind28 dual-memory observer.
line_truth_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.clear_d: move.w d0,(a0)+
        dbra d7,.clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #3,d0
        lea line_truth_profiles(pc),a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        move.w d3,$74(a6)
        move.w d4,$72(a6)
        lea $16000,a0
        move.w #1023,d7
.truth_b: move.w d4,(a0)+
        dbra d7,.truth_b
        move.w d5,$70(a6)
        lea $11000,a0
        move.w #1023,d7
.truth_c: move.w d5,(a0)+
        dbra d7,.truth_c
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$0b00,d0
        move.w 4(a4),d1
        andi.w #$00ff,d1
        or.w d1,d0
        move.w d0,$40(a6)
        move.w #$0001,$42(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        addi.l #$ff0000,d0
        move.l d0,a2
        move.w d6,d5
        jsr (a2)
        move.l (sp)+,d7
        rts
        include "line_truth_profiles.i"
; Kind36 crosses the full raw minterm byte with selected BSHIFT states. The
; table is five literal words per row: A/B/C data, BLTSIZE, BLTCON1.
line_shift_truth_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.shift_clear_d: move.w d0,(a0)+
        dbra d7,.shift_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #1,d0
        move.w d0,d1
        lsl.w #2,d0
        add.w d1,d0
        lea line_shift_truth_profiles(pc),a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        move.w (a0)+,d7
        move.w d3,$74(a6)
        move.w d4,$72(a6)
        move.w d5,$70(a6)
        lea $16000,a0
        move.w #1023,d2
.shift_fill_b: move.w d4,(a0)+
        dbra d2,.shift_fill_b
        lea $11000,a0
        move.w #1023,d2
.shift_fill_c: move.w d5,(a0)+
        dbra d2,.shift_fill_c
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$0b00,d0
        moveq #0,d1
        move.w 4(a4),d1
        andi.w #$00ff,d1
        or.w d1,d0
        move.w d0,$40(a6)
        move.w d7,$42(a6)
        move.w #-280,$64(a6)
        clr.w $62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        move.l #$ff3000,a2
        move.w d6,d5
        jsr (a2)
        move.l (sp)+,d7
        rts
        include "line_shift_truth_profiles.i"
; Kind37 measures completed line lengths. Kind38/39 reuse this setup with
; distinct literal preset tables; kind39 stores C words at $11000/$11050 and
; loads BLTCDAT independently from the third table word.
line_wrap_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.wrap_clear_d: move.w d0,(a0)+
        dbra d7,.wrap_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #2,d0
        move.w d0,d1
        lsl.w #1,d0
        add.w d1,d0
        cmpi.w #40,(a4)
        beq.s .wrap_c_tomography
        cmpi.w #41,(a4)
        beq.s .wrap_c_onset
        cmpi.w #39,(a4)
        beq.s .wrap_c_words
        cmpi.w #38,(a4)
        beq.s .wrap_c_cross
        lea line_wrap_presets(pc),a0
        bra.s .wrap_table_ready
.wrap_c_cross:
        movea.l #line_c_cross_presets,a0
        bra.s .wrap_table_ready
.wrap_c_words:
        movea.l #line_c_word_presets,a0
        bra.s .wrap_table_ready
.wrap_c_tomography:
        movea.l #line_c_tomography_presets,a0
        bra.s .wrap_table_ready
.wrap_c_onset:
        movea.l #line_c_onset_presets,a0
.wrap_table_ready:
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        move.w (a0)+,d7
        move.w (a0)+,d2
        cmpi.w #40,(a4)
        beq.s .wrap_data_tomography
        cmpi.w #41,(a4)
        beq.s .wrap_data_onset
        cmpi.w #39,(a4)
        beq.s .wrap_data_c_words
        move.w d3,$74(a6)
        move.w d4,$72(a6)
        move.w d5,$70(a6)
        bra.s .wrap_data_ready
.wrap_data_c_words:
        move.w d5,$74(a6)
        move.w #0,$72(a6)
        move.w d5,$70(a6)
        bra.s .wrap_data_ready
.wrap_data_tomography:
        move.w #$8000,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        bra.s .wrap_data_ready
.wrap_data_onset:
        move.w #0,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
.wrap_data_ready:
        lea $16000,a0
        move.w #1023,d1
.wrap_fill_b:
        cmpi.w #39,(a4)
        bne.s .wrap_fill_b_data
        clr.w (a0)+
        bra.s .wrap_fill_b_next
.wrap_fill_b_data:
        move.w d4,(a0)+
.wrap_fill_b_next:
        dbra d1,.wrap_fill_b
        lea $11000,a0
        move.w #1023,d1
.wrap_fill_c:
        cmpi.w #39,(a4)
        beq.s .wrap_fill_c_zero
        cmpi.w #41,(a4)
        bne.s .wrap_fill_c_data
.wrap_fill_c_zero:
        clr.w (a0)+
        bra.s .wrap_fill_c_next
.wrap_fill_c_data:
        move.w d5,(a0)+
.wrap_fill_c_next:
        dbra d1,.wrap_fill_c
        cmpi.w #39,(a4)
        beq.s .wrap_store_c_words
        cmpi.w #40,(a4)
        beq.s .wrap_store_c_words
        cmpi.w #41,(a4)
        bne.s .wrap_sources_ready
.wrap_store_c_words:
        move.w d3,$11000
        move.w d4,$11050
.wrap_sources_ready:
        move.w d2,$40(a6)
        move.w d7,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        clr.w $62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        cmpi.w #37,(a4)
        bne.s .wrap_c_observer
        move.l #$ff7000,a2
        bra.s .wrap_observer_ready
.wrap_c_observer:
        cmpi.w #41,(a4)
        bne.s .wrap_fixed_observer
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        moveq #0,d1
        move.w 6(a4),d1
        andi.w #1,d1
        lsl.w #5,d1
        lsl.w #8,d1
        add.l d1,d0
        addi.l #$ff0000,d0
        move.l d0,a2
        bra.s .wrap_observer_ready
.wrap_fixed_observer:
        move.l #$ff3000,a2
.wrap_observer_ready:
        move.w d6,d5
        jsr (a2)
        move.l (sp)+,d7
        rts
        include "line_wrap_presets.i"
; Kind30 holds A at $8000 and B at zero, varying the two C source words
; fetched by a 2-pixel line operation. The target table selects C first/
; second plus USEB; variant is one of five raw minterms.
line_stage_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.stage_clear_d: move.w d0,(a0)+
        dbra d7,.stage_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #1,d0
        move.w d0,d1
        lsl.w #1,d0
        add.w d1,d0
        lea line_stage_profiles(pc),a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w #$8000,$74(a6)
        clr.w $72(a6)
        clr.w $70(a6)
        lea $16000,a0
        moveq #0,d0
        move.w #1023,d7
.stage_fill_b: move.w d0,(a0)+
        dbra d7,.stage_fill_b
        lea $11000,a0
        move.w #1023,d7
.stage_fill_c: move.w d0,(a0)+
        dbra d7,.stage_fill_c
        move.w d3,$11000
        move.w d4,$11050
        move.w #$0b00,d0
        tst.w d5
        beq.s .stage_use_ready
        ori.w #$0400,d0
.stage_use_ready:
        moveq #0,d1
        move.w 4(a4),d1
        andi.w #$00ff,d1
        or.w d1,d0
        move.w d0,$40(a6)
        move.w #1,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        moveq #0,d1
        move.w 6(a4),d1
        andi.w #1,d1
        lsl.w #5,d1
        lsl.w #8,d1
        add.l d1,d0
        addi.l #$ff0000,d0
        move.l d0,a2
        move.w #$0082,d5
        jsr (a2)
        move.l (sp)+,d7
        rts
        include "line_stage_profiles.i"
; Kind31 isolates B texture/shifting with B-only CC and an A-sensitive CA
; discriminator. Target indexes texture/BSHIFT/USEB; variant selects A/LF.
; BLTCON1 is programmed before BLTBDAT.
line_b_hold_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.hold_clear_d: move.w d0,(a0)+
        dbra d7,.hold_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #3,d0
        lea line_b_hold_presets(pc),a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        clr.w $70(a6)
        move.w #1,$42(a6)
        tst.w d6
        bne.s .hold_early_bdat
        move.w d4,$42(a6)
        move.w d3,$72(a6)
        bra.s .hold_bdat_ready
.hold_early_bdat:
        move.w d3,$72(a6)
        move.w d4,$42(a6)
.hold_bdat_ready:
        lea $16000,a0
        move.w #1023,d7
.hold_fill_b: move.w d3,(a0)+
        dbra d7,.hold_fill_b
        lea $11000,a0
        moveq #0,d0
        move.w #1023,d7
.hold_fill_c: move.w d0,(a0)+
        dbra d7,.hold_fill_c
        moveq #0,d6
        move.w 4(a4),d6
        lsl.w #2,d6
        lea line_b_hold_variants(pc),a0
        adda.w d6,a0
        move.w (a0)+,d2
        move.w (a0)+,d1
        move.w d2,$74(a6)
        move.w d1,d0
        tst.w d5
        beq.s .hold_use_ready
        ori.w #$0400,d0
.hold_use_ready:
        move.w d0,$40(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        moveq #0,d1
        move.w 6(a4),d1
        andi.w #1,d1
        lsl.w #5,d1
        lsl.w #8,d1
        add.l d1,d0
        addi.l #$ff0000,d0
        move.l d0,a2
        move.w #$0082,d5
        jsr (a2)
        move.l (sp)+,d7
        rts
        include "line_b_hold_presets.i"
        include "line_b_hold_variants.i"
; Kind34 primes the normal B path before the shared kind28 line driver.
; variant 0 does nothing; 1 writes normal BLTCON1/BLTBDAT; 2/3 run a two-word
; normal B+D copy from $18000 to $19000 with zero/$ffff B source data.
line_b_prime_trial:
        move.l d7,-(sp)
        moveq #0,d6
        move.w 4(a4),d6
        tst.w d6
        beq.w .prime_done
        move.w #0,$42(a6)
        move.w #0,$72(a6)
        cmpi.w #1,d6
        beq.w .prime_done
        moveq #0,d0
        cmpi.w #3,d6
        bne.s .prime_value_ready
        move.w #$ffff,d0
.prime_value_ready:
        lea $18000,a0
        move.w d0,(a0)+
        move.w d0,(a0)+
        lea $19000,a0
        clr.w (a0)+
        clr.w (a0)+
        move.w d0,$72(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$05cc,$40(a6)
        clr.w $60(a6)
        clr.w $62(a6)
        clr.w $64(a6)
        clr.w $66(a6)
        move.l #$18000,$4c(a6)
        move.l #$19000,$54(a6)
        move.w #$8240,$96(a6)
        move.w #$0042,$58(a6)
.prime_busy: btst #6,$02(a6)
        bne.s .prime_busy
        rept 8
        nop
        endr
.prime_done:
        move.l (sp)+,d7
        bsr line_pipeline_trial
        rts
divirq_handler:
        move.w 6(a6),24(a4)
        move.l 2(sp),28(a4)
        move.w d4,34(a4)
        move.w #1,DONE(a5)
        move.w #$0010,$9c(a6)
        rte
edges_trial:
        lea $10000,a0
        lea $15000,a1
        moveq #63,d0
.clear: clr.w (a0)+
        move.w #$ffff,(a1)+
        dbra d0,.clear
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$01ff,$40(a6)
        clr.w $42(a6)
        clr.w $64(a6)
        clr.w $66(a6)
        move.l #$10000,$54(a6)
        move.l #$15000,$50(a6)
        move.w 4(a4),d5
        ori.w #$40,d5
        move.w 4(a4),d0
        subq.w #1,d0
        add.w d0,d0
        lea $10000,a0
        adda.w d0,a0
        tst.w 2(a4)
        beq.w .configured
        move.w #$09f0,$40(a6)
        cmpi.w #2,2(a4)
        bne.s .not_fill
        move.w #$0012,$42(a6)
        move.l a0,$54(a6)
        lea $15000,a1
        adda.w d0,a1
        move.l a1,$50(a6)
        lea $10000,a0
.not_fill:
        cmpi.w #3,2(a4)
        bne.w .configured
        move.w #$0bca,$40(a6)
        move.w #$0001,$42(a6)
        move.w #-280,$64(a6)
        move.w #120,$62(a6)
        move.l #-80,$50(a6)
        move.w #$8000,$74(a6)
        move.w #$ffff,$72(a6)
        move.l #$10000,$48(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.w 4(a4),d5
        lsl.w #6,d5
        ori.w #2,d5
        lea $10000,a0
.configured:
        move.w #$8240,$96(a6)
        bsr sync_beam
        lea $58(a6),a1
        cmpi.w #4,2(a4)
        bne.s .blitter
        lea $9c(a6),a1
        move.w #$8040,d5
.blitter:
        btst #0,7(a4)
        beq.s .even
        exg d0,d1
        bra.s .phase
.even: nop
        nop
.phase:
        moveq #0,d0
        move.w 8(a4),d0
        lsl.w #8,d0
        addi.l #$f90000,d0
        move.l d0,a2
        jsr (a2)
        rts
cpu_trial:
        lea $bfd000,a0
        move.l a0,REF
        move.b #$ff,$600(a0)
        move.b #$ff,$700(a0)
        move.b #$11,$f00(a0)
        move.w #$2c81,$8e(a6)
        move.w #$2cc1,$90(a6)
        move.w #$38,$92(a6)
        move.w #$d0,$94(a6)
        clr.w $108(a6)
        clr.w $10a(a6)
        lea $e0(a6),a0
        moveq #5,d0
.pointers: move.l #$10000,(a0)+
        dbra d0,.pointers
        move.w 2(a4),d0
        lsl.w #8,d0
        lsl.w #4,d0
        move.w d0,$100(a6)
        move.w #$8300,$96(a6)
        move.l #$12345678,d2
        move.w #$789a,d3
        cmpi.w #1,4(a4)
        bne.s .not_zero
        moveq #0,d2
        moveq #1,d3
.not_zero:
        cmpi.w #2,4(a4)
        bne.s .operands
        moveq #-1,d2
        moveq #1,d3
.operands:
        move.w 8(a4),d5
        subq.w #1,d5
        move.w #$789a,$15000
        lea $15000,a0
        move.w 4(a4),d0
        add.w d0,d0
        lea cpu_offsets(pc),a2
        move.w 0(a2,d0.w),d0
        lea cpu_div(pc),a2
        adda.w d0,a2
        move.l a2,$30a0
        bsr sync_beam
        bsr read_reference
        move.w d0,14(a4)
        jsr $fb0000
        move.l $30a0,a2
        move.w 6(a6),12(a4)
        jsr (a2)
        move.w 6(a6),16(a4)
        move.w #$7fff,$96(a6)
        move.l d0,20(a4)
        clr.b $bfdf00
        rept 16
        nop
        endr
        bsr read_reference
        move.w d0,18(a4)
        move.l d2,36(a4)
        rts
cpu_offsets:
        dc.w 0,0,0,cpu_mul-cpu_div,cpu_nops-cpu_div
        dc.w cpu_divs-cpu_div,cpu_divimm-cpu_div,cpu_divmem-cpu_div
cpu_div:
.loop:  move.l d2,d0
        divu.w d3,d0
        dbra d5,.loop
        rts
cpu_divs:
.loop:  move.l d2,d0
        divs.w d3,d0
        dbra d5,.loop
        rts
cpu_divimm:
.loop:  move.l d2,d0
        divu.w #$789a,d0
        dbra d5,.loop
        rts
cpu_divmem:
.loop:  move.l d2,d0
        divu.w (a0),d0
        dbra d5,.loop
        rts
cpu_mul:
.loop:  move.l d2,d0
        mulu.w d3,d0
        dbra d5,.loop
        rts
cpu_nops:
.loop:  move.l d2,d0
        rept 30
        nop
        endr
        exg d0,d1
        dbra d5,.loop
        rts
blits_trial:
        move.l #blit_irq,$6c
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #$0100,$40(a6)
        clr.w $42(a6)
        clr.w $64(a6)
        clr.w $66(a6)
        move.l #$10000,$54(a6)
        move.w 8(a4),d5
        lsl.w #6,d5
        ori.w #22,d5
        cmpi.w #1,2(a4)
        bne.s .not_fill
        move.w #$09f0,$40(a6)
        move.w #$0012,$42(a6)
        move.l #$1a000,$50(a6)
        move.l #$14000,$54(a6)
.not_fill:
        cmpi.w #2,2(a4)
        bne.s .configured
        move.w #$0bca,$40(a6)
        move.w #$0001,$42(a6)
        move.w #-280,$64(a6)
        move.w #120,$62(a6)
        move.l #-80,$50(a6)
        move.w #$8000,$74(a6)
        move.w #$ffff,$72(a6)
        move.l #$10000,$48(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        andi.w #$ffc0,d5
        ori.w #2,d5
.configured:
        move.w #$8240,$96(a6)
        cmpi.w #2,4(a4)
        bne.s .not_nasty
        move.w #$8400,$96(a6)
.not_nasty:
        move.w #$c040,$9a(a6)
        bsr sync_beam
        move.w 6(a6),12(a4)
        move.w d5,$58(a6)
        tst.w 4(a4)
        bne.s .poll
.stop:  stop #$2000
        tst.w DONE(a5)
        beq.s .stop
        move.w #$2700,sr
        move.w EVBEAM(a5),d0
        bra.s .record
.poll:  tst.w $02(a6)
.busy:  btst #6,$02(a6)
        bne.s .busy
        move.w 6(a6),d0
.record:
        move.w d0,16(a4)
        move.w EVBEAM(a5),24(a4)
        move.l #irq3,$6c
        rts
blit_irq:
        move.w 6(a6),EVBEAM(a5)
        move.w #$0040,$9c(a6)
        move.w #1,DONE(a5)
        rte
loads_trial:
        bsr select_target
        move.w LOREG,d2
        move.w HIREG,d3
        move.w CONTROL,d4
        move.b #200,0(a0,d2.w)
        clr.b 0(a0,d3.w)
        move.b #$11,0(a0,d4.w)
        bsr sync_beam
        moveq #1,d1
        tst.w 4(a4)
        beq.s .control
        moveq #$11,d1
.control:
        move.w 8(a4),d0
        lea loads_delay_end(pc),a2
        add.w d0,d0
        suba.w d0,a2
        move.w 6(a6),12(a4)
        move.b d1,0(a0,d4.w)
        jmp (a2)
        rept 16
        nop
        endr
loads_delay_end:
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,20(a4)
        clr.b 0(a0,d4.w)
        rept 16
        nop
        endr
        moveq #0,d0
        move.b 0(a0,d3.w),d0
        lsl.w #8,d0
        move.b 0(a0,d2.w),d0
        move.w d0,34(a4)
        move.w 6(a6),16(a4)
        rts
stop_only_trial:
        bsr select_target
        move.w LOREG,d2
        move.w HIREG,d3
        move.w CONTROL,d4
        move.b #200,0(a0,d2.w)
        clr.b 0(a0,d3.w)
        move.b #$11,0(a0,d4.w)
        bsr sync_beam
        bsr read_reference
        move.w d0,14(a4)
        move.w 6(a6),12(a4)
        move.w 8(a4),d0
        lea post_end(pc),a2
        add.w d0,d0
        suba.w d0,a2
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,34(a4)
        clr.b 0(a0,d4.w)
        jmp (a2)
; First and final underflow snapshots, before and after target STOP.
; repeat selects START, START+LOAD, one-shot START, one-shot START+LOAD.
pulses_trial:
        bsr select_target
        move.w LOREG,d2
        move.w CONTROL,d4
        move.l REF,a1
        moveq #0,d0
        move.b d0,$f00(a1)
        move.b #$ff,$600(a1)
        move.b #$ff,$700(a1)
        move.b #$ff,$600(a0)
        move.b #$ff,$700(a0)
        move.w 4(a4),d0
        move.b d0,0(a0,d2.w)
        move.w HIREG,d0
        clr.b 0(a0,d0.w)
        bsr sync_beam
        move.w #$ffff,14(a4)
        move.w 6(a6),12(a4)
        move.w 10(a4),d0
        add.w d0,d0
        lea pulse_controls(pc),a2
        move.w 0(a2,d0.w),d0
        move.w d0,d1
        andi.w #8,d1
        move.w 8(a4),d6
        lea pulses_delay_end(pc),a2
        add.w d6,d6
        suba.w d6,a2
        move.b #$11,$f00(a1)
        move.b #$51,$f00(a0)
        move.b d0,0(a0,d4.w)
        jmp (a2)
        rept 64
        nop
        endr
pulses_delay_end:
        moveq #0,d5
        move.b $600(a0),d5
        ori.w #$ff00,d5
        move.w d5,34(a4)
        moveq #0,d6
        move.b d6,$f00(a1)
        move.b 0(a0,d2.w),d6
        move.w d6,20(a4)
        move.b 0(a0,d4.w),d6
        move.w d6,22(a4)
        move.b d1,0(a0,d4.w)
        rept 16
        nop
        endr
        move.b #$40,$f00(a0)
        rept 16
        nop
        endr
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,36(a4)
        move.b $700(a0),d0
        lsl.w #8,d0
        move.b $600(a0),d0
        move.w d0,38(a4)
        bsr read_reference
        move.w d0,18(a4)
        move.w 6(a6),16(a4)
        rts
pulse_controls:
        dc.w $01,$11,$09,$19
; Input-mode transitions: target TB, target TA stopped, other CIA TB clock.
; aux is last running low count, counter/second_counter are fully frozen.
modes_trial:
        bsr select_target
        move.w LOREG,d2
        move.w CONTROL,d4
        move.l REF,a1
        moveq #0,d0
        move.b d0,$f00(a1)
        move.b #$ff,$600(a1)
        move.b #$ff,$700(a1)
        move.b #200,0(a0,d2.w)
        move.w HIREG,d0
        clr.b 0(a0,d0.w)
        bsr sync_beam
        move.w #$ffff,14(a4)
        move.w 6(a6),12(a4)
        move.w 4(a4),d0
        mulu.w #6,d0
        lea mode_controls(pc),a2
        move.w 0(a2,d0.w),d5
        move.w 4(a2,d0.w),d1
        move.w 2(a2,d0.w),d0
        move.w 8(a4),d6
        lea modes_delay_end(pc),a2
        add.w d6,d6
        suba.w d6,a2
        move.b #$11,$f00(a1)
        move.b d5,0(a0,d4.w)
        rept 16
        nop
        endr
        moveq #0,d6
        move.b 0(a0,d2.w),d6
        move.w d6,34(a4)
        move.b d0,0(a0,d4.w)
        jmp (a2)
        rept 32
        nop
        endr
modes_delay_end:
        move.b d1,0(a0,d4.w)
        moveq #0,d0
        move.b d0,$f00(a1)
        rept 16
        nop
        endr
        move.b 0(a0,d2.w),d0
        move.w d0,20(a4)
        move.w 6(a6),16(a4)
        bsr read_reference
        move.w d0,18(a4)
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,36(a4)
        move.b $d00(a0),d0
        move.w d0,22(a4)
        rts
mode_controls:
        dc.w $11,$20,$20 ; PHI2 -> STOP + CNT
        dc.w $11,$40,$40 ; PHI2 -> STOP + TA
        dc.w $11,$41,$40 ; running PHI2 -> running TA
        dc.w $51,$01,$00 ; running TA -> running PHI2
        dc.w $11,$00,$00 ; PHI2 -> STOP, same source control
; Frozen continuous-timer experiment. Kind 6 paired timer counts PHI2;
; kind 7 paired TB counts target TA underflows. Other CIA TB counts PHI2.
; Both reference timers and target are stopped and drained before reads.
continuous_trial:
        bsr select_target
        move.w LOREG,d2
        move.w HIREG,d3
        move.w CONTROL,d4
        move.w d4,d5
        eori.w #$100,d5
        move.w d2,d6
        eori.w #$200,d6
        move.l REF,a1
        moveq #0,d0
        move.b d0,$f00(a1)
        move.b d0,0(a0,d4.w)
        move.b d0,0(a0,d5.w)
        move.b #$ff,$600(a1)
        move.b #$ff,$700(a1)
        move.b #$ff,0(a0,d6.w)
        move.w d6,d3
        addi.w #$100,d3
        move.b #$ff,0(a0,d3.w)
        move.w 4(a4),d0
        move.b d0,0(a0,d2.w)
        move.w HIREG,d0
        clr.b 0(a0,d0.w)
        bsr sync_beam
        move.w #$ffff,14(a4)
        move.w 6(a6),12(a4)
        move.w 8(a4),d0
        lea continuous_delay_end(pc),a2
        add.w d0,d0
        suba.w d0,a2
        moveq #$11,d1
        cmpi.w #7,(a4)
        beq.s .cascade
        cmpi.w #8,(a4)
        beq.s .cascade
        cmpi.w #12,(a4)
        bne.s .phi2
.cascade: moveq #$51,d1
.phi2:  moveq #$11,d0
        move.b d0,$f00(a1)
        move.b d1,0(a0,d5.w)
        cmpi.w #12,(a4)
        bne.s .continuous_mode
        moveq #$19,d0
.continuous_mode:
        move.b d0,0(a0,d4.w)
        cmpi.w #8,(a4)
        bne.s .short_delay
        move.l #$0001fedc,d0
        divu.w #$1234,d0
.short_delay:
        jmp (a2)
        rept 128
        nop
        endr
continuous_delay_end:
        cmpi.w #9,(a4)
        bne.s .freeze
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,20(a4)
        moveq #0,d0
        move.b d0,$f00(a1)
.freeze:
        moveq #0,d0
        move.b d0,0(a0,d4.w)
        rept 16
        nop
        endr
        andi.b #$40,d1
        move.b d1,0(a0,d5.w)
        cmpi.w #9,(a4)
        beq.s .reference_stopped
        move.b d0,$f00(a1)
.reference_stopped:
        rept 16
        nop
        endr
        cmpi.w #9,(a4)
        beq.s .live_recorded
        move.b 0(a0,d2.w),d0
        move.w d0,20(a4)
.live_recorded:
        move.w 6(a6),16(a4)
        move.b $d00(a0),d0
        move.w d0,22(a4)
        moveq #0,d0
        move.b 0(a0,d3.w),d0
        lsl.w #8,d0
        move.b 0(a0,d6.w),d0
        move.w d0,34(a4)
        bsr read_reference
        move.w d0,18(a4)
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,36(a4)
        move.b 0(a0,d3.w),d0
        lsl.w #8,d0
        move.b 0(a0,d6.w),d0
        move.w d0,38(a4)
        rts
timer_trial:
        bsr select_target
        move.w LOREG,d2
        move.w HIREG,d3
        move.w CONTROL,d4
        moveq #40,d0
        cmpi.w #4,(a4)
        bne.s .period_latch
        moveq #3,d0
.period_latch:
        cmpi.w #2,(a4)
        bne.s .latch
        move.w 8(a4),d0
.latch: move.b d0,0(a0,d2.w)
        clr.b 0(a0,d3.w)
        bsr sync_beam
        cmpi.w #3,(a4)
        bne.s .race_setup
        move.b #$19,0(a0,d4.w)
        moveq #32,d0
        bsr delay
        tst.w 4(a4)
        bne.s .transition1
        clr.b 0(a0,d4.w)
        bra.s .race_setup
.transition1:
        cmpi.w #2,4(a4)
        bne.s .transition3
        move.b #8,0(a0,d4.w)
.transition3:
        cmpi.w #3,4(a4)
        bne.s .race_setup
        move.b #8,0(a0,d4.w)
.race_setup:
        cmpi.w #4,(a4)
        bne.s .ready
        tst.w 4(a4)
        beq.s .ready
        moveq #1,d0
        btst #0,3(a4)
        beq.s .mask
        moveq #2,d0
.mask:  ori.b #$80,d0
        move.b d0,$d00(a0)
.ready: bsr read_reference
        move.w d0,14(a4)
        move.w 6(a6),12(a4)
        move.w 8(a4),d0
        cmpi.w #2,(a4)
        bne.s .tap
        moveq #64,d0
.tap:   lea post_end(pc),a2
        add.w d0,d0
        suba.w d0,a2
        moveq #$19,d0
        cmpi.w #1,(a4)
        bne.s .period_control
        tst.w 4(a4)
        bne.s .period_control
        moveq #9,d0
.period_control:
        cmpi.w #2,(a4)
        bne.s .transition_control
        tst.w 4(a4)
        beq.s .transition_control
        moveq #$11,d0
.transition_control:
        cmpi.w #3,(a4)
        bne.s .start
        tst.w 4(a4)
        bne.s .load_running
        moveq #1,d0
        bra.s .start
.load_running:
        cmpi.w #1,4(a4)
        bne.s .auto_start
        moveq #$11,d0
        bra.s .start
.auto_start:
        cmpi.w #3,4(a4)
        bne.s .start
        clr.b 0(a0,d3.w)
        bra.s .post
.start: move.b d0,0(a0,d4.w)
.post:  moveq #0,d0
        jmp (a2)
        rept 64
        nop
        endr
post_end:
        cmpi.w #4,(a4)
        beq.s race_observe
        move.b 0(a0,d2.w),d0
        move.w d0,20(a4)
        move.w 6(a6),16(a4)
        move.b $d00(a0),d0
        move.w d0,22(a4)
        bra.s timer_finish
race_observe:
        tst.w 4(a4)
        bne.s .clear_mask
        moveq #1,d0
        btst #0,3(a4)
        beq.s .enable
        moveq #2,d0
.enable: ori.b #$80,d0
        move.b d0,$d00(a0)
        bra.s .read
.clear_mask:
        cmpi.w #2,4(a4)
        bne.s .read
        moveq #1,d0
        btst #0,3(a4)
        beq.s .disable
        moveq #2,d0
.disable: move.b d0,$d00(a0)
.read:  moveq #0,d0
        move.w $1e(a6),34(a4)
        move.b $d00(a0),d0
        move.w d0,22(a4)
        move.w 6(a6),16(a4)
        move.b 0(a0,d2.w),d0
        move.w d0,20(a4)
        move.b $d00(a0),d0
        move.w d0,38(a4)
timer_finish:
        moveq #0,d0
        move.b 0(a0,d2.w),d0
        move.w d0,36(a4)
        bsr read_reference
        move.w d0,18(a4)
        rts
interrupt_trial:
        ; delay encodes DMA (0..2) plus memory (0/4). Record remains explicit.
        btst #2,9(a4)
        beq.s .chip_code
        tst.b slow_present
        bne.s .slow_code
        move.w #2,32(a4)
        rts
.slow_code: move.l #$c00000,RUNBASE
        bra.s .code_ready
.chip_code: move.l #kernels,RUNBASE
.code_ready:
        lea $bfd000,a0
        move.l a0,REF
        move.b #$ff,$600(a0)
        move.b #$ff,$700(a0)
        move.b #$11,$f00(a0)
        move.w #$2c81,$8e(a6)
        move.w #$f4c1,$90(a6)
        move.w #$38,$92(a6)
        move.w #$d0,$94(a6)
        clr.w $108(a6)
        clr.w $10a(a6)
        lea $e0(a6),a0
        move.l #$10000,d0
        moveq #3,d1
.bpl:   move.l d0,(a0)+
        addi.l #$3000,d0
        dbra d1,.bpl
        move.w 8(a4),d0
        andi.w #3,d0
        beq.s .no_bpl
        move.w #$1200,$100(a6)
        cmpi.w #2,d0
        bne.s .enable_bpl
        move.w #$4200,$100(a6)
.enable_bpl: move.w #$8300,$96(a6)
.no_bpl:
        move.w #1,EXPECT(a5)
        cmpi.w #2,2(a4)
        bne.s .copper
        move.w #2,EXPECT(a5)
.copper:
        cmpi.w #3,2(a4)
        bne.s .timers
        lea copper_list(pc),a0
        move.w 6(a4),d0
        add.w d0,d0
        cmpi.w #5,4(a4)
        bcs.s .wait_phase
        moveq #0,d0
.wait_phase:
        ori.w #$6041,d0
        move.w d0,(a0)
        move.l a0,$80(a6)
        move.w #0,$88(a6)
        move.w #$8280,$96(a6)
.timers:
        move.w 6(a4),d0
        addi.w #24,d0
        move.b d0,$bfe401
        clr.b $bfe501
        move.b d0,$bfd400
        clr.b $bfd500
        cmpi.w #2,2(a4)
        bne.s .masks
        move.b #$4f,$bfe401
        move.b #2,$bfe501
        move.b #$ff,$bfd400
        move.b #1,$bfd500
.masks:
        move.b #$81,$bfed01
        move.b #$81,$bfdd00
        move.w #$e02c,$9a(a6)
        bsr sync_beam
        bsr read_reference
        move.w d0,14(a4)
        move.w 6(a6),12(a4)
        move.w #$7fff,$9c(a6)
        move.w 2(a4),d0
        cmpi.w #3,d0
        beq.s .dispatch
        cmpi.w #1,d0
        beq.s .only_b
        move.b #$19,$bfee01
.only_b:
        tst.w d0
        beq.s .dispatch
        move.b #$19,$bfde00
.dispatch:
        move.w 4(a4),d0
        add.w d0,d0
        lea kernel_offsets(pc),a0
        move.w 0(a0,d0.w),d0
        move.l RUNBASE,a0
        adda.w d0,a0
        jsr (a0)
        move.w #$2700,sr
        move.w 6(a6),16(a4)
        bsr read_reference
        move.w d0,18(a4)
        move.w EVBEAM(a5),24(a4)
        move.w EVLEVEL(a5),26(a4)
        move.l EVPC(a5),d0
        sub.l RUNBASE,d0
        move.l d0,28(a4)
        move.w EVCOUNT(a5),34(a4)
        cmpi.w #5,4(a4)
        bcs.s .normal_aux
        move.w 20(a5),34(a4)
.normal_aux:
        move.w EVBEAM2(a5),36(a4)
        move.w EVLEVEL2(a5),38(a4)
        tst.w DONE(a5)
        bpl.s .ok
        move.w #1,32(a4)
.ok:    rts
kernel_offsets:
        dc.w k_stop-kernels,k_nop-kernels,k_load-kernels,k_store-kernels,k_div-kernels,k_phase-kernels,k_exg-kernels
kernels:
k_stop: stop #$2000
        tst.w DONE(a5)
        beq.s k_stop
        rts
k_nop:  move.w #$2000,sr
.loop:  nop
        tst.w DONE(a5)
        beq.s .loop
        rts
k_load: move.w #$2000,sr
.loop:  movem.l $6000,d0-d3
        tst.w DONE(a5)
        beq.s .loop
        rts
k_store: move.w #$2000,sr
.loop:  movem.l d0-d3,$6000
        tst.w DONE(a5)
        beq.s .loop
        rts
k_div:  move.w #$2000,sr
.loop:  move.l #$12345678,d0
        divu.w #$1234,d0
        tst.w DONE(a5)
        beq.s .loop
        rts
; Both kernels execute a RAM beam read then a phase sweep before STOP.
; EXG adds six CPU clocks (three CCK), unlike a NOP's four (two CCK).
k_phase:
        move.w 6(a6),20(a5)
        move.w 6(a4),d0
        lea phase_end-k_phase(a0),a1
        add.w d0,d0
        suba.w d0,a1
        jmp (a1)
        rept 16
        nop
        endr
phase_end:
        stop #$2000
        tst.w DONE(a5)
        beq.s phase_end
        rts
k_exg:
        move.w 6(a6),20(a5)
        move.w 6(a4),d0
        lea exg_end-k_exg(a0),a1
        add.w d0,d0
        suba.w d0,a1
        jmp (a1)
        rept 16
        nop
        endr
exg_end:
        exg d0,d1
        stop #$2000
        tst.w DONE(a5)
        beq.s exg_end
        rts
kernels_end:
irq1:   move.w 6(a6),EVBEAM2(a5)
        move.w #$2700,sr
        movem.l d0-d1/a0,-(sp)
        moveq #1,d0
        bra.s irq_common
irq2:   move.w 6(a6),EVBEAM2(a5)
        move.w #$2700,sr
        movem.l d0-d1/a0,-(sp)
        moveq #2,d0
        bra.s irq_common
irq6:   move.w 6(a6),EVBEAM2(a5)
        move.w #$2700,sr
        movem.l d0-d1/a0,-(sp)
        moveq #6,d0
irq_common:
        tst.w EVCOUNT(a5)
        bne.s .second
        move.w EVBEAM2(a5),EVBEAM(a5)
        move.w d0,EVLEVEL(a5)
        move.l 14(sp),EVPC(a5)
.second:
        move.w d0,EVLEVEL2(a5)
        addq.w #1,EVCOUNT(a5)
        tst.b $bfed01
        tst.b $bfdd00
        move.w #$200c,$9c(a6)
        move.w EVCOUNT(a5),d0
        cmp.w EXPECT(a5),d0
        bcs.s .more
        move.w #1,DONE(a5)
.more:  movem.l (sp)+,d0-d1/a0
        rte
irq3:   addq.w #1,WATCHDOG(a5)
        cmpi.w #3,WATCHDOG(a5)
        bcs.s .ack
        move.w #-1,DONE(a5)
.ack:   move.w #$20,$9c(a6)
        rte
fault:
        movem.l d0-d7/a0-a7,$3110
        move.l sp,a0
        move.w #$2700,sr
        move.l #$7f000,sp
        lea $3150,a1
        moveq #7,d0
.stack: move.l (a0)+,(a1)+
        dbra d0,.stack
        move.l #$41354641,$3100
        move.l #$554c5431,$3104
        move.w $303c,$3108
        clr.w $310a
        clr.l $310c
        clr.l $3170
        clr.l $3174
        clr.l $3178
        cmpa.l #RESULT+64,a4
        bcs.s .no_descriptor
        cmpa.l #RESULT+64+TRIAL_COUNT*40,a4
        bcc.s .no_descriptor
        move.l (a4),$3170
        move.l 4(a4),$3174
        move.l 8(a4),$3178
.no_descriptor:
        move.w $dff006,$317c
        clr.w $317e
        lea 0,a0
        lea $3180,a1
        moveq #31,d0
.vecdump: move.l (a0)+,(a1)+
        dbra d0,.vecdump
        movea.l #kernels,a0
        lea $3200,a1
        moveq #31,d0
.codedump: move.l (a0)+,(a1)+
        dbra d0,.codedump
        lea VARS,a0
        lea $3280,a1
        moveq #31,d0
.vardump: move.l (a0)+,(a1)+
        dbra d0,.vardump
        lea $3100,a0
        moveq #127,d1
        moveq #0,d0
.checksum: add.l (a0)+,d0
        dbra d1,.checksum
        neg.l d0
        move.l d0,$310c
        move.l #$3100,$3080
        move.l #$3300,$3084
        move.w #$f00,$dff180
        jsr stream_results
.halt:  bra.s .halt
fault_vectors:
fault_index set 2
        rept 46
        move.w #fault_index,($303c).l
        jmp fault
fault_index set fault_index+1
        endr
copper_list:
        dc.w $6041,$fffe,$009c,$8004,$ffff,$fffe
slow_present: dc.b 0
        even
; RBCP begins only after the complete, checksum-protected RAM capture exists.
stream_results:
        move.w #$2700,sr
        jsr quiet
        lea CONFIG_RBCP_SCRATCH_BASE,a0
        moveq #7,d0
.scratch: clr.l (a0)+
        dbra d0,.scratch
        bsr rbcp_reset
        bsr rbcp_cmd_enter_cmd_resp
        tst.b d0
        bne transport_fault
        bsr rbcp_check_protocol_version
        tst.b d0
        bne transport_fault
        bsr rbcp_cmd_get_pipe_cap
        tst.b d0
        bne transport_fault
        moveq #1,d0
        moveq #0,d1
        bsr rbcp_read_data
        moveq #0,d5
        move.b CONFIG_RBCP_DATA_BUF,d5
        moveq #0,d6
.pipe:  cmp.w d5,d6
        bcc transport_fault
        move.w d6,d0
        bsr rbcp_cmd_get_pipe_info
        tst.b d0
        bne.s .next
        moveq #2,d0
        moveq #0,d1
        bsr rbcp_read_data
        btst #0,CONFIG_RBCP_DATA_BUF+RBCP_PIPE_INFO_FLAGS
        bne.s .found
.next:  addq.w #1,d6
        bra.s .pipe
.found: move.b d6,PIPE
        lea begin_text(pc),a0
        bsr send_text
        move.l $3080,STREAM_PTR
        move.l $3084,STREAM_END
        moveq #0,d6
.byte:  move.l STREAM_PTR,a0
        cmpa.l STREAM_END,a0
        bcc.s .ended
        moveq #0,d4
        move.b (a0)+,d4
        move.l a0,STREAM_PTR
        move.w d4,d0
        lsr.w #4,d0
        bsr send_hex
        move.w d4,d0
        andi.w #15,d0
        bsr send_hex
        addq.w #1,d6
        andi.w #31,d6
        bne.s .byte
        moveq #10,d0
        bsr send_char
        bra.s .byte
.ended: lea end_text(pc),a0
        bsr send_text
        rts
send_hex:
        addi.b #'0',d0
        cmpi.b #'9',d0
        bls.s send_char
        addq.b #7,d0
send_char:
        movem.l d0-d3/a0-a1,-(sp)
        move.b d0,RBCP_ARG0
        move.w #$ffff,d3
.retry: moveq #1,d0
        moveq #0,d1
        move.b PIPE,d1
        bsr rbcp_cmd_pipe_write
        tst.b d0
        beq.s .sent
        ; Restore the payload: protocol scratch may be changed on failure.
        move.l (sp),d0
        move.b d0,RBCP_ARG0
        dbra d3,.retry
        bra transport_fault
.sent:  movem.l (sp)+,d0-d3/a0-a1
        rts
send_text:
        moveq #0,d0
        move.b (a0)+,d0
        beq.s .end
        bsr send_char
        bra.s send_text
.end:   rts
transport_fault:
        move.w #$f0f,$dff180
        bra.s transport_fault
begin_text: dc.b 10,"A5RBCP-BEGIN",10,0
end_text: dc.b 10,"A5RBCP-END",10,0
        even
        include "rbcp.s"
header:
        dc.b "A5RBCP01"
        dc.w 1,40
        dc.l 0,0,0
        include "source_id.i"
        dc.w 0,0,0,0
        include "trials.i"
        include "line_c_cross_presets.i"
        include "line_c_word_presets.i"
        include "line_c_tomography_presets.i"
        include "line_c_onset_presets.i"
; Kind42 uses the same six-word C preset layout as kind41. The third word is
; ADAT; CDAT/BDAT are explicitly zero, and the C memory fill is independent.
line_c_read_sequence_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.read_clear_d: move.w d0,(a0)+
        dbra d7,.read_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #2,d0
        move.w d0,d1
        lsl.w #1,d0
        add.w d1,d0
        movea.l #line_c_read_sequence_presets,a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        move.w (a0)+,d7
        move.w (a0)+,d2
        move.w d5,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        lea $16000,a0
        move.w #1023,d1
.read_fill_b: clr.w (a0)+
        dbra d1,.read_fill_b
        lea $11000,a0
        move.w #1023,d1
.read_fill_c: clr.w (a0)+
        dbra d1,.read_fill_c
        move.w d3,$11000
        move.w d4,$11050
        move.w d2,$40(a6)
        move.w d7,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        lea $58(a6),a1
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        jsr sync_beam
        move.w d6,d5
        moveq #0,d0
        move.w 4(a4),d0
        beq.s .read_early
        movea.l #$ff7500,a2
        bra.s .read_observer_ready
.read_early:
        movea.l #$ff7400,a2
.read_observer_ready:
        jsr (a2)
        move.l (sp)+,d7
        rts

        include "line_c_read_sequence_presets.i"
        even

; Kind44 repeats kind42's inputs with an explicit normal-mode A/B/C/D blit
; before the line blit in the primed variant. This seeds all three fetched
; source channels through real DMA before changing to line mode.
line_c_activity_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.activity_clear_d: move.w d0,(a0)+
        dbra d7,.activity_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #2,d0
        move.w d0,d1
        lsl.w #1,d0
        add.w d1,d0
        movea.l #line_c_activity_presets,a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        move.w (a0)+,d7
        move.w (a0)+,d2
        move.w #0,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        lea $12000,a0
        moveq #0,d0
        move.w #7,d1
.activity_fill_a: move.w d0,(a0)+
        dbra d1,.activity_fill_a
        lea $16000,a0
        moveq #0,d0
        move.w #7,d1
.activity_fill_b: move.w d0,(a0)+
        dbra d1,.activity_fill_b
        lea $11000,a0
        move.w #7,d1
.activity_fill_c: move.w d0,(a0)+
        dbra d1,.activity_fill_c
        lea $17000,a0
        moveq #0,d0
        move.w #7,d1
.activity_clear_prime_d: move.w d0,(a0)+
        dbra d1,.activity_clear_prime_d
        move.w d2,$40(a6)
        move.w d7,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #0,$64(a6)
        move.w #0,$62(a6)
        move.w #0,$60(a6)
        move.w #0,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #$12000,$50(a6)
        move.l #$17000,$54(a6)
        btst #0,4(a4)
        beq.s .activity_unprimed
        move.w #$0fca,$40(a6)
        move.w #0,$42(a6)
        move.w #$8240,$96(a6)
        move.w #$0088,$58(a6)
.activity_prime_busy: btst #6,$02(a6)
        beq.s .activity_prime_busy
.activity_prime_done: btst #6,$02(a6)
        bne.s .activity_prime_done
.activity_unprimed:
        move.w d5,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        move.w d3,$11000
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        move.w d2,$40(a6)
        move.w d7,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        lea $58(a6),a1
        jsr sync_beam
        move.w d6,d5
        movea.l #$ff7600,a2
        cmpi.w #1,8(a4)
        beq.s .activity_poll_observer
        bra.s .activity_observer_ready
.activity_poll_observer:
        movea.l #$ff7700,a2
.activity_observer_ready:
        jsr (a2)
        move.l (sp)+,d7
        rts

        include "line_c_activity_presets.i"
        even

; Kind45 repeats kind42's inputs after a selected normal-mode A/B/C/D blit.
; Its literal source patterns exercise full, partial and zero DMA histories
; before the unchanged line-mode observer begins.
line_c_history_trial:
        move.l d7,-(sp)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.history_clear_d: move.w d0,(a0)+
        dbra d7,.history_clear_d
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #2,d0
        move.w d0,d1
        lsl.w #1,d0
        add.w d1,d0
        movea.l #line_c_history_presets,a0
        adda.w d0,a0
        move.w (a0)+,d3
        move.w (a0)+,d4
        move.w (a0)+,d5
        move.w (a0)+,d6
        move.w (a0)+,d7
        move.w (a0)+,d2
        move.w #0,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        moveq #0,d0
        move.w 4(a4),d0
        move.w d0,d1
        lsl.w #1,d0
        add.w d1,d0
        lsl.w #1,d0
        lea line_c_history_patterns,a2
        adda.w d0,a2
        move.w (a2)+,d1
        lea $12000,a0
        moveq #7,d0
.history_fill_a: move.w d1,(a0)+
        dbra d0,.history_fill_a
        move.w (a2)+,d1
        lea $16000,a0
        moveq #7,d0
.history_fill_b: move.w d1,(a0)+
        dbra d0,.history_fill_b
        move.w (a2)+,d1
        lea $11000,a0
        moveq #7,d0
.history_fill_c: move.w d1,(a0)+
        dbra d0,.history_fill_c
        lea $17000,a0
        moveq #0,d0
        move.w #7,d1
.history_clear_prime_d: move.w d0,(a0)+
        dbra d1,.history_clear_prime_d
        move.w d2,$40(a6)
        move.w d7,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #0,$64(a6)
        move.w #0,$62(a6)
        move.w #0,$60(a6)
        move.w #0,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #$12000,$50(a6)
        move.l #$17000,$54(a6)
        tst.w 4(a4)
        beq.s .history_unprimed
        move.w #$0fca,$40(a6)
        move.w #0,$42(a6)
        move.w #$8240,$96(a6)
        move.w #$0088,$58(a6)
.history_prime_busy: btst #6,$02(a6)
        beq.s .history_prime_busy
.history_prime_done: btst #6,$02(a6)
        bne.s .history_prime_done
.history_unprimed:
        moveq #0,d0
        lea $17000,a0
        moveq #7,d1
.history_clear_prime_d_after: move.w d0,(a0)+
        dbra d1,.history_clear_prime_d_after
        lea $11000,a0
        moveq #7,d1
.history_reset_c: move.w d0,(a0)+
        dbra d1,.history_reset_c
        move.w d3,$11000
        move.w d5,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        move.w d3,$11000
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        move.w d2,$40(a6)
        move.w d7,$42(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        lea $58(a6),a1
        jsr sync_beam
        move.w d6,d5
        movea.l #$ff7600,a2
        cmpi.w #1,8(a4)
        beq.s .history_poll_observer
        bra.s .history_observer_ready
.history_poll_observer:
        movea.l #$ff7700,a2
.history_observer_ready:
        jsr (a2)
        move.l (sp)+,d7
        rts

        include "line_c_history_presets.i"
        include "line_c_history_patterns.i"
        even

; Kind46 writes a selected CPU word to chip or slow RAM immediately after
; BLTSIZE, then samples eight consecutive DMACONR words. Its source channels
; remain zero, and the two scratch destinations are outside the D area.
line_c_bus_data_trial:
        move.l a3,-(sp)
        move.l d7,-(sp)
        move.w 6(a4),-(sp)
        clr.w 6(a4)
        move.w #$7fff,$96(a6)
        lea $10000,a0
        moveq #0,d0
        move.w #1023,d7
.bus_data_clear_d: move.w d0,(a0)+
        dbra d7,.bus_data_clear_d
        lea $12000,a0
        moveq #7,d7
.bus_data_clear_a: move.w d0,(a0)+
        dbra d7,.bus_data_clear_a
        lea $16000,a0
        moveq #7,d7
.bus_data_clear_b: move.w d0,(a0)+
        dbra d7,.bus_data_clear_b
        lea $11000,a0
        move.w #81,d7
.bus_data_clear_c: move.w d0,(a0)+
        dbra d7,.bus_data_clear_c
        move.w d0,$11050
        move.w #$8000,$74(a6)
        move.w #0,$72(a6)
        move.w #0,$70(a6)
        move.w #$ffff,$44(a6)
        move.w #$ffff,$46(a6)
        move.w #-280,$64(a6)
        move.w #0,$62(a6)
        move.w #80,$60(a6)
        move.w #80,$66(a6)
        move.l #$11000,$48(a6)
        move.l #$16000,$4c(a6)
        move.l #-80,$50(a6)
        move.l #$10000,$54(a6)
        move.w 2(a4),d0
        lsl.w #8,d0
        lsl.w #4,d0
        ori.w #$0bca,d0
        move.w d0,$40(a6)
        move.w #$0001,$42(a6)
        move.w #$7fff,$96(a6)
        move.w #$8240,$96(a6)
        lea $58(a6),a1
        move.w #$0082,d5
        jsr sync_beam
        move.w 4(a4),d0
        add.w d0,d0
        lea line_c_bus_data_patterns,a2
        adda.w d0,a2
        move.w (a2),d3
        move.w (sp),d0
        lsl.w #2,d0
        lea line_c_bus_data_regions,a3
        adda.w d0,a3
        movea.l (a3),a3
        movea.l #$ff7800,a2
        jsr (a2)
        move.w (sp)+,6(a4)
        move.l (sp)+,d7
        move.l (sp)+,a3
        rts

        include "line_c_bus_data_patterns.i"
        include "line_c_bus_data_regions.i"
        even

        include "copper_wait_kernel.i"
        include "copper_start_busy_kernel.i"

; Kind 43: masked Copper COPER request visibility and straight-line CPU IPL observations.
irq_focus_trial:
        move.l #divirq_handler,$6c
        clr.l $3100
        lea $3100,a1
        moveq #0,d4
        moveq #0,d0
        move.w 2(a4),d0
        lsl.w #8,d0
        lsl.w #2,d0
        addi.l #$f95000,d0
        move.l d0,a0
        lea $6000,a2
        move.l #$42c1fffe,(a2)+
        move.l #$009c8010,(a2)+
        move.l #$fffffffe,(a2)+
        move.l #$6000,$80(a6)
        move.w #$8280,$96(a6)
        move.w #$c010,$9a(a6)
        jsr sync_beam
        move.w #0,$88(a6)
        move.w #$0010,$9c(a6)
        tst.w 2(a4)
        beq.s .masked
        move.w #$2000,sr
.masked:
        jsr $fb0000
        jsr (a0)
        move.w #$2700,sr
        move.w d6,12(a4)
        move.w 6(a6),16(a4)
        move.w d4,38(a4)
        tst.w 2(a4)
        beq.s .done
        tst.w DONE(a5)
        bne.s .done
        move.w #1,32(a4)
.done:
        move.l #irq3,$6c
        rts

        even
        include "line_a_bit_kernel.i"

        even
        include "blitter_handoff_kernel.i"
