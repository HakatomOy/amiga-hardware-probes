; SPDX-License-Identifier: MIT
; All measured code and data reside in RAM. No RBCP commands during collection.
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
        bsr stream_results
        move.w #$0ff,CUSTOM+$180
.idle:  stop #$2700
        bra.s .idle
main:
        lea CUSTOM,a6
        lea VARS,a5
        lea fault_vectors(pc),a0
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
        lea kernels(pc),a0
        lea $c00000,a1
        move.w #(kernels_end-kernels)/2-1,d0
.slow_copy: move.w (a0)+,(a1)+
        dbra d0,.slow_copy
.no_slow:
        lea header(pc),a0
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
        lea trials(pc),a3
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
        lea kernels(pc),a0
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
        bsr stream_results
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
        bsr quiet
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
        even
