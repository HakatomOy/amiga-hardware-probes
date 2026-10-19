#!/usr/bin/env python3
"""Kind63: drained CIA serial output, active/queued/idle SDR write controls."""
import argparse
from pathlib import Path
import shutil
from functools import partial
import build_irq_stage_rom as base

SAMPLES=(24,28,30,31,32,33,34,36,40,48)


def trials(first_boundary=False):
    if first_boundary:
        return [(63,cia,0,latch,sample,r) for cia in range(2) for latch in range(2)
                for sample in (14,15,16,17,18) for r in range(2)]
    return [(63,cia,variant,latch,sample,r) for cia in range(2) for variant in range(4)
            for latch in range(2) for sample in SAMPLES for r in range(2)]


def transform(stage,first_boundary=False):
    shutil.copyfile(__file__,stage/Path(__file__).name)
    p=stage/'src/rom/experiment.asm';s=p.read_text()
    s=s.replace('cmpi.w #56,(a4)','cmpi.w #63,(a4)').replace('jsr irq_stage_trial','jsr cia_serial_buffer_trial')
    p.write_text(s+'\n        even\n        include "cia_serial_buffer_kernel.i"\n')
    if first_boundary:
        p=stage/'src/rom/cia_serial_buffer_kernel.i'
        p.write_text(p.read_text().replace('moveq #18,d1','moveq #12,d1'))


def build(assembler,wsl,out,first_boundary=False):
    return base.build(assembler,wsl,out,rows=trials(first_boundary),transform=partial(transform,first_boundary=first_boundary),
        profile=dict(kind=63,targets=['CIA-A','CIA-B'],sources=['Timer-A-clocked serial output'],masks=None,
            phases='TA latch15 or31',event_offset='second snapshot target underflow count',watchdog='bounded2048 TB polls per wait',
            variants='0=single;1=active write atUF4;2=active writes atUF4/8;3=idle write atUF20',
            launch='actual before/after UF brackets for SDR writes; FFFF means absent',
            drain='latch1 output512 DBRA,stop/settle/ack; prestart SP flag must be clear',
            masked_fields=None,fields={'launch_beam':'write1 UF before','launch_ref':'write1 UF after',
                'end_beam':'write2 UF before','end_ref':'write2 UF after','counter':'ICR atUF12' if first_boundary else 'ICR atUF18',
                'icr':'ICR at sampled UF','irq_beam':'ICR atUF56','irq_level':'first UF before',
                'saved_pc_offset':'first UF after:second UF before','aux':'second UF after',
                'second_counter_or_beam':'third UF before','second_icr_or_level':'third UF after'},
            units='TB cascade counts TA underflows, one-edge delayed; not CPU cycles; no alignment',
            first_snapshot_target=12 if first_boundary else 18,
            limitations='ICR completion flags only; no transmitted pin data or isolated IPL propagation'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm',required=True);p.add_argument('--wsl',action='store_true');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--first-boundary',action='store_true',help='single-byte first completion sweep14..18; acknowledge at12')
    a=p.parse_args();build(a.vasm,a.wsl,a.out,a.first_boundary)
