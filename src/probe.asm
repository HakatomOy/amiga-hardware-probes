; SPDX-License-Identifier: MIT
; Position-independent 68000-only boot program. No ROM-specific addresses.
; The OS is suspended during measurements, then restored for trackdisk writes.
        include "layout.i"
CUSTOM  equ     $dff000
CIAA    equ     $bfe001
CIAB    equ     $bfd000
start:
        bra     main
vars:
sysbase:        dc.l 0
bootio:         dc.l 0
codebase:       dc.l 0
resultbuf:      dc.l 0
readbuf:        dc.l 0
recordptr:      dc.l 0
gfxbase:        dc.l 0
oldview:        dc.l 0
systemcop:      dc.l 0
ciaares:        dc.l 0
ciabres:        dc.l 0
oldssp:         dc.l 0
oldvectors:     ds.l 5
olddma:         dc.w 0
oldintena:      dc.w 0
oldmaska:       dc.b 0
oldmaskb:       dc.b 0
oldcrala:       dc.b 0
oldcralb:       dc.b 0
oldtimera:      dc.w 0
oldtimerb:      dc.w 0
source:         dc.w 0
kernel:         dc.w 0
phase:          dc.w 0
repeat:         dc.w 0
doneflag:       dc.w 0
eventcount:     dc.w 0
expected:       dc.w 0
entrybeam:      dc.w 0
actuallevel:    dc.w 0
errorcode:      dc.w 0
        even
coplist:        ds.w 40
kerneldata:     dc.l $11111111,$22222222,$33333333,$44444444
                dc.l $55555555,$66666666,$77777777,$88888888

main:
        lea     vars(pc),a5
        move.l  a6,sysbase-vars(a5)
        move.l  a1,bootio-vars(a5)
        lea     start(pc),a0
        move.l  a0,codebase-vars(a5)
        move.w  296(a6),d0       ; ExecBase.AttnFlags
        andi.w  #$008f,d0        ; 68010/020/030/040/060
        bne     unsupported
        move.l  #RESULT_BYTES,d0
        move.l  #$10002,d1
        jsr     -198(a6)         ; AllocMem(CHIP|CLEAR)
        tst.l   d0
        beq     unsupported
        move.l  d0,resultbuf-vars(a5)
        move.l  d0,a1
        lea     header(pc),a0
        moveq   #31,d0
.header:
        move.l  (a0)+,(a1)+
        dbra    d0,.header
        move.l  resultbuf-vars(a5),a0
        move.w  $dff004,64(a0)
        move.w  $dff07c,66(a0)   ; Raw; OCS Denise may float
        move.w  296(a6),68(a0)
        move.w  20(a6),70(a0)
        move.w  22(a6),72(a0)
        lea     graphicsname(pc),a1
        moveq   #0,d0
        jsr     -552(a6)         ; OpenLibrary
        tst.l   d0
        beq     unsupported
        move.l  d0,gfxbase-vars(a5)
        move.l  d0,a6
        move.l  34(a6),oldview-vars(a5)
        move.l  38(a6),systemcop-vars(a5)
        suba.l  a1,a1
        jsr     -222(a6)         ; LoadView(NULL)
        jsr     -270(a6)         ; WaitTOF twice, also on interlaced displays
        jsr     -270(a6)
        jsr     -228(a6)         ; WaitBlit
        move.l  sysbase-vars(a5),a6
        lea     ciaaname(pc),a1
        jsr     -498(a6)         ; OpenResource
        tst.l   d0
        beq     unsupported
        move.l  d0,ciaares-vars(a5)
        lea     ciabname(pc),a1
        jsr     -498(a6)
        tst.l   d0
        beq     unsupported
        move.l  d0,ciabres-vars(a5)
        jsr     -132(a6)         ; Forbid: no other task during takeover
        jsr     -120(a6)         ; Disable
        move.l  ciaares-vars(a5),a6
        moveq   #0,d0
        jsr     -18(a6)          ; AbleICR: snapshot OS mask shadow
        move.b  d0,oldmaska-vars(a5)
        moveq   #$7f,d0
        jsr     -18(a6)
        move.l  ciabres-vars(a5),a6
        moveq   #0,d0
        jsr     -18(a6)
        move.b  d0,oldmaskb-vars(a5)
        moveq   #$7f,d0
        jsr     -18(a6)
        move.l  sysbase-vars(a5),a6
        lea     measure(pc),a5   ; Supervisor's function argument
        jsr     -30(a6)          ; Supervisor callback returns with RTE
        lea     vars(pc),a5
        move.l  ciaares-vars(a5),a6
        moveq   #0,d0
        move.b  oldmaska-vars(a5),d0
        ori.b   #$80,d0
        jsr     -18(a6)
        move.l  ciabres-vars(a5),a6
        moveq   #0,d0
        move.b  oldmaskb-vars(a5),d0
        ori.b   #$80,d0
        jsr     -18(a6)
        move.l  sysbase-vars(a5),a6
        jsr     -126(a6)         ; Enable
        jsr     -138(a6)         ; Permit
        move.l  gfxbase-vars(a5),a6
        move.l  oldview-vars(a5),a1
        jsr     -222(a6)
        jsr     -270(a6)
        jsr     -270(a6)
        ; Allocate verification buffer only after measurement.
        move.l  sysbase-vars(a5),a6
        move.l  #RESULT_BYTES,d0
        move.l  #$10002,d1
        jsr     -198(a6)
        tst.l   d0
        beq     unsupported
        move.l  d0,readbuf-vars(a5)
        move.l  resultbuf-vars(a5),a0
        move.w  #1,74(a0)        ; Completed test matrix
        clr.l   28(a0)
        moveq   #0,d0
        move.w  #RESULT_BYTES/4-1,d1
