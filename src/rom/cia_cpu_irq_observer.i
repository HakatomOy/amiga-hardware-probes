; Kind51 fixed-ROM observer, included at FFC600 by edge_kernel.asm.
; Timed source release and both 128-iteration DBRA loops execute from ROM.
; Handler stubs are fixed at FFC900 (level 2), FFC940 (level 3), and
; FFC980 (level 6).
; edge_kernel.asm is assembled separately from experiment.asm, so give this
; translation unit the matching VARS offsets used by the trial-side kernel.
EVLEVEL    equ 2
EVCOUNT    equ 10
CIAEVLOOP  equ 20
CIAEVPTR   equ 22
CIAEVICR   equ 26

cia_cpu_irq_observer:
        moveq #127,d1               ; 128 DBRA iterations, no completion poll
        move.w #$7fff,$9c(a6)       ; clear stale PORTS/COPER requests
        move.w 4(a4),d0
        cmpi.w #1,d0
        beq.s .prep_copper
        cmpi.w #2,d0
        beq.s .prep_ciab
        move.b #$81,$bfed01         ; enable CIA-A Timer-A ICR flag
        move.w #$c008,$9a(a6)       ; master + PORTS, level 2
        bra.s .target_select
.prep_copper:
        move.w #$c010,$9a(a6)       ; master + COPER, level 3
        bra.s .target_select
.prep_ciab:
        move.b #$81,$bfdd00         ; enable CIA-B Timer-A ICR flag
        move.w #$e000,$9a(a6)       ; master + EXTER, level 6
.target_select:
        move.w 2(a4),d0
        andi.w #1,d0
        beq.s .target_nop
        lea cia_cpu_move_loop(pc),a2
        bra.s .phase_select
.target_nop:
        lea cia_cpu_nop_loop(pc),a2
.phase_select:
        lea .phase_table(pc),a0
        move.w 6(a4),d0
        andi.w #3,d0
        add.w d0,d0
        move.w 0(a0,d0.w),d0
        ext.l d0
        adda.l d0,a0
        jmp (a0)
.phase_table:
        dc.w .phase0-.phase_table,.phase1-.phase_table
        dc.w .phase2-.phase_table,.phase3-.phase_table
.phase0:
        bra.w .release
.phase1:
        nop
        bra.w .release
.phase2:
        nop
        nop
        bra.w .release
.phase3:
        nop
        nop
        nop
.release:
        move.w 4(a4),d0
        btst #0,d0
        bne.s .copper_release
        cmpi.w #2,d0
        beq.s .ciab_release
.cia_release:
        moveq #$5a,d0
        move.w 6(a6),d2             ; pre-start VHPOSR saved in D2 across IRQ
        move.b #$19,$bfee01         ; start + one-shot + force-load Timer A
        move.w 6(a6),d3             ; post-start VHPOSR, before enabling IRQs
        move.w #$2000,sr            ; enable level-2 interrupts at loop boundary
        jmp (a2)
.ciab_release:
        moveq #$5a,d0
        move.w 6(a6),d2             ; pre-start VHPOSR saved in D2 across IRQ
        move.b #$19,$bfde00         ; start CIA-B Timer A, one-shot + force-load
        move.w 6(a6),d3             ; post-start VHPOSR before enabling IRQs
        move.w #$2000,sr            ; allow level-6 EXTER
        jmp (a2)
.copper_release:
        moveq #$5a,d0
        move.w 6(a6),d2             ; pre-DMA-start VHPOSR saved in D2 across IRQ
        move.w #$8280,$96(a6)       ; SETCLR + master + Copper DMA
        move.w #0,$88(a6)           ; COPJMP1 starts the prepared WAIT list
        move.w 6(a6),d3             ; post-start VHPOSR, before enabling IRQs
        move.w #$2000,sr            ; enable level-3 interrupts at loop boundary
        jmp (a2)

        dcb.b $ffc700-*,0
cia_cpu_nop_loop:
        nop
        dbra d1,cia_cpu_nop_loop
        bra.w cia_cpu_loop_done
        dcb.b $ffc800-*,0
cia_cpu_move_loop:
        move.b d0,-(a1)
        dbra d1,cia_cpu_move_loop
        bra.w cia_cpu_loop_done
cia_cpu_loop_done:
        move.w #$2700,sr
        rts

        dcb.b $ffc900-*,0
cia_cpu_irq2:
        move.w 6(a6),EVBEAM(a5)     ; timestamp before pushing registers
        move.l 2(sp),EVPC(a5)
        move.w d1,CIAEVLOOP(a5)
        move.w a1,CIAEVPTR(a5)
        move.w #2,EVLEVEL(a5)
        addq.w #1,EVCOUNT(a5)
        movem.l d0,-(sp)
        moveq #0,d0
        move.b $bfed01,d0           ; one-shot CIA-A ICR read acknowledges Timer A
        move.w d0,CIAEVICR(a5)
        move.w #$0008,$9c(a6)       ; clear Paula PORTS request after ICR read
        move.w #$0008,$9a(a6)       ; disable this source before RTE
        movem.l (sp)+,d0
        rte

        dcb.b $ffc940-*,0
cia_cpu_irq3:
        move.w 6(a6),EVBEAM(a5)     ; timestamp before pushing registers
        move.l 2(sp),EVPC(a5)
        move.w d1,CIAEVLOOP(a5)
        move.w a1,CIAEVPTR(a5)
        move.w #3,EVLEVEL(a5)
        addq.w #1,EVCOUNT(a5)
        move.w #0,CIAEVICR(a5)
        move.w #$0010,$9c(a6)       ; clear COPER request
        move.w #$0010,$9a(a6)       ; disable this source before RTE
        rte

        dcb.b $ffc980-*,0
cia_cpu_irq6:
        move.w 6(a6),EVBEAM(a5)     ; timestamp before pushing registers
        move.l 2(sp),EVPC(a5)
        move.w d1,CIAEVLOOP(a5)
        move.w a1,CIAEVPTR(a5)
        move.w #6,EVLEVEL(a5)
        addq.w #1,EVCOUNT(a5)
        movem.l d0,-(sp)
        moveq #0,d0
        move.b $bfdd00,d0           ; CIA-B ICR read acknowledges Timer A
        move.w d0,CIAEVICR(a5)
        move.w #$2000,$9c(a6)       ; acknowledge Paula EXTER request
        move.w #$2000,$9a(a6)       ; disable EXTER before RTE
        movem.l (sp)+,d0
        rte

        dcb.b $ffca00-*,0
