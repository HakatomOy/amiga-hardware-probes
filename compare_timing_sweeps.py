#!/usr/bin/env python3
"""Compare validated A500 timing sweeps (RBCP experiment kinds 18–21)."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path

import compare_golden_rom
import rom_results


def load(folder):
    """Load a complete capture and its manifest using the shared strict validator."""
    return compare_golden_rom.load(Path(folder))



def capture_provenance(folder, expected_binary=None, expected_sha256=None):
    """Validate invocation provenance, and optionally pin it to one binary build."""
    if (expected_binary is None) != (expected_sha256 is None):
        raise ValueError('Expected emulator binary path and SHA256 must be supplied together')
    path = Path(folder) / 'invocation.json'
    if not path.exists():
        if expected_binary is not None:
            raise ValueError(f'Missing invocation provenance: {path}')
        return None
    invocation = json.loads(path.read_text())
    command = invocation.get('command')
    declared_path = command[0] if isinstance(command, list) and command else None
    declared_hash = invocation.get('binary_sha256')
    if not declared_path or not declared_hash:
        raise ValueError(f'Incomplete binary provenance: {path}')
    binary_path = Path(declared_path)
    disk_hash = None
    if binary_path.is_file():
        disk_hash = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    hash_matches = disk_hash is not None and disk_hash.casefold() == declared_hash.casefold()
    result = dict(binary_path=str(binary_path), binary_sha256=declared_hash.lower(),
                  current_disk_sha256=disk_hash, verified_on_disk=hash_matches)
    if expected_binary is not None and not hash_matches:
        raise ValueError(f'Invocation binary hash no longer matches on-disk file: {declared_path}')
    if expected_binary is not None:
        expected_path = Path(expected_binary).resolve(strict=True)
        if os.path.normcase(str(binary_path.resolve(strict=True))) != os.path.normcase(str(expected_path)):
            raise ValueError(f'Unexpected emulator binary path: {declared_path}')
        expected_digest = expected_sha256.lower()
        if declared_hash.lower() != expected_digest:
            raise ValueError(f'Unexpected emulator invocation SHA256: {declared_hash}')
        actual_digest = disk_hash or hashlib.sha256(expected_path.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError(f'Emulator binary file SHA256 mismatch: {actual_digest}')
        result['expected_binary_verified'] = True
    return result

def histogram(values):
    return dict(sorted(collections.Counter(values).items()))


def _beam_elapsed(start, end, reject_ambiguous=True):
    """Convert packed PAL VPOS/HPOS to color clocks, rejecting ambiguous endpoints."""
    start_v, start_h = (start >> 8) & 0xff, start & 0xff
    end_v, end_h = (end >> 8) & 0xff, end & 0xff
    if (start_h <= 3 or start_h >= 224 or end_h <= 3 or end_h >= 224
            or end_v < start_v or (end_v == start_v and end_h < start_h)):
        if reject_ambiguous:
            raise ValueError(f'ambiguous beam line/frame wrap: {start:04x}->{end:04x}')
        return None
    elapsed = (end_v - start_v) * 227 + end_h - start_h
    return elapsed


def _paired_rows(hw_rows, emu_rows):
    """Pair by the six ROM-defined trial descriptor words, never by list position alone."""
    def index(rows, label):
        result = {}
        for row in rows:
            key = tuple(row[k] for k in rom_results.FIELDS[:6])
            if key in result:
                raise ValueError(f'duplicate trial descriptor in {label}: {key}')
            result[key] = row
        return result
    hw = index(hw_rows, 'hardware')
    emu = index(emu_rows, 'emulator')
    if hw.keys() != emu.keys():
        missing_hw = sorted(emu.keys() - hw.keys())[:3]
        missing_emu = sorted(hw.keys() - emu.keys())[:3]
        raise ValueError(f'Trial coverage differs (missing hardware={missing_hw}, missing emulator={missing_emu})')
    return [(key, hw[key], emu[key]) for key in sorted(hw)]


def _assert_kind(rows, kind):
    found = {r['kind'] for r in rows}
    if found != {kind}:
        raise ValueError(f'Expected only experiment kind {kind}, found {sorted(found)}')


def _compare_cpu(pairs):
    grouped = collections.defaultdict(list)
    for key, hw, emu in pairs:
        _, plane, operand, phase, count, repeat = key
        grouped[(plane, operand, count)].append((phase, repeat, hw, emu))
    groups = []
    for (plane, operand, count), samples in sorted(grouped.items()):
        hraw = [_beam_elapsed(h['launch_beam'], h['end_beam'], False) for _, _, h, _ in samples]
        eraw = [_beam_elapsed(e['launch_beam'], e['end_beam'], False) for _, _, _, e in samples]
        hbeam = histogram(x for x in hraw if x is not None)
        ebeam = histogram(x for x in eraw if x is not None)
        # read_reference() records the independent CIA timer delta in launch_ref/end_ref.
        href = histogram((h['launch_ref'] - h['end_ref']) & 0xffff for _, _, h, _ in samples)
        eref = histogram((e['launch_ref'] - e['end_ref']) & 0xffff for _, _, _, e in samples)
        beam_deltas = []
        for h, e in ((h, e) for _, _, h, e in samples):
            hb = _beam_elapsed(h['launch_beam'], h['end_beam'], False)
            eb = _beam_elapsed(e['launch_beam'], e['end_beam'], False)
            if hb is not None and eb is not None:
                beam_deltas.append(eb - hb)
        ref_deltas = [(((e['launch_ref'] - e['end_ref']) & 0xffff) -
                       ((h['launch_ref'] - h['end_ref']) & 0xffff))
                      for _, _, h, e in samples]
        groups.append(dict(plane=plane, operand=operand, count=count, samples=len(samples),
                           hardware_beam_cck=hbeam, emulator_beam_cck=ebeam,
                           hardware_ambiguous_beam_samples=sum(x is None for x in hraw),
                           emulator_ambiguous_beam_samples=sum(x is None for x in eraw),
                           beam_elapsed_delta_emu_minus_hardware=histogram(beam_deltas),
                           reference_ticks_delta_emu_minus_hardware=histogram(ref_deltas),
                           hardware_reference_ticks=href, emulator_reference_ticks=eref,
                           phase_descriptor_frequencies=histogram(phase for phase, _, _, _ in samples),
                           hardware_launch_beam=histogram(h['launch_beam'] for _, _, h, _ in samples),
                           emulator_launch_beam=histogram(e['launch_beam'] for _, _, _, e in samples)))
    return dict(kind=18, groups=groups,
                note='PAL beam deltas use 227 color clocks per line. Endpoints at HPOS <=3 or >=224, and line/frame wraps, are excluded and counted. Reference ticks are an independent CIA measurement that starts before the ROM alignment call, so it also includes alignment setup. Phase values are descriptor buckets; launch beam positions are reported as distributions, not asserted to align exactly.')


def _compare_observers(pairs):
    """Compare the actual kind-19 DMA, interrupt, and memory observation points."""
    masks = {'dmaconr': 0x7fff, 'intreqr': 0x7fff, 'memory_word': 0xffff}
    by_group = collections.defaultdict(list)
    for key, hw, emu in pairs:
        by_group[(key[1], key[2])].append((hw, emu))
    groups = []
    for (target, variant), samples in sorted(by_group.items()):
        state_specs = {
            'dmaconr': ('counter', masks['dmaconr']),
            'intreqr': ('icr', masks['intreqr']),
            'memory_word': ('aux', masks['memory_word']),
        }
        observables = {}
        for name, (field, mask) in state_specs.items():
            hv = [h[field] & mask for h, _ in samples]
            ev = [e[field] & mask for _, e in samples]
            observables[name] = dict(mask=f'0x{mask:04x}', hardware=histogram(hv), emulator=histogram(ev),
                                     mismatches=sum(a != b for a, b in zip(hv, ev)))
        time_specs = {
            'dmaconr_first_read': ('end_beam',),
            'intreqr_second_read': ('irq_beam',),
            'memory_word_read': ('second_counter_or_beam',),
        }
        timings = {}
        for name, (field,) in time_specs.items():
            hvalues, evalues, deltas = [], [], []
            rejected = 0
            for h, e in samples:
                ht = _beam_elapsed(h['launch_beam'], h[field], False)
                et = _beam_elapsed(e['launch_beam'], e[field], False)
                if ht is None or et is None:
                    rejected += 1
                    continue
                hvalues.append(ht)
                evalues.append(et)
                deltas.append(et - ht)
            timings[name] = dict(hardware_cck=histogram(hvalues), emulator_cck=histogram(evalues),
                                 emulator_minus_hardware_cck=histogram(deltas),
                                 mismatches=sum(a != b for a, b in zip(hvalues, evalues)),
                                 rejected_ambiguous_samples=rejected)
        groups.append(dict(target=target, variant=variant, samples=len(samples),
                           observables=observables, timings=timings))
    return dict(kind=19, groups=groups,
                note='Kind 19 reads DMACONR at counter, INTREQR at icr, and the memory word at aux. end_beam, irq_beam, and second_counter_or_beam timestamp those reads. State mismatches use the explicit register masks shown.')

def _compare_div_irq(pairs):
    by_target = collections.defaultdict(list)
    for key, hw, emu in pairs:
        by_target[key[1]].append((hw, emu))
    targets = []
    for target, samples in sorted(by_target.items()):
        # aux holds the D4 marker captured by the DIV IRQ handler; combine it with
        # the stacked PC so classification never relies on PC or marker alone.
        classify = lambda r: (r['saved_pc_offset'], r['aux'])
        hclass = collections.Counter(classify(h) for h, _ in samples)
        eclass = collections.Counter(classify(e) for _, e in samples)
        class_rows = [dict(saved_pc_offset=pc, marker=marker,
                           hardware=hclass[(pc, marker)], emulator=eclass[(pc, marker)])
                      for pc, marker in sorted(set(hclass) | set(eclass))]
        targets.append(dict(target=target, samples=len(samples),
                            pc_marker_classifications=class_rows,
                            classification_mismatches=sum(classify(h) != classify(e) for h, e in samples),
                            irq_beam_mismatches=sum(h['irq_beam'] != e['irq_beam'] for h, e in samples),
                            irq_level_mismatches=sum(h['irq_level'] != e['irq_level'] for h, e in samples)))
    return dict(kind=20, targets=targets,
                note='Saved-PC plus D4 marker (aux) forms the DIV IRQ classification key.')


def _compare_aligned(pairs):
    observer_masks = {0: 0x4000, 1: 0x0040, 2: 0xffff}
    by_target = collections.defaultdict(list)
    priorities = set()
    for key, hw, emu in pairs:
        _, target, variant, phase, delay, repeat = key
        observer = repeat & 3
        priority = bool(repeat & 4)
        if observer not in observer_masks or repeat not in (*range(3), *range(4, 7)):
            raise ValueError(f'Unknown aligned-channel observer/priority repeat {repeat}')
        priorities.add(priority)
        if hw['launch_beam'] != emu['launch_beam']:
            raise ValueError(f'Aligned launch position differs for trial {key}: '
                             f'{hw["launch_beam"]:04x} != {emu["launch_beam"]:04x}')
        by_target[target].append((key, hw, emu, observer_masks[observer], observer, priority))
    if len(priorities) > 1:
        raise ValueError('Aligned-channel capture mixes BLTPRI-off and BLTPRI-on rows')
    bltpri_enabled = next(iter(priorities), False)
    targets = []
    for target, samples in sorted(by_target.items()):
        state_diffs = 0
        time_diffs = 0
        per_observer = {}
        for repeat in sorted({key[5] for key, *_ in samples}):
            observer = repeat & 3
            mask = observer_masks[observer]
            subset = [(h, e) for key, h, e, *_ in samples if key[5] == repeat]
            if not subset:
                continue
            hstate = [h['counter'] & mask for h, _ in subset]
            estate = [e['counter'] & mask for _, e in subset]
            htime = [_beam_elapsed(h['launch_beam'], h['end_beam']) for h, _ in subset]
            etime = [_beam_elapsed(e['launch_beam'], e['end_beam']) for _, e in subset]
            sd = sum(a != b for a, b in zip(hstate, estate))
            td = sum(a != b for a, b in zip(htime, etime))
            state_diffs += sd
            time_diffs += td
            per_observer[str(repeat)] = dict(observer=observer, bltpri_enabled=bool(repeat & 4),
                state_mask=f'0x{mask:04x}', samples=len(subset),
                hardware_state=histogram(hstate), emulator_state=histogram(estate), state_mismatches=sd,
                hardware_elapsed_cck=histogram(htime), emulator_elapsed_cck=histogram(etime), timing_mismatches=td)
        targets.append(dict(target=target, bltpri_enabled=bltpri_enabled, samples=len(samples), state_mismatches=state_diffs,
                            timing_mismatches=time_diffs, observers=per_observer))
    return dict(kind=21, bltpri_enabled=bltpri_enabled, targets=targets,
                note='State masks: busy=0x4000, IRQ=0x0040, memory=0xffff. Repeat bit 2 identifies BLTPRI-on rows; low two bits select observer. Elapsed PAL beam time uses 227 color clocks per line.')


def _compare_bzero(pairs):
    """Compare BZERO/BBUSY samples and beam timing per target, source variant and priority."""
    bzero_mask = 0x6000
    dmaconr_mask = 0x67ff
    by_group = collections.defaultdict(list)
    for key, hw, emu in pairs:
        _, target, variant, phase, delay, repeat = key
        if repeat not in (0, 4):
            raise ValueError(f'Unknown BZERO priority repeat {repeat}')
        if phase not in (0, 1) or delay not in range(16):
            raise ValueError(f'Invalid BZERO phase/delay descriptor {key}')
        if hw['launch_beam'] != emu['launch_beam']:
            raise ValueError(f'BZERO launch position differs for trial {key}: '
                             f'{hw["launch_beam"]:04x} != {emu["launch_beam"]:04x}')
        by_group[(target, variant, repeat)].append((hw, emu))

    groups = []
    for target, variant in sorted({(t, v) for t, v, _ in by_group}):
        repeats = {}
        total = 0
        for repeat in (0, 4):
            samples = by_group.get((target, variant, repeat), [])
            if not samples:
                continue
            total += len(samples)
            hstate = [h['counter'] & bzero_mask for h, _ in samples]
            estate = [e['counter'] & bzero_mask for _, e in samples]
            hfull = [h['counter'] & dmaconr_mask for h, _ in samples]
            efull = [e['counter'] & dmaconr_mask for _, e in samples]
            htime = [_beam_elapsed(h['launch_beam'], h['end_beam']) for h, _ in samples]
            etime = [_beam_elapsed(e['launch_beam'], e['end_beam']) for _, e in samples]
            repeats[str(repeat)] = dict(
                bltpri_enabled=bool(repeat & 4), samples=len(samples),
                bzero_busy_mask=f'0x{bzero_mask:04x}',
                hardware_bzero_busy=histogram(hstate), emulator_bzero_busy=histogram(estate),
                bzero_busy_mismatches=sum(a != b for a, b in zip(hstate, estate)),
                dmaconr_valid_mask=f'0x{dmaconr_mask:04x}',
                hardware_dmaconr_valid=histogram(hfull), emulator_dmaconr_valid=histogram(efull),
                dmaconr_valid_mismatches=sum(a != b for a, b in zip(hfull, efull)),
                hardware_elapsed_cck=histogram(htime), emulator_elapsed_cck=histogram(etime),
                elapsed_mismatches=sum(a != b for a, b in zip(htime, etime)))
        groups.append(dict(target=target, variant=variant, samples=total, repeats=repeats))
    return dict(kind=22, groups=groups,
                note='counter bit mask 0x6000 compares BBUSY/BZERO; 0x67ff reports valid DMACONR bits. Repeat 0/4 separates BLTPRI clear/set. Beam elapsed is 227*deltaV+deltaH; launch coordinates must match exactly.')


def _compare_irq_paths(pairs):
    """Report STOP wake timing and interrupted-PC classification by IRQ source/path."""
    grouped = collections.defaultdict(list)
    for key, hw, emu in pairs:
        _, target, variant, phase, delay, repeat = key
        if target not in range(7) or variant not in (0, 1) or phase not in (0, 1):
            raise ValueError(f'Invalid IRQ-path descriptor {key}')
        if delay not in range(16) or repeat not in (0, 4):
            raise ValueError(f'Invalid IRQ-path delay/priority descriptor {key}')
        if hw['launch_beam'] != emu['launch_beam']:
            raise ValueError(f'IRQ-path launch position differs for {key}')
        grouped[(target, variant, phase, repeat)].append((key, hw, emu))
    groups = []
    for target, variant, phase, repeat in sorted(grouped):
        samples = grouped[(target, variant, phase, repeat)]
        hdelta=[]; edelta=[]; hpc=[]; epc=[]
        irq_diffs=pc_diffs=level_diffs=completion_diffs=0
        h_pc_status=[]; e_pc_status=[]; h_level_bad=e_level_bad=0
        for key, hw, emu in samples:
            _, sample_target, _, sample_phase, sample_delay, _ = key
            expected_pc = 0xfe0000 + sample_phase * 0x1000 + sample_delay * 0x100 + 20 + 2 * sample_delay
            expected_level = 1 if sample_target == 6 else 3
            hdelta.append(_beam_elapsed(hw['launch_beam'], hw['irq_beam']))
            edelta.append(_beam_elapsed(emu['launch_beam'], emu['irq_beam']))
            hpc.append(hw['saved_pc_offset']); epc.append(emu['saved_pc_offset'])
            h_pc_status.append(hw['saved_pc_offset'] == expected_pc)
            e_pc_status.append(emu['saved_pc_offset'] == expected_pc)
            h_level_bad += hw['irq_level'] != expected_level
            e_level_bad += emu['irq_level'] != expected_level
            irq_diffs += hdelta[-1] != edelta[-1]
            pc_diffs += hw['saved_pc_offset'] != emu['saved_pc_offset']
            level_diffs += hw['irq_level'] != emu['irq_level']
            completion_diffs += hw['aux'] != emu['aux']
        groups.append(dict(target=target, handler='RAM' if variant == 0 else 'ROM',
            phase=phase, phase_pad_cck=2 if phase == 0 else 3,
            bltpri_enabled=bool(repeat & 4), samples=len(samples),
            hardware_irq_elapsed_cck=histogram(hdelta), emulator_irq_elapsed_cck=histogram(edelta),
            irq_elapsed_mismatches=irq_diffs,
            hardware_saved_pc=histogram(hpc), emulator_saved_pc=histogram(epc),
            saved_pc_mismatches=pc_diffs,
            expected_post_stop_pc_mismatches=dict(hardware=sum(not v for v in h_pc_status),
                                                  emulator=sum(not v for v in e_pc_status)),
            hardware_irq_level=histogram([h['irq_level'] for _,h,_ in samples]),
            emulator_irq_level=histogram([e['irq_level'] for _,_,e in samples]),
            irq_level_mismatches=level_diffs,
            expected_irq_level=1 if target == 6 else 3,
            unexpected_irq_level=dict(hardware=h_level_bad, emulator=e_level_bad),
            handler_completion_mismatches=completion_diffs))
    return dict(kind=23, groups=groups,
        note='Targets 0-3 are native D-only/AD-copy/AD-fill/line BLIT IRQs; 4-6 are Copper INTREQ BLIT/COPER/SOFT. Variant 0 uses copied chip-RAM handler, 1 ROM handler. Saved PC is the 68000 exception-frame PC; IRQ elapsed uses 227*deltaV+deltaH and exact launch-beam pairing.')


def _compare_bzero_line(pairs):
    """Compare line BZERO state and destination-memory effects."""
    by_group=collections.defaultdict(list)
    for key,hw,emu in pairs:
        _,target,variant,phase,delay,repeat=key
        pattern=variant & 0xff
        late_bdat=bool(variant & 0x100)
        if target not in (32,33) or pattern not in (0,1,4,8,16) or variant & ~0x11f:
            raise ValueError(f'Invalid line BZERO pattern/order descriptor {key}')
        if phase not in (0,1) or delay not in range(32) or repeat not in (0,4):
            raise ValueError(f'Invalid line BZERO phase/delay/priority descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Line BZERO launch position differs for trial {key}')
        by_group[(target,pattern,late_bdat,phase,repeat)].append((hw,emu))
    groups=[]
    for target,pattern,late_bdat,phase,repeat in sorted(by_group):
        samples=by_group[(target,pattern,late_bdat,phase,repeat)]
        hstate=[h['counter']&0x6000 for h,_ in samples]
        estate=[e['counter']&0x6000 for _,e in samples]
        hfull=[h['counter']&0x67ff for h,_ in samples]
        efull=[e['counter']&0x67ff for _,e in samples]
        htime=[_beam_elapsed(h['launch_beam'],h['end_beam']) for h,_ in samples]
        etime=[_beam_elapsed(e['launch_beam'],e['end_beam']) for _,e in samples]
        memory_fields=(('destination_or', 'icr'), ('destination_first', 'irq_beam'),
                       ('destination_10050', 'irq_level'), ('destination_100a0', 'saved_pc_offset'))
        memory={}
        for label,field in memory_fields:
            hv=[h[field] if field!='saved_pc_offset' else h[field] >> 16 for h,_ in samples]
            ev=[e[field] if field!='saved_pc_offset' else e[field] >> 16 for _,e in samples]
            memory[label]=dict(hardware=histogram(hv),emulator=histogram(ev),
                               mismatches=sum(a!=b for a,b in zip(hv,ev)))
        groups.append(dict(target=target,b_use_enabled=target==33,
            b_pattern=pattern,bdat_written_after_bltcon1=late_bdat,
            phase=phase,phase_pad_cck=2 if phase==0 else 3,
            bltpri_enabled=bool(repeat&4),samples=len(samples),
            hardware_bzero_busy=histogram(hstate),emulator_bzero_busy=histogram(estate),
            bzero_busy_mismatches=sum(a!=b for a,b in zip(hstate,estate)),
            hardware_dmaconr_valid=histogram(hfull),emulator_dmaconr_valid=histogram(efull),
            dmaconr_valid_mismatches=sum(a!=b for a,b in zip(hfull,efull)),
            hardware_elapsed_cck=histogram(htime),emulator_elapsed_cck=histogram(etime),
            elapsed_mismatches=sum(a!=b for a,b in zip(htime,etime)),
            destination_memory=memory))
    return dict(kind=24,groups=groups,
        note='Line-mode BZERO and destination memory; targets 32/33 differ by USEB. Variant low byte selects B pattern 0000/8000/1000/0100/ffff; bit 8 writes BLTBDAT after BLTCON1. Each group reports OR of 1024 destination words and words at $10000/$10050/$100a0. Fixed 22-pixel line walk, 0-31 NOP delays, phase NOP/EXG and BLTPRI clear/set. State mask 0x6000; full valid DMACONR mask 0x67ff; beam elapsed uses 227*deltaV+deltaH.')




def _compare_line_logic(pairs):
    """Compare line minterm/BZERO states and destination data by exact setup."""
    minterms=(0x00,0xff,0xca,0xf0)
    b_patterns=(0x0000,0xffff,0x1000)
    pixel_counts=(1,2,22)
    delays=(0,1,2,4,8,16)
    memory_fields=(('destination_or','icr'),('destination_first','irq_beam'),
                   ('destination_10050','irq_level'),('destination_100a0','saved_pc_offset'))
    grouped=collections.defaultdict(dict)
    for key,hw,emu in pairs:
        _,target,variant,phase,delay,repeat=key
        lf=variant&3
        a_index=(variant>>2)&1
        b_index=(variant>>3)&3
        c_full=(variant>>5)&1
        pixel_index=(variant>>6)&3
        if target not in (32,33) or variant & ~0xff or b_index not in range(3) or pixel_index not in range(3):
            raise ValueError(f'Invalid line-logic descriptor {key}')
        if phase not in (0,1) or delay not in delays or repeat!=0:
            raise ValueError(f'Invalid line-logic phase/delay/repeat {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Line-logic launch position differs for {key}')
        group=(target,variant,phase)
        if delay in grouped[group]:
            raise ValueError(f'Duplicate line-logic delay {key}')
        elapsed_hw=_beam_elapsed(hw['launch_beam'],hw['end_beam'])
        elapsed_emu=_beam_elapsed(emu['launch_beam'],emu['end_beam'])
        hw_memory=[hw[f] if f!='saved_pc_offset' else hw[f]>>16 for _,f in memory_fields]
        emu_memory=[emu[f] if f!='saved_pc_offset' else emu[f]>>16 for _,f in memory_fields]
        grouped[group][delay]=dict(
            hardware_dmaconr=hw['counter']&0x67ff, emulator_dmaconr=emu['counter']&0x67ff,
            dmaconr_mismatch=(hw['counter']&0x67ff)!=(emu['counter']&0x67ff),
            hardware_elapsed_cck=elapsed_hw, emulator_elapsed_cck=elapsed_emu,
            elapsed_mismatch=elapsed_hw!=elapsed_emu,
            hardware_memory=hw_memory, emulator_memory=emu_memory,
            memory_mismatch=hw_memory!=emu_memory)
    groups=[]
    for (target,variant,phase),by_delay in sorted(grouped.items()):
        lf=variant&3; a_index=(variant>>2)&1; b_index=(variant>>3)&3
        c_full=(variant>>5)&1; pixel_index=(variant>>6)&3
        traces=[dict(delay=delay,**by_delay[delay]) for delay in delays if delay in by_delay]
        groups.append(dict(target=target,use_b=target==33,variant=variant,
            minterm_index=lf,minterm=minterms[lf],a_data=0x8000 if a_index else 0,
            b_pattern=b_patterns[b_index],initial_c=0xffff if c_full else 0,
            pixels=pixel_counts[pixel_index],phase=phase,phase_pad_cck=2 if phase==0 else 3,
            samples=len(traces),delay_trace=traces,
            dmaconr_mismatches=sum(row['dmaconr_mismatch'] for row in traces),
            elapsed_mismatches=sum(row['elapsed_mismatch'] for row in traces),
            destination_memory_mismatches=sum(row['memory_mismatch'] for row in traces)))
    return dict(kind=25,groups=groups,
        note='Variant packs minterm selector in bits 0-1 (00/ff/ca/f0), A data in bit 2 (0000/8000), B data in bits 3-4 (0000/ffff/1000), initial C data in bit 5 (0000/ffff), and line length in bits 6-7 (1/2/22 pixels). Target 32/33 selects USEB off/on. Delays are 0/1/2/4/8/16 NOPs, phase padding is NOP/EXG, and BLTPRI is off. Comparison covers DMACONR bits 0x67ff, beam elapsed (227*deltaV+deltaH), and destination OR/selected words after BBUSY clears.')


def _compare_line_logic_fine(pairs):
    """Compare the focused 1-CCK line BZERO readback sweep."""
    delays=tuple(range(17))
    memory_fields=(('destination_or','icr'),('destination_first','irq_beam'),
                   ('destination_10050','irq_level'),('destination_100a0','saved_pc_offset'))
    grouped=collections.defaultdict(dict)
    for key,hw,emu in pairs:
        _,target,variant,phase,delay,repeat=key
        if target not in (32,33) or variant not in range(4):
            raise ValueError(f'Invalid fine line-logic descriptor {key}')
        if phase not in (0,1) or delay not in delays or repeat not in (0,4):
            raise ValueError(f'Invalid fine line-logic phase/delay/priority {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Fine line-logic launch position differs for {key}')
        group=(target,variant,phase,repeat)
        if delay in grouped[group]:
            raise ValueError(f'Duplicate fine line-logic delay {key}')
        elapsed_hw=_beam_elapsed(hw['launch_beam'],hw['end_beam'])
        elapsed_emu=_beam_elapsed(emu['launch_beam'],emu['end_beam'])
        hw_memory=[hw[f] if f!='saved_pc_offset' else hw[f]>>16 for _,f in memory_fields]
        emu_memory=[emu[f] if f!='saved_pc_offset' else emu[f]>>16 for _,f in memory_fields]
        grouped[group][delay]=dict(
            hardware_dmaconr=hw['counter']&0x67ff,emulator_dmaconr=emu['counter']&0x67ff,
            dmaconr_mismatch=(hw['counter']&0x67ff)!=(emu['counter']&0x67ff),
            hardware_elapsed_cck=elapsed_hw,emulator_elapsed_cck=elapsed_emu,
            elapsed_mismatch=elapsed_hw!=elapsed_emu,
            hardware_memory=hw_memory,emulator_memory=emu_memory,
            memory_mismatch=hw_memory!=emu_memory)
    groups=[]
    for (target,variant,phase,repeat),by_delay in sorted(grouped.items()):
        traces=[dict(delay=delay,**by_delay[delay]) for delay in delays if delay in by_delay]
        groups.append(dict(target=target,use_b=target==33,b_pattern=0x1000 if variant&1 else 0,
            pixels=22 if variant&2 else 2,variant=variant,phase=phase,
            phase_pad_cck=2 if phase==0 else 3,bltpri_enabled=bool(repeat&4),
            samples=len(traces),delay_trace=traces,
            dmaconr_mismatches=sum(row['dmaconr_mismatch'] for row in traces),
            elapsed_mismatches=sum(row['elapsed_mismatch'] for row in traces),
            destination_memory_mismatches=sum(row['memory_mismatch'] for row in traces)))
    return dict(kind=26,groups=groups,
        note='Fixed line-mode setup: minterm $CA, BLTADAT=$8000, C source/data zero, B data $0000/$1000, USEB off/on, line length 2/22, BLTAPT=-80. Repeat 0/4 selects BLTPRI off/on. Delay is each integer NOP count 0-16, with NOP/EXG phase pads; phase plus delay covers contiguous readback ages. Each trial records full valid DMACONR and beam first, waits for BBUSY, then records destination OR/selected words.')


def _compare_line_logic_followup(pairs):
    """Validate and compare the kind27 line-mode BZERO input matrix."""
    groups=collections.defaultdict(dict)
    for key,hw,emu in pairs:
        _,target,variant,phase,delay,order=key
        b_index=variant&7; a_index=(variant>>3)&3
        if target not in (32,33) or b_index not in range(7) or a_index not in range(3):
            raise ValueError(f'Invalid kind27 descriptor {key}')
        if phase not in (0,1) or delay not in range(5) or order not in (0,1):
            raise ValueError(f'Invalid kind27 phase/delay/BDAT order {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind27 launch position differs for {key}')
        group=(target,variant,phase,order)
        if delay in groups[group]:
            raise ValueError(f'Duplicate kind27 delay {key}')
        elapsed_hw=_beam_elapsed(hw['launch_beam'],hw['end_beam'])
        elapsed_emu=_beam_elapsed(emu['launch_beam'],emu['end_beam'])
        hw_memory=[hw[f] if f!='saved_pc_offset' else hw[f]>>16 for f in ('icr','irq_beam','irq_level','saved_pc_offset')]
        emu_memory=[emu[f] if f!='saved_pc_offset' else emu[f]>>16 for f in ('icr','irq_beam','irq_level','saved_pc_offset')]
        groups[group][delay]=dict(hardware_dmaconr=hw['counter']&0x67ff,
            emulator_dmaconr=emu['counter']&0x67ff,
            dmaconr_mismatch=(hw['counter']&0x67ff)!=(emu['counter']&0x67ff),
            hardware_elapsed_cck=elapsed_hw,emulator_elapsed_cck=elapsed_emu,
            elapsed_mismatch=elapsed_hw!=elapsed_emu,hardware_memory=hw_memory,
            emulator_memory=emu_memory,memory_mismatch=hw_memory!=emu_memory)
    output=[]
    for (target,variant,phase,order),by_delay in sorted(groups.items()):
        traces=[dict(delay=d,**by_delay[d]) for d in range(5) if d in by_delay]
        output.append(dict(target=target,use_b=target==33,variant=variant,
            b_index=variant&7,b_pattern=(0,1,2,4,0x8000,0x1000,0xffff)[variant&7],
            a_pattern=(0,0x8000,0xffff)[(variant>>3)&3],
            c_pattern=0xffff if variant&0x20 else 0,
            pixels=22 if variant&0x40 else 2,phase=phase,
            phase_pad_cck=2 if phase==0 else 3,
            bdat_order='early' if order else 'late',samples=len(traces),delay_trace=traces,
            dmaconr_mismatches=sum(r['dmaconr_mismatch'] for r in traces),
            elapsed_mismatches=sum(r['elapsed_mismatch'] for r in traces),
            destination_memory_mismatches=sum(r['memory_mismatch'] for r in traces)))
    return dict(kind=27,groups=output,
        note='Line-mode BZERO follow-up: minterm $CA, BLTAPT=-80; A=0/$8000/$ffff, C=0/$ffff, B=0/1/2/4/$8000/$1000/$ffff, USEB off/on, 2/22 pixels. Repeat 0/1 loads BLTBDAT late/early while all other blitter registers are initialized directly. Five consecutive NOP delays 0-4 are paired with NOP/EXG phase; capture reads full DMACONR and beam first, then destination OR/selected words after BBUSY clears.')


def compare(hw_folder, emu_folder, expected_emulator_binary=None, expected_emulator_sha256=None):
    provenance = capture_provenance(emu_folder, expected_emulator_binary, expected_emulator_sha256)
    hm, hr = load(hw_folder)
    em, er = load(emu_folder)
    if hm['source_id'] != em['source_id']:
        raise ValueError('Different measured ROMs')
    pairs = _paired_rows(hr, er)
    kinds = {key[0] for key, _, _ in pairs}
    reports = []
    funcs = {18: _compare_cpu, 19: _compare_observers, 20: _compare_div_irq, 21: _compare_aligned, 22: _compare_bzero, 23: _compare_irq_paths, 24: _compare_bzero_line, 25: _compare_line_logic, 26: _compare_line_logic_fine, 27: _compare_line_logic_followup}
    for kind in sorted(kinds):
        if kind not in funcs:
            raise ValueError(f'Unsupported experiment kind {kind}')
        kind_pairs = [p for p in pairs if p[0][0] == kind]
        reports.append(funcs[kind](kind_pairs))
    return dict(hardware=hm, emulator=em, emulator_provenance=provenance, groups=reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hardware', type=Path)
    parser.add_argument('emulator', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--expected-emulator-binary', type=Path)
    parser.add_argument('--expected-emulator-sha256')
    args = parser.parse_args()
    result = json.dumps(compare(args.hardware, args.emulator, args.expected_emulator_binary,
                                args.expected_emulator_sha256), indent=2) + '\n'
    if args.out:
        args.out.write_text(result)
    else:
        print(result, end='')


if __name__ == '__main__':
    main()
