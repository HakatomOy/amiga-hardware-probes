; SPDX-License-Identifier: MIT
; Kickstart supplies A1 = open boot IORequest, A6 = ExecBase.
; Allocate rather than assuming an unused address in a 512K machine.
        include "layout.i"
        dc.b    "DOS",0
        dc.l    0,880
        move.l  a1,a3
        move.l  #PROGRAM_BYTES,d0
        move.l  #$10002,d1       ; MEMF_CLEAR | MEMF_CHIP
        jsr     -198(a6)         ; AllocMem
        tst.l   d0
        beq.s   failed
        move.l  d0,a4
        move.l  a3,a1
        move.w  #2,28(a1)        ; CMD_READ
        move.l  #PROGRAM_BYTES,36(a1)
        move.l  a4,40(a1)
        move.l  #1024,44(a1)
        jsr     -456(a6)         ; DoIO
        tst.l   d0
        bne.s   failed
        move.l  a3,a1
        jsr     (a4)
failed:
        move.w  #$7fff,$dff09a
        move.w  #$7fff,$dff096
        move.w  #$f00,$dff180
forever:
        bra.s   forever
