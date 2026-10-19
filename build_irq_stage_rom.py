#!/usr/bin/env python3
"""Build paired source/readback and CPU-recognition controls without editing base ROMs."""
import argparse
import json
from pathlib import Path
import shutil
import build_rom

ROOT = Path(__file__).resolve().parent
TARGETS = ("NOP_DBRA", "STORE_DBRA", "STOP", "TST_MEMORY_DBRA", "MASKED_INTREQR")
SOURCES = ("CIA_A_PORTS", "COPPER_COPER", "CIA_B_EXTER", "COPPER_PORTS", "COPPER_EXTER")
MASKS = (8, 16, 0x2000, 8, 0x2000)


def trials(repeats=2):
    if not 1 <= repeats <= 2:
        raise ValueError("repeats must be 1..2")
    return [(56, t, s, p, d, r) for t in range(5) for s in range(5)
            for p in range(4) for d in range(8) for r in range(repeats)]


def build(assembler, wsl, out, repeats=2, aligned=False, rows=None, transform=None, profile=None):
    selected_rows = trials(repeats) if rows is None else rows
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out / "source_snapshot"
    shutil.copytree(ROOT / "src", stage / "src")
    shutil.copytree(ROOT / "vendor/rbcp", stage / "vendor/rbcp")
    for name in ("build_rom.py", "build_irq_stage_rom.py"):
        shutil.copyfile(ROOT / name, stage / name)
    p = stage / "src/rom/experiment.asm"
    text = p.read_text()
    anchor = "        cmpi.w #10,(a4)"
    assert text.count(anchor) == 1
    text = text.replace(anchor, "        cmpi.w #56,(a4)\n        beq .irq_stage\n" + anchor)
    text = text.replace(".channels:\n", ".irq_stage:\n        jsr irq_stage_trial\n        bra.w .recorded\n.channels:\n", 1)
    if aligned:
        text_kernel = stage / "src/rom/irq_stage_kernel.i"
        text_kernel.write_text(text_kernel.read_text().replace("        jsr sync_beam\n", "        jsr sync_beam\n        jsr $fb0000\n").replace("#$4261", "#$4461").replace("#$4661", "#$4861"))
        observer = stage / "src/rom/irq_stage_observer.i"
        observer_text = observer.read_text().replace("rept 128", "rept 384")
        observer_text = observer_text.replace(".raw:\n", ".raw:\n        move.w 4(a4),d0\n        beq.w .raw_padding\n        cmpi.w #2,d0\n        beq.w .raw_padding\n        rept 88\n        nop\n        endr\n.raw_padding:\n")
        observer.write_text(observer_text)
    p.write_text(text + '\n        even\n        include "irq_stage_kernel.i"\n')
    p = stage / "src/rom/edge_kernel.asm"
    p.write_text(p.read_text() + '\n        dcb.b $ffca00-*,0\n        include "irq_stage_observer.i"\n')
    if transform is not None:
        transform(stage)
    old_root, old_trials = build_rom.ROOT, build_rom.trials
    try:
        build_rom.ROOT = stage
        build_rom.trials = lambda *a, **k: selected_rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.ROOT, build_rom.trials = old_root, old_trials
    for p in (stage / "build/rom").iterdir():
        if p.is_file():
            shutil.copyfile(p, out / p.name)
    manifest["irq_stage"] = dict(kind=56, aligned=aligned, targets=TARGETS, sources=SOURCES,
        masks=MASKS, phases="NOP bit0 (+2 CCK), EXG bit1 (+3 CCK); conditional branch costs also apply; recorded brackets are authoritative",
        event_offset="CIA Timer-A latch32+offset E clocks; Copper WAIT line%d h60+2*offset CCK" % (68 if aligned else 66),
        watchdog="Copper SOFT level1 at line%d h60; all ordinary handlers disable all sources" % (72 if aligned else 70),
        units="raw VHPOSR words, register flags, absolute stacked PC; no alignment or packed-beam subtraction",
        launch="pre/post source release VHPOSR; exact bracket cohorts only",
        masked_fields={"counter": "raw0", "icr": "raw1", "irq_beam": "raw2",
                       "irq_level": "beam0", "saved_pc_offset": "beam1:beam2",
                       "aux": "beam3", "second_counter_or_beam": "settled INTREQR",
                       "second_icr_or_level": "expected source mask"},
        limitations="Request readback is not an electrical IPL timestamp; instruction polls and exception entry remain combined in handler beam")
    if profile is not None:
        manifest["irq_stage"].update(profile)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("source_id", "trial_count", "rom_sha256")}))
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vasm", required=True)
    p.add_argument("--wsl", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--aligned", action="store_true")
    a = p.parse_args()
    build(a.vasm, a.wsl, a.out, a.repeats, a.aligned)
