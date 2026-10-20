#!/usr/bin/env python3
"""Build and archive the bounded kind51 CIA-A/Copper interrupt probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_ROWS = 1536
TARGETS = (0, 1, 2, 3)
SOURCES = (0, 1, 2)  # CIA-A PORTS / Copper COPER / CIA-B EXTER
PHASES = range(4)
EVENT_OFFSETS = range(16)
REPEATS = range(2)
TARGET_INFO = {
    0: dict(name="NOP_ROM", operation="NOP; DBRA D1,loop", storage="ROM"),
    1: dict(name="MOVE_B_predecrement_ROM", operation="MOVE.B D0,-(A1); DBRA D1,loop", storage="ROM"),
    2: dict(name="NOP_CHIP", operation="NOP; DBRA D1,loop", storage="CHIP RAM"),
    3: dict(name="MOVE_B_predecrement_CHIP", operation="MOVE.B D0,-(A1); DBRA D1,loop", storage="CHIP RAM"),
}
SOURCE_INFO = {
    0: dict(name="CIA_A_Timer_A_PORTS", level=2,
            timing="one-shot Timer-A count 16+event_offset E-clock ticks"),
    1: dict(name="Copper_COPER", level=3,
            timing="line65 WAIT at hpos 0x50+8*event_offset color clocks"),
    2: dict(name="CIA_B_Timer_A_EXTER", level=6,
            timing="one-shot Timer-A count 16+event_offset E-clock ticks"),
}


def cia_cpu_irq_rows(targets=TARGETS, sources=SOURCES, phases=PHASES,
                     event_offsets=EVENT_OFFSETS, repeats=2):
    """Return unique (kind,target,source,phase,event_offset,repeat) rows."""
    targets, sources = tuple(targets), tuple(sources)
    phases, event_offsets = tuple(phases), tuple(event_offsets)
    if not targets or any(not isinstance(v, int) or v not in TARGETS for v in targets):
        raise ValueError("targets must be a non-empty selection from 0..3")
    if len(set(targets)) != len(targets):
        raise ValueError("targets must not contain duplicates")
    if not sources or any(not isinstance(v, int) or v not in SOURCES for v in sources):
        raise ValueError("sources must be a non-empty selection from 0..2")
    if len(set(sources)) != len(sources):
        raise ValueError("sources must not contain duplicates")
    if not phases or any(not isinstance(v, int) or v not in PHASES for v in phases):
        raise ValueError("phases must be a non-empty selection from 0..3")
    if len(set(phases)) != len(phases):
        raise ValueError("phases must not contain duplicates")
    if not event_offsets or any(not isinstance(v, int) or v not in EVENT_OFFSETS
                                for v in event_offsets):
        raise ValueError("event_offsets must be a non-empty selection from 0..15")
    if len(set(event_offsets)) != len(event_offsets):
        raise ValueError("event_offsets must not contain duplicates")
    if not isinstance(repeats, int) or repeats < 1 or repeats > 2:
        raise ValueError("repeats must be 1 or 2")
    rows = [(51, target, source, phase, event_offset, repeat)
            for target in targets for source in sources for phase in phases
            for event_offset in event_offsets for repeat in range(repeats)]
    if len(rows) > MAX_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds pilot cap {MAX_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("descriptor matrix contains duplicate rows")
    return rows


def snapshot_sources(out):
    """Archive the wrapper and exact ROM/runner sources used for the build."""
    sources = [ROOT / "build_cia_cpu_irq_rom.py", ROOT / "build_rom.py",
               ROOT / "run_rom.py", ROOT / "run_winuae_rom.py"]
    sources += sorted(path for folder in (ROOT / "src/rom", ROOT / "vendor/rbcp")
                      for path in folder.rglob("*") if path.is_file())
    snapshot = out / "source_snapshot"
    entries = []
    for source in sources:
        relative = source.relative_to(ROOT)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        entries.append(dict(path=relative.as_posix(),
                            sha256=hashlib.sha256(data).hexdigest()))
    (snapshot / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")
    return entries


def metadata(rows, repeats, source_snapshot=None):
    return dict(
        suite="cia_cpu_irq",
        kind=51,
        row_count=len(rows),
        repeats=repeats,
        descriptor_fields=["kind", "target", "source", "phase", "event_offset", "repeat"],
        targets=[dict(target=target, **TARGET_INFO[target]) for target in TARGETS],
        sources=[dict(source=source, **SOURCE_INFO[source]) for source in SOURCES],
        target_bits={"bit0": "0=Nop loop, 1=MOVE.B D0,-(A1) loop",
                     "bit1": "0=fixed ROM execution, 1=exact observer copy in CHIP RAM at 0x1c000"},
        phase=dict(values=list(PHASES), meaning="0..3 NOP instructions immediately before source release"),
        event_offset=dict(values=list(EVENT_OFFSETS),
            warning="CIA E-clock and Copper color-clock values are separate requested axes; compare captured beam values, not numeric offsets."),
        observer=dict(
            fixed_rom_range=["0xffc600", "0xffca00"],
            chip_copy=dict(source="0xffc600..0xffc9ff", destination="0x1c000..0x1c3ff",
                           copied_before_trials=True, size=0x400,
                           code_references="observer loops and phase table use PC-relative addresses; IRQ vectors remain fixed in ROM"),
            loop_iterations=128,
            completion_poll=False,
            irq="single level-2 CIA-A PORTS, level-3 Copper COPER, or level-6 CIA-B EXTER; handler stores first VHPOSR before saving registers, stacked PC, D1 and A1, then acknowledges/disables the selected source",
            source_release_beams={"pre_start": "D2 captures VHPOSR immediately before selected CIA CRA start or Copper COPJMP1; copied to +14 after the loop",
                                  "post_start": "D3 captures VHPOSR immediately after selected CIA CRA start or Copper COPJMP1, before SR=$2000; copied to +12 after the loop"},
            timer_a=dict(latch="16+event_offset", units="E-clock ticks", one_shot=True,
                         cia_a=dict(icr=0xbfec01, cra=0xbfed01, icr_mask=0x81, custom_intena=0xc008, intreq_ack=0x0008),
                         cia_b=dict(icr=0xbfdd00, cra=0xbfde00, icr_mask=0x81, custom_intena=0xe000, intreq_ack=0x2000)),
            copper=dict(wait_line=65, wait_hpos="0x50+8*event_offset", wait_mask=0xfffe,
                        marker=(0x009c, 0x8010), custom_intena=0xc010,
                        dmacon=0x8280, copjmp1=True),
            loops={"bit0_clear": "NOP; DBRA D1,loop", "bit0_set": "MOVE.B D0,-(A1); DBRA D1,loop",
                   "initial_d1": 127, "move_value": 0x5a, "a1_start": 0x18100,
                   "move_range": [0x18080, 0x180ff]},
            record_offsets={"post_start_vhposr": 12, "pre_start_vhposr": 14,
                            "loop_end_beam": 16, "cia_icr_at_irq": 18,
                            "d1_at_irq": 20, "a1_low_at_irq": 22,
                            "irq_vhposr": 24, "irq_level": 26,
                            "stacked_pc_normalized_to_loop_entry": 28, "status": 32,
                            "event_count": 34, "final_d1": 36,
                            "final_a1_low": 38},
            status={"0": "exactly one event received", "1": "event count was not exactly one"},
            watchdogs=dict(sync_beam="existing sync_beam routine", loop="128 fixed iterations; no polling")),
        source_snapshot=source_snapshot or [],
        source_sha256=hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    )


def build(assembler, wsl, out, repeats=2):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = cia_cpu_irq_rows(repeats=repeats)
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials
    shutil.copytree(ROOT / "build/rom", out)
    source_snapshot = snapshot_sources(out)
    manifest["cia_cpu_irq"] = metadata(rows, repeats, source_snapshot)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the immutable ROM build archive")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out, args.repeats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
