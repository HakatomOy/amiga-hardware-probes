; Kinds 52/53: serial completion and PB6 output against actual TA underflows.
; Target 0/1 selects CIA-A/B. Timer B counts TA underflows, not CPU delays.
cia_hardware_verify_trial:
        movem.l d0-d7/a0-a3,-(sp)
        lea $bfe001,a0
        tst.w 2(a4)
        beq.s .selected
        lea $bfd000,a0
.selected:
        clr.b $e00(a0)
        clr.b $f00(a0)
        move.b #$7f,$d00(a0)
        tst.b $d00(a0)
        move.b #$ff,$100(a0)
        clr.b $300(a0)
        cmpi.w #52,(a4)
        bne.s .pb_ddr
        move.b #$40,$e00(a0)
        move.b #1,$400(a0)
        clr.b $500(a0)
        clr.b $c00(a0)
        move.b #$51,$e00(a0)
        move.w #255,d0            ; drain old shift register + pending byte
.drain: dbra d0,.drain
        move.b #$40,$e00(a0)
        rept 32
        nop
        endr
        tst.b $d00(a0)
        bra.s .ddr_ready
.pb_ddr:
        btst #2,5(a4)
        beq.s .ddr_ready
        move.b #$ff,$300(a0)
.ddr_ready:
        moveq #0,d0
        move.b $100(a0),d0
        move.w d0,28(a4)           ; pin baseline before PBON selection
        moveq #0,d6
        cmpi.w #52,(a4)
        bne.s .pb_mode
        move.b #$40,d6             ; serial output, stopped
        bra.s .control_ready
.pb_mode:
        moveq #2,d6                ; PBON, pulse
        btst #0,5(a4)
        beq.s .pulse
        ori.b #4,d6                ; toggle
.pulse: btst #1,5(a4)
        beq.s .control_ready
        ori.b #8,d6                ; one-shot
.control_ready:
        move.b d6,d0
        andi.b #$f7,d0             ; prevent TAHI one-shot auto-start in setup
        move.b d0,$e00(a0)
        moveq #0,d0
        move.w 6(a4),d0            ; phase is latch index
        add.w d0,d0
        lea .latches(pc),a1
        move.w 0(a1,d0.w),d1
        move.b d1,$400(a0)
        lsr.w #8,d1
        move.b d1,$500(a0)
        move.b d6,$e00(a0)         ; select one-shot only after latch writes
        move.b #$ff,$600(a0)
        move.b #$ff,$700(a0)
        move.b #$51,$f00(a0)        ; TB START+LOAD, TA cascade
        rept 12
        nop
        endr
        moveq #0,d0
        move.b $100(a0),d0
        move.w d0,34(a4)           ; PB before START
        cmpi.w #52,(a4)
        bne.s .start
        move.b #$a5,$c00(a0)        ; one byte, queued before START
        btst #0,5(a4)
        beq.s .start
        move.b #$88,$d00(a0)        ; only SP may assert /IRQ
.start:
        tst.b $d00(a0)             ; acknowledge setup flags before measured START
        move.w 6(a6),30(a4)        ; pre-start beam, not a PC
        cmpi.w #54,(a4)
        bne.s .manual_start
        clr.b $500(a0)             ; stopped one-shot high-byte auto-start
        bra.s .released
.manual_start:
        move.b d6,d0
        ori.b #$11,d0
        move.b d0,$e00(a0)
.released:
        move.w 6(a6),12(a4)
        move.w 8(a4),d0
.delay: dbra d0,.delay
        moveq #0,d2
        move.b $700(a0),d2
        lsl.w #8,d2
        move.b $600(a0),d2
        move.w d2,14(a4)           ; UF bracket before observations
        move.w $1e(a6),24(a4)      ; raw INTREQ before ICR acknowledgement
        moveq #0,d3
        move.b $d00(a0),d3
        move.w d3,20(a4)
        moveq #0,d3
        move.b $100(a0),d3
        move.w d3,26(a4)           ; live PB pins
        move.w 6(a6),16(a4)
        moveq #0,d2
        move.b $700(a0),d2
        lsl.w #8,d2
        move.b $600(a0),d2
        move.w d2,18(a4)           ; UF bracket after observations
        move.b d6,$e00(a0)         ; stop, preserving PB/serial mode
        rept 16
        nop
        endr
        move.b #$40,$f00(a0)       ; stop TB without changing its source
        rept 12
        nop
        endr
        moveq #0,d0
        move.b $100(a0),d0
        move.w d0,22(a4)           ; settled PB, after pulse has expired
        moveq #0,d0
        move.b $500(a0),d0
        lsl.w #8,d0
        move.b $400(a0),d0
        move.w d0,36(a4)
        moveq #0,d0
        move.b $700(a0),d0
        lsl.w #8,d0
        move.b $600(a0),d0
        move.w d0,38(a4)           ; all TA underflows, including stop tail
        movem.l (sp)+,d0-d7/a0-a3
        rts
.latches: dc.w 0,1,3,15,200
