#!/usr/bin/env python3
"""Run a fresh writable copy of the test disk and validate its saved results."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import results

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'captures'/'copperline')
    parser.add_argument('--seconds',type=int,default=45)
    parser.add_argument('--chip',default='512K')
    parser.add_argument('--slow',default='512K')
    parser.add_argument('--video',choices=('PAL','NTSC'),default='PAL')
    parser.add_argument('--write-protected',action='store_true',help='Negative test: expect no saved results; inspect the error screenshot')
    parser.add_argument('--irq-latency',type=int,help='Optional diagnostic override; omitted uses Copperline default')
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True,exist_ok=True)
    disk = output/'capture.adf'
    fresh = ROOT/'build'/'a500-irq-probe.adf'
    if disk.exists():
        parser.error(f'{disk} already exists; use a different --out to preserve this capture')
    shutil.copyfile(fresh,disk)
    config = output/'machine.toml'
    config.write_text('rom = '+json.dumps(str(args.rom.resolve()))+'\n\n[floppy.df0]\nenabled = true\npath = '+json.dumps(str(disk))+'\nwrite_protected = '+str(args.write_protected).lower()+'\n',encoding='utf-8')
    env = dict(os.environ)
    # Pin diagnostics that otherwise survive in the caller's shell.
    for key in list(env):
        if key.startswith('COPPERLINE_'):
            del env[key]
    env['RUST_LOG'] = 'info'
    if args.irq_latency is not None:
        env['COPPERLINE_IRQ_LATENCY_CCK'] = str(args.irq_latency)
    command = [str(args.exe.resolve()),'--factory','--config',str(config),'--model','A500',
               '--cpu','68000','--no-jit','--chipset','OCS','--video',args.video,'--chip',args.chip,'--slow',args.slow,'--fast','0',
               '--noaudio','--screenshot-after',str(args.seconds),str(output/'screen.png')]
    (output/'invocation.json').write_text(json.dumps(dict(command=command,irq_latency=args.irq_latency),indent=2)+'\n',encoding='utf-8')
    with (output/'run.log').open('w',encoding='utf-8') as stream:
        subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=240)
    image = disk.read_bytes()
    original = fresh.read_bytes()
    if args.write_protected:
        if image != original:
            raise RuntimeError('Write-protected image was modified')
        print(f'Write-protected image remained unchanged; inspect {output/"screen.png"} for the red error screen')
        return
    if image[:results.OFFSET] != original[:results.OFFSET] or image[results.OFFSET+results.SIZE:] != original[results.OFFSET+results.SIZE:]:
        raise RuntimeError('Guest changed sectors outside the reserved results region')
    meta, records = results.decode(image)
    (output/'results.json').write_text(json.dumps(dict(metadata=meta,records=records),indent=2)+'\n',encoding='utf-8')
    print(f"Verified {len(records)} saved records, {meta['timeouts']} timeouts: {disk}")


if __name__ == '__main__':
    main()
