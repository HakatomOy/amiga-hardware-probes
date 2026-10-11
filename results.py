#!/usr/bin/env python3
"""Extract validated A500 IRQ records from an ADF and compare two captures."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

ADF_BYTES = 901120
OFFSET = 1536 * 512
SIZE = 65536
COUNT = 768
SOURCES = ['ciaa-ta', 'ciab-ta', 'copper-softint', 'paired-cia-ta']
KERNELS = ['nop', 'movem-load', 'movem-store', 'divu', 'stop', 'trap-rte']


def decode(image):
    if len(image) != ADF_BYTES:
        raise ValueError(f'Expected an ordinary {ADF_BYTES}-byte DD ADF')
    raw = image[OFFSET:OFFSET+SIZE]
    if raw[:8] != b'A5IRQ001':
        raise ValueError('No results saved: missing A5IRQ001 signature')
    version, header_size, record_size, reserved = struct.unpack_from('>4H', raw, 8)
    count, size, record_offset, checksum = struct.unpack_from('>4I', raw, 16)
    if (version, header_size, record_size, reserved, size, record_offset) != (1,512,64,0,SIZE,512):
        raise ValueError('Unsupported or damaged result layout')
    if count != COUNT or struct.unpack_from('>H', raw, 74)[0] != 1:
        raise ValueError(f'Incomplete capture ({count}/{COUNT} records)')
    if sum(struct.unpack('>16384I', raw)) & 0xffffffff:
        raise ValueError('Results checksum failed: image is incomplete or damaged')
    meta = dict(source_id=raw[32:64].hex(), checksum=f'{checksum:08x}',
                agnus_vposr=f'{struct.unpack_from(">H",raw,64)[0]:04x}',
                denise_id_raw=f'{struct.unpack_from(">H",raw,66)[0]:04x}',
                cpu_attnflags=f'{struct.unpack_from(">H",raw,68)[0]:04x}',
                exec_version=struct.unpack_from('>H',raw,70)[0],
                exec_revision=struct.unpack_from('>H',raw,72)[0],
                adf_sha256=hashlib.sha256(image).hexdigest(), record_count=count)
    records = []
    for index in range(count):
        pos = record_offset + index * record_size
        source, kernel, phase, repeat = struct.unpack_from('>4B', raw, pos)
        expected_id = (index//192, (index//32)%6, (index//2)%16, index%2)
        if (source,kernel,phase,repeat) != expected_id:
            raise ValueError(f'Record {index}: invalid test identity')
        status, event_count, launch, reserved = struct.unpack_from('>4H', raw, pos+4)
        if status not in (0,1) or event_count > 2 or reserved:
            raise ValueError(f'Record {index}: invalid status or event count')
        expected_count = 2 if source == 3 else 1
        if status == 0 and event_count != expected_count:
            raise ValueError(f'Record {index}: missing interrupt with success status')
        record = dict(index=index, source=SOURCES[source], kernel=KERNELS[kernel],
                      phase=phase, repeat=repeat, status='timeout' if status else 'ok',
                      event_count=event_count, launch_vhposr=f'{launch:04x}')
        for event in range(2):
            prefix = f'event{event+1}_'
            if event >= event_count:
                continue
            values = struct.unpack_from('>4HI4BI',raw,pos+12+event*20)
            beam, vposr, sr, intreq, pc, ciaa, ciab, level, pad, d0 = values
            if level not in (1,2,6) or pad:
                raise ValueError(f'Record {index}: invalid interrupt event')
            record.update({prefix+'vhposr':f'{beam:04x}', prefix+'vposr_later':f'{vposr:04x}',
                           prefix+'sr':f'{sr:04x}', prefix+'intreq':f'{intreq:04x}',
                           prefix+'pc_offset':f'{pc:08x}', prefix+'ciaa_icr':f'{ciaa:02x}',
                           prefix+'ciab_icr':f'{ciab:02x}', prefix+'level':level,
                           prefix+'d0':f'{d0:08x}'})
        for offset, name in ((52,'d1'),(56,'d3'),(60,'d5')):
            record['final_'+name] = f'{struct.unpack_from(">I",raw,pos+offset)[0]:08x}'
        records.append(record)
    meta['timeouts'] = sum(record['status']=='timeout' for record in records)
    return meta, records


def compare(left, right):
    left_meta, left_records = left
    right_meta, right_records = right
    if left_meta['source_id'] != right_meta['source_id']:
        raise ValueError('Test source IDs differ; compare images from the same build')
    differences = []
    for a, b in zip(left_records, right_records):
        changed = {key: [a.get(key),b.get(key)] for key in sorted(set(a)|set(b)) if a.get(key)!=b.get(key)}
        if changed:
            differences.append(dict(index=a['index'], source=a['source'], kernel=a['kernel'],
                                    phase=a['phase'], repeat=a['repeat'], changes=changed))
    return dict(left=left_meta, right=right_meta, differing_records=len(differences), differences=differences)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    extract = sub.add_parser('extract')
    extract.add_argument('adf',type=Path)
    extract.add_argument('--out',type=Path,required=True,help='Output stem for .json and .csv')
    extract.add_argument('--label',default='',help='Machine configuration / capture notes')
    diff = sub.add_parser('compare')
    diff.add_argument('left',type=Path)
    diff.add_argument('right',type=Path)
    diff.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == 'extract':
            meta, records = decode(args.adf.read_bytes())
            meta['label'] = args.label
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.with_suffix('.json').write_text(json.dumps(dict(metadata=meta,records=records),indent=2)+'\n',encoding='utf-8')
            fields = list(dict.fromkeys(key for record in records for key in record))
            with args.out.with_suffix('.csv').open('w',newline='',encoding='utf-8') as stream:
                writer = csv.DictWriter(stream,fieldnames=fields)
                writer.writeheader()
                writer.writerows(records)
            print(f"Extracted {len(records)} records; {meta['timeouts']} timeouts; source {meta['source_id']}")
        else:
            report = compare(decode(args.left.read_bytes()),decode(args.right.read_bytes()))
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(f"{report['differing_records']}/{COUNT} records differ; report: {args.out}")
    except (ValueError,OSError) as error:
        parser.exit(1,f'error: {error}\n')


if __name__ == '__main__':
    main()
