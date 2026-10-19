#!/usr/bin/env python3
"""Build isolated, immutable CIA HW checks without changing in-progress probes."""
import argparse
import json
from pathlib import Path
import shutil

import build_rom

ROOT = Path(__file__).resolve().parent
SERIAL_DELAYS = (0, 4, 8, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
PB_DELAYS = (0, 1, 2, 3, 4, 7, 15, 31, 63, 127)


def trials():
    serial = [(52, cia, mask, latch, delay, repeat)
              for cia in range(2) for mask in range(2) for latch in (1, 2, 3)
              for delay in SERIAL_DELAYS for repeat in range(2)]
    pb = [(53, cia, mode, latch, delay, repeat)
          for cia in range(2) for mode in range(8) for latch in range(5)
          for delay in PB_DELAYS for repeat in range(2)]
    auto = [(54, cia, mode, latch, delay, repeat)
            for cia in range(2) for mode in (2, 3, 6, 7) for latch in (0, 1, 4)
            for delay in (0, 31, 127) for repeat in range(2)]
    return serial + pb + auto


def build(assembler, wsl, out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out / "source_snapshot"
    shutil.copytree(ROOT / "src", stage / "src")
    shutil.copytree(ROOT / "vendor/rbcp", stage / "vendor/rbcp")
    for name in ("build_rom.py", "build_cia_hardware_verify.py"):
        shutil.copyfile(ROOT / name, stage / name)
    source = stage / "src/rom/experiment.asm"
    text = source.read_text()
    anchor = "        cmpi.w #10,(a4)"
    assert text.count(anchor) == 1
    text = text.replace(anchor, "        cmpi.w #52,(a4)\n        beq .cia_hw_verify\n        cmpi.w #53,(a4)\n        beq .cia_hw_verify\n        cmpi.w #54,(a4)\n        beq .cia_hw_verify\n" + anchor)
    text = text.replace(".channels:\n", ".cia_hw_verify:\n        jsr cia_hardware_verify_trial\n        bra.w .recorded\n.channels:\n", 1)
    text += '\n        even\n        include "cia_hardware_verify.i"\n'
    source.write_text(text)
    original_root, original_trials = build_rom.ROOT, build_rom.trials
    try:
        build_rom.ROOT = stage
        build_rom.trials = lambda *args, **kwargs: trials()
        manifest = build_rom.build(assembler, wsl=wsl)
    finally:
        build_rom.ROOT, build_rom.trials = original_root, original_trials
    for path in (stage / "build/rom").iterdir():
        if path.is_file():
            shutil.copyfile(path, out / path.name)
    manifest["cia_hardware_verification"] = {
        "kinds": {"52": "serial SP completion", "53": "TA PB6 pulse/toggle", "54": "TA high-byte one-shot auto-start PB6"},
        "target": "0=CIA-A, 1=CIA-B", "variant52": "0=SP masked, 1=SP enabled",
        "variant53": "bit0 toggle, bit1 one-shot, bit2 DDRB=FF rather than 00", "phase": "latch index into 0,1,3,15,200",
        "delay": "DBRA delay, not an E-clock timestamp", "repeat": "two executions",
        "fields": {"launch_beam": "post-start VHPOSR", "launch_ref": "TB cascade bracket before observations",
                   "end_beam": "VHPOSR after live PB read", "end_ref": "TB cascade bracket after observations",
                   "counter": "ICR snapshot", "icr": "settled PB pins", "irq_beam": "raw INTREQR before ICR",
                   "irq_level": "live PB pins", "saved_pc_offset": "high16=PB before PBON, low16=pre-start VHPOSR; not PC",
                   "aux": "PB pins before START", "second_counter_or_beam": "stopped TA",
                   "second_icr_or_level": "stopped TB cascade count", "status": "0=collected"},
        "units": "raw registers; underflows=65535-TB; no trace alignment or inferred CPU delay",
        "setup": "Serial pipeline drained at latch1 for 256 DBRA iterations, stopped and settled; one-shot configured only after high-byte latch write",
        "limits": "TB cascade is one edge delayed; before/after counts bracket observations; all CPU IRQs masked; no pin propagation claim from beam differences"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vasm", required=True)
    p.add_argument("--wsl", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    build(a.vasm, a.wsl, a.out)
