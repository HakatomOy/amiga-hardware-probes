#!/usr/bin/env python3
"""Build and archive the focused kind43 IRQ/ordinary-CPU timing probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_ROWS = (0x7E000 - 0x40000 - 64) // 40
MAX_PAYLOAD_ROWS = 2560
SAFE_STOP_MAX_DELAY = 40
PHASES = range(4)
DEFAULT_TARGETS = (0, 1, 2, 3, 4, 5, 6, 7, 10)

TARGETS = (
    dict(target=0, name="INTREQR_masked_COPER", description="masked Copper COPER request; read INTREQR"),
    dict(target=1, name="NOP", description="ordinary CPU NOP"),
    dict(target=2, name="MOVEQ", description="ordinary CPU MOVEQ #7,D0"),
    dict(target=3, name="EXG", description="ordinary CPU EXG D0,D1"),
    dict(target=4, name="TST_W_D0", description="ordinary CPU TST.W D0"),
    dict(target=5, name="TST_W_A1", description="ordinary CPU TST.W (A1)"),
    dict(target=6, name="TST_W_d16_A1", description="ordinary CPU TST.W 0(A1)"),
    dict(target=7, name="TST_L_A1", description="ordinary CPU TST.L (A1)"),
    dict(target=8, name="DIVU", description="ordinary CPU DIVU.W D3,D0 with D0=100 and D3=3"),
    dict(target=9, name="DIVS", description="ordinary CPU DIVS.W D3,D0 with D0=100 and D3=-3"),
    dict(target=10, name="STOP", description="ordinary CPU STOP instruction"),
)


def irq_focus_rows(targets=DEFAULT_TARGETS, delays=range(64), repeats=1):
    """Generate kind43 descriptors: target, variant, phase, delay, repeat."""
    targets, delays = tuple(targets), tuple(delays)
    valid_targets = {row["target"] for row in TARGETS}
    if not targets or any(not isinstance(target, int) or target not in valid_targets
                          for target in targets):
        raise ValueError("targets must be a non-empty selection from 0..10")
    if len(set(targets)) != len(targets):
        raise ValueError("targets must not contain duplicates")
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if not delays or any(not isinstance(delay, int) or not 0 <= delay <= 95
                         for delay in delays):
        raise ValueError("delays must be a non-empty selection from 0..95")
    if len(set(delays)) != len(delays):
        raise ValueError("delays must not contain duplicates")
    stop_delays = tuple(delay for delay in delays if delay <= SAFE_STOP_MAX_DELAY)
    if 10 in targets and not stop_delays:
        raise ValueError(
            f"target 10 STOP requires at least one delay at or below {SAFE_STOP_MAX_DELAY}")
    rows = [(43, target, 0, phase, delay, repeat)
            for target in targets for phase in PHASES
            for delay in (stop_delays if target == 10 else delays)
            for repeat in range(repeats)]
    if len(rows) > MAX_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds builder capacity {MAX_ROWS}")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(
            f"row count {len(rows)} exceeds the boot payload limit {MAX_PAYLOAD_ROWS}; "
            "reduce --targets, --delays, or --repeats")
    if len(rows) != len(set(rows)):
        raise ValueError("descriptor matrix contains duplicate rows")
    return rows


def parse_targets(value):
    """Parse comma-separated target IDs, for example 0,1,10."""
    try:
        targets = tuple(int(part.strip(), 10) for part in value.split(","))
    except (AttributeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("use comma-separated target IDs such as 0,1,10") from exc
    valid = {row["target"] for row in TARGETS}
    if not targets or any(target not in valid for target in targets):
        raise argparse.ArgumentTypeError("target IDs must be selected from 0..10")
    if len(set(targets)) != len(targets):
        raise argparse.ArgumentTypeError("target IDs must not contain duplicates")
    return targets


def parse_delays(value):
    """Parse an inclusive integer interval such as 0..95."""
    try:
        first, last = (int(part) for part in value.split("..", 1))
    except (AttributeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("use an inclusive range such as 0..95") from exc
    if first < 0 or last > 95 or first > last:
        raise argparse.ArgumentTypeError("delay range must be within 0..95")
    return range(first, last + 1)


def snapshot_sources(out):
    """Archive the wrapper and exact assembler inputs used for the ROM."""
    sources = [ROOT / "build_irq_focus_rom.py", ROOT / "build_rom.py"]
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


def irq_focus_metadata(rows, targets, delays, repeats, source_snapshot=None):
    """Return the archive manifest section for this experiment."""
    selected = set(targets)
    return dict(
        suite="irq_focus",
        source_sha256=hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        source_snapshot=source_snapshot or [],
        row_count=len(rows),
        repeats=repeats,
        delays=list(delays),
        targets=[dict(row) for row in TARGETS if row["target"] in selected],
        variant=dict(variant=0, name="COPER_INTREQ_mask_0x0010"),
        descriptor_fields=["kind", "target", "variant", "phase", "delay", "repeat"],
        phase_values=list(PHASES),
        safe_stop_max_delay=SAFE_STOP_MAX_DELAY,
        observer="A500 masked Copper COPER request and ordinary CPU instruction/IRQ observations; DMA disabled",
        measurement=dict(
            kernel_base="0xf95000", kernel_slot_stride="0x400", straight_line_nops=128,
            entry_launch_offset=12, masked_before_offset=14, raw_counter_offset=20,
            irq_beam_offset=24, saved_pc_offset=28, marker_irq_offset=34,
            masked_after_offset=36, final_marker_offset=38),
    )


def build(assembler, wsl, out, targets=DEFAULT_TARGETS, delays=range(64), repeats=1):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    targets, delays = tuple(targets), tuple(delays)
    rows = irq_focus_rows(targets, delays, repeats)
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials

    shutil.copytree(ROOT / "build/rom", out)
    archived_manifest = out / "manifest.json"
    source_snapshot = snapshot_sources(out)
    manifest["irq_focus"] = irq_focus_metadata(
        rows, targets, delays, repeats, source_snapshot)
    archived_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the completed build/rom archive")
    parser.add_argument("--targets", type=parse_targets, default=DEFAULT_TARGETS,
                        help="comma-separated target IDs (default: 0,1,2,3,4,5,6,7,10)")
    parser.add_argument("--delays", type=parse_delays, default=range(64), metavar="FIRST..LAST",
                        help="inclusive delay range (default: 0..63)")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out, args.targets, args.delays, args.repeats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
