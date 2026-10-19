#!/usr/bin/env python3
"""Diagnostic latency sweep; records explicit overrides before compact comparison."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_rom
import compare_irq_stage as compare


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("binary","romdir","config","hardware","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--latency",type=int,action="append",required=True)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=False)
    original=run_rom._popen_with_binary_hash
    for latency in a.latency:
        if latency < 0: raise ValueError("negative latency")
        capture=a.out / str(latency)
        overrides=dict(COPPERLINE_IRQ_LATENCY_CCK=str(latency))
        def launch(binary,command,**kwargs):
            kwargs["env"].update(overrides)
            return original(binary,command,**kwargs)
        run_rom._popen_with_binary_hash=launch
        try:
            with (a.out / f"{latency}.log").open("w") as log, contextlib.redirect_stdout(log):
                run_rom.run(a.binary.resolve(),capture.resolve(),a.config.resolve(),a.romdir.resolve(),70)
        finally:
            run_rom._popen_with_binary_hash=original
        (capture / "diagnostic-overrides.json").write_text(json.dumps(overrides,indent=2)+"\n")
        hm,h=compare.load(a.hardware); cm,c=compare.load(capture)
        if hm["source_id"] != cm["source_id"]: raise ValueError("source identity differs")
        report=compare.compare(h,c)
        report["diagnostic_overrides"]=overrides
        (a.out / f"{latency}.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(dict(latency=latency,counts=report["counts"])),flush=True)


if __name__ == "__main__":main()
