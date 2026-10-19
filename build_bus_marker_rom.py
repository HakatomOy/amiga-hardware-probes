#!/usr/bin/env python3
"""Build isolated, immutable bus-marker HW checks without changing in-progress probes."""
import argparse
import json
from pathlib import Path
import shutil

import build_rom

ROOT = Path(__file__).resolve().parent
GATES = tuple(range(0x40, 0x75, 4))


def trials(focused=False, completion=False, pressure=False, onset=False, phasepad=False, phase_entry=False):
    phasepad = phasepad or phase_entry
    if phasepad:
        return [(55, 1, variant | phase, gate, 0, repeat)
                for variant in range(16) for phase in (0, 16)
                for gate in (range(2, 9) if phase_entry else (4, 5, 6)) for repeat in range(8)]
    if onset:
        return [(55, width, variant, gate, 0, repeat)
                for width in range(2) for variant in (0, 1, 4, 5, 8, 9, 12, 13)
                for gate in range(17) for repeat in range(8)]
    if pressure:
        return [(55, 1, variant, gate, mask, repeat)
                for variant in (0, 1, 4, 5, 8, 9, 12, 13)
                for gate in (4, 5, 6) for mask in range(4) for repeat in range(8)]
    if completion:
        return [(55, 1, variant, gate, 0, repeat)
                for variant in (0, 1, 4, 5, 8, 9, 12, 13)
                for gate in range(4, 14) for repeat in range(8)]
    if focused:
        return [(55, 1, variant, gate, 0, repeat)
                for variant in range(1, 16, 2) for gate in (4, 5, 6)
                for repeat in range(16)]
    return [(55, width, variant, gate, 0, repeat)
            for width in range(2) for variant in range(16)
            for gate in range(len(GATES)) for repeat in range(2)]


