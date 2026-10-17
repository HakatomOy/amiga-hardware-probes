#!/usr/bin/env python3
"""Build and archive the kind49 BBUSY/final-D blitter handoff probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_PAYLOAD_ROWS = 2560
CHANNEL_MODES = (
    dict(id=0, name="D", bltcon0=0x01FF, output=0xFFFF),
    dict(id=1, name="AD", bltcon0=0x09F0, output=0xAAAA),
    dict(id=2, name="ABCD", bltcon0=0x0FFF, output=0xFFFF),
)
WIDTHS = (1, 2, 16)
VARIANTS = tuple(
    dict(id=(priority | (dma << 1)), priority=priority, dma_mode=dma)
    for priority in range(2) for dma in range(4)
)


def blitter_handoff_rows(channel_modes=range(3), width_indexes=range(3),
                         variants=range(8), phases=range(2), delays=range(8),
                         repeats=range(2)):
    """Generate kind49 rows: channel/width target, DMA/BLTPRI variant, phase, pad, repeat."""
    selections = (tuple(channel_modes), tuple(width_indexes), tuple(variants),
                  tuple(phases), tuple(delays), tuple(repeats))
    ranges = (range(3), range(3), range(8), range(2), range(8), range(2))
    names = ("channel modes", "width indexes", "variants", "phases", "delays", "repeats")
    for name, values, allowed in zip(names, selections, ranges):
        if not values or any(not isinstance(value, int) or value not in allowed for value in values):
            raise ValueError(f"{name} must be a non-empty valid selection")
        if len(set(values)) != len(values):
            raise ValueError(f"{name} must not contain duplicates")
    rows = [(49, channel * 3 + width, variant, phase, delay, repeat)
            for channel in selections[0] for width in selections[1]
            for variant in selections[2] for phase in selections[3]
            for delay in selections[4] for repeat in selections[5]]
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    return rows


def snapshot_sources(out):
    sources = [ROOT / "build_blitter_handoff_rom.py", ROOT / "build_rom.py"]
    sources += sorted(path for folder in (ROOT / "src/rom", ROOT / "vendor/rbcp")
                      for path in folder.rglob("*") if path.is_file())
    entries = []
    snapshot = out / "source_snapshot"
    for source in sources:
        relative = source.relative_to(ROOT)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        destination.write_bytes(data)
        entries.append(dict(path=relative.as_posix(), sha256=hashlib.sha256(data).hexdigest()))
    (snapshot / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")
    return entries


def metadata(rows, source_snapshot):
    return dict(
        suite="blitter_handoff",
        source_snapshot=source_snapshot,
        reference="Toni Wilen, EAB post #1422393: BLTCON0/BLTCON1 are safe to change after BBUSY clears, while final D may still be pending.",
        row_count=len(rows),
        descriptor_fields=["kind", "target", "variant", "phase", "delay", "repeat"],
        target_encoding="channel_mode * 3 + width_index",
        channel_modes=[dict(mode, width_index=index, words=WIDTHS[index],
                            bltsize=(1 << 6) | WIDTHS[index])
                       for mode in CHANNEL_MODES for index in range(len(WIDTHS))],
        variant_fields=dict(bit0="BLTPRI", bits2_1="DMA mode: 0 off, 1 four planes, 2 six planes, 3 six planes plus bounded Copper NOOP burst"),
        phase_values=[0, 1], delay_values=list(range(8)), repeat_values=[0, 1],
        expected_output="D-only and ABCD: FFFF; AD: AAAA. Early D read after first clear is observational and may precede the pending final write.",
        observer="Software observes BBUSY, immediately reads D and writes BLTCON0=0; leaves BLTEN enabled for 256 NOPs before final memory/interrupt reads.",
        poll_bound=4096,
        result_status=dict(offset=32, success=0, timeout=1),
        measurement=dict(kernel_base="0xffb000", status_offset=32,
                         fields={"launch_vhposr":12,"first_clear_dmaconr":14,"early_d":16,
                                 "postwrite_dmaconr":18,"handoff_vhposr":20,
                                 "postwrite_vhposr":22,"final_first_d":24,"final_last_d":26,
                                 "intreqr":28,"settled_vhposr":30,"status":32}),
    )


def build(assembler, wsl, out):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = blitter_handoff_rows()
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials
    shutil.copytree(ROOT / "build/rom", out)
    sources = snapshot_sources(out)
    manifest["blitter_handoff"] = metadata(rows, sources)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
