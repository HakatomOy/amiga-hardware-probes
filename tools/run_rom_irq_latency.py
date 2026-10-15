#!/usr/bin/env python3
"""Run a ROM capture with a diagnostic Copperline IRQ latency override."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_rom

ENVIRONMENT_KEY = "COPPERLINE_IRQ_LATENCY_CCK"


def _validate_latency(latency):
    if not isinstance(latency, int) or isinstance(latency, bool) or not 0 <= latency <= 16:
        raise ValueError("latency must be an integer from 0 through 16")


def _invoke_with_latency(callback, latency):
    """Temporarily inject one environment setting into run_rom's Popen calls."""
    _validate_latency(latency)
    original_popen = run_rom.subprocess.Popen

    def injected_popen(*args, **kwargs):
        environment = dict(kwargs.get("env") or os.environ)
        environment[ENVIRONMENT_KEY] = str(latency)
        kwargs["env"] = environment
        return original_popen(*args, **kwargs)

    try:
        run_rom.subprocess.Popen = injected_popen
        return callback()
    finally:
        run_rom.subprocess.Popen = original_popen


def _mark_diagnostic(out, binary, latency):
    manifest_path = out / "build-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["diagnostic_only"] = True
    manifest["diagnostic_irq_latency_cck"] = latency
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    invocation_path = out / "invocation.json"
    invocation = json.loads(invocation_path.read_text())
    invocation["diagnostic_irq_latency_cck"] = latency
    invocation["diagnostic_only"] = True
    invocation_path.write_text(json.dumps(invocation, indent=2) + "\n")

    results_path = out / "results.json"
    if results_path.exists():
        results = json.loads(results_path.read_text())
        results["metadata"]["diagnostic_only"] = True
        results["metadata"]["diagnostic_irq_latency_cck"] = latency
        results_path.write_text(json.dumps(results, indent=2) + "\n")

    diagnostic = {
        "classification": "diagnostic_only",
        "accepted_as_final_comparison": False,
        "diagnostic_irq_latency_cck": latency,
        "environment_override": {ENVIRONMENT_KEY: str(latency)},
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    (out / "diagnostic.json").write_text(json.dumps(diagnostic, indent=2) + "\n")


def run(binary, romdir, out, latency):
    _validate_latency(latency)
    binary, romdir, out = Path(binary).resolve(), Path(romdir).resolve(), Path(out).resolve()
    _invoke_with_latency(lambda: run_rom.run(binary, out, romdir=romdir), latency)
    _mark_diagnostic(out, binary, latency)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True,
                        help="Copperline executable")
    parser.add_argument("--romdir", type=Path, required=True,
                        help="directory containing a built timing ROM")
    parser.add_argument("--out", type=Path, required=True,
                        help="new output directory for this diagnostic capture")
    parser.add_argument("--latency", type=int, required=True, metavar="CCK",
                        help="diagnostic IRQ latency override from 0 through 16")
    args = parser.parse_args(argv)
    _validate_latency(args.latency)
    run(args.binary, args.romdir, args.out, args.latency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
