; SPDX-License-Identifier: MIT
; Continuous CPU reads for validating A1..A8 address-line wiring.
; The boot stub has already disabled DMA/interrupts and entered with a RAM stack.
        move.w  #$2700,sr
        move.w  #$7fff,$dff09a
        move.w  #$7fff,$dff096
        move.w  #$0000,$dff100
        lea     $dff000,a6

scope_address_loop:
        move.w  $002(a6),d0
        nop
        nop
        nop
        move.w  $004(a6),d0
        nop
        nop
        nop
        move.w  $008(a6),d0
        nop
        nop
        nop
        move.w  $010(a6),d0
        nop
        nop
        nop
        move.w  $020(a6),d0
        nop
        nop
        nop
        move.w  $040(a6),d0
        nop
        nop
        nop
        move.w  $080(a6),d0
        nop
        nop
        nop
        move.w  $100(a6),d0
        nop
        nop
        nop
        bra.w   scope_address_loop