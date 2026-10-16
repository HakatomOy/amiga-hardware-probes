; SPDX-License-Identifier: MIT
; Continuous line-mode BZERO/DMACONR status probe for hardware scope capture.
; Launch controls and data words are emitted as literals by the builder.
; The first two C words are reset each iteration; only C[0] is configurable.
        include "bzero_config.i"
        move.w  #$2700,sr
        move.w  #$7fff,$dff09a
        move.w  #$7fff,$dff096
        move.w  #$0000,$dff100
        lea     $dff000,a6

scope_bzero_loop:
        ; Restore the two destination words and C words used by this launch.
        move.l  #$10000,a0
        clr.w   (a0)
        clr.w   $50(a0)
        move.l  #$11000,a0
        move.w  #BZERO_C_FIRST,(a0)
        clr.w   $50(a0)
        move.l  #$16000,a0
        clr.w   (a0)
        clr.w   $50(a0)

        ; Inputs and pointers are rewritten on every pass.
        move.w  #BZERO_A_DATA,$74(a6) ; BLTADAT
        move.w  #BZERO_B_DATA,$72(a6) ; BLTBDAT; USEB selection is independent
        move.w  #$0000,$70(a6)       ; BLTCDAT = 0
        move.w  #BZERO_BLTCON0,$40(a6) ; literal line minterm/USEB/ASHIFT
        move.w  #BZERO_BLTCON1,$42(a6) ; literal BSHIFT, line mode
        move.w  #$ffff,$44(a6)
        move.w  #$ffff,$46(a6)
        move.w  #$0000,$62(a6)       ; BLTBMOD
        move.w  #$0050,$60(a6)       ; BLTCMOD = 80
        move.w  #$fee8,$64(a6)       ; BLTAMOD = -280
        move.w  #$0050,$66(a6)       ; BLTDMOD = 80
        move.l  #$11000,$48(a6)      ; BLTCPTH
        move.l  #$16000,$4c(a6)      ; BLTBPTH
        move.l  #-$50,$50(a6)        ; BLTAPTH = -80
        move.l  #$10000,$54(a6)      ; BLTDPTH
        move.w  #$7fff,$96(a6)       ; clear all DMA enables
        move.w  #$8240,$96(a6)       ; enable master + blitter DMA
        move.w  #BZERO_BLTSIZE,$58(a6) ; launch configured line blit

        ; Keep these eight DMACONR reads adjacent and in D0..D7 order.
        move.w  $002(a6),d0
        move.w  $002(a6),d1
        move.w  $002(a6),d2
        move.w  $002(a6),d3
        move.w  $002(a6),d4
        move.w  $002(a6),d5
        move.w  $002(a6),d6
        move.w  $002(a6),d7

        ; The eight samples can outlast this short blit. Only wait for idle.
scope_bzero_wait_idle:
        btst    #6,$002(a6)
        bne.s   scope_bzero_wait_idle
        rept    16
        nop
        endr
        bra.w   scope_bzero_loop