.sum:
        add.l   (a0)+,d0
        dbra    d1,.sum
        neg.l   d0
        move.l  resultbuf-vars(a5),a0
        move.l  d0,28(a0)        ; Whole results region sums to zero
        lea     writingimage(pc),a0
        move.w  #$fa0,d0
        bsr     show_status
        move.l  resultbuf-vars(a5),d1
        moveq   #3,d0            ; CMD_WRITE
        bsr     disk_io
        tst.l   d0
        bne     io_failed
        moveq   #4,d0            ; CMD_UPDATE: flush trackdisk's dirty cache
        moveq   #0,d1
        bsr     disk_io
        tst.l   d0
        bne     io_failed
        moveq   #5,d0            ; CMD_CLEAR: invalidate cache for readback
        bsr     disk_io
        tst.l   d0
        bne     io_failed
        lea     verifyingimage(pc),a0
        move.w  #$80f,d0
        bsr     show_status
        move.l  readbuf-vars(a5),d1
        moveq   #2,d0            ; CMD_READ
        bsr     disk_io
        tst.l   d0
        bne     io_failed
        move.l  resultbuf-vars(a5),a0
        move.l  readbuf-vars(a5),a1
        move.w  #RESULT_BYTES/4-1,d0
.verify:
        cmpm.l  (a0)+,(a1)+
        bne     verify_failed
        dbra    d0,.verify
        moveq   #9,d0            ; TD_MOTOR off (io_Length is the motor flag)
        moveq   #0,d1
        bsr     disk_io
        lea     successimage(pc),a0
        move.w  #$080,d0
        bsr     show_status
idle_forever:
        bra.s   idle_forever
io_failed:
        move.w  d0,errorcode-vars(a5)
        bra.s   failure
verify_failed:
        move.w  #$101,errorcode-vars(a5)
        bra.s   failure
unsupported:
        move.w  #$102,errorcode-vars(a5)
failure:
        lea     errorimage(pc),a0
        move.w  #$f00,d0
        bsr     show_status
        bra.s   idle_forever

; D0 command, D1 data pointer (or 0 for commands with no data).
disk_io:
        move.l  sysbase-vars(a5),a6
        move.l  bootio-vars(a5),a1
        move.w  d0,28(a1)
        clr.b   31(a1)           ; io_Error
        clr.l   32(a1)           ; io_Actual
        move.l  d1,40(a1)
        move.l  #RESULT_OFFSET,44(a1)
        move.l  #RESULT_BYTES,36(a1)
        tst.l   d1
        bne.s   .do
        clr.l   36(a1)
