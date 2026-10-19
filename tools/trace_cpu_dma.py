#!/usr/bin/env python3
"""Trace selected CPU/IRQ addresses and verify unchanged measurement results."""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_rom


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("binary","romdir","config","out","reference_results"):
        p.add_argument("--"+name.replace('_','-'),type=Path,required=True)
    p.add_argument('--seconds',type=float,default=90)
    p.add_argument('--addresses',default='0x180fe:0x18100,0x64:0x7b,0x7efb0:0x7f000,0xdff09a:0xdff09c')
    a=p.parse_args();a.out.parent.mkdir(parents=True,exist_ok=True)
    flags=dict(COPPERLINE_DIAG_CPU_BUS='1',COPPERLINE_DIAG_CPU_BUS_ADDR=a.addresses,
               COPPERLINE_DIAG_COP_WRITES='1',COPPERLINE_DBG_IRQ='1')
    original=run_rom._popen_with_binary_hash
    def launch(*args,**kwargs):
        kwargs['env'].update(flags);return original(*args,**kwargs)
    run_rom._popen_with_binary_hash=launch
    try:
        with (a.out.parent/(a.out.name+'-driver.log')).open('w') as log,contextlib.redirect_stdout(log):
            run_rom.run(a.binary.resolve(),a.out.resolve(),a.config.resolve(),a.romdir.resolve(),a.seconds)
    finally:
        run_rom._popen_with_binary_hash=original
        if a.out.exists():(a.out/'diagnostic-environment.json').write_text(json.dumps(flags,indent=2)+'\n')
    actual=(a.out/'results.bin').read_bytes();expected=a.reference_results.read_bytes()
    report=dict(byte_identical=actual==expected,sha256=hashlib.sha256(actual).hexdigest(),
                trace=str(a.out/'run.log'),reference=str(a.reference_results))
    (a.out/'trace-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));return 0 if actual==expected else 2


if __name__=='__main__':raise SystemExit(main())
