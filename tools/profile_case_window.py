"""Read a bounded raw CCK window from a packet-qualified single-case profile."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

OWNERS = ('idle', 'refresh', 'cpu', 'copper', 'audio', 'blitter', 'bitplane', 'sprite', 'disk', 'conflict')
SLOT = struct.Struct('<HBBBBHIQI')


def window(run, beam, count=24, owners=('cpu', 'copper'), limit=24):
    if not 1 <= count <= 512 or not 1 <= limit <= 64:
        raise ValueError('window must be1..512CCK and limit1..64 events')
    if any(owner not in OWNERS for owner in owners):
        raise ValueError('unknown slot owner')
    verification = json.loads((run/'trace-verification.json').read_text())
    if verification.get('byte_identical') is not True:
        raise ValueError('profile packet is not qualified against its parent')
    vpos, hpos = [int(part, 16) for part in beam.split(':')]
    profile = run/'case-profile'
    frames = [json.loads(line) for line in (profile/'profile.jsonl').read_text().splitlines() if line.strip()]
    frames = [frame for frame in frames if 'slots_file' in frame]
    if len(frames) != 1:
        raise ValueError('expected exactly one captured frame')
    frame = frames[0]
    stride = frame['line_cck']
    if frame.get('slots_record_bytes') != SLOT.size or not (0 <= vpos < frame['rows'] and 0 <= hpos < stride):
        raise ValueError('unsupported slot layout or out-of-frame beam')
    raw_path = profile/frame['slots_file']
    raw = raw_path.read_bytes()
    if len(raw) != frame['rows'] * stride * SLOT.size:
        raise ValueError('truncated slot sidecar')
    start = vpos * stride + hpos
    selection = json.loads((run/'case-profile-selection.json').read_text())
    stopped = selection['stop']
    first_observed = stopped['vpos'] * stride + stopped['hpos']
    # The exporter labels a committed partial frame at the boundary counter;
    # depending on field timing that is the entry counter or its successor.
    if frame['frame'] not in (stopped['frame'], stopped['frame']+1) or start < first_observed:
        raise ValueError('window precedes the selected case; partial-frame zeros are not observations')
    if start + count > len(raw)//SLOT.size:
        raise ValueError('window runs beyond the captured frame')
    events, counts = [], Counter()
    for clock in range(start, start+count):
        reg, kind, subtype, size, ipl, flags, addr, data, edges = SLOT.unpack_from(raw, clock*SLOT.size)
        owner = OWNERS[kind] if kind < len(OWNERS) else f'unknown-{kind}'
        counts[owner] += 1
        if owner in owners:
            row, column = divmod(clock, stride)
            events.append(dict(beam=f'{row:02x}:{column:02x}', owner=owner, subtype=subtype,
                               bytes=size, reg=f'{reg:04x}', addr=f'{addr:08x}', data=f'{data:016x}',
                               flags=f'{flags:04x}', ipl=ipl, edges=edges))
    return dict(case=selection['case'], frame=frame['frame'], start=beam, cck=count,
                units='Raw color-clock slots; hexadecimal beam/register/address/data; no alignment',
                owner_cck=dict(counts), events=events[:limit], omitted_events=max(0,len(events)-limit),
                packet_sha256=verification['actual_sha256'], detail=str(raw_path.resolve()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--beam', required=True, help='Hexadecimal VPOS:HPOS, e.g.42:dc')
    parser.add_argument('--cck', type=int, default=24)
    parser.add_argument('--owners', default='cpu,copper')
    parser.add_argument('--limit', type=int, default=24)
    args = parser.parse_args()
    try:
        print(json.dumps(window(args.run, args.beam, args.cck, args.owners.split(','), args.limit)))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, json.dumps(dict(status='invalid_profile_window', error=str(error)[:400]))+'\n')
