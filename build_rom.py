#!/usr/bin/env python3
"""Build the standalone 68000 measurement ROM, with pinned RBCP sources."""
import argparse, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def trials(focused=False,continuous=False,modes=False,pulses=False,reads=False,loads=False,blits=False,cpu=False,edges=False,channels=False,observe=0,priority=False,bzero=False,irq_paths=False,bzero_line=False,line_logic=False,line_logic_fine=False,line_logic_followup=False):
    if bzero:
        targets=[*range(32),32,33]
        rows=[]
        for target in targets:
            variants=(0,1,4) if target<32 and target&8 else (0,)
            if target in (0,1,9,15,25,32):
                variants=(*variants,0x100)
            rows.extend((22,target,variant,phase,delay,repeat)
                        for variant in variants for phase in range(2)
                        for delay in range(16) for repeat in (0,4))
        return rows
    if irq_paths:
        return [(23,target,variant,phase,delay,repeat)
                for target in range(7) for variant in range(2)
                for phase in range(2) for delay in range(16) for repeat in (0,4)]
    if bzero_line:
        return [(24,target,pattern | (late << 8),phase,delay,repeat)
                for target in (32,33) for pattern in (0,1,4,8,16) for late in (0,1)
                for phase in range(2)
                for delay in range(32) for repeat in (0,4)]
    if line_logic_fine:
        return [(26,target,b_pattern | (long_line << 1),phase,delay,repeat)
                for target in (32,33) for b_pattern in range(2) for long_line in range(2)
                for phase in range(2) for delay in range(17) for repeat in (0,4)]
    if line_logic_followup:
        # variant: B pattern index[0:2], A pattern index[3:4], C full[5],
        # long line[6]. repeat bit 0 selects early (1) vs late (0) BLTBDAT.
        return [(27,target,b_index | (a_index<<3) | (c_full<<5) | (long_line<<6),phase,delay,order)
                for target in (32,33) for b_index in range(7) for a_index in range(3)
                for c_full in range(2) for long_line in range(2) for phase in range(2)
                for delay in range(5) for order in (0,1)]
    if line_logic:
        delays=(0,1,2,4,8,16)
        rows=[]
        for target in (32,33):
            for lf_index in range(4):
                for a_enabled in range(2):
                    for b_index in range(3):
                        for c_full in range(2):
                            for pixel_index in range(3):
                                variant=(lf_index | (a_enabled<<2) | (b_index<<3)
                                         | (c_full<<5) | (pixel_index<<6))
                                rows.extend((25,target,variant,phase,delay,0)
                                            for phase in range(2) for delay in delays)
        return rows
    if channels or priority:
        masks=[*range(16),*(16+m for m in range(1,16,2)),32,33,34]
        repeat=observe | (4 if priority else 0)
        return [(21,t,22,p,d,repeat) for t in masks for p in range(2) for d in range(64)]
    if edges:
        return ([(19,t,w,p,d,0) for t in range(5) for w in (1,2,22) for p in range(4) for d in range(48)]
                + [(20,t,0,p,d,0) for t in range(4) for p in range(4) for d in range(96)])
    if cpu:
        return [(18,t,v,p,n,0) for t in range(7) for v in range(8) for p in range(8) for n in (1,2,16,64)]
    if blits:
        return [(17,t,v,p,h,r) for t in range(3) for v in range(3) for p in range(5) for h in (1,2,8,32,128,220) for r in range(2)]
    if loads:
        return [(16,t,v,p,d,r) for t in range(4) for v in range(2) for p in range(5) for d in range(16) for r in range(2)]
    if reads:
        return [(9,t,l,p,d,r) for t in range(4) for l in (1,3,15,200)
                for p in range(3) for d in (*range(64),127) for r in range(2)]
    if pulses:
        return [(14,t,l,p,d,style) for t in (0,2) for l in (0,1,3,200)
                for p in range(3) for d in (*range(16),31,63) for style in range(4)]
    if modes:
        return [(13,t,v,p,d,r) for t in (1,3) for v in range(5)
                for p in range(3) for d in (0,1,2,3,4,5,6,7,15,31) for r in range(2)]
    if continuous:
        latches=(0,1,2,3,4,7,15,200)
        delays=(0,1,2,3,4,5,6,7,15,31,63,127)
        rows=[(kind,t,l,p,d,r) for kind,targets in ((6,range(4)),(7,(0,2)))
              for t in targets for l in latches for p in range(3) for d in delays for r in range(2)]
        rows += [(8,t,l,p,d,r) for t in (0,2) for l in (0,1,3,15,200)
                 for p in range(3) for d in (0,1,3,7,31,63) for r in range(2)]
        rows += [(9,t,l,p,d,r) for t in range(4) for l in (0,1,3,15,200)
                 for p in range(3) for d in delays for r in range(2)]
        rows += [(12,t,l,p,d,r) for t in (0,2) for l in (0,1,3,15,40)
                 for p in range(3) for d in delays for r in range(2)]
        return rows
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

