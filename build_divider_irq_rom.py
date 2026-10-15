#!/usr/bin/env python3
"""Build and archive the A500 DIVS/DIVU interrupt timing probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_ROWS = (0x7E000 - 0x40000 - 64) // 40
# The boot payload must stay below $10000 before the edge kernel at $f90000.
# The current default is 2,560 rows; wider delay ranges need a smaller matrix.
MAX_PAYLOAD_ROWS = 2560

# Signed operands are the actual 32-bit dividend and 16-bit divisor values
# consumed by the kind20 measurement. Positive variant IDs are reserved by this
# standalone probe; variant zero remains available to the legacy suite.
DIVS_OPERANDS = (
    dict(variant=1, name="positive_by_positive", dividend=100, divisor=3,
         description="100 / 3"),
    dict(variant=2, name="positive_by_negative", dividend=100, divisor=-3,
         description="100 / -3"),
    dict(variant=3, name="negative_by_positive", dividend=-100, divisor=3,
         description="-100 / 3"),
    dict(variant=4, name="negative_by_negative", dividend=-100, divisor=-3,
         description="-100 / -3"),
    dict(variant=5, name="zero_by_negative", dividend=0, divisor=-3,
         description="0 / -3"),
    dict(variant=6, name="quotient_overflow", dividend=100000, divisor=-2,
         description="100000 / -2; signed quotient does not fit in 16 bits",
         overflow="signed_quotient"),
    dict(variant=7, name="absolute_early_overflow", dividend=0x10000000, divisor=-1,
         description="0x10000000 / -1; nonzero upper dividend word",
         overflow="absolute_early"),
    dict(variant=8, name="minimum_by_negative_one", dividend=-2147483648, divisor=-1,
         description="-2147483648 / -1; absolute dividend overflows early",
         overflow="absolute_early"),
)
DIVU_OPERANDS = (
    dict(variant=1, name="positive_by_positive", dividend=100, divisor=3,
         description="100 / 3 as unsigned words"),
    dict(variant=2, name="positive_by_negative_bits", dividend=100, divisor=-3,
         description="100 / 0xFFFD as unsigned words"),
)
TARGETS = (
    dict(target=3, name="DIVS", description="signed word divide"),
    dict(target=0, name="DIVU_control", description="unsigned word divide control"),
)


def divider_irq_operands():
    """Return the auditable operand definitions used by the row matrix."""
    return {"DIVS": [dict(row) for row in DIVS_OPERANDS],
            "DIVU": [dict(row) for row in DIVU_OPERANDS]}


def divider_irq_rows(delays=range(64), repeats=1):
    """Generate kind20 descriptors: target, operand variant, phase, delay, repeat."""
    delays = tuple(delays)
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if not delays or any(not isinstance(delay, int) or not 0 <= delay <= 95 for delay in delays):
        raise ValueError("delays must be a non-empty selection from 0..95")
    if len(set(delays)) != len(delays):
        raise ValueError("delays must not contain duplicates")
    rows = []
    for target, operands in ((3, DIVS_OPERANDS), (0, DIVU_OPERANDS)):
        for operand in operands:
            for phase in range(4):
                for delay in delays:
                    for repeat in range(repeats):
                        rows.append((20, target, operand["variant"], phase, delay, repeat))
    if len(rows) > MAX_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds builder capacity {MAX_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("descriptor matrix contains duplicate rows")
    return rows


def parse_delays(value):
    """Parse an inclusive integer interval such as 0..95."""
    try:
        first, last = (int(part) for part in value.split("..", 1))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("use an inclusive range such as 0..95") from exc
    if first < 0 or last > 95 or first > last:
        raise argparse.ArgumentTypeError("delay range must be within 0..95")
    return range(first, last + 1)


def snapshot_sources(out):
    """Archive the exact wrapper and assembler inputs used to make the ROM."""
    sources = [ROOT / "build_divider_irq_rom.py", ROOT / "build_rom.py"]
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


def divider_irq_metadata(rows, delays, repeats, source_snapshot=None):
    """Build the archive manifest section, including wrapper provenance."""
    return dict(
        suite="divider_irq",
        source_sha256=hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        source_snapshot=source_snapshot or [],
        row_count=len(rows),
        repeats=repeats,
        delays=list(delays),
        targets=[dict(row) for row in TARGETS],
        operands=divider_irq_operands(),
        descriptor_fields=["kind", "target", "variant", "phase", "delay", "repeat"],
        phase_values=list(range(4)),
        observer="A500 IRQ timing; DMA disabled",
    )


def build(assembler, wsl, out, delays=range(64), repeats=1):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = divider_irq_rows(delays, repeats)
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(
            f"row count {len(rows)} exceeds the boot payload limit {MAX_PAYLOAD_ROWS}; "
            "reduce --delays or --repeats"
        )
    original_trials = build_rom.trials
    try:
        build_rom.trials = lambda *args, **kwargs: rows
        manifest = build_rom.build(assembler, wsl=wsl, edges=True)
    finally:
        build_rom.trials = original_trials

    shutil.copytree(ROOT / "build/rom", out)
    archived_manifest = out / "manifest.json"
    source_snapshot = snapshot_sources(out)
    metadata = divider_irq_metadata(rows, delays, repeats, source_snapshot)
    manifest["divider_irq"] = metadata
    archived_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vasm", default="vasmm68k_mot")
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--out", type=Path, required=True,
                        help="new directory receiving the completed build/rom archive")
    parser.add_argument("--delays", type=parse_delays, default=range(64), metavar="FIRST..LAST",
                        help="inclusive delay range (default: 0..63; wider matrices may exceed payload size)")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args(argv)
    build(args.vasm, args.wsl, args.out, args.delays, args.repeats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
