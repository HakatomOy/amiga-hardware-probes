; SPDX-License-Identifier: MIT
        include "rom_layout.i"
        org $f80000
        dc.w $1114,$4ef9
        dc.l boot
        dcb.b $d0-(*-$f80000),0
        reset
boot:
        move.w #$2700,sr
        move.b #3,$bfe201
        move.b #2,$bfe001
        move.l #$7f000,sp
        move.w #$7fff,$dff09a
        move.w #$7fff,$dff096
        move.w #$7fff,$dff09c
        move.w #$0200,$dff100
        move.w #$00f,$dff180
        lea 0,a0
        move.w #32767,d0
.clear: clr.l (a0)+
        dbra d0,.clear
        lea payload(pc),a0
        lea $20000,a1
        move.w #(PAYLOAD_BYTES/4)-1,d0
.copy:  move.l (a0)+,(a1)+
        dbra d0,.copy
        jmp $20000
        even
payload:
        incbin "experiment.bin"
        dcb.b $7fc00-(*-$f80000),0
        ; Interrupt acknowledge reads at $FFFFF0 + level*2 must return
        ; the standard 68000 vector number. Commands use addresses only,
        ; so these data words may coexist with the RBCP command page.
        dcb.b 1008,0
        dc.w $18,$19,$1a,$1b,$1c,$1d,$1e,$1f
