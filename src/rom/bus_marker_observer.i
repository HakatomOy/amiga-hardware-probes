; Fixed ROM critical path; all records stored after the eight raw reads.
bus_marker_observer:
        move.w 6(a4),d0
        lsl.w #2,d0
        addi.w #$0040,d0
        move.w d0,d6
        lea .sample(pc),a3
        btst #1,5(a4)
        beq.s .poll_start
        lea .cpu_launch(pc),a3
        lea $009c(a6),a0
        move.w #$8010,d4
        lea $0058(a6),a1
        move.w #$0041,d5
        tst.w 2(a4)
        beq.s .cpu_size_ready
        move.w #$0050,d5
.cpu_size_ready:
        btst #3,5(a4)
        beq.s .cpu_control_ready
        lea $01fe(a6),a1
        moveq #0,d5
.cpu_control_ready:
        btst #2,5(a4)
        beq.s .poll_start
        exg a0,a1
        exg d4,d5
.poll_start:
        move.w #$7fff,d3
.poll:
        move.w $006(a6),d7
        move.w d7,d0
        andi.w #$ff00,d0
        cmpi.w #$4200,d0
        bne.s .next
        move.w d7,d0
        andi.w #$00ff,d0
        cmp.w d6,d0
        bcc.s .ready
.next:
        dbra d3,.poll
        move.w #$ffff,12(a4)
        move.w #$ffff,14(a4)
        rts
.ready:
        move.w d7,a2
        jmp (a3)
.cpu_launch:
        move.w d4,(a0)
        move.w d5,(a1)
.sample:
        move.w $01e(a6),d0
        move.w $002(a6),d1
        move.w $01e(a6),d2
        move.w $002(a6),d3
        move.w $01e(a6),d4
        move.w $002(a6),d5
        move.w $01e(a6),d6
        move.w $002(a6),d7
        move.w $006(a6),a3
        movem.w d0-d7,20(a4)
        move.w a2,12(a4)
        move.w a3,14(a4)
        rts