def build(assembler, wsl, out, focused=False, completion=False, pressure=False, onset=False, phasepad=False, phase_entry=False):
    phasepad = phasepad or phase_entry
    completion = completion or pressure or onset
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out / "source_snapshot"
    shutil.copytree(ROOT / "src", stage / "src")
    shutil.copytree(ROOT / "vendor/rbcp", stage / "vendor/rbcp")
    for name in ("build_rom.py", "build_bus_marker_rom.py"):
        shutil.copyfile(ROOT / name, stage / name)
    source = stage / "src/rom/experiment.asm"
    text = source.read_text()
    anchor = "        cmpi.w #10,(a4)"
    assert text.count(anchor) == 1
    text = text.replace(anchor, "        cmpi.w #55,(a4)\n        beq .bus_marker\n" + anchor)
    text = text.replace(".channels:\n", ".bus_marker:\n        jsr bus_marker_trial\n        bra.w .recorded\n.channels:\n", 1)
    text += '\n        even\n        include "bus_marker_kernel.i"\n'
    edge = stage / "src/rom/edge_kernel.asm"
    if pressure:
        observer = (stage / "src/rom/bus_marker_observer.i").read_text()
        appended = ""
        for mask in range(4):
            observer_text = observer.replace("bus_marker_observer:", f"bus_marker_observer_{mask}:")
            for bit, register in ((1, "d1"), (2, "d3")):
                if mask & bit:
                    observer_text = observer_text.replace(f"move.w $002(a6),{register}", f"move.w .dummy(pc),{register}")
            observer_text += "\n.dummy: dc.w $a55a\n"
            name = f"bus_marker_pressure_{mask}.i"
            (stage / "src/rom" / name).write_text(observer_text)
            appended += f'\n        dcb.b ${0xffca00 + mask * 0x200:06x}-*,0\n        include "{name}"\n'
        edge.write_text(edge.read_text() + appended)
    elif phasepad:
        observer = (stage / "src/rom/bus_marker_observer.i").read_text()
        appended = ""
        for phase, instruction in enumerate(("nop", "exg d0,d1")):
            observer_text = observer.replace("bus_marker_observer:", f"bus_marker_phase_{phase}:")
            if phase_entry:
                observer_text = observer_text.replace(".poll_start:", f".poll_start:\n        {instruction}")
            else:
                observer_text = observer_text.replace("        move.w d7,a2", f"        move.w d7,a2\n        {instruction}")
            name = f"bus_marker_phase_{phase}.i"
            (stage / "src/rom" / name).write_text(observer_text)
            appended += f'\n        dcb.b ${0xffca00 + phase * 0x200:06x}-*,0\n        include "{name}"\n'
        edge.write_text(edge.read_text() + appended)
    else:
        edge.write_text(edge.read_text() + '\n        dcb.b $ffca00-*,0\n        include "bus_marker_observer.i"\n')
    source.write_text(text)
    if onset:
        observer_path = stage / "src/rom/bus_marker_observer.i"
        observer_path.write_text(observer_path.read_text().replace("addi.w #$0040,d0", "addi.w #$0020,d0"))
    if completion:
        kernel = stage / "src/rom/bus_marker_kernel.i"
        text = kernel.read_text()
        text = text.replace(".list_end:\n        move.l #$fffffffe,(a0)",
                            ".list_end:\n        move.w #$4261,(a0)+\n        move.w #$7ffe,(a0)+\n        move.w #$009c,(a0)+\n        move.w #$8004,(a0)+\n        move.l #$fffffffe,(a0)")
        if pressure:
            text = text.replace("        jsr $ffca00", "        moveq #0,d0\n        move.w 8(a4),d0\n        lsl.w #8,d0\n        add.w d0,d0\n        lea $ffca00,a0\n        adda.w d0,a0\n        jsr (a0)")
        kernel.write_text(text)
    if phasepad:
        kernel = stage / "src/rom/bus_marker_kernel.i"
        kernel.write_text(kernel.read_text().replace("        jsr $ffca00", "        move.w 4(a4),d0\n        andi.w #16,d0\n        lsl.w #5,d0\n        lea $ffca00,a0\n        adda.w d0,a0\n        jsr (a0)"))
    original_root, original_trials = build_rom.ROOT, build_rom.trials
    try:
        build_rom.ROOT = stage
        build_rom.trials = lambda *args, **kwargs: trials(focused, completion, pressure, onset, phasepad, phase_entry)
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.ROOT, build_rom.trials = original_root, original_trials
    for path in (stage / "build/rom").iterdir():
        if path.is_file():
            shutil.copyfile(path, out / path.name)
    manifest["bus_marker"] = {
        "kind": 55, "focused": focused, "completion_marker": completion, "bus_pressure": pressure, "onset": onset, "phase_pad": phasepad, "phase_entry": phase_entry, "widths": [1, 16], "gates": list(range(0x20, 0x61, 4)) if onset else list(GATES),
        "variant": "bit0 BLTPRI; bit1 CPU launch; bit2 marker after size; bit3 no blit",
        "phase": "gate index", "delay": "mask: bit0/1 replaces first/second status read with equal-length 12-clock ROM read" if pressure else "reserved zero", "repeat": "two executions",
        "observer": "FFC A00 (FFCA00); four alternating INTREQR/DMACONR pairs, no stores between reads",
        "fields": {"launch_beam": "pre-train or pre-CPU-launch VHPOSR", "launch_ref": "post-train VHPOSR",
                   "end_beam": "settled VHPOSR; FFFF on watchdog", "end_ref": "settled INTREQR",
                   "20..34": "four INTREQR/DMACONR pairs; status and saved PC are raw samples",
                   "36..38": "settled first/last D words"},
        "units": "raw register values; beam brackets only; no inferred cycle offsets or trace alignment",
        "copper": "line66 h60 WAIT; marker/size adjacent moves; completion profile adds BFD=0 WAIT and INTREQ.SOFT",
        "limits": "CPU sequence starts after its gate; Copper sequence starts at fixed WAIT. Do not equate their gates to transfer timestamps."}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vasm", required=True)
    p.add_argument("--wsl", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--focused", action="store_true")
    p.add_argument("--completion", action="store_true", help="Copper-only completion marker sweep")
    p.add_argument("--pressure", action="store_true", help="replace early status reads with ROM traffic")
    p.add_argument("--onset", action="store_true", help="earlier gates with widths1/16 to distinguish launch delay")
    p.add_argument("--phasepad", action="store_true", help="NOP/EXG phase control across launch owners")
    p.add_argument("--phase-entry", action="store_true", help="phase control before polling, original read window")
    a = p.parse_args()
    build(a.vasm, a.wsl, a.out, a.focused, a.completion, a.pressure, a.onset, a.phasepad, a.phase_entry)
