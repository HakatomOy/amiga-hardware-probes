#!/usr/bin/env python3
"""Capture real OneROM RBCP pipe output with onerom console and validate it."""
import argparse,json,subprocess,time
from pathlib import Path
import rom_results
ROOT=Path(__file__).resolve().parent

def collect(onerom,out,timeout):
    out.mkdir(parents=True,exist_ok=False)
    transcript=out/'usb.txt'
    manifest_path=out/'build-manifest.json'
    manifest_path.write_bytes((ROOT/'build/rom/manifest.json').read_bytes())
    command=[str(onerom),'console','--output',str(transcript)]
    (out/'invocation.json').write_text(json.dumps(dict(command=command,timeout_seconds=timeout),indent=2))
    log=(out/'console.log').open('wb')
    proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if transcript.exists() and b'A5RBCP-END' in transcript.read_bytes(): break
            if proc.poll() is not None: raise RuntimeError('Console exited: '+(out/'console.log').read_text(errors='replace'))
            time.sleep(.5)
        else: raise TimeoutError('Incomplete capture; inspect USB log and physical screen')
        # The output file is written as data arrives; success requires a full
        # frame, matching build fingerprint, trial order and checksum.
        rom_results.extract(transcript,out,True,manifest_path)
    finally:
        if proc.poll() is None: proc.terminate();proc.wait(timeout=15)
        log.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--onerom',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout',type=int,default=480);a=p.parse_args();collect(a.onerom.resolve(),a.out.resolve(),a.timeout)