def build(assembler,wsl=False,focused=False,continuous=False,modes=False,pulses=False,reads=False,loads=False,blits=False,cpu=False,edges=False,channels=False,observe=0,priority=False,bzero=False,irq_paths=False,bzero_line=False,line_logic=False,line_logic_fine=False,line_logic_followup=False):
    rows=trials(focused,continuous,modes,pulses,reads,loads,blits,cpu,edges,channels,observe,priority,bzero,irq_paths,bzero_line,line_logic,line_logic_fine,line_logic_followup)
    build=ROOT/'build/rom'; build.mkdir(parents=True,exist_ok=True)
    sources=sorted([ROOT/'build_rom.py',*list((ROOT/'src/rom').glob('*')),*list((ROOT/'vendor/rbcp').glob('*'))])
    h=hashlib.sha256()
    for source in sources:
        h.update(source.relative_to(ROOT).as_posix().encode()+b'\0'+source.read_bytes().replace(b'\r\n',b'\n'))
    h.update(json.dumps(rows).encode())
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
        if edges or channels or cpu or priority or bzero or irq_paths or bzero_line or line_logic or line_logic_fine or line_logic_followup: command+=['-DEDGE_ROM_KERNEL=1']
        for p in paths: command+=['-I',path(p)]
        command += [path(source),'-o',path(out),'-L',path(out.with_suffix('.lst'))]
        subprocess.run(command,cwd=ROOT,check=True)
    # Raw VHPOSR feedback followed by ROM-only NOP/EXG padding. The
    # table returns on the following line at one fixed horizontal phase.
    alignment = ["        org $fb0000", "rom_align:",
        ".wait:  move.w 6(a6),d0", "        andi.w #$ff,d0",
        "        cmpi.w #$30,d0", "        bcs.s .wait",
        "        cmpi.w #$60,d0", "        bhi.s .wait",
        "        move.w 6(a6),d0", "        andi.w #$ff,d0",
        "        sub.w 6(a4),d0", "        lsl.w #2,d0",
        "        lea rom_align_table(pc),a2", "        move.l 0(a2,d0.w),a2",
        "        jmp (a2)", "rom_align_table:"]
    alignment += [f"        dc.l rom_align_{h}" for h in range(256)]
    for h in range(256):
        clocks = max(0, 227 + 64 - 44 - h)
        alignment.append(f"rom_align_{h}:")
        if clocks % 2:
            alignment.append("        exg d0,d1")
            clocks -= 3
        alignment += [f"        rept {max(0,clocks)//2}", "        nop", "        endr", "        rts"]
    (build/'rom_alignment.i').write_text('\n'.join(alignment)+'\n')
    payload=build/'experiment.bin'
    assemble(ROOT/'src/rom/experiment.asm',payload)
    data=payload.read_bytes(); data+=b'\0'*((-len(data))%4); payload.write_bytes(data)
    assert len(data)<0x20000, 'Payload overlaps result buffer or exceeds boot copy loop'
    assert 0x40000+64+len(rows)*40 < 0x7e000, 'Results overlap stack'
    (build/'rom_layout.i').write_text(f'TRIAL_COUNT equ {len(rows)}\nPAYLOAD_BYTES equ {len(data)}\n')
    out=build/'a500-timing-rom.bin'
    if edges or channels or cpu or priority or bzero or irq_paths or bzero_line or line_logic or line_logic_fine or line_logic_followup: assemble(ROOT/'src/rom/edge_kernel.asm',build/'rom_kernel.bin')
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
    p=argparse.ArgumentParser(); p.add_argument('--vasm',default='vasmm68k_mot'); p.add_argument('--wsl',action='store_true'); group=p.add_mutually_exclusive_group(); group.add_argument('--focused',action='store_true'); group.add_argument('--continuous',action='store_true'); group.add_argument('--modes',action='store_true'); group.add_argument('--pulses',action='store_true'); group.add_argument('--reads',action='store_true'); group.add_argument('--loads',action='store_true'); group.add_argument('--blits',action='store_true'); group.add_argument('--cpu',action='store_true'); group.add_argument('--edges',action='store_true'); group.add_argument('--channels',action='store_true'); group.add_argument('--priority',action='store_true',help='aligned observer sweep with BLTPRI enabled'); group.add_argument('--bzero',action='store_true',help='BZERO transition observer matrix'); group.add_argument('--irq-paths',action='store_true',help='native and Copper-generated IRQ STOP path matrix'); group.add_argument('--bzero-line',action='store_true',help='line-mode BZERO onset sweep'); group.add_argument('--line-logic',action='store_true',help='line minterm and BZERO/data behavior matrix'); group.add_argument('--line-logic-fine',action='store_true',help='focused 1-CCK line BZERO readback sweep'); group.add_argument('--line-logic-followup',action='store_true',help='focused kind27 line BZERO input/BDAT ordering matrix'); p.add_argument('--observe',choices=['busy','irq','memory'],default='busy')
    a=p.parse_args(); build(a.vasm,a.wsl,a.focused,a.continuous,a.modes,a.pulses,a.reads,a.loads,a.blits,a.cpu,a.edges,a.channels,['busy','irq','memory'].index(a.observe),a.priority,a.bzero,a.irq_paths,a.bzero_line,a.line_logic,a.line_logic_fine,a.line_logic_followup)
