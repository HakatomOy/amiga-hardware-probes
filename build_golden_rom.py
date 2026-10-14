#!/usr/bin/env python3
"""Run Copperline's committed RAM probes with a standalone RBCP ROM wrapper."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def build(copperline, suite='timing', repeats=8, assembler='vasmm68k_mot', wsl=False):
    if repeats < 1: raise ValueError('At least one repetition is required')
    out=ROOT/'build/golden';out.mkdir(parents=True,exist_ok=True)
    name='test' if suite!='blitter' else 'bltprobe-pace'
    original=(copperline/'timing-test'/f'{name}.bin').read_bytes()
    program=bytearray(original)
    if suite!='blitter':
        signature=bytes.fromhex('43f900040000303c09ff')
        assert program.count(signature)==1
        hook=program.index(signature);program[hook:hook+2]=bytes.fromhex('4e4f')
        instrument=None;count=32;values=0x48000
    else:
        assert program.count(bytes.fromhex('60fe'))==1
        hook=program.index(bytes.fromhex('60fe'));program[hook:hook+2]=bytes.fromhex('4e4f')
        signature=bytes.fromhex('4a43')
        assert program.count(signature)==1
        instrument=program.index(signature);program[instrument:instrument+2]=bytes.fromhex('4e4e')
        count=5;values=0x3300
    if suite=='copper':
        signature=bytes.fromhex('72104841302e001e08000004')
        assert program.count(signature)==1
        phase_hook=program.index(signature)
        displacement=0x32000-(0x30000+phase_hook+2)
        program[phase_hook:phase_hook+4]=bytes.fromhex('4eba')+displacement.to_bytes(2,'big',signed=True)
    (out/'program.bin').write_bytes(program)
    rows=[(15,(2 if suite=='divu' else 0) if suite!='blitter' else 1,i,r%16,0,r) for r in range(repeats) for i in range(count)]
    base=0x70000;length=64+40*len(rows)
    assert base+length<0x7d000 and len(program)<0x4000
    experiment=(ROOT/'src/rom/experiment.asm').read_text()
    transport_start=experiment.index('\nstream_results:')+1
    transport=experiment[transport_start:experiment.index('\nheader:',transport_start)+1]
    wrapper='''; SPDX-License-Identifier: MIT
        include "rbcp_config.s"
        include "rbcp_defs.s"
CUSTOM equ $dff000
PIPE equ $3030
STREAM_PTR equ $3034
STREAM_END equ $3038
RESULT equ $70000
        org $8000
probe_entry:  bra.w main
        dcb.b $10-(*-probe_entry),0
collection_done:
        move.l #RESULT,$3080
        move.l #RESULT+PACKET_BYTES,$3084
        bsr stream_results
        move.w #$0ff,$dff180
.idle:  stop #$2700
        bra.s .idle
main:
        lea CUSTOM,a6
        bsr quiet
        lea fault_vectors(pc),a0
        lea 8,a1
        moveq #45,d0
.vectors: move.l a0,(a1)+
        adda.w #14,a0
        dbra d0,.vectors
        move.l #collected,$bc
        move.l #bar_hook,$b8
        lea header(pc),a0
        lea RESULT,a1
        moveq #15,d0
.header: move.l (a0)+,(a1)+
        dbra d0,.header
        move.w 4(a6),RESULT+56
        move.w $7c(a6),RESULT+58
        clr.w $3044
        move.l #descriptors,$3048
start_run:
        move.w #$2700,sr
        lea CUSTOM,a6
        bsr quiet
        lea $34000,a0
        move.w #(($70000-$34000)/4)-1,d0
.scratch: clr.l (a0)+
        dbra d0,.scratch
        lea $3300,a0
        moveq #31,d0
.bars:  clr.l (a0)+
        dbra d0,.bars
        move.l #$7f000,a0
        move.l a0,usp
        move.l #$7e000,sp
        ; Launch phase sweep; all tested instructions remain at $30000.
.leave: move.w $dff006,d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        beq.s .leave
.line:  move.w $dff006,d0
        andi.w #$ff00,d0
        cmpi.w #$4000,d0
        bne.s .line
        move.w $3044,d0
        andi.w #15,d0
.phase: nop
        dbra d0,.phase
        move.w $dff006,$3052
        moveq #0,d0
        moveq #0,d1
        moveq #0,d2
        moveq #0,d3
        moveq #0,d4
        moveq #0,d5
        moveq #0,d6
        moveq #0,d7
        move.w #0,sr
        jmp $30000
collected:
        move.w #$2700,sr
        move.l #$7e000,sp
        lea CUSTOM,a6
        bsr quiet
        moveq #0,d0
        move.w $3044,d0
        mulu #ROW_COUNT*40,d0
        lea RESULT+64,a4
        adda.l d0,a4
        move.l $3048,a2
        lea VALUE_BASE,a0
        lea $3340,a1
        moveq #ROW_COUNT-1,d6
.record:
        moveq #9,d0
        move.l a4,a3
.zero:  clr.l (a3)+
        dbra d0,.zero
        moveq #5,d0
        move.l a4,a3
.desc:  move.w (a2)+,(a3)+
        dbra d0,.desc
        move.w $3052,12(a4)
        move.w $dff006,16(a4)
        move.l (a0)+,d0
        move.w d0,20(a4)
        swap d0
        move.w d0,22(a4)
        move.w (a1)+,34(a4)
        adda.w #40,a4
        dbra d6,.record
        move.l a2,$3048
        addq.w #1,$3044
        cmpi.w #RUN_COUNT,$3044
        bcs start_run
        lea RESULT,a0
        move.l #PACKET_BYTES/4-1,d1
        moveq #0,d0
        move.w #1,RESULT+62
.sum:   add.l (a0)+,d0
        subq.l #1,d1
        bpl.s .sum
        neg.l d0
        move.l d0,RESULT+20
        jmp collection_done
bar_hook:
        movem.l d0/a0,-(sp)
        moveq #0,d0
        move.w d2,d0
        lsr.w #4,d0
        subq.w #1,d0
        add.w d0,d0
        lea $3340,a0
        move.w d3,(a0,d0.w)
        add.w d0,d0
        lea $3300,a0
        move.l d7,(a0,d0.w)
        ; Original replaced TST.W D3 is positive for every drawbar call.
        andi.w #$fff0,8(sp)
        movem.l (sp)+,d0/a0
        rte
quiet:
        move.w #$7fff,$dff096
        move.w #$7fff,$dff09a
        move.w #$7fff,$dff09c
        clr.b $bfee01
        clr.b $bfef01
        clr.b $bfde00
        clr.b $bfdf00
        move.b #$7f,$bfed01
        move.b #$7f,$bfdd00
        tst.b $bfed01
        tst.b $bfdd00
        rts
fault:
        movem.l d0-d7/a0-a7,$3110
        move.l sp,a0
        move.w #$2700,sr
        move.l #$7e000,sp
        lea $3150,a1
        moveq #7,d0
.stack: move.l (a0)+,(a1)+
        dbra d0,.stack
        move.l #$41354641,$3100
        move.l #$554c5431,$3104
        move.w $303c,$3108
        clr.w $310a
        clr.l $310c
        lea $3100,a0
        moveq #31,d1
        moveq #0,d0
.sum:   add.l (a0)+,d0
        dbra d1,.sum
        neg.l d0
        move.l d0,$310c
        move.l #$3100,$3080
        move.l #$3180,$3084
        move.w #$f00,$dff180
        bsr stream_results
.halt:  bra.s .halt
fault_vectors:
fault_index set 2
        rept 46
        move.w #fault_index,($303c).l
        jmp fault
fault_index set fault_index+1
        endr
'''
    if suite=='divu':
        signature=bytes.fromhex('3d7c60000100')
        plane=original.rindex(signature)+2+0x30000
        wrapper=wrapper.replace('start_run:\n', f"""start_run:
        moveq #0,d0
        move.w $3044,d0
        divu.w #7,d0
        swap d0
        lsl.w #8,d0
        lsl.w #4,d0
        move.w d0,${plane:x}
