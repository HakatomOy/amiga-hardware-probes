#!/usr/bin/env python3
"""Build the standalone 68000 measurement ROM, with pinned RBCP sources."""
import argparse, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def trials(focused=False):
    if focused:
        rows=[(5,t,0,p,d,r) for t in range(4) for p in range(5) for d in range(8) for r in range(2)]
        return rows + [(10,3,k,p,m*4,r) for k in (5,6) for p in range(16) for m in range(2) for r in range(4)]
    rows=[]
    for target in range(4):
        for variant in range(2):
            for phase in range(5):
                for delay in range(8):
                    for repeat in range(2):
                        rows.append((1,target,variant,phase,delay,repeat))
    for target in range(4):
        for variant in range(2):
            for phase in range(5):
                for latch in (0,1,3,15):
                    for repeat in range(2):
                        rows.append((2,target,variant,phase,latch,repeat))
    for target in range(4):
        for variant in range(4):
            for phase in range(5):
                for repeat in range(2):
                    rows.append((3,target,variant,phase,4,repeat))
    for target in range(4):
        for variant in range(4):
            for phase in range(5):
                for delay in range(8):
                    for repeat in range(2):
                        rows.append((4,target,variant,phase,delay,repeat))
    for source in range(4):
        for kernel in range(5):
            for phase in range(16):
                for memory in range(2):
                    for dma in range(3):
                        for repeat in range(2):
                            rows.append((10,source,kernel,phase,dma+memory*4,repeat))
    return rows

def build(assembler,wsl=False,focused=False):
    rows=trials(focused)
    build=ROOT/'build/rom'; build.mkdir(parents=True,exist_ok=True)
    sources=sorted([ROOT/'build_rom.py',*list((ROOT/'src/rom').glob('*')),*list((ROOT/'vendor/rbcp').glob('*'))])
    h=hashlib.sha256()
    for source in sources:
        h.update(source.relative_to(ROOT).as_posix().encode()+b'\0'+source.read_bytes().replace(b'\r\n',b'\n'))
    fingerprint=h.hexdigest()
    (build/'trials.i').write_text('trials:\n'+''.join('        dc.w '+','.join(map(str,row))+'\n' for row in rows))
    (build/'source_id.i').write_text('        dc.b '+','.join('$'+fingerprint[i:i+2] for i in range(0,64,2))+'\n')
    (build/'rom_layout.i').write_text(f'TRIAL_COUNT equ {len(rows)}\nPAYLOAD_BYTES equ 0\n')
    def assemble(source,out):
        paths=[build,ROOT/'src/rom',ROOT/'vendor/rbcp']
        def path(p):
            if not wsl: return str(p)
            if p.drive: return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
            return str(p)
        command=(['wsl','-d','Ubuntu-24.04','--exec',assembler] if wsl else [assembler])
        command+=['-m68000','-no-opt','-Fbin','-DCONFIG_ROM_KB=512']
        for p in paths: command+=['-I',path(p)]
        command += [path(source),'-o',path(out),'-L',path(out.with_suffix('.lst'))]
        subprocess.run(command,cwd=ROOT,check=True)
    payload=build/'experiment.bin'
    assemble(ROOT/'src/rom/experiment.asm',payload)
    data=payload.read_bytes(); data+=b'\0'*((-len(data))%4); payload.write_bytes(data)
    assert len(data)<0x20000, 'Payload overlaps result buffer or exceeds boot copy loop'
    assert 0x40000+64+len(rows)*40 < 0x7e000, 'Results overlap stack'
    (build/'rom_layout.i').write_text(f'TRIAL_COUNT equ {len(rows)}\nPAYLOAD_BYTES equ {len(data)}\n')
    out=build/'a500-timing-rom.bin'
    assemble(ROOT/'src/rom/boot.asm',out)
    data=out.read_bytes(); assert len(data)==524288
    assert data[-16:]==bytes.fromhex('00180019001a001b001c001d001e001f')
    swapped=bytearray(data); swapped[0::2]=data[1::2]; swapped[1::2]=data[0::2]
    (build/'a500-timing-rom-onerom.bin').write_bytes(swapped)
    manifest=dict(version=1,source_id=fingerprint,trial_count=len(rows),record_bytes=40,
                  result_address=0x40000,result_bytes=64+len(rows)*40,
                  collection_done_pc=0x20010,payload_bytes=len(payload.read_bytes()),
                  rom_sha256=hashlib.sha256(data).hexdigest(),
                  onerom_sha256=hashlib.sha256(swapped).hexdigest(),trials=rows)
    (build/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('ROM built:',len(rows),'trials;',manifest['source_id'])
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--vasm',default='vasmm68k_mot'); p.add_argument('--wsl',action='store_true'); p.add_argument('--focused',action='store_true')
    a=p.parse_args(); build(a.vasm,a.wsl,a.focused)
