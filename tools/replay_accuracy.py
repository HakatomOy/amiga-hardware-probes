#!/usr/bin/env python3
"""Replay immutable CIA/IRQ reference ROMs; print one summary per suite."""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import compare_captures
import compare_copper_busy
import compare_divider_irq
import compare_irq_focus
import run_rom
import rom_results

SUITES = {
    "cia-irq": ("cia-cpu-irq-kind51-review3", "references/cia-irq-kind51-review3-run1"),
    "irq-focus": ("irq-focus-v3", "references/irq-focus-v3"),
    "divider-irq": ("divider-irq-signs-v3", "references/divider-irq-v3"),
    "copper-busy": ("copper-start-busy-kind50-review1", "references/copper-busy-kind50"),
    "blitter-handoff": ("blitter-handoff-kind49-review1", "references/blitter-handoff-kind49"),
    "bzero-edges": (str(ROOT.parent / "Copperline/tmp/timing-isolation/bzero-edges-rom2"), "references/bzero-edges-kind22"),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new directory, never overwritten")
    parser.add_argument("--config", type=Path, required=True, help="explicit source-matched hardware configuration")
    parser.add_argument("--suite", action="append", choices=SUITES, help="repeat to select; default all")
    args = parser.parse_args(argv)
    binary, out, config = args.binary.resolve(), args.out.resolve(), args.config.resolve()
    if not binary.is_file() or not config.is_file():
        parser.error("binary and config must exist")
    suites = args.suite or list(SUITES)
    for suite in suites:
        archive, reference = SUITES[suite]
        if not (ROOT / "build" / archive / "manifest.json").is_file() or not (ROOT / reference / "results.bin").is_file():
            parser.error(f"missing immutable local archive/reference for {suite}")
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / "emulator.exe"
    shutil.copy2(binary, snapshot)
    config_snapshot = out / "machine.toml"
    shutil.copyfile(config, config_snapshot)
    summary = {"binary": str(binary), "binary_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
               "config": str(config), "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(), "suites": {}}
    any_error = False
    for suite in suites:
        archive, reference = SUITES[suite]
        destination = out / suite
        hardware = ROOT / reference
        log_path = out / (suite + ".log")
        try:
            with log_path.open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                run_rom.run(snapshot, destination, config_snapshot, ROOT / "build" / archive)
                left = compare_captures.load_capture(hardware)
                right = compare_captures.load_capture(destination)
                if suite == "copper-busy":
                    _, hw_rows = compare_copper_busy.load(hardware)
                    _, emu_rows = compare_copper_busy.load(destination)
                    raw = compare_copper_busy.compare(hw_rows, emu_rows)
                else:
                    raw = compare_captures.compare(left, right)
                (destination / "raw-comparison.json").write_text(json.dumps(raw, indent=2) + "\n")
                result = {"raw_counts": raw["counts"], "reference": str(hardware),
                          "source_id": left["metadata"]["source_id"], "report": str(destination / "raw-comparison.json")}
                if suite == "cia-irq":
                    result["eligible"] = raw["kind51_launch_eligibility"]
                elif suite in ("irq-focus", "divider-irq"):
                    module = compare_irq_focus if suite == "irq-focus" else compare_divider_irq
                    meta, rows = rom_results.decode((hardware / "results.bin").read_bytes())
                    report = module.compare({"metadata": meta, "records": rows},
                                            json.loads((destination / "results.json").read_text()))
                    (destination / "focused-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
                    result["focused"] = {key: value for key, value in report.items()
                                         if isinstance(value, (int, str, bool))}
            summary["suites"][suite] = result
            print(suite + ": " + json.dumps(result, sort_keys=True), flush=True)
        except Exception as exc:
            with log_path.open("a", encoding="utf-8") as log:
                traceback.print_exc(file=log)
            summary["suites"][suite] = {"error": str(exc)[:400], "log": str(log_path)}
            any_error = True
            print(suite + ": " + json.dumps(summary["suites"][suite]))
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 2 if any_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
