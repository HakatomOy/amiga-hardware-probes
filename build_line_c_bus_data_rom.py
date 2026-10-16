#!/usr/bin/env python3
"""Build and archive the controlled kind46 post-BLTSIZE CPU bus write probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_PAYLOAD_ROWS = 2560


def line_c_bus_data_rows():
    """Return the full 16 ASHIFT x 6 CPU-word x 2-region x 8-repeat matrix."""
    rows = build_rom.trials(line_c_bus_data=True)
    expected = 16 * len(build_rom.line_c_bus_data_patterns()) * len(build_rom.line_c_bus_data_regions()) * 8
    if len(rows) != expected:
        raise ValueError(f"kind46 matrix has {len(rows)} rows, expected {expected}")
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind46 descriptor matrix contains duplicate rows")
    if any(row[0] != 46 or row[4] != 0 for row in rows):
        raise ValueError("kind46 descriptors must use kind 46 and fixed delay zero")
    return rows


def snapshot_sources(out):
    """Archive this wrapper and every source file used to assemble the ROM."""
    sources = [ROOT / "build_line_c_bus_data_rom.py", ROOT / "build_rom.py", ROOT / "run_rom.py"]
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
        entries.append(dict(path=relative.as_posix(), sha256=hashlib.sha256(data).hexdigest()))
    (snapshot / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")
    return entries


def build(assembler, wsl, out):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = line_c_bus_data_rows()
    manifest = build_rom.build(assembler, wsl=wsl, line_c_bus_data=True)
    shutil.copytree(ROOT / "build/rom", out)
    snapshot = snapshot_sources(out)
    manifest["line_c_bus_data"] = dict(
        suite="line_c_bus_data",
        row_count=len(rows),
        descriptor_fields=["kind", "ashift", "pattern_index", "scratch_region_index", "fixed_delay", "repeat"],
        ashift_values=list(range(16)),
        patterns=build_rom.line_c_bus_data_patterns(),
        scratch_regions=build_rom.line_c_bus_data_regions(),
        fixed_delay=0,
        repeats=8,
        line=dict(a_data=0x8000, b_data=0, c_data=0, bltcon0_base=0x0bca,
                  bltcon1=0x0001, bshift=0, bltapt=-80, bltsize=0x0082,
                  c_source=0x11000, d_destination=0x10000),
        observer_address=0xff7800,
        write_sequence=["BLTSIZE write", "MOVE.W D3,(A3)", "8 adjacent DMACONR reads"],
        source_addresses=dict(a=0x12000, b=0x16000, c=0x11000),
        source_lengths=dict(a=16, b=16, c=164),
        runtime_memory_check=dict(expected_source_value=0,
                                  source_lengths=dict(a=16, b=16, c=164),
                                  scratch_addresses=[0x18000, 0x00c01000],
                                  expected_final_scratch_word=0xd7ff),
        source_snapshot=snapshot,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
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
