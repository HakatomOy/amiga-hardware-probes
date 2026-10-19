"""Kind64: serial flag boundaries with independent TA/TB phase brackets."""
import argparse
from pathlib import Path
import shutil
from functools import partial
import build_irq_stage_rom as base


def trials(extended=False):
    return [(64,c,v,l,(uf<<5)|pad,r) for c in range(2) for v in range(2)
            for l in range(4 if extended else 2) for uf in ((14,15,16) if v==0 else (30,31,32))
            for pad in range(16 if extended else 8) for r in range(2)]


def transform(stage,extended=False):
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm'
    s=p.read_text().replace('cmpi.w #56,(a4)','cmpi.w #64,(a4)').replace('jsr irq_stage_trial','jsr cia_serial_buffer_trial')
    p.write_text(s+'\n        even\n        include "cia_serial_buffer_kernel.i"\n')
    p=stage/'src/rom/cia_serial_buffer_kernel.i';s=p.read_text()
    if extended:
        s=s.replace('        lsl.w #4,d0\n        addi.w #15,d0',
                    '        lea .latches(pc),a1\n        add.w d0,d0\n        move.w 0(a1,d0.w),d0')
        s+='\n.latches: dc.w 15,31,63,127\n'
    s=s.replace('.first:\n        moveq #18,d1', '.first:\n        moveq #18,d1\n        tst.w 4(a4)\n        bne.s .first_ready\n        moveq #12,d1\n.first_ready:')
    s=s.replace('        move.w 8(a4),d1\n        bsr.w .snapshot',
        '        move.w 8(a4),d1\n        lsr.w #5,d1\n        bsr.w .wait_uf\n'
        '        move.w 8(a4),d2\n        andi.w #31,d2\n        bra.s .pad_test\n'
        '.pad:  nop\n.pad_test:\n        dbra d2,.pad\n        bsr.w .snapshot\n'
        '        move.w d5,16(a4)\n        move.w d6,18(a4)')
    s=s.replace('        moveq #0,d3\n        move.b $d00(a0),d3',
        '        moveq #0,d5\n        move.b $400(a0),d5\n        moveq #0,d3\n'
        '        move.b $d00(a0),d3\n        moveq #0,d6\n        move.b $400(a0),d6')
    p.write_text(s)


def build(assembler,wsl,out,extended=False):
    return base.build(assembler,wsl,out,rows=trials(extended),transform=partial(transform,extended=extended),
        profile=dict(kind=64,targets=['CIA-A','CIA-B'],sources=['Timer-A serial output'],masks=None,
                     units='TA counter ticks and TB observed underflows; no alignment',
                     variants='single first ack12; queued writeUF4 first ack18',
                     phases=[15,31,63,127] if extended else [15,31],
                     event_offset='sampleUF<<5 | NOP pad',watchdog='bounded2048 TB polls per wait',
                     masked_fields=None,launch='actual SDR-write UF brackets; FFFF if absent',
                     fields={'launch_beam':'write UF before','launch_ref':'write UF after',
                             'end_beam':'TA low before second ICR','end_ref':'TA low after second ICR',
                             'counter':'first ICR atUF12(single)/18(queued)','icr':'sampled ICR',
                             'irq_beam':'third ICR atUF56','irq_level':'first UF before',
                             'saved_pc_offset':'first UF after:second UF before','aux':'second UF after',
                             'second_counter_or_beam':'third UF before','second_icr_or_level':'third UF after',
                             'delay':'sampleUF<<5 | NOP pad'},
                     limitations='Serial completion flags only; no transmitted payload or electrical pin edges'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--extended',action='store_true')
    a=p.parse_args();build(a.vasm,a.wsl,a.out,a.extended)
