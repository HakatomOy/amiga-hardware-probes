#!/usr/bin/env python3
"""Compare actual validated ROM captures without assuming phase-index equality."""
import argparse,collections,json,statistics
from pathlib import Path
import rom_results

def stats(values):
    return dict(n=len(values),min=min(values),median=statistics.median(values),max=max(values)) if values else dict(n=0)

def beam(value): return (value>>8)*227+(value&255)

def compare(hardware,candidate,out):
    hm,hr=rom_results.decode(hardware.read_bytes());cm,cr=rom_results.decode(candidate.read_bytes())
    if hm['source_id']!=cm['source_id'] or len(hr)!=len(cr): raise ValueError('Different probe sources')
    groups=collections.defaultdict(list)
    for h,c in zip(hr,cr):
        if [h[k] for k in rom_results.FIELDS[:6]] != [c[k] for k in rom_results.FIELDS[:6]]: raise ValueError('Different trial order')
        if h['status'] or c['status']: continue
        if h['kind']==10:
            key=(10,h['target'],h['variant'],h['delay']&3,h['delay']>>2)
        else: key=(h['kind'],h['target'],h['variant'])
        groups[key].append((h,c))
    report=dict(hardware=hm,candidate=cm,groups=[])
    for key,pairs in sorted(groups.items()):
        item=dict(key=list(key),pairs=len(pairs))
        item['reference_tick_error']=stats([c['reference_ticks']-h['reference_ticks'] for h,c in pairs])
        if key[0]==10:
            valid=[(h,c) for h,c in pairs if all((r[k]&255)>1 for r in (h,c) for k in ('irq_beam','launch_beam'))]
            item['irq_elapsed_error']=stats([(beam(c['irq_beam'])-beam(c['launch_beam']))-(beam(h['irq_beam'])-beam(h['launch_beam'])) for h,c in valid])
            item['same_launch_elapsed_error']=stats([(beam(c['irq_beam'])-beam(c['launch_beam']))-(beam(h['irq_beam'])-beam(h['launch_beam'])) for h,c in valid if h['launch_beam']==c['launch_beam']])
            item['saved_pc_equal']=sum(h['saved_pc_offset']==c['saved_pc_offset'] for h,c in pairs)
            item['irq_level_equal']=sum(h['irq_level']==c['irq_level'] for h,c in pairs)
            item['event_count_equal']=sum(h['aux']==c['aux'] for h,c in pairs)
            if key[1]==3:
                for name,index in [('hardware',0),('candidate',1)]:
                    item[name+'_copper_offsets']=dict(collections.Counter(beam(pair[index]['irq_beam'])-(96*227+64+pair[index]['phase']*2) for pair in pairs if (pair[index]['irq_beam']&255)>1))
        else:
            item['counter_equal']=sum(h['counter']==c['counter'] for h,c in pairs)
            item['icr_equal']=sum(h['icr']==c['icr'] for h,c in pairs)
            item['icr_ir_equal']=sum((h['icr']&0x80)==(c['icr']&0x80) for h,c in pairs)
            same_ticks=[(h,c) for h,c in pairs if h['reference_ticks']==c['reference_ticks']]
            item['same_reference_ticks']=len(same_ticks)
            item['same_ticks_counter_equal']=sum(h['counter']==c['counter'] for h,c in same_ticks)
            item['same_ticks_counter_error']=stats([c['counter']-h['counter'] for h,c in same_ticks])
        report['groups'].append(item)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    lines=['# ROM probe hardware comparison','',f"Source: `{hm['source_id']}`",'',
           f"Hardware: {hm['record_count']} records, {hm['timeouts']} timeouts, {hm['skipped']} skipped.",
           f"Candidate: {cm['record_count']} records, {cm['timeouts']} timeouts, {cm['skipped']} skipped.",
           '', 'Errors are candidate minus physical hardware. Beam units are colour clocks.',
           'Injected NOP phase indices do not prove matching E-clock phase. Reference ticks',
           'and actual launch beam positions are additional checks, not perfect phase locks.',
           'PAL beam decoding is used; horizontal 0/1 launch or IRQ reads are excluded from elapsed errors.', '',
           '| Kind/target/variant[/DMA/memory] | Pairs | Counter equal | ICR equal | IRQ error min/median/max | Same-tick counter error |',
           '|---|---:|---:|---:|---|---|']
    def triplet(s): return f"{s['min']}/{s['median']}/{s['max']} ({s['n']})" if s.get('n') else '-'
    for g in report['groups']:
        lines.append('| '+ '/'.join(map(str,g['key']))+f" | {g['pairs']} | {g.get('counter_equal','-')} | {g.get('icr_equal','-')} | "+triplet(g.get('irq_elapsed_error',{}))+' | '+triplet(g.get('same_ticks_counter_error',{}))+' |')
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('hardware',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=compare(a.hardware,a.candidate,a.out)
    print('Validated comparison:',len(r['groups']),'groups')
