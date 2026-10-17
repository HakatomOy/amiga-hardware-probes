#!/usr/bin/env python3
"""Build and archive the bounded kind50 Copper BBUSY onset pilot."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_ROWS = 768
REPEATS = range(2)
GATE_HPOS = (0x10, 0x18, 0x20, 0x28, 0x30, 0x38,
             0x40, 0x48, 0x50, 0x58, 0x60)
WIDTHS = (1, 8, 16)


def copper_start_busy_rows():
    """Kind50 fields: kind, width-index, variant, gate-index, reserved, repeat."""
    rows = [(50, width_index, variant, gate_index, 0, repeat)
            for width_index in range(len(WIDTHS))
            for variant in range(8)  # BLTPRI, read train, no-blit
            for gate_index in range(len(GATE_HPOS))
            for repeat in REPEATS]
    if len(rows) != 528 or len(rows) > MAX_ROWS:
        raise ValueError(f"kind50 matrix has invalid row count {len(rows)}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind50 descriptor matrix contains duplicate rows")
    for kind, width, variant, gate, reserved, repeat in rows:
        if kind != 50 or width not in range(3) or variant not in range(8):
            raise ValueError("kind50 descriptor outside its encoding")
        if gate not in range(len(GATE_HPOS)) or reserved != 0 or repeat not in REPEATS:
            raise ValueError("kind50 gate/reserved/repeat field outside its encoding")
    return rows


def snapshot_sources(out):
    sources = [ROOT / "build_copper_start_busy_rom.py", ROOT / "build_rom.py",
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


def build(assembler, wsl, out):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = copper_start_busy_rows()
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials
    shutil.copytree(ROOT / "build/rom", out)
    snapshot = snapshot_sources(out)
    manifest["copper_start_busy"] = dict(
        suite="copper_start_busy",
        kind=50,
        row_count=len(rows),
        descriptor_fields=["kind", "width_index", "variant", "gate_index",
                           "reserved_zero", "repeat"],
        widths_words=list(WIDTHS),
        variants={
            "bit0": "BLTPRI off/on",
            "bit1": "one DMACONR read / eight adjacent DMACONR reads",
            "bit2": "Copper BLTSIZE launch / two-word NOOP control",
            "bits3_15": "zero",
        },
        gate=dict(line=66, requested_hpos=list(GATE_HPOS),
                  source="VHPOSR polling; recorded +12 is the final poll value",
                  timeout_sentinel="+12/+14 are 0xffff when the bounded gate poll expires",
                  caution="Requested gate is not the read timestamp; use +12/+14 brackets and raw sample values."),
        copper=dict(
            initial_wait=(0x4261, 0xfffe),
            bltcon0=0x01ff,
            bltcon1=0,
            bltsize=dict(values=[0x0041, 0x0048, 0x0050], height=1,
                         width_words=list(WIDTHS), destination=0x10000),
            no_blit_slot=(0x01fe, 0x0000),
            bfd_wait=(0x4261, 0x7ffe),
            bfd=0,
            marker=(0x009c, 0x8010),
            copcon_cdang=True),
        observer=dict(
            irq_enabled=False,
            sync="CPU waits for line64 h>=0x20 with DMA disabled; clears stale INTREQ immediately before enabling COP DMA and starting COPJMP1",
            critical_path="Fixed ROM observer at FFC200 polls VHPOSR; it keeps the final full beam poll in A2, performs one or eight adjacent MOVE.W DMACONR reads into D0-D7 with no stores between reads, and captures post-train VHPOSR in A3. No DMACONR polling occurs during the interval.",
            registers=dict(before_beam="A2", after_beam="A3",
                           single_sample="D0", train_samples="D0..D7",
                           bbusy_bit=14),
            record_offsets={"pre_sample_vhposr": 12, "post_sample_vhposr": 14,
                            "settled_vhposr": 16,
                            "intreqr_after_raw_sample_stores": 18,
                            "dmaconr_samples": dict(offset=20, spacing=2,
                                                    count="1 or 8 selected by variant bit1"),
                            "final_first_d": 36, "final_last_d": 38,
                            "note": "Offsets +20..+34 are raw DMACONR samples in train mode; +32 is sample 7, not a canonical status field. In single mode only +20 is sampled and other sample slots retain the framework's zero initialization."},
            end_marker_wait="bounded INTREQR polling for COPER; IRQ remains masked",
            watchdogs=dict(sync_each=32768, gate=32768, marker=32768),
            marker_timeout_sentinel="+16 is 0xffff if COPER does not arrive within its bound"),
        blit=dict(launch_owner="Copper when variant bit2 is clear; none in NOOP control",
                  d_only=True, minterm=0xff,
                  expected_destination=0xffff, initial_destination=0xdead,
                  bltafwm=0xffff, bltalwm=0xffff,
                  bltamod=0, bltbmod=0, bltcmod=0, bltdmod=0,
                  priority_bit=10, dma_enable_bits=dict(master=9, copper=7, blitter=6)),
        source_snapshot=snapshot,
        source_sha256=hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the immutable ROM build archive")
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