""",1)
    provenance=Path(__file__).read_bytes()+original+experiment.encode()+json.dumps(rows).encode()
    for dependency in [ROOT/'src/rom/boot.asm',*sorted((ROOT/'vendor/rbcp').glob('*'))]:
        if dependency.is_file():
            provenance+=dependency.relative_to(ROOT).as_posix().encode()+b'\0'+dependency.read_bytes()
    fingerprint=hashlib.sha256(provenance).hexdigest()
    constants=f'PACKET_BYTES equ {length}\nROW_COUNT equ {count}\nRUN_COUNT equ {repeats}\nVALUE_BASE equ ${values:x}\n'
    header='''header:
        dc.b "A5RBCP01"
        dc.w 1,40
'''+f'        dc.l {len(rows)},{length},0\n        dc.b '+','.join('$'+fingerprint[i:i+2] for i in range(0,64,2))+'\n        dc.w 0,0,1,0\ndescriptors:\n'+''.join('        dc.w '+','.join(map(str,r))+'\n' for r in rows)
    source=constants+wrapper+transport+header+'\n        dcb.b $30000-*,0\nprogram:\n        incbin "program.bin"\n'
    if suite=='copper':
        source += """
        dcb.b $32000-*,0
copper_phase:
        moveq #16,d1
        swap d1
        move.w $3044,d0
        andi.w #15,d0
