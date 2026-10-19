#!/usr/bin/env python3
"""Kind57: independent CIA access phase plus underflow/prelatched controls."""
import argparse
import shutil
from pathlib import Path
import build_irq_stage_rom as base

SOURCES = (0, 2, 5, 6)
TARGETS = (0, 2, 4)


def trials():
    return [(57, t, s, p, d, r) for t in TARGETS for s in SOURCES
            for p in range(4) for d in range(8) for r in range(5)]


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    experiment = stage / "src/rom/experiment.asm"
    experiment.write_text(experiment.read_text().replace("cmpi.w #56,(a4)", "cmpi.w #57,(a4)"))
    p = stage / "src/rom/irq_stage_kernel.i"
    s = p.read_text()
    s = s.replace("        move.w 4(a4),d0\n        add.w d0,d0", '''        cmpi.w #5,4(a4)
        beq.s .prime_a
        cmpi.w #6,4(a4)
        bne.w .primed
        move.b #$19,$bfde00
        bra.s .prime_wait
.prime_a:
        move.b #$19,$bfee01
.prime_wait:
        rept 256
        nop
        endr
.primed:
        move.w 4(a4),d0
        add.w d0,d0''', 1)
    s = s.replace("        move.w #$009c,(a0)+\n        move.w d5,d0", '''        move.w #$009c,d0
        cmpi.w #5,4(a4)
        bcs.s .list_register
        move.w #$009a,d0
.list_register:
        move.w d0,(a0)+
        move.w d5,d0''', 1)
    s = s.replace("        move.w 6(a6),16(a4)\n", "")
    s = s.replace("        move.w d1,36(a4)\n        move.w a1,38(a4)\n", "")
    s = s.replace(".masks: dc.w $0008,$0010,$2000,$0008,$2000", ".masks: dc.w $0008,$0010,$2000,$0008,$2000,$0008,$2000")
    p.write_text(s)
    p = stage / "src/rom/irq_stage_observer.i"
    s = p.read_text().replace("irq_stage_observer:\n", '''irq_stage_observer:
        move.w 6(a6),d4
        moveq #0,d5
        move.b $bfe001,d5
        move.w 6(a6),d6
        move.w d4,16(a4)
        move.w d6,36(a4)
        move.w d5,38(a4)
''', 1)
    s = s.replace("        move.w 18(a5),d0\n        ori.w #$c004,d0", '''        move.w 18(a5),d0
        cmpi.w #5,4(a4)
        bcs.s .normal_mask
        clr.w d0
.normal_mask:
        ori.w #$c004,d0''', 1)
    s = s.replace(".release:\n", '''.release:
        cmpi.w #4,2(a4)
        bne.w .normal_release
        move.w 4(a4),d0
        beq.w .fast_timer_a
        cmpi.w #2,d0
        beq.w .fast_timer_b
        cmpi.w #5,d0
        beq.w .fast_mask_a
        jmp $ffe000
.fast_timer_a:
        jmp $ffda00
.fast_timer_b:
        jmp $ffdc00
.fast_mask_a:
        jmp $ffde00
.normal_release:
''', 1)
    s = s.replace("        cmpi.w #0,4(a4)\n        bne.s .release_b", '''        cmpi.w #5,4(a4)
        beq.w .mask_a_release
        cmpi.w #6,4(a4)
        beq.w .mask_b_release
        cmpi.w #0,4(a4)
        bne.s .release_b''', 1)
    s = s.replace(".released:\n", '''        bra.s .released
.mask_a_release:
        move.b #$81,$bfed01
        bra.s .released
.mask_b_release:
        move.b #$81,$bfdd00
.released:
''', 1)
    s = s.replace("        move.w $1e(a6),36(a4)\n        move.w 18(a5),38(a4)\n", "")
    p.write_text(s)
    fast = []
    for address, reg, value, delay in [(0xffda00, 0xbfee01, 0x19, 76),
                                      (0xffdc00, 0xbfde00, 0x19, 76),
                                      (0xffde00, 0xbfed01, 0x81, 0),
                                      (0xffe000, 0xbfdd00, 0x81, 0)]:
        fast.append(f'''        dcb.b ${address:06x}-*,0
        move.w 6(a6),d2
        move.b #${value:02x},${reg:06x}
        rept {delay}
        nop
        endr
        move.w $1e(a6),d0
        move.w 6(a6),d3
        move.w $1e(a6),d1
        move.w 6(a6),d4
        move.w $1e(a6),d5
        move.w 6(a6),d6
        move.w d2,12(a4)
        move.w d3,14(a4)
        move.w d0,20(a4)
        move.w d1,22(a4)
        move.w d5,24(a4)
        move.w d2,26(a4)
        move.w d3,28(a4)
        move.w d4,30(a4)
        move.w d6,34(a4)
        rept 128
        nop
        endr
        rts
''')
    edge = stage / "src/rom/edge_kernel.asm"
    edge.write_text(edge.read_text() + "\n" + "\n".join(fast))


def build(assembler, wsl, out):
    return base.build(assembler, wsl, out, aligned=True, rows=trials(), transform=transform,
        profile=dict(kind=57, sources=list(SOURCES), targets=list(TARGETS),
            calibration="+16 pre-CIA-A-PRA beam; +36 post-read beam; +38 raw PRA diagnostic",
            masked_fields=dict(counter="raw0", icr="raw1", irq_beam="raw2", irq_level="beam0",
                saved_pc_offset="beam1:beam2", aux="beam3", end_ref="settled INTREQR",
                end_beam="calibration pre-beam", second_counter_or_beam="calibration post-beam",
                second_icr_or_level="raw PRA diagnostic"),
            prelatched="variants5/6: prime flag masked; CPU ICR mask-enable; Copper INTENA unmask line68 for recognition",
            masked="direct CIA write then INTREQR/beam pairs; timer streams pad76 NOP, mask-enable no pad; +18 settled INTREQR",
            limits="Calibration brackets condition evidence; no trace shifts. Prelatched recognition isolates Paula unmask; raw streams isolate CIA mask enable."))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vasm", required=True)
    p.add_argument("--wsl", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    build(a.vasm, a.wsl, a.out)