; Kind51: CIA-A Timer-A/PORTS, Copper COPER, and CIA-B Timer-A/EXTER while a
; 128-iteration ROM- or CHIP-resident loop executes with no DONE polling.
CIAEVLOOP equ 20
CIAEVPTR  equ 22
CIAEVICR  equ 26

cia_cpu_irq_trial:
        movem.l d0-d7/a0-a3,-(sp)
        move.l #$ffc900,$68         ; level 2: CIA-A PORTS
        move.l #$ffc940,$6c         ; level 3: Copper COPER
        move.l #$ffc980,$78         ; level 6: CIA-B EXTER
        clr.w DONE(a5)
        clr.w EVCOUNT(a5)
        clr.w WATCHDOG(a5)
        clr.w EVBEAM(a5)
        clr.w EVLEVEL(a5)
        clr.l EVPC(a5)
        clr.w CIAEVLOOP(a5)
        clr.w CIAEVPTR(a5)
        clr.w CIAEVICR(a5)

        move.w #$7fff,$96(a6)       ; disable all DMA while configuring
        move.w 2(a4),d0             ; CHIP-execution rows need an exact ROM copy
        btst #1,d0
        beq.s .observer_copy_done
        lea $ffc600,a0
        lea $1c000,a1
        move.w #$01ff,d0             ; exactly 512 words / 0x400 bytes
.observer_copy:
        move.w (a0)+,(a1)+
        dbra d0,.observer_copy
.observer_copy_done:
        move.w #$7fff,$9a(a6)       ; disable all custom interrupts
        move.w #$7fff,$9c(a6)       ; clear stale custom requests
        move.b #$7f,$bfed01         ; disable CIA-A ICR masks
        move.b #$7f,$bfdd00         ; disable CIA-B ICR masks
        tst.b $bfed01               ; clear old CIA-A ICR flags
        tst.b $bfdd00               ; clear old CIA-B ICR flags
        move.w #$0008,$9c(a6)       ; clear stale Paula PORTS request
        clr.b $bfee01               ; stop CIA-A Timer A
        clr.b $bfde00               ; stop CIA-B Timer A

        move.w 8(a4),d0
        addi.w #16,d0               ; CIA Timer-A latch: 16..31 E-clock ticks
        move.b d0,$bfe401
        clr.b $bfe501
        move.b d0,$bfd400
        clr.b $bfd500

        ; Copper control uses the same eventoffset index, encoded as a
        ; distinct line-65 CCK WAIT. Do not equate these units with CIA ECLK.
        move.l #$6000,a0
        move.w 8(a4),d0
        lsl.w #3,d0
        addi.w #$4151,d0            ; line65, hpos=$50+8*eventoffset, WAIT
        move.w d0,(a0)+
        move.w #$fffe,(a0)+
        move.w #$009c,(a0)+
        move.w #$8010,(a0)+        ; set INTREQ COPER
        move.l #$fffffffe,(a0)      ; terminate list
        move.l #$6000,$80(a6)

        lea $18100,a1               ; target stores occupy $18080..$180ff
        moveq #$5a,d0
        move.w 6(a4),d3
        clr.w 6(a4)                 ; fixed sync beam; phase is applied in ROM
        jsr sync_beam               ; line64 h>=$20
        move.w d3,6(a4)
        move.w 2(a4),d0             ; bit1 selects copied CHIP execution
        btst #1,d0
        bne.s .run_chip
        jsr $ffc600                ; fixed ROM release + no-poll loop
        bra.s .observer_return
.run_chip:
        jsr $1c000                 ; exact observer copy in chip RAM
.observer_return:
        move.w #$2700,sr
        move.w d3,12(a4)            ; VHPOSR immediately after source start
        move.w d2,14(a4)            ; VHPOSR immediately before source release
        move.w 6(a6),16(a4)         ; beam after the 128-iteration loop
        move.w CIAEVICR(a5),18(a4)  ; raw CIA-A ICR at first IRQ entry
        move.w CIAEVLOOP(a5),20(a4) ; DBRA remaining at IRQ entry
        move.w CIAEVPTR(a5),22(a4)  ; A1 low word at IRQ entry
        move.w EVBEAM(a5),24(a4)
        move.w EVLEVEL(a5),26(a4)
        move.w EVCOUNT(a5),34(a4)
        move.w d1,36(a4)            ; DBRA remaining after loop completion
        move.w a1,38(a4)            ; final A1 low word
        ; Normalize the stacked loop PC to the selected loop entry so ROM and
        ; CHIP execution can be compared without subtracting different bases.
        move.l EVPC(a5),d0
        move.w 2(a4),d1
        btst #1,d1
        bne.s .pc_chip
        btst #0,d1
        bne.s .pc_rom_move
        subi.l #$ffc700,d0
        bra.s .pc_ready
.pc_rom_move:
        subi.l #$ffc800,d0
        bra.s .pc_ready
.pc_chip:
        btst #0,d1
        bne.s .pc_chip_move
        subi.l #$0001c100,d0
        bra.s .pc_ready
.pc_chip_move:
        subi.l #$0001c200,d0
.pc_ready:
        move.l d0,28(a4)
        cmpi.w #1,EVCOUNT(a5)
        bne.s .no_irq
        clr.w 32(a4)                ; status 0: exactly one event observed
        bra.s .status_ready
.no_irq:
        move.w #1,32(a4)            ; status 1: event missed the finite loop
.status_ready:
        move.w #$7fff,$9a(a6)
        move.w #$7fff,$96(a6)
        move.w #$7fff,$9c(a6)
        tst.b $bfed01
        tst.b $bfdd00
        move.b #$7f,$bfed01
        move.b #$7f,$bfdd00
        move.w #$0008,$9c(a6)
        move.l #irq2,$68
        move.l #irq3,$6c
        move.l #irq6,$78
        movem.l (sp)+,d0-d7/a0-a3
        rts
