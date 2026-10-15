; SPDX-License-Identifier: MIT
; Single-event IRQ probes: no polling loop in the timed tail.
        dcb.b $f95000-*,0
irq_focus_0:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        move.w 6(a6),d1
        move.w $1e(a6),d0
        move.w 6(a6),d2
        move.w d1,14(a4)
        move.w d0,20(a4)
        move.w d2,36(a4)
        rts
        dcb.b $f95400-*,0
irq_focus_1:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        nop
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f95800-*,0
irq_focus_2:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        moveq #7,d0
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f95c00-*,0
irq_focus_3:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        exg d0,d1
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f96000-*,0
irq_focus_4:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        tst.w d0
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f96400-*,0
irq_focus_5:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        tst.w (a1)
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f96800-*,0
irq_focus_6:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        tst.w 0(a1)
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f96c00-*,0
irq_focus_7:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        tst.l (a1)
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f97000-*,0
irq_focus_8:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        divu.w d3,d0
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f97400-*,0
irq_focus_9:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #-3,d3
.target:
        divs.w d3,d0
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
        dcb.b $f97800-*,0
irq_focus_10:
        move.w 6(a6),d6
        moveq #0,d0
        move.w 8(a4),d0
        add.w d0,d0
        lea .delay_end(pc),a2
        suba.w d0,a2
        jmp (a2)
        rept 96
        nop
        endr
.delay_end:
        moveq #100,d0
        moveq #7,d1
        moveq #3,d3
.target:
        stop #$2000
.after_target:
        moveq #1,d4
.after_marker:
        rept 128
        nop
        endr
        move.w #$2700,sr
        move.l d0,20(a4)
        rts
