#!/usr/bin/env python3
"""Kind58: CPU INTREQ writes versus INTENA unmask, with no CIA source."""
import argparse
from pathlib import Path
import shutil
import build_irq_stage_rom as base

SOURCES = ("CPU_PORTS_WRITE", "CPU_EXTER_WRITE", "CPU_PORTS_UNMASK",
           "CPU_EXTER_UNMASK", "CPU_COPER_WRITE", "CPU_COPER_UNMASK")
MASKS = (8, 0x2000, 8, 0x2000, 16, 16)


def trials(targets=(0,2,4)):
    return [(58,t,s,p,d,r) for t in targets for s in range(6)
            for p in range(4) for d in range(8) for r in range(2)]


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    p = stage / "src/rom/experiment.asm"
    p.write_text(p.read_text().replace("cmpi.w #56,(a4)", "cmpi.w #58,(a4)"))
    p = stage / "src/rom/irq_stage_kernel.i"
    s = p.read_text().replace(".masks: dc.w $0008,$0010,$2000,$0008,$2000",
                              ".masks: dc.w $0008,$2000,$0008,$2000,$0010,$0010")
    for old_addr,new_addr in (("ffd900","ffe000"),("ffd940","ffe080"),("ffd980","ffe100"),("ffd9c0","ffe180")):
        s = s.replace(old_addr,new_addr)
    p.write_text(s)
    p = stage / "src/rom/irq_stage_observer.i"
    old = p.read_text()
    handlers = old[old.index("        dcb.b $ffd900-*,0"):]
    for old_addr,new_addr in (("ffd900","ffe000"),("ffd940","ffe080"),("ffd980","ffe100"),("ffd9c0","ffe180")):
        handlers = handlers.replace(old_addr,new_addr)
    handlers = handlers.replace("        rte", "        jsr cpu_irq_stop_guard\n        rte")
    handlers += """
        dcb.b $ffe200-*,0
cpu_irq_stop_guard:
        cmpi.w #2,2(a4)
        bne.s .done
        move.l #$ffcd10,6(sp)
.done:
        rts
"""
    code = """irq_stage_observer:
        move.w 18(a5),d5
        move.w 4(a4),d0
        lea $9c(a6),a0
        cmpi.w #2,d0
        beq.s .unmask
        cmpi.w #3,d0
        beq.s .unmask
        cmpi.w #5,d0
        bne.s .write
.unmask:
        move.w d5,d0
        ori.w #$8000,d0
        move.w d0,$9c(a6)
        lea $9a(a6),a0
        moveq #0,d0
        bra.s .enable
.write:
        move.w d5,d0
.enable:
        cmpi.w #4,2(a4)
        beq.s .no_enable
        ori.w #$c000,d0
        move.w d0,$9a(a6)
.no_enable:
        ori.w #$8000,d5
        move.w 8(a4),d0
.pad:
        nop
        dbra d0,.pad
        btst #0,7(a4)
        beq.s .phase2
        nop
.phase2:
        btst #1,7(a4)
        beq.s .choose
        exg d0,d1
.choose:
        clr.w 14(a4)
        moveq #127,d1
        cmpi.w #4,2(a4)
        beq.w .raw
        cmpi.w #2,2(a4)
        beq.w .stop
        cmpi.w #1,2(a4)
        beq.w .store
        cmpi.w #3,2(a4)
        beq.w .tst
        bra.w .running
        dcb.b $ffcc00-*,0
.running:
        move.w 6(a6),12(a4)
        move.w #$2000,sr
        move.w d5,(a0)
.loop:
        nop
        dbra d1,.loop
        bra.w .done
        dcb.b $ffcd00-*,0
.stop:
        move.w 6(a6),12(a4)
        move.w #$2000,sr
        move.w d5,(a0)
        stop #$2000
        bra.w .done
        dcb.b $ffce00-*,0
.raw:
        move.w 6(a6),d4
        move.w d4,12(a4)
        move.w d5,(a0)
        move.w $1e(a6),d0
        move.w 6(a6),d5
        move.w $1e(a6),d3
        move.w 6(a6),d6
        move.w $1e(a6),d7
        move.w 6(a6),d2
        move.w d0,20(a4)
        move.w d3,22(a4)
        move.w d7,24(a4)
        move.w d4,26(a4)
        move.w d5,28(a4)
        move.w d6,30(a4)
        move.w d2,34(a4)
        move.w $1e(a6),36(a4)
        move.w 18(a5),38(a4)
.done:
        move.w #$2700,sr
        rts
        dcb.b $ffcf00-*,0
.store:
        moveq #$5a,d0
        move.w 6(a6),12(a4)
        move.w #$2000,sr
        move.w d5,(a0)
.store_loop:
        move.b d0,-(a1)
        dbra d1,.store_loop
        bra.w .done
        dcb.b $ffd000-*,0
.tst:
        move.w 6(a6),12(a4)
        move.w #$2000,sr
        move.w d5,(a0)
.tst_loop:
        tst.w (a1)
        dbra d1,.tst_loop
        bra.w .done
"""
    p.write_text(old[:old.index("irq_stage_observer:")] + code + handlers)


def build(assembler,wsl,out,neighbors=False):
    targets=(1,3) if neighbors else (0,2,4)
    return base.build(assembler,wsl,out,aligned=True,rows=trials(targets),transform=transform,
        profile=dict(kind=58,sources=SOURCES,masks=MASKS,targets=list(targets),
            launch="+12 pre-write beam; +14 zero (no post-write read before STOP); SR lowered immediately before CPU write",
            event_offset="delay selects prelaunch NOP/DBRA padding, not source latency",
            stop_guard="Handler records original stacked PC, then STOP cases resume after STOP to avoid a real-HW early-interrupt hang",
            watchdog="disabled; request must wake STOP; bounded emulator preflight before hardware",
            limitations="CPU custom write and instruction-poll recognition remain combined; no electrical IPL measurement"))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vasm",required=True);p.add_argument("--wsl",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--neighbors",action="store_true",help="held-out STORE/TST operand controls")
    a=p.parse_args();build(a.vasm,a.wsl,a.out,a.neighbors)