.do:
        jsr     -456(a6)
        tst.l   d0
        bne.s   .out
        move.l  bootio-vars(a5),a1
        cmpi.w  #2,28(a1)
        beq.s   .actual
        cmpi.w  #3,28(a1)
        bne.s   .out
.actual:
        cmpi.l  #RESULT_BYTES,32(a1)
        beq.s   .out
        move.l  #$103,d0
.out:
        rts

; A0 = 320x64 one-plane status image, D0 = border colour.
; Outside measurement: disk DMA and OS interrupts may run normally.
show_status:
        movem.l d0-d2/a0-a2/a6,-(sp)
        lea     CUSTOM,a6
        move.w  #$0100,$96(a6)   ; Disable bitplanes before changing pointers
        move.w  d0,$180(a6)
        move.w  #$fff,$182(a6)
        move.w  #$1200,$100(a6)
        clr.w   $102(a6)
        clr.w   $104(a6)
        clr.w   $108(a6)
        clr.w   $10a(a6)
        move.w  #$5081,$8e(a6)
        move.w  #$90c1,$90(a6)
        move.w  #$38,$92(a6)
        move.w  #$d0,$94(a6)
        lea     coplist-vars(a5),a1
        move.l  a1,a2
        move.l  a0,d1
        swap    d1
        move.w  #$e0,(a1)+
        move.w  d1,(a1)+
        swap    d1
        move.w  #$e2,(a1)+
        move.w  d1,(a1)+
        move.l  #$fffffffe,(a1)+
        move.l  a2,$80(a6)
        move.w  #0,$88(a6)
        move.w  #$8380,$96(a6)   ; Master, Copper, bitplanes; keep disk DMA
        movem.l (sp)+,d0-d2/a0-a2/a6
        rts

measure:
        movem.l d0-d7/a0-a6,-(sp)
        lea     vars(pc),a5
        move.l  sp,oldssp-vars(a5)
        lea     stacktop(pc),sp
        move.w  #$2700,sr
        lea     CUSTOM,a6
        move.w  $2(a6),olddma-vars(a5)
        move.w  $1c(a6),oldintena-vars(a5)
        move.w  #$7fff,$9a(a6)
        move.w  #$7fff,$96(a6)
        move.w  #$7fff,$9c(a6)
        move.w  #$00a,$180(a6)
        lea     oldvectors-vars(a5),a0
        move.l  $64.w,(a0)+
        move.l  $68.w,(a0)+
        move.l  $6c.w,(a0)+
        move.l  $78.w,(a0)+
        move.l  $80.w,(a0)+
        lea     irq1(pc),a0
        move.l  a0,$64.w
        lea     irq2(pc),a0
        move.l  a0,$68.w
        lea     irq3(pc),a0
        move.l  a0,$6c.w
        lea     irq6(pc),a0
        move.l  a0,$78.w
        lea     trapreturn(pc),a0
        move.l  a0,$80.w
        move.b  CIAA+$e00,oldcrala-vars(a5)
        move.b  CIAB+$e00,oldcralb-vars(a5)
        clr.b   CIAA+$e00
        clr.b   CIAB+$e00
        move.b  CIAA+$400,oldtimera+1-vars(a5)
        move.b  CIAA+$500,oldtimera-vars(a5)
        move.b  CIAB+$400,oldtimerb+1-vars(a5)
        move.b  CIAB+$500,oldtimerb-vars(a5)
        move.b  #$7f,CIAA+$d00
        move.b  #$7f,CIAB+$d00
        move.b  CIAA+$d00,d0
        move.b  CIAB+$d00,d0
        move.l  resultbuf-vars(a5),a0
        lea     512(a0),a0
        move.l  a0,recordptr-vars(a5)
        clr.w   source-vars(a5)
.source:
        clr.w   kernel-vars(a5)
.kernel:
        clr.w   phase-vars(a5)
.phase:
        clr.w   repeat-vars(a5)
