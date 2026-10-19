#!/usr/bin/env python3
"""Build isolated, immutable bus-marker HW checks without changing in-progress probes."""
import argparse
import json
from pathlib import Path
import shutil

import build_rom

ROOT = Path(__file__).resolve().parent
GATES = tuple(range(0x40, 0x75, 4))


def trials(focused=False, completion=False):
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


def build(assembler, wsl, out, focused=False, completion=False):
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
    edge.write_text(edge.read_text() + '\n        dcb.b $ffca00-*,0\n        include "bus_marker_observer.i"\n')
    source.write_text(text)
    if completion:
        kernel = stage / "src/rom/bus_marker_kernel.i"
        text = kernel.read_text()
        text = text.replace(".list_end:\n        move.l #$fffffffe,(a0)",
                            ".list_end:\n        move.w #$4261,(a0)+\n        move.w #$7ffe,(a0)+\n        move.w #$009c,(a0)+\n        move.w #$8004,(a0)+\n        move.l #$fffffffe,(a0)")
        kernel.write_text(text)
    original_root, original_trials = build_rom.ROOT, build_rom.trials
    try:
        build_rom.ROOT = stage
        build_rom.trials = lambda *args, **kwargs: trials(focused, completion)
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.ROOT, build_rom.trials = original_root, original_trials
    for path in (stage / "build/rom").iterdir():
        if path.is_file():
            shutil.copyfile(path, out / path.name)
    manifest["bus_marker"] = {
        "kind": 55, "focused": focused, "completion_marker": completion, "widths": [1, 16], "gates": list(GATES),
        "variant": "bit0 BLTPRI; bit1 CPU launch; bit2 marker after size; bit3 no blit",
        "phase": "gate index", "delay": "reserved zero", "repeat": "two executions",
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
    a = p.parse_args()
    build(a.vasm, a.wsl, a.out, a.focused, a.completion)
