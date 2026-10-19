#!/usr/bin/env python3
"""Replay immutable hardware reference ROMs; print one summary per suite."""
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
import compare_cia_hardware
import compare_bus_marker
import compare_copper_busy
import compare_divider_irq
import compare_irq_stage
import compare_irq_focus
import run_rom
import rom_results

SUITES = {
    "irq-stages": ("irq-stage-v7", "references/irq-stage-v7-run1"),
    "bus-phasepad": ("bus-phasepad-v1", "references/bus-phasepad-v1-run1"),
    "bus-phase-entry": ("bus-phase-entry-v1", "references/bus-phase-entry-v1-run1"),
    "bus-phase-completion": ("bus-phase-completion-v1", "references/bus-phase-completion-v1-run1"),
    "bus-pressure": ("bus-pressure-v2", "references/bus-pressure-v2-run1"),
    "bus-onset": ("bus-onset-v1", "references/bus-onset-v1-run1"),
    "bus-marker": ("bus-marker-focus-v2", "references/bus-marker-focus-v2-run1"),
    "bus-completion": ("bus-marker-completion-v3", "references/bus-marker-completion-v3-run1"),
    "cia-output": ("cia-hw-verify-v4", "references/cia-output-serial-v4-run1"),
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
                if suite == "cia-output":
                    if left["metadata"]["source_id"] != right["metadata"]["source_id"]:
                        raise ValueError("source_id mismatch")
                    _, hw_rows = compare_cia_hardware.load(hardware)
                    _, emu_rows = compare_cia_hardware.load(destination)
                    raw = compare_cia_hardware.compare(hw_rows, emu_rows)
                elif suite.startswith("bus-"):
                    if left["metadata"]["source_id"] != right["metadata"]["source_id"]:
                        raise ValueError("source_id mismatch")
                    _, hw_rows = compare_bus_marker.load(hardware)
                    _, emu_rows = compare_bus_marker.load(destination)
                    raw = compare_bus_marker.compare(hw_rows, emu_rows)
                    raw["phase_cohorts"] = compare_bus_marker.compare_cohorts(hw_rows, emu_rows)
                elif suite == "irq-stages":
                    second = ROOT / "references/irq-stage-v7-run2"
                    hm, h = compare_irq_stage.load(hardware)
                    hm2, h2 = compare_irq_stage.load(second)
                    cm, c = compare_irq_stage.load(destination)
                    if len({m["source_id"] for m in (hm, hm2, cm)}) != 1:
                        raise ValueError("source_id mismatch")
                    raw = compare_irq_stage.compare(h + h2, c)
                    raw["software_requests"] = compare_irq_stage.software_summary(raw)
                    raw["references"] = [str(hardware), str(second)]
                elif suite == "copper-busy":
                    _, hw_rows = compare_copper_busy.load(hardware)
                    _, emu_rows = compare_copper_busy.load(destination)
                    raw = compare_copper_busy.compare(hw_rows, emu_rows)
                else:
                    raw = compare_captures.compare(left, right)
                (destination / "raw-comparison.json").write_text(json.dumps(raw, indent=2) + "\n")
                result = {"raw_counts": raw["counts"], "reference": str(hardware),
                          "source_id": left["metadata"]["source_id"], "report": str(destination / "raw-comparison.json")}
                if suite.startswith("bus-"):
                    result["phase_cohorts"] = raw["phase_cohorts"]["counts"]
                    result["signal_mismatches"] = raw["phase_cohorts"]["signal_mismatches"]
                if suite == "irq-stages":
                    result["software_requests"] = raw["software_requests"]
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