.repeat:
        bsr     trial
        move.l  resultbuf-vars(a5),a0
        addq.l  #1,16(a0)
        addi.l  #RECORD_BYTES,recordptr-vars(a5)
        addq.w  #1,repeat-vars(a5)
        cmpi.w  #2,repeat-vars(a5)
        blo.s   .repeat
        addq.w  #1,phase-vars(a5)
        cmpi.w  #16,phase-vars(a5)
        blo.s   .phase
        addq.w  #1,kernel-vars(a5)
        cmpi.w  #6,kernel-vars(a5)
        blo.s   .kernel
        addq.w  #1,source-vars(a5)
        cmpi.w  #4,source-vars(a5)
        blo.s   .source
        ; Restore hardware sufficiently to let the original boot IORequest
        ; write through trackdisk. The machine stays on this disk until reset.
        move.w  #$2700,sr
        move.w  #$7fff,$9a(a6)
        move.w  #$7fff,$96(a6)
        move.w  #$7fff,$9c(a6)
        move.b  #$7f,CIAA+$d00
        move.b  #$7f,CIAB+$d00
        clr.b   CIAA+$e00
        clr.b   CIAB+$e00
        move.b  oldtimera+1-vars(a5),CIAA+$400
        move.b  oldtimera-vars(a5),CIAA+$500
        move.b  oldtimerb+1-vars(a5),CIAB+$400
        move.b  oldtimerb-vars(a5),CIAB+$500
        move.b  oldcrala-vars(a5),d0
        ori.b   #$10,d0
        move.b  d0,CIAA+$e00
        move.b  oldcralb-vars(a5),d0
        ori.b   #$10,d0
        move.b  d0,CIAB+$e00
        move.b  CIAA+$d00,d0
        move.b  CIAB+$d00,d0
        lea     oldvectors-vars(a5),a0
        move.l  (a0)+,$64.w
        move.l  (a0)+,$68.w
        move.l  (a0)+,$6c.w
        move.l  (a0)+,$78.w
        move.l  (a0)+,$80.w
        move.l  systemcop-vars(a5),$80(a6)
        move.w  #0,$88(a6)
        move.w  olddma-vars(a5),d0
        andi.w  #$07ff,d0
        ori.w   #$8000,d0
        move.w  d0,$96(a6)
        move.w  oldintena-vars(a5),d0
        ori.w   #$8000,d0
        move.w  d0,$9a(a6)
        move.l  oldssp-vars(a5),sp
        movem.l (sp)+,d0-d7/a0-a6
        rte

trial:
        move.w  #$2700,sr
        move.w  #$7fff,$9a(a6)
        move.w  #$7fff,$96(a6)
        clr.b   CIAA+$e00
        clr.b   CIAB+$e00
        move.b  #$7f,CIAA+$d00
        move.b  #$7f,CIAB+$d00
        move.b  CIAA+$d00,d0
        move.b  CIAB+$d00,d0
        move.w  #$7fff,$9c(a6)
        clr.w   doneflag-vars(a5)
        clr.w   eventcount-vars(a5)
        move.w  #1,expected-vars(a5)
        cmpi.w  #3,source-vars(a5)
        bne.s   .single
        move.w  #2,expected-vars(a5)
.single:
        move.l  recordptr-vars(a5),a0
        move.b  source+1-vars(a5),(a0)
        move.b  kernel+1-vars(a5),1(a0)
        move.b  phase+1-vars(a5),2(a0)
        move.b  repeat+1-vars(a5),3(a0)
        ; Resolve the kernel and reset its data BEFORE starting a timer, so
        ; short latches measure execution rather than lengthy setup at IPL 7.
        move.w  kernel-vars(a5),d0
        add.w   d0,d0
        lea     kerneltable(pc),a4
        move.w  (a4,d0.w),d0
        adda.w  d0,a4
        lea     kerneldata-vars(a5),a2
        move.l  #$11111111,(a2)
        move.l  #$22222222,4(a2)
        move.l  #$33333333,8(a2)
        ; New occurrence of raster line 32; no display or disk DMA active.
.leave:
        move.w  $6(a6),d0
        andi.w  #$ff00,d0
        cmpi.w  #$2000,d0
        beq.s   .leave
