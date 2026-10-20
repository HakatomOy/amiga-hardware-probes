"""Create exact, baseline-qualified contracts for existing bus/handoff captures."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import experiment as e

SUITES={
 'bus-onset':('bus-onset-v1',['bus-onset-v1-run1'],'captures/serial-buffer-20261019/regression/bus-onset'),
 'bus-completion':('bus-marker-completion-v3',['bus-marker-completion-v3-run1'],'captures/serial-buffer-20261019/regression/bus-completion'),
 'bus-pressure':('bus-pressure-v2',['bus-pressure-v2-run1'],'captures/serial-buffer-20261019/regression/bus-pressure'),
 'handoff-focus':('handoff-focus-v1',['handoff-focus-v1-run1','handoff-focus-v1-run2'],'captures/handoff-focus-20261019/baseline-v1'),
 'handoff-read':('handoff-read-v1',['handoff-read-v1-run1'],'captures/handoff-focus-20261019/read-baseline-v1'),
 'handoff-neighbor':('handoff-read-neighbors-v1',['handoff-read-neighbor-v1-run1','handoff-read-neighbor-v1-run2'],'captures/handoff-focus-20261019/read-neighbor-baseline-v1'),
}


def field(name,key,unit,meaning,**kw):
    return dict(name=name,field=key,unit=unit,meaning=meaning,**kw)


def policy(kind):
    if kind==55:
        measurements=[]
        for name,key,shift,mask in (
            ('marker0','counter',0,0x14),('status0','icr',0,0x6000),
            ('marker1','irq_beam',0,0x14),('status1','irq_level',0,0x6000),
            ('marker2','saved_pc_offset',16,0x14),('status2','saved_pc_offset',0,0x6000),
            ('marker3','status',0,0x14),('status3','aux',0,0x6000),('settled_marker','end_ref',0,0x14),
            ('first_D','second_counter_or_beam',0,65535),('last_D','second_icr_or_level',0,65535)):
            measurements.append(field(name,key,'register/data bits','Marker/status observation; pressure variants may substitute immutable ROM control data',shift=shift,mask=mask))
        qualification=[field(f,f,'packed beam word','Exact launch/read bracket') for f in ('launch_beam','launch_ref')]
    elif kind in (59,60):
        measurements=[field(n,f,u,m,mask=mask,shift=shift) for n,f,u,m,mask,shift in (
            ('clear_status','launch_ref','DMACONR bits','First clear status',0x6000,0),
            ('early_D','end_beam','data word','Immediate data read',65535,0),
            ('post_status','end_ref','DMACONR bits','Postwrite status',0x6000,0),
            ('handoff','counter','packed beam','Handoff observation',65535,0),
            ('post_beam','icr','packed beam','Postwrite observation',65535,0),
            ('first_D','irq_beam','data word','Final first destination',65535,0),
            ('last_D','irq_level','data word','Final last destination',65535,0),
            ('blit_irq','saved_pc_offset','INTREQ bit','Settled BLIT request',64,16),
            ('settled_beam','saved_pc_offset','packed beam','Settled observation',65535,0))]
        if kind==60:measurements.append(field('remaining_polls','aux','DBRA count','4095 minus this value is busy-sample count'))
        qualification=[field('launch','launch_beam','packed beam','Exact pre-write beam')]
    else:raise ValueError('unsupported measurement kind')
    return dict(alignment='exact',measurements=measurements,qualification=qualification)


def make(suite):
    archive,refs,baseline=SUITES[suite]
    build=e.read(ROOT/'build'/archive/'manifest.json')
    _,rows=e.rom_results.decode((ROOT/baseline/'results.bin').read_bytes());kind=rows[0]['kind']
    capture=dict(minimum_seconds=500,expected_cases=build['trial_count'],valid_statuses=[0])
    if kind==55:capture.update(validator='bus',status_is_measurement=True)
    if kind in (59,60):capture['validator']='handoff'
    hardware=[]
    for ref in refs:hardware+=e.load_capture(ROOT/'references'/ref,build,capture,True)[1]
    comparison=policy(kind)
    prior,_=e.compare(hardware,rows,comparison)
    comparison.update(max_excluded=prior['counts']['excluded'],max_unstable=prior['counts']['unstable_reference'])
    return dict(version=1,id='regression-'+suite,investigation='investigations/regression-'+suite+'.json',
        hypothesis='The candidate preserves or repairs qualified existing bus measurements without new field regressions.',
        competitor='The new timing rule overfits the focused family or changes existing valid controls.',
        test='Replay immutable '+suite+'; compare exact cohorts and per-field delta against accepted baseline.',
        outcomes={'repairs/unchanged only':'Continue validation; retain known differences and exclusions explicitly.',
                  'new field or qualification regression':'Reject or narrow the candidate before acceptance.'},
        next_question='Does this candidate generalize to '+suite+'?',binary='../Copperline/target/ci/copperline.exe',
        config='../Copperline/tmp/golden-a500-ecs.toml',romdir='build/'+archive,rom_sha256=build['rom_sha256'],
        capture=capture,comparison=comparison,baseline=baseline,references=['references/'+r for r in refs],
        reuse_preflight=True,replay_inputs=[],build=[],validation=[],
        budget_evidence=dict(baseline=baseline,counts=prior['counts'],rule='Freeze baseline exclusions; never derive budget from candidate.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'experiments/workflows')
    p.add_argument('--suite',choices=SUITES,action='append');a=p.parse_args()
    for name in a.suite or SUITES:
        spec=e.validate_spec(make(name));path=a.out/('regression-'+name+'.json')
        if path.exists():raise ValueError('refuse to overwrite '+str(path))
        e.write(path,spec);print(json.dumps(dict(suite=name,contract=str(path),baseline=spec['budget_evidence']['counts'])))
