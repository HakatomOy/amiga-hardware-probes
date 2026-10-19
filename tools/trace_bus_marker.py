#!/usr/bin/env python3
"""File-backed observational bus traces with explicit diagnostic provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_rom


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--romdir", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--reference-results", type=Path, required=True,
                   help="untraced emulator packet; must be byte-identical")
    a = p.parse_args()
    flags = {key: "1" for key in ("COPPERLINE_DIAG_BLT_SLOTS", "COPPERLINE_DIAG_COP_WRITES",
                                 "COPPERLINE_DIAG_CPU_READS")}
    original = run_rom._popen_with_binary_hash
    def launch(*args, **kwargs):
        kwargs["env"].update(flags)
        return original(*args, **kwargs)
    run_rom._popen_with_binary_hash = launch
    try:
        run_rom.run(a.binary.resolve(), a.out.resolve(), a.config.resolve(), a.romdir.resolve())
    finally:
        run_rom._popen_with_binary_hash = original
        if a.out.is_dir():
            (a.out / "diagnostic-environment.json").write_text(json.dumps(flags, indent=2) + "\n")
    expected = a.reference_results.read_bytes()
    actual = (a.out / "results.bin").read_bytes()
    same = actual == expected
    report = {"identical_to_untraced_packet": same, "reference": str(a.reference_results.resolve()),
              "reference_sha256": hashlib.sha256(expected).hexdigest(),
              "actual_sha256": hashlib.sha256(actual).hexdigest(), "trace": str(a.out / "run.log")}
    (a.out / "trace-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if same else 2


if __name__ == "__main__":
    raise SystemExit(main())