.wait:
        move.w  $4(a6),d0
        btst    #0,d0            ; Reject line 288 (same low eight V bits)
        bne.s   .wait
        move.w  $6(a6),d0
        andi.w  #$ff00,d0
        cmpi.w  #$2000,d0
        bne.s   .wait
        move.w  $6(a6),8(a0)
        move.w  #24,d0
        add.w   phase-vars(a5),d0
        cmpi.w  #3,source-vars(a5)
        bne.s   .latch
        move.w  #$24f,d0
        add.w   phase-vars(a5),d0
.latch:
        move.b  d0,CIAA+$400
        lsr.w   #8,d0
        move.b  d0,CIAA+$500
        move.w  #24,d0
        add.w   phase-vars(a5),d0
        cmpi.w  #3,source-vars(a5)
        bne.s   .latchb
        move.w  #$1ff,d0
.latchb:
        move.b  d0,CIAB+$400
        lsr.w   #8,d0
        move.b  d0,CIAB+$500
        move.w  #$7fff,$9c(a6)
        move.w  source-vars(a5),d0
        beq.s   .ciaa
        cmpi.w  #1,d0
        beq.s   .ciab
        cmpi.w  #2,d0
        beq.s   .copper
        move.b  #$81,CIAA+$d00
        move.b  #$81,CIAB+$d00
        move.w  #$e018,$9a(a6)
        move.b  #$19,CIAA+$e00
        move.b  #$19,CIAB+$e00
        bra.s   .run
.ciaa:
        move.b  #$81,CIAA+$d00
        move.w  #$c018,$9a(a6)
        move.b  #$19,CIAA+$e00
        bra.s   .run
.ciab:
        move.b  #$81,CIAB+$d00
        move.w  #$e010,$9a(a6)
        move.b  #$19,CIAB+$e00
        bra.s   .run
.copper:
        lea     coplist-vars(a5),a1
        move.w  phase-vars(a5),d0
        add.w   d0,d0
        addi.w  #$4041,d0        ; WAIT line 64, h=$40+phase*2
        move.w  d0,(a1)
        move.w  #$fffe,2(a1)
        move.l  #$009c8004,4(a1) ; MOVE SET|SOFTINT to INTREQ
        move.l  #$fffffffe,8(a1)
        move.l  a1,$80(a6)
        move.w  #0,$88(a6)
        move.w  #$8280,$96(a6)
        move.w  #$c014,$9a(a6)
.run:
        move.l  a2,a0
        move.l  #$12345678,d0
        move.l  #$11111111,d1
        move.l  #$33333333,d3
        move.l  #$55555555,d5
        jsr     (a4)            ; Each kernel opens IPL itself
        move.w  #$2700,sr
        move.l  recordptr-vars(a5),a1
        move.l  d1,52(a1)
        move.l  d3,56(a1)
        move.l  d5,60(a1)
        move.w  eventcount-vars(a5),6(a1)
        move.w  #$7fff,$9a(a6)
        rts

kerneltable:
        dc.w kernel_nop-kerneltable,kernel_load-kerneltable
        dc.w kernel_store-kerneltable,kernel_div-kerneltable
        dc.w kernel_stop-kerneltable,kernel_rte-kerneltable
kernel_nop:
        move.w  #$2000,sr
.loop:
        nop
        nop
        tst.w   doneflag-vars(a5)
        beq.s   .loop
        rts
kernel_load:
        move.w  #$2000,sr
.loop:
        movem.l (a0),d1/d3/d5
        tst.w   doneflag-vars(a5)
        beq.s   .loop
        rts
kernel_store:
        move.w  #$2000,sr
.loop:
        movem.l d1/d3/d5,(a0)
        tst.w   doneflag-vars(a5)
        beq.s   .loop
        rts
kernel_div:
        move.w  #$2000,sr
.loop:
        move.l  #$12345678,d0
        divu    #$4321,d0
        tst.w   doneflag-vars(a5)
        beq.s   .loop
        rts
kernel_stop:
        stop    #$2000
kernel_stop_end:
        tst.w   doneflag-vars(a5)
        beq.s   kernel_stop
        rts
