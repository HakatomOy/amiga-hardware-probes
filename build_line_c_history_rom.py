#!/usr/bin/env python3
"""Build and archive the isolated kind45 line-mode A/B/C history probe."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_rom

ROOT = Path(__file__).resolve().parent
MAX_PAYLOAD_ROWS = 2560


def line_c_history_rows(patterns=None):
    """Return the complete kind45 matrix or a requested priming-pattern subset."""
    catalog = build_rom.line_c_history_patterns()
    if patterns is None:
        selected = None
    else:
        names = {item["name"]: item["index"] for item in catalog}
        unknown = sorted(set(patterns) - set(names))
        if unknown:
            raise ValueError("unknown priming pattern(s): " + ", ".join(unknown))
        selected = sorted({names[name] for name in patterns})
    rows = build_rom.trials(line_c_history=True, line_c_history_subset=selected)
    if len(rows) > MAX_PAYLOAD_ROWS:
        raise ValueError(f"row count {len(rows)} exceeds boot payload limit {MAX_PAYLOAD_ROWS}")
    if len(rows) != len(set(rows)):
        raise ValueError("kind45 descriptor matrix contains duplicate rows")
    return rows


def snapshot_sources(out):
    """Archive the wrapper and all exact assembler inputs used for this ROM."""
    sources = [ROOT / "build_line_c_history_rom.py", ROOT / "build_rom.py", ROOT / "run_rom.py"]
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


def build(assembler, wsl, out, patterns=None):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"output archive already exists: {out}")
    rows = line_c_history_rows(patterns)
    catalog = build_rom.line_c_history_patterns()
    selected = None if patterns is None else sorted({item["index"] for item in catalog if item["name"] in patterns})
    manifest = build_rom.build(assembler, wsl=wsl, line_c_history=True,
                               line_c_history_subset=selected)
    shutil.copytree(ROOT / "build/rom", out,
                    ignore=shutil.ignore_patterns("expected-rebuild.json"))
    snapshot = snapshot_sources(out)
    manifest["line_c_history"] = dict(
        suite="line_c_history",
        row_count=len(rows),
        descriptor_fields=["kind", "preset", "priming_pattern", "phase", "observer", "repeat"],
        phase_values=[0],
        priming_patterns=catalog,
        selected_pattern_indices=selected,
        observer_values={0: "direct fixed ROM alignment; no pre-sample DMACONR poll",
                         1: "poll BBUSY clear before the eight DMACONR samples"},
        repeats=8,
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
    parser.add_argument("--patterns", help="optional comma-separated subset: " +
                        ",".join(item["name"] for item in build_rom.line_c_history_patterns()))
    args = parser.parse_args(argv)
    patterns = args.patterns.split(",") if args.patterns else None
    build(args.vasm, args.wsl, args.out, patterns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