.phase: nop
        dbra d0,.phase
        rts
"""
    (out/'wrapper.asm').write_text(source)
    def path(p):
        if not wsl or not p.drive: return str(p)
        return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
    def assemble(src,dest):
        command=(['wsl','-d','Ubuntu-24.04','--exec'] if wsl else [])+[assembler,'-m68000','-no-opt','-Fbin','-DCONFIG_ROM_KB=512']
        for p in [out,ROOT/'src/rom',ROOT/'vendor/rbcp']:command+=['-I',path(p)]
        command += [path(src),'-o',path(dest),'-L',path(dest.with_suffix('.lst'))]
        subprocess.run(command,cwd=ROOT,check=True)
    assemble(out/'wrapper.asm',out/'experiment.bin')
    payload=(out/'experiment.bin').read_bytes();payload+=b'\0'*((-len(payload))%4);(out/'experiment.bin').write_bytes(payload)
    assert len(payload)<0x40000
    (out/'rom_layout.i').write_text(f'PAYLOAD_BYTES equ {len(payload)}\n')
    boot=(ROOT/'src/rom/boot.asm').read_text().replace('lea $20000,a1','lea $8000,a1').replace('jmp $20000','jmp $8000')
    (out/'boot.asm').write_text(boot)
    assemble(out/'boot.asm',out/'a500-timing-rom.bin')
    rom=(out/'a500-timing-rom.bin').read_bytes();assert len(rom)==524288
    swapped=bytearray(rom);swapped[0::2]=rom[1::2];swapped[1::2]=rom[0::2]
    (out/'a500-timing-rom-onerom.bin').write_bytes(swapped)
    patches=[dict(offset=hook,before=original[hook:hook+2].hex(),after='4e4f',purpose='post-measurement collection')]
    if instrument is not None:patches.append(dict(offset=instrument,before=original[instrument:instrument+2].hex(),after='4e4e',purpose='post-poll raw-count/width logging'))
    if suite=='copper':
        patches.append(dict(offset=phase_hook,before=original[phase_hook:phase_hook+4].hex(),
            after=program[phase_hook:phase_hook+4].hex(),purpose='polling phase sweep stub'))
    runtime_patches=[]
    if suite=='divu':
        runtime_patches.append(dict(address=plane,values=[i<<12 for i in range(7)],
            purpose='final DIVU row BPLCON0 immediate, indexed by repeat modulo seven'))
    manifest=dict(version=1,suite=suite,source_id=fingerprint,trial_count=len(rows),record_bytes=40,result_address=base,result_bytes=length,
        collection_done_pc=0x8010,payload_bytes=len(payload),trials=rows,rom_sha256=hashlib.sha256(rom).hexdigest(),
        onerom_sha256=hashlib.sha256(swapped).hexdigest(),original_program_sha256=hashlib.sha256(original).hexdigest(),patches=patches,runtime_patches=runtime_patches,
        copperline=str(copperline),original_program=f'timing-test/{name}.bin')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='trials'},indent=2))
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--copperline',type=Path,required=True);p.add_argument('--suite',choices=['timing','blitter','divu','copper'],default='timing');p.add_argument('--repeats',type=int,default=8)
    p.add_argument('--install',action='store_true',help='Copy the ROMs and manifest into build/rom for existing runners')
    p.add_argument('--vasm',default='vasmm68k_mot');p.add_argument('--wsl',action='store_true')
    a=p.parse_args();build(a.copperline.resolve(),a.suite,a.repeats,a.vasm,a.wsl)
    if a.install:
        (ROOT/'build/rom').mkdir(parents=True,exist_ok=True)
        for filename in ('a500-timing-rom.bin','a500-timing-rom-onerom.bin','manifest.json'):
            shutil.copyfile(ROOT/'build/golden'/filename,ROOT/'build/rom'/filename)