kernel_rte:
        move.w  #$2000,sr
.loop:
        trap    #0
        tst.w   doneflag-vars(a5)
        beq.s   .loop
        rts
trapreturn:
        rte

; First instruction in every entry stub captures VHPOSR without destroying
; the interrupted registers. All following instrumentation is part of the test.
irq1:
        move.w  $6(a6),entrybeam-vars(a5)
        move.w  #$2700,sr
        move.w  #1,actuallevel-vars(a5)
        bra.s   irq_common
irq2:
        move.w  $6(a6),entrybeam-vars(a5)
        move.w  #$2700,sr
        move.w  #2,actuallevel-vars(a5)
        bra.s   irq_common
irq3:
        move.w  $6(a6),entrybeam-vars(a5)
        move.w  #$2700,sr
        move.w  #3,actuallevel-vars(a5)
        bra.s   irq_common
irq6:
        move.w  $6(a6),entrybeam-vars(a5)
        move.w  #$2700,sr
        move.w  #6,actuallevel-vars(a5)
irq_common:
        movem.l d0-d7/a0-a4/a6,-(sp) ; 56 bytes; A5 is invariant
        move.l  recordptr-vars(a5),a1
        cmpi.w  #3,actuallevel-vars(a5)
        beq     .timeout
        move.w  eventcount-vars(a5),d0
        cmpi.w  #2,d0
        bhs     .finish
        mulu    #20,d0
        lea     12(a1,d0.w),a0
        move.w  entrybeam-vars(a5),(a0)
        move.w  $4(a6),2(a0)
        move.w  56(sp),4(a0)     ; Interrupted SR, before our instrumentation
        move.w  $1e(a6),6(a0)
        move.l  58(sp),d0        ; Interrupted PC, normalized to program start
        sub.l   codebase-vars(a5),d0
        move.l  d0,8(a0)
        move.w  #$ffff,12(a0)    ; Unread CIA ICR = FF (not read, not zero)
        move.b  actuallevel+1-vars(a5),14(a0)
        move.l  (sp),16(a0)      ; Interrupted D0
        move.w  actuallevel-vars(a5),d0
        cmpi.w  #2,d0
        beq.s   .acka
        cmpi.w  #6,d0
        beq.s   .ackb
        move.w  #4,$9c(a6)
        bra.s   .count
.acka:
        move.b  CIAA+$d00,12(a0)
        move.w  #8,$9c(a6)
        bra.s   .count
.ackb:
        move.b  CIAB+$d00,13(a0)
        move.w  #$2000,$9c(a6)
.count:
        addq.w  #1,eventcount-vars(a5)
        move.w  eventcount-vars(a5),d0
        cmp.w   expected-vars(a5),d0
        blo.s   .return
.finish:
        move.w  #1,doneflag-vars(a5)
        move.w  #$7fff,$9a(a6)
        bra.s   .return
.timeout:
        move.w  #1,4(a1)
        move.w  #1,doneflag-vars(a5)
        move.w  #$7fff,$9a(a6)
        move.w  #$10,$9c(a6)
.return:
        ; Avoid the interrupt-before-STOP race. Return to the STOP kernel's
        ; flag check; another STOP is executed if a paired IRQ is still due.
        cmpi.w  #4,kernel-vars(a5)
        bne.s   .restore
        lea     kernel_stop_end(pc),a0
        move.l  a0,58(sp)
.restore:
        movem.l (sp)+,d0-d7/a0-a4/a6
        rte

graphicsname:   dc.b "graphics.library",0
ciaaname:       dc.b "ciaa.resource",0
ciabname:       dc.b "ciab.resource",0
        even
header:
        dc.b "A5IRQ001"
        dc.w 1,512,RECORD_BYTES,0
        dc.l 0,RESULT_BYTES,512,0
        incbin "source-id.bin"
        ds.b 64
        even
        ds.b 2048
stacktop:
writingimage:
        incbin "writing.bin"
verifyingimage:
        incbin "verifying.bin"
successimage:
        incbin "success.bin"
errorimage:
        incbin "error.bin"
program_end:
