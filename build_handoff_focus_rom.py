#!/usr/bin/env python3
"""Kind59: paired four-plane handoff and no-start arbitration controls."""
import argparse
from pathlib import Path
import shutil
import build_irq_stage_rom as base


def trials(neighbors=False,read_control=False):
    variants=(4,5,6,7,12,13,14,15) if neighbors else (2,3,10,11)
    if read_control:
        variants=tuple(variants)+tuple(v|16 for v in variants)
    kind=60 if read_control else 59
    return [(kind,3,v,p,d,r) for v in variants for p in range(2)
            for d in range(8) for r in range(2)]


def transform(stage,read_control=False):
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage / "src/rom/experiment.asm"
    s=p.read_text();assert s.count("cmpi.w #49,(a4)")==1
    p.write_text(s.replace("cmpi.w #49,(a4)",f"cmpi.w #{60 if read_control else 59},(a4)"))
    p=stage / "src/rom/blitter_handoff_kernel.i"
    s=p.read_text();anchor="        ; Align in ROM, then apply phase and the 0..7 NOP launch padding."
    assert anchor in s
    s=s.replace(anchor,"""        move.l #$dff058,d2
        btst #3,5(a4)
        beq.s .start_address_ready
        move.l #$dff1fe,d2
.start_address_ready:
"""+anchor)
    s=s.replace("        jsr $fb0000", "        jsr $fb0000\n        movea.l d2,a2")
    if read_control:
        s=s.replace(anchor,"""        move.l #$10000,d4
        btst #4,5(a4)
        beq.s .read_address_ready
        move.l #$f80000,d4
.read_address_ready:
"""+anchor)
        s=s.replace("        jsr $ffb000", "        movea.l d4,a1\n        jsr $ffb000")
    p.write_text(s)
    p=stage / "src/rom/blitter_handoff_observer.i"
    s=p.read_text();assert "move.w d5,$58(a6)" in s
    s=s.replace("move.w d5,$58(a6)","move.w d5,(a2)")
    if read_control:
        s=s.replace("move.w (a0),d2", "move.w (a1),d2")
        s=s.replace("        rept 256", "        move.w d3,34(a4)\n        rept 256")
    p.write_text(s)


def build(assembler,wsl,out,neighbors=False,read_control=False):
    return base.build(assembler,wsl,out,rows=trials(neighbors,read_control),
        transform=lambda stage:transform(stage,read_control),
        profile=dict(kind=60 if read_control else 59,
            targets=["AD one word (descriptor3)"], sources=["CPU BLTSIZE or no-start inert write"],
            masks=None, phases="0=no extra;1=EXG +3 CCK; exact measured prelaunch beam is authoritative",
            event_offset="0..7 NOP launch pad", watchdog="bounded4096 BBUSY samples; CPU IRQs masked",
            masked_fields=None,
            measurement_fields={"launch_beam":"pre-write beam", "launch_ref":"first clear DMACONR",
                "end_beam":"early D/ROM word", "end_ref":"postwrite DMACONR", "counter":"handoff beam",
                "icr":"postwrite beam", "irq_beam":"final first D", "irq_level":"final last D",
                "saved_pc_offset":"INTREQR:final beam", "aux":"kind60 remaining poll counter"},
            family="AD one word; four planes or six-plane/Copper neighbors",
            variants="bit0 BLTPRI; bits2:1 DMA mode1=four planes,2=six,3=six+Copper; bit3=no start; kind60 bit4=early ROM read instead of chip destination",
            poll_count="kind60 +34: remaining DBRA counter, busy samples=4095-value; one final clear sample",
            launch="+12 pre-write beam; fixed indirect write to BLTSIZE or inert register, address selected before alignment",
            units="Encoded beam words; register/data words; never subtract packed beam across lines",
            limitations="CPU observations combine arbitration and sequencer timing; no-blit pair discriminates them"))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vasm",required=True);p.add_argument("--wsl",action="store_true")
    p.add_argument("--out",type=Path,required=True);p.add_argument("--neighbors",action="store_true")
    p.add_argument("--read-control",action="store_true")
    a=p.parse_args();build(a.vasm,a.wsl,a.out,a.neighbors,a.read_control)
