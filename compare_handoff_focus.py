#!/usr/bin/env python3
"""Exact-launch kind59 comparison; no timestamp alignment or rescaling."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import rom_results


def key(r): return tuple(r[f] for f in rom_results.FIELDS[:6])


def cohort(r): return key(r)[:-1]+(r["launch_beam"],)


def measures(r):
    result = dict(first_clear=r["launch_ref"]&0x6000,early_d=r["end_beam"],
        postwrite_dmacon=r["end_ref"]&0x6000,handoff_beam=r["counter"],
        postwrite_beam=r["icr"],final_first_d=r["irq_beam"],final_last_d=r["irq_level"],
        blit_intreq=(r["saved_pc_offset"]>>16)&0x40,settled_beam=r["saved_pc_offset"]&65535)
    if r["kind"]==60:
        return dict(busy_samples=4095-r["aux"],**result)
    return result


def validate(r):
    if (r["kind"] not in (59,60) or r["target"]!=3 or (r["variant"]&15) not in (2,3,4,5,6,7,10,11,12,13,14,15) or not 0 <= r["variant"] < (32 if r["kind"]==60 else 16)
            or r["phase"] not in (0,1) or r["delay"] not in range(8) or r["repeat"] not in (0,1)):
        raise ValueError("unexpected descriptor")
    if r["status"]: raise ValueError(f"failed case {key(r)} status={r['status']}")


def load(path):
    path=Path(path);meta,rows=rom_results.decode((path/'results.bin' if path.is_dir() else path).read_bytes())
    if len({key(r) for r in rows})!=len(rows):raise ValueError("duplicate descriptor")
    for r in rows:validate(r)
    return meta,rows


def pattern(diff):
    result=[]
    for field,expected,actual in diff:
        if (field.endswith("_beam") and expected>>8 == actual>>8
                and abs((actual&255)-(expected&255)) <= 32):
            result.append((field,"same_line_cck_delta",(actual&255)-(expected&255)))
        else:
            result.append((field,expected,actual))
    return tuple(result)


def compare(hardware,candidate):
    ref=defaultdict(list)
    for r in hardware:validate(r);ref[cohort(r)].append(r)
    counts=Counter(total=len(candidate),matches=0,mismatches=0,missing_results=0,
                   no_identical_bracket=0,unstable_reference=0,invalid_captures=0)
    counts['missing_results']=len({key(r) for r in hardware}-{key(r) for r in candidate})
    groups=defaultdict(list);by=defaultdict(Counter)
    for r in candidate:
        validate(r);rows=ref.get(cohort(r),[])
        label=f"dma{(r['variant']>>1)&3}:priority{r['variant']&1}:"+('no_start' if r['variant']&8 else 'blit')+(':rom_read' if r['variant']&16 else ':chip_read')
        if not rows:counts['no_identical_bracket']+=1;by[label]['excluded']+=1;continue
        expected={tuple(measures(x).items()) for x in rows}
        if len(expected)!=1:counts['unstable_reference']+=1;by[label]['unstable']+=1;continue
        expected=dict(next(iter(expected)));actual=measures(r)
        diff=tuple((f,expected[f],actual[f]) for f in expected if expected[f]!=actual[f])
        outcome='mismatches' if diff else 'matches';counts[outcome]+=1;by[label][outcome]+=1
        if diff:groups[(label,pattern(diff))].append(dict(case=key(r),hardware=[key(x) for x in rows],
            launch_beam=f"{r['launch_beam']:04x}",differences=diff))
    return dict(counts=dict(counts),by_condition={k:dict(v) for k,v in by.items()},
        groups=[dict(condition=k,count=len(rows),pattern=diff,first_divergent_field=diff[0][0],representatives=rows[:3])
                for (k,diff),rows in sorted(groups.items(),key=lambda item:(-len(item[1]),repr(item[0])))])


def candidate_delta(hardware,baseline,candidate):
    ref=defaultdict(list)
    for r in hardware:ref[cohort(r)].append(r)
    before={key(r):r for r in baseline}
    counts=Counter(comparable=0,excluded=0,complete_repairs=0,complete_regressions=0,
                   cases_with_field_repairs=0,cases_with_field_regressions=0)
    fixed=Counter();regressed=Counter();examples=defaultdict(list)
    for r in candidate:
        old=before.get(key(r));rows=ref.get(cohort(r),[])
        if old is None or cohort(old)!=cohort(r) or not rows:
            counts['excluded']+=1;continue
        values={tuple(measures(x).items()) for x in rows}
        if len(values)!=1:counts['excluded']+=1;continue
        expected=dict(next(iter(values)));a=measures(old);b=measures(r)
        counts['comparable']+=1
        repairs=[f for f in expected if a[f]!=expected[f] and b[f]==expected[f]]
        regressions=[f for f in expected if a[f]==expected[f] and b[f]!=expected[f]]
        fixed.update(repairs);regressed.update(regressions)
        counts['complete_repairs']+=a!=expected and b==expected
        counts['complete_regressions']+=a==expected and b!=expected
        counts['cases_with_field_repairs']+=bool(repairs)
        counts['cases_with_field_regressions']+=bool(regressions)
        for field in regressions:
            if len(examples[field])<3:examples[field].append(dict(case=key(r),expected=expected[field],before=a[field],after=b[field]))
    return dict(counts=dict(counts),repaired_fields=dict(fixed),regressed_fields=dict(regressed),
                regression_representatives=dict(examples))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hardware',type=Path,required=True,action='append')
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--baseline',type=Path)
    a=p.parse_args();captures=[(path,*load(path)) for path in a.hardware];cm,c=load(a.candidate)
    if any(m['source_id']!=cm['source_id'] for _,m,_ in captures):raise ValueError('source identity differs')
    report=compare([r for _,_,rows in captures for r in rows],c)
    report.update(hardware=[str(path) for path,_,_ in captures],candidate=str(a.candidate),
        source_id=cm['source_id'],reference_hashes=[m['sha256'] for _,m,_ in captures],
        alignment='none; exact descriptor except repeat plus prelaunch beam',
        units='encoded beam words, data words and masked BBUSY/BZERO/BLIT flags; no packed beam subtraction')
    if a.baseline:
        bm,b=load(a.baseline)
        if bm['source_id']!=cm['source_id']:raise ValueError('baseline source identity differs')
        report['baseline_delta']=candidate_delta([r for _,_,rows in captures for r in rows],b,c)
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['counts']));print(json.dumps(report['by_condition']));print('detail:',a.out)
    if a.baseline:print(json.dumps(report['baseline_delta']))
