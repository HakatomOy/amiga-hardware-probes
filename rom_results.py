#!/usr/bin/env python3
"""Decode checksum-protected RBCP captures; never accept partial results."""
import argparse, csv, hashlib, json, struct
from pathlib import Path
FIELDS=['kind','target','variant','phase','delay','repeat','launch_beam','launch_ref',
        'end_beam','end_ref','counter','icr','irq_beam','irq_level','pc_hi','pc_lo',
        'status','aux','second_counter_or_beam','second_icr_or_level']

def from_transcript(data):
    start=b'A5RBCP-BEGIN\n'; end=b'A5RBCP-END'
    normalized=data.replace(b'\r\n',b'\n')
    if start not in normalized or end not in normalized: raise ValueError('Missing complete RBCP frame')
    body=normalized.split(start,1)[1].split(end,1)[0]
    return bytes.fromhex(body.decode('ascii'))

def decode(data):
    if data[:8]!=b'A5RBCP01': raise ValueError('Wrong ROM result magic')
    if len(data)<64: raise ValueError('Truncated header')
    version,size,count,length,checksum=struct.unpack_from('>HHIII',data,8)
    if version!=1 or size!=40 or length!=64+count*size or length!=len(data): raise ValueError('Invalid result layout')
    if sum(struct.unpack('>'+str(len(data)//4)+'I',data))&0xffffffff: raise ValueError('Checksum mismatch')
    agnus,denise,slow,complete=struct.unpack_from('>4H',data,56)
    if complete!=1: raise ValueError('Collection incomplete')
    rows=[]
    for offset in range(64,len(data),40):
        row=dict(zip(FIELDS,struct.unpack_from('>20H',data,offset)))
        row['saved_pc_offset']=(row.pop('pc_hi')<<16)|row.pop('pc_lo')
        row['reference_ticks']=(row['launch_ref']-row['end_ref'])&0xffff
        rows.append(row)
    meta=dict(version=version,source_id=data[24:56].hex(),record_count=count,
              agnus_vposr=f'{agnus:04x}',denise_id_raw=f'{denise:04x}',slow_ram=bool(slow),
              timeouts=sum(r['status']==1 for r in rows),skipped=sum(r['status']==2 for r in rows),
              sha256=hashlib.sha256(data).hexdigest())
    return meta,rows

def extract(path,out,transcript=False,manifest=None):
    data=path.read_bytes()
    if transcript: data=from_transcript(data)
    if data[:8]==b'A5FAULT1':
        if len(data) not in (128,512) or sum(struct.unpack('>'+str(len(data)//4)+'I',data))&0xffffffff:
            raise ValueError('Damaged fault capsule')
        out.mkdir(parents=True,exist_ok=True)
        vector=struct.unpack_from('>H',data,8)[0]
        registers=struct.unpack_from('>16I',data,16)
        stack=struct.unpack_from('>16H',data,80)
        descriptor=struct.unpack_from('>6H',data,112)
        report=dict(vector=vector,registers=dict(zip([f'd{i}' for i in range(8)]+[f'a{i}' for i in range(8)],registers)),
                    raw_stack_words=list(stack),descriptor=list(descriptor),beam=struct.unpack_from('>H',data,124)[0])
        if vector not in (2,3): report['saved_pc']=(stack[1]<<16)|stack[2]
        if len(data)==512:
            report['vectors']={str(i):v for i,v in enumerate(struct.unpack_from('>32I',data,128))}
            report['kernel_bytes']=data[256:384].hex()
            report['variables']=data[384:512].hex()
        (out/'fault.bin').write_bytes(data)
        (out/'fault.json').write_text(json.dumps(report,indent=2)+'\n')
        raise RuntimeError('Physical CPU exception: '+json.dumps(report))
    meta,rows=decode(data)
    if manifest:
        spec=json.loads(manifest.read_text())
        if meta['source_id']!=spec['source_id'] or len(rows)!=spec['trial_count']: raise ValueError('Source mismatch')
        for row,trial in zip(rows,spec['trials']):
            if [row[k] for k in FIELDS[:6]]!=trial: raise ValueError('Trial descriptor mismatch')
    out.mkdir(parents=True,exist_ok=True)
    (out/'results.bin').write_bytes(data)
    (out/'results.json').write_text(json.dumps(dict(metadata=meta,records=rows),indent=2)+'\n')
    with (out/'results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(meta))
    return meta,rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--transcript',action='store_true');p.add_argument('--manifest',type=Path)
    a=p.parse_args();extract(a.capture,a.out,a.transcript,a.manifest)
