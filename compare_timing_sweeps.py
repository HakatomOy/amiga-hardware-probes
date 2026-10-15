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
import build_rom


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


def _compare_line_pipeline(pairs):
    """Validate kind28's compact preset/delay matrix and retain its raw trace."""
    expected={tuple(row) for row in build_rom.trials(line_pipeline=True)}
    presets=build_rom.line_pipeline_presets()
    seen=set()
    grouped=collections.defaultdict(dict)
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind28 descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind28 descriptor {key}')
        seen.add(key)
        _,preset,variant,phase,delay,repeat=key
        if variant!=0 or repeat!=0 or phase not in (0,1) or delay not in range(17):
            raise ValueError(f'Invalid kind28 phase/delay descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind28 launch position differs for {key}')
        captured=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
            row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
            row['second_counter_or_beam'],row['second_icr_or_level'])
        hmem,emem=captured(hw),captured(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        grouped[(preset,phase)][delay]=dict(
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hmem[2:5]),emulator_dpt_words=list(emem[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hmem[6:]),emulator_cpt_words=list(emem[6:]),
            raw_mismatch=hmem!=emem,elapsed_mismatch=helapsed!=eelapsed)
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind28 descriptor matrix; missing {missing}')
    size_pixels=(1,2,22)
    names=('A','B','C')
    output=[]
    for (index,phase),by_delay in sorted(grouped.items()):
        preset=presets[index]
        trace=[dict(delay=d,**by_delay[d]) for d in range(17)]
        output.append(dict(preset=index,phase=phase,phase_pad='NOP' if phase==0 else 'EXG',
            a_data=f'0x{preset["a_word"]:04x}',a_shift=preset['ashift'],
            b_texture=f'0x{preset["b_word"]:04x}',b_shift=preset['bshift'],
            c_data=f'0x{preset["c_word"]:04x}',
            minterm=f'0x{preset["minterm_word"]:02x}',
            useabc=[name for bit,name in ((0,'A'),(1,'B'),(2,'C')) if preset['use']&(1<<bit)],
            used=bool(preset['used']),sing=bool(preset['sing']),sign=bool(preset['sign']),
            initial_error=preset['bltapt'],size_pixels=size_pixels[preset['size']],
            bltcon0=f'0x{preset["bltcon0"]:04x}',bltcon1=f'0x{preset["bltcon1"]:04x}',
            bltapt=preset['bltapt'],bltsize=f'0x{preset["bltsize"]:04x}',
            bdat_preseed_order='0_then_ffff' if preset['seed_order'] else 'ffff_then_0',
            samples=len(trace),delay_trace=trace,
            raw_mismatches=sum(row['raw_mismatch'] for row in trace),
            elapsed_mismatches=sum(row['elapsed_mismatch'] for row in trace)))
    return dict(kind=28,groups=output,
        note='Each preset carries raw DMACONR in counter, post-first-read beam in end_beam, DPT OR/words in icr/irq_beam/irq_level/saved_pc_hi, and CPT OR/words in aux/pc_lo/second_counter_or_beam/second_icr_or_level. Delay is 0-16 NOPs; phase selects NOP/EXG. The complete preset catalog is required at both phases and every delay.')


def _compare_line_truth_table(pairs):
    """Validate kind29's complete 8-bit line minterm truth-table sweep."""
    expected={tuple(row) for row in build_rom.trials(line_truth_table=True)}
    profiles=build_rom.line_truth_profiles()
    seen=set()
    grouped=collections.defaultdict(dict)
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind29 descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind29 descriptor {key}')
        seen.add(key)
        _,target,minterm,phase,delay,repeat=key
        if not 0<=minterm<=0xff or phase!=0 or delay!=16 or repeat!=0:
            raise ValueError(f'Invalid kind29 minterm/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind29 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        grouped[target][minterm]=dict(
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed)
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind29 descriptor matrix; missing {missing}')
    output=[]
    for target,by_minterm in sorted(grouped.items()):
        profile=profiles[target]
        trace=[dict(minterm=f'0x{m:02x}',**by_minterm[m]) for m in range(256)]
        output.append(dict(target=target,profile=profile['profile'],size_pixels=(1,2)[profile['size']],
            bltcon0=f'0x{profile["bltcon0"]:04x}',bltcon1=f'0x{profile["bltcon1"]:04x}',
            bltapt=profile['bltapt'],bltsize=f'0x{profile["bltsize"]:04x}',
            a_data=f'0x{profile["a"]:04x}',b_data=f'0x{profile["b"]:04x}',
            c_data=f'0x{profile["c"]:04x}',samples=len(trace),minterm_trace=trace,
            raw_mismatches=sum(row['raw_mismatch'] for row in trace),
            elapsed_mismatches=sum(row['elapsed_mismatch'] for row in trace)))
    return dict(kind=29,groups=output,
        note='Every raw 8-bit minterm is tested for five A/B/C profiles at 1 and 2 pixels. Each record retains DMACONR/beam plus raw DPT and CPT OR/selected-word observations from the kind28 dual-memory observer.')


def _compare_line_stage(pairs):
    """Validate kind30 C-stage predicate sweep and preserve both memory paths."""
    expected={tuple(row) for row in build_rom.trials(line_stage=True)}
    profiles=build_rom.line_stage_profiles()
    minterms=(0x04,0x08,0x40,0x80,0x48)
    seen=set()
    grouped=collections.defaultdict(dict)
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind30 descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind30 descriptor {key}')
        seen.add(key)
        _,target,minterm,phase,delay,repeat=key
        if minterm not in minterms or phase not in (0,1) or delay not in range(17) or repeat!=0:
            raise ValueError(f'Invalid kind30 stage/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind30 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        grouped[(target,minterm,phase)][delay]=dict(
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed)
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind30 descriptor matrix; missing {missing}')
    output=[]
    for (target,minterm,phase),by_delay in sorted(grouped.items()):
        profile=profiles[target]
        trace=[dict(delay=d,**by_delay[d]) for d in range(17)]
        output.append(dict(target=target,profile=profile['profile'],
            c_first=f'0x{profile["c_first"]:04x}',c_second=f'0x{profile["c_second"]:04x}',
            useb=bool(profile['useb']),a_data=f'0x{profile["a_data"]:04x}',
            b_data=f'0x{profile["b_data"]:04x}',c_data=f'0x{profile["c_data"]:04x}',
            minterm=f'0x{minterm:02x}',phase=phase,phase_pad='NOP' if phase==0 else 'EXG',
            bltcon0=f'0x{profile["bltcon0"]|minterm:04x}',bltcon1=f'0x{profile["bltcon1"]:04x}',
            bltapt=profile['bltapt'],bltsize=f'0x{profile["bltsize"]:04x}',
            samples=len(trace),delay_trace=trace,
            raw_mismatches=sum(row['raw_mismatch'] for row in trace),
            elapsed_mismatches=sum(row['elapsed_mismatch'] for row in trace)))
    return dict(kind=30,groups=output,
        note='Kind30 holds A=$8000, B data and C data registers at zero, and writes profile C words at source addresses $11000 and $11050. Presets cross first/second C words with USEB off/on; each minterm and phase is sampled at all delays 0-16. DPT/CPT raw ORs and selected words are retained.')


def _compare_line_b_hold(pairs,useb):
    """Validate one kind31/32 USEB half of the hidden B matrix."""
    kind=32 if useb else 31
    expected={tuple(row) for row in build_rom.trials(line_b_hold_dma=bool(useb),line_b_hold=not useb)}
    presets=build_rom.line_b_hold_presets(useb)
    variants=build_rom.line_b_hold_variants()
    delays=(0,1,2,4,16)
    seen=set()
    grouped=collections.defaultdict(dict)
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind{kind} descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind{kind} descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if variant not in (0,1) or phase!=1 or delay not in delays or repeat!=0:
            raise ValueError(f'Invalid kind{kind} variant/phase/delay descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind{kind} launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        grouped[(target,variant)][delay]=dict(
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed)
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind{kind} descriptor matrix; missing {missing}')
    output=[]
    for (target,variant_index),by_delay in sorted(grouped.items()):
        preset=presets[target]
        variant=variants[variant_index]
        bltcon0=variant['bltcon0']|(0x0400 if preset['useb'] else 0)
        trace=[dict(delay=d,**by_delay[d]) for d in delays]
        output.append(dict(target=target,texture=preset['texture'],
            b_word=f'0x{preset["b_word"]:04x}',bshift=preset['bshift'],useb=bool(preset['useb']),
            a_data=f'0x{variant["a_data"]:04x}',c_data='0x0000',minterm=f'0x{variant["minterm"]:02x}',
            variant=variant['name'],phase=1,phase_pad='EXG',bltcon0=f'0x{bltcon0:04x}',
            bltcon1=f'0x{preset["bltcon1"]:04x}',bdat_order=preset['bdat_order'],
            bltapt=preset['bltapt'],
            bltsize=f'0x{preset["bltsize"]:04x}',samples=len(trace),delay_trace=trace,
            raw_mismatches=sum(row['raw_mismatch'] for row in trace),
            elapsed_mismatches=sum(row['elapsed_mismatch'] for row in trace)))
    return dict(kind=kind,groups=output,
        note=f'Kind{kind} crosses all 16 B shifts with zero, each one-hot B texture bit and $ffff, USEB={useb}, and two discriminator variants: A=0/LF=$CC and A=$8000/LF=$CA. Selected B patterns also compare BDAT written before target BSHIFT (after setting BSHIFT=0) against BDAT written after target BSHIFT. Phase is EXG; delays are 0,1,2,4,16. The manifest records literal preset and variant register words, and each group preserves DPT/CPT raw traces.')


def _compare_line_b_mask(pairs):
    """Strictly validate kind33's A/B shift and line-length matrix."""
    expected={tuple(row) for row in build_rom.trials(line_b_mask=True)}
    presets=build_rom.line_b_mask_presets()
    seen=set()
    output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind33 descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind33 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if variant!=0 or phase!=1 or delay!=16 or repeat!=0:
            raise ValueError(f'Invalid kind33 observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind33 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        preset=presets[target]
        output.append(dict(target=target,a_shift=preset['ashift'],b_shift=preset['bshift'],
            a_data=f'0x{preset["a_word"]:04x}',b_texture=f'0x{preset["b_word"]:04x}',
            c_data=f'0x{preset["c_word"]:04x}',useabc=[name for bit,name in ((0,'A'),(1,'B'),(2,'C')) if preset['use']&(1<<bit)],
            used=bool(preset['used']),minterm=f'0x{preset["minterm_word"]:02x}',
            size_pixels=(1,2)[preset['size']],phase=phase,phase_pad='EXG',delay=delay,
            bltcon0=f'0x{preset["bltcon0"]:04x}',bltcon1=f'0x{preset["bltcon1"]:04x}',
            bltapt=preset['bltapt'],bltsize=f'0x{preset["bltsize"]:04x}',
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind33 descriptor matrix; missing {missing}')
    return dict(kind=33,groups=sorted(output,key=lambda row:row['target']),
        note='Kind33 fixes A=$8000, B=C=0, LF=$CA and crosses ASHIFT 0-15, BSHIFT 0-15, USEB off/on and 1/2-pixel lines. One EXG-phase, delay-16 observer sample is recorded for each configuration.')


def _compare_line_b_prime(pairs):
    """Validate kind34's normal-B priming modes before line operation."""
    expected={tuple(row) for row in build_rom.trials(line_b_prime=True)}
    presets=build_rom.line_b_prime_presets()
    modes=build_rom.line_b_prime_modes()
    seen=set()
    output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind34 descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind34 descriptor {key}')
        seen.add(key)
        _,target,prime,phase,delay,repeat=key
        if prime not in range(4) or phase!=1 or delay!=16 or repeat!=0:
            raise ValueError(f'Invalid kind34 prime/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind34 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        preset=presets[target]
        output.append(dict(target=target,prime=prime,prime_mode=modes[prime],
            a_shift=preset['ashift'],b_shift=preset['bshift'],useb=bool(preset['use']&2),
            size_pixels=(1,2)[preset['size']],a_data=f'0x{preset["a_word"]:04x}',
            b_texture=f'0x{preset["b_word"]:04x}',c_data=f'0x{preset["c_word"]:04x}',
            minterm=f'0x{preset["minterm_word"]:02x}',bltcon0=f'0x{preset["bltcon0"]:04x}',
            bltcon1=f'0x{preset["bltcon1"]:04x}',bltapt=preset['bltapt'],
            bltsize=f'0x{preset["bltsize"]:04x}',phase=phase,phase_pad='EXG',delay=delay,
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind34 descriptor matrix; missing {missing}')
    return dict(kind=34,groups=sorted(output,key=lambda row:(row['target'],row['prime'])),
        note='Kind34 crosses ASHIFT0-15, BSHIFT0/1/8/15, USEB off/on, line size1/2 and four normal-B priming modes. It records one EXG-phase delay16 sample per full descriptor and retains both DPT/CPT readbacks.')


def _compare_line_word_control(pairs):
    """Validate kind35's equal-cycle instruction-word observer matrix."""
    expected={tuple(row) for row in build_rom.trials(line_word_control=True)}
    presets=build_rom.line_word_control_presets()
    variants=build_rom.line_word_control_variants()
    delays={item['delay']:item for item in build_rom.line_word_control_delays()}
    seen=set()
    output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected:
            raise ValueError(f'Invalid kind35 descriptor {key}')
        if key in seen:
            raise ValueError(f'Duplicate kind35 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if variant not in range(3) or phase!=0 or delay not in delays or repeat!=0:
            raise ValueError(f'Invalid kind35 instruction/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind35 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        preset=presets[target]
        instruction=variants[variant]
        output.append(dict(target=target,profile=preset['profile'],variant=variant,
            instruction=instruction,phase=phase,delay=delay,delay_slot=delays[delay]['observer_slot'],
            equal_cpu_cycles=instruction['cpu_cycles'],equal_cck_cycles=instruction['cck_cycles'],
            a_data=f'0x{preset["a_word"]:04x}',a_shift=preset['ashift'],
            b_texture=f'0x{preset["b_word"]:04x}',b_shift=preset['bshift'],
            c_data=f'0x{preset["c_word"]:04x}',useb=bool(preset['use']&2),
            minterm=f'0x{preset["minterm_word"]:02x}',bltcon0=f'0x{preset["bltcon0"]:04x}',
            bltcon1=f'0x{preset["bltcon1"]:04x}',bltapt=preset['bltapt'],
            bltsize=f'0x{preset["bltsize"]:04x}',
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        missing=sorted(expected-seen)[:3]
        raise ValueError(f'Incomplete kind35 descriptor matrix; missing {missing}')
    return dict(kind=35,groups=sorted(output,key=lambda row:(row['target'],row['variant'],row['delay'])),
        note='Kind35 crosses four A/LF profiles, BSHIFT0-15, USEB off/on, three equal-four-cycle one-word opcodes, and delays0/1/2/4/16. All rows use the phase-zero private observer and retain DPT/CPT readbacks.')


def _compare_line_shift_truth(pairs):
    """Strictly compare kind36's shifted-B full truth-table closure."""
    expected={tuple(row) for row in build_rom.trials(line_shift_truth=True)}
    profiles=build_rom.line_shift_truth_profiles()
    seen=set(); output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind36 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind36 descriptor {key}')
        seen.add(key)
        _,target,minterm,phase,delay,repeat=key
        if target not in range(len(profiles)) or minterm not in range(256) or phase!=1 or delay!=16 or repeat!=0:
            raise ValueError(f'Invalid kind36 profile/minterm/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind36 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        profile=profiles[target]
        output.append(dict(target=target,profile=profile['profile'],minterm=minterm,
            phase=phase,delay=delay,a_data=f"0x{profile['a']:04x}",
            b_data=f"0x{profile['b']:04x}",c_data=f"0x{profile['c']:04x}",
            b_shift=profile['bshift'],size=profile['size'],useb=False,
            bltcon0=f"0x{(profile['bltcon0']|minterm):04x}",
            bltcon1=f"0x{profile['bltcon1']:04x}",bltsize=f"0x{profile['bltsize']:04x}",
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        raise ValueError(f'Incomplete kind36 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=36,groups=sorted(output,key=lambda row:(row['target'],row['minterm'])),
        note='Kind36 measures all 256 raw minterms for 15 A/C/BSH two-pixel profiles plus a one-pixel control, with USEB off and the phase-one delay-16 observer.')


def _compare_line_wrap(pairs):
    """Validate kind37's line-length/counter-wrap descriptors and traces."""
    expected={tuple(row) for row in build_rom.trials(line_wrap=True)}
    presets=build_rom.line_wrap_presets(); seen=set(); output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind37 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind37 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if target not in range(len(presets)) or (variant,phase,delay,repeat)!=(0,0,96,0):
            raise ValueError(f'Invalid kind37 preset/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind37 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        preset=presets[target]
        output.append(dict(target=target,profile=preset['profile'],pixels=preset['pixels'],
            a_data=f"0x{preset['a_data']:04x}",b_data=f"0x{preset['b_data']:04x}",
            c_data=f"0x{preset['c_data']:04x}",b_shift=preset['bshift'],useb=bool(preset['useb']),
            minterm=f"0x{preset['minterm']:02x}",bltcon0=f"0x{preset['bltcon0']:04x}",
            bltcon1=f"0x{preset['bltcon1']:04x}",bltapt=preset['bltapt'],
            bltsize=f"0x{preset['bltsize']:04x}",phase=phase,delay=delay,
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        raise ValueError(f'Incomplete kind37 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=37,groups=sorted(output,key=lambda row:row['target']),
        note='Kind37 maps completed line lengths1-18 across BSHIFT0-15, USEB off/on and A=0/LF=CC or A=8000/LF=CA, sampled at phase0 after 96 NOPs.')


def _compare_line_c_cross(pairs):
    """Validate kind38's C-data/USEC controls under B-only LF=CC."""
    expected={tuple(row) for row in build_rom.trials(line_c_cross=True)}
    presets=build_rom.line_c_cross_presets(); seen=set(); output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind38 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind38 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if target not in range(len(presets)) or (variant,phase,delay,repeat)!=(0,1,16,0):
            raise ValueError(f'Invalid kind38 profile/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind38 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        preset=presets[target]
        output.append(dict(target=target,c_pattern=preset['c_pattern'],
            a_data=f"0x{preset['a_data']:04x}",b_data=f"0x{preset['b_data']:04x}",
            c_data=f"0x{preset['c_data']:04x}",b_shift=preset['bshift'],
            useb=bool(preset['useb']),usec=bool(preset['usec']),pixels=preset['pixels'],
            minterm=f"0x{preset['minterm']:02x}",bltcon0=f"0x{preset['bltcon0']:04x}",
            bltcon1=f"0x{preset['bltcon1']:04x}",bltapt=preset['bltapt'],
            bltsize=f"0x{preset['bltsize']:04x}",phase=phase,delay=delay,
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        raise ValueError(f'Incomplete kind38 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=38,groups=sorted(output,key=lambda row:row['target']),
        note='Kind38 crosses A=0/8000 and C=0/ffff/8000/0001/5555/aaaa, USEB/USEC off/on, BSHIFT0-15 and 1/2-pixel lines under LF=CC, sampled at phase1/delay16.')


def _compare_line_c_words(pairs):
    """Validate kind39 one-hot C-memory words separately from BLTCDAT."""
    expected={tuple(row) for row in build_rom.trials(line_c_words=True)}
    presets=build_rom.line_c_word_presets(); seen=set(); output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind39 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind39 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if target not in range(len(presets)) or (variant,phase,delay,repeat)!=(0,1,16,0):
            raise ValueError(f'Invalid kind39 profile/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind39 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        helapsed=_beam_elapsed(hw['launch_beam'],hw['end_beam'],False)
        eelapsed=_beam_elapsed(emu['launch_beam'],emu['end_beam'],False)
        preset=presets[target]
        output.append(dict(target=target,profile=preset['profile'],
            c_first=f"0x{preset['c_first']:04x}",c_second=f"0x{preset['c_second']:04x}",
            c_data=f"0x{preset['c_data']:04x}",b_shift=preset['bshift'],
            useb=bool(preset['useb']),usec=bool(preset['usec']),pixels=preset['pixels'],
            minterm=f"0x{preset['minterm']:02x}",bltcon0=f"0x{preset['bltcon0']:04x}",
            bltcon1=f"0x{preset['bltcon1']:04x}",bltapt=preset['bltapt'],
            bltsize=f"0x{preset['bltsize']:04x}",phase=phase,delay=delay,
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_elapsed_cck=helapsed,emulator_elapsed_cck=eelapsed,
            hardware_dpt_or=hw['icr'],emulator_dpt_or=emu['icr'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_or=hw['aux'],emulator_cpt_or=emu['aux'],
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw,elapsed_mismatch=helapsed!=eelapsed))
    if seen!=expected:
        raise ValueError(f'Incomplete kind39 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=39,groups=sorted(output,key=lambda row:row['target']),
        note='Kind39 crosses isolated first/second C-memory words and independent BLTCDAT seeds at BSHIFT4 under LF=CC, with USEB/USEC controls and 1/2-pixel lines; observer phase1/delay16.')


def _compare_line_c_tomography(pairs):
    shifts={key[2] for key,_,_ in pairs}
    if len(shifts)!=1 or not 0<=next(iter(shifts),-1)<=15:
        raise ValueError('Invalid kind40 BSHIFT descriptor set')
    shift=next(iter(shifts))
    expected={tuple(row) for row in build_rom.trials(line_c_tomography=True,
        line_c_tomography_shift=shift)}
    presets=build_rom.line_c_tomography_presets(shift);seen=set();output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind40 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind40 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if target not in range(len(presets)) or variant!=shift or (phase,delay,repeat)!=(1,16,0):
            raise ValueError(f'Invalid kind40 profile/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind40 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        preset=presets[target]
        output.append(dict(target=target,profile=preset['profile'],a_data=f"0x{preset['a_data']:04x}",
            ashift=preset['ashift'],b_data=f"0x{preset['b_data']:04x}",bshift=shift,
            c_first=f"0x{preset['c_first']:04x}",c_second=f"0x{preset['c_second']:04x}",
            c_data=f"0x{preset['c_data']:04x}",useb=bool(preset['useb']),usec=bool(preset['usec']),
            pixels=preset['pixels'],bltcon0=f"0x{preset['bltcon0']:04x}",
            bltcon1=f"0x{preset['bltcon1']:04x}",bltsize=f"0x{preset['bltsize']:04x}",
            phase=phase,delay=delay,hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw))
    if seen!=expected:
        raise ValueError(f'Incomplete kind40 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=40,bshift=shift,groups=sorted(output,key=lambda row:row['target']),
        note=f'Kind40 varies first C word and all A shifts under LF=C0, fixed A data 8000, B=0, BSHIFT{shift}; second C word and C data are zero. Includes full USEB/USEC controls on zero/full-word patterns.')


def _compare_line_c_onset(pairs):
    shifts={key[2] for key,_,_ in pairs}
    if len(shifts)!=1 or not 0<=next(iter(shifts),-1)<=15:
        raise ValueError('Invalid kind41 BSHIFT descriptor set')
    shift=next(iter(shifts))
    expected={tuple(row) for row in build_rom.trials(line_c_onset=True,
        line_c_onset_shift=shift)}
    presets=build_rom.line_c_onset_presets(shift);seen=set();output=[]
    capture=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['aux'],row['saved_pc_offset']&0xffff,
        row['second_counter_or_beam'],row['second_icr_or_level'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind41 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind41 descriptor {key}')
        seen.add(key)
        _,target,variant,phase,delay,repeat=key
        if target not in range(len(presets)) or variant!=shift or phase not in (0,1) or delay not in range(17) or repeat!=0:
            raise ValueError(f'Invalid kind41 profile/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind41 launch position differs for {key}')
        hraw,eraw=capture(hw),capture(emu)
        preset=presets[target]
        output.append(dict(target=target,profile=preset['profile'],
            a_data=f"0x{preset['a_data']:04x}",b_data=f"0x{preset['b_data']:04x}",
            bshift=shift,ashift=preset['ashift'],c_first=f"0x{preset['c_first']:04x}",
            c_second=f"0x{preset['c_second']:04x}",cdat=f"0x{preset['cdat']:04x}",
            minterm=f"0x{preset['minterm']:02x}",usea=bool(preset['usea']),
            useb=bool(preset['useb']),usec=bool(preset['usec']),used=bool(preset['used']),
            pixels=preset['pixels'],bltcon0=f"0x{preset['bltcon0']:04x}",
            bltcon1=f"0x{preset['bltcon1']:04x}",bltsize=f"0x{preset['bltsize']:04x}",
            phase=phase,delay=delay,observer_address=0xff0000+(phase<<13)+(delay<<8),
            hardware_counter=hw['counter'],emulator_counter=emu['counter'],
            hardware_bzero=bool(hw['counter']&0x2000),emulator_bzero=bool(emu['counter']&0x2000),
            hardware_end_beam=hw['end_beam'],emulator_end_beam=emu['end_beam'],
            hardware_dpt_words=list(hraw[2:5]),emulator_dpt_words=list(eraw[2:5]),
            hardware_cpt_words=list(hraw[6:]),emulator_cpt_words=list(eraw[6:]),
            raw_mismatch=hraw!=eraw))
    if seen!=expected:
        raise ValueError(f'Incomplete kind41 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=41,bshift=shift,groups=sorted(output,key=lambda row:row['target']),
        note=f'Kind41 maps BZERO onset over phase and delay for zero/full/one-cold first C words and A data 0000/8000; B=0, BSHIFT{shift}, C second word and CDAT zero.')


def _compare_line_c_read_sequence(pairs):
    expected={tuple(row) for row in build_rom.trials(line_c_read_sequence=True)}
    presets=build_rom.line_c_read_sequence_presets();seen=set();output=[]
    samples=lambda row:(row['counter'],row['icr'],row['irq_beam'],row['irq_level'],
        row['saved_pc_offset']>>16,row['saved_pc_offset']&0xffff,row['status'],row['aux'])
    for key,hw,emu in pairs:
        if key not in expected: raise ValueError(f'Invalid kind42 descriptor {key}')
        if key in seen: raise ValueError(f'Duplicate kind42 descriptor {key}')
        seen.add(key)
        _,target,observer,phase,delay,repeat=key
        if target not in range(len(presets)) or observer not in (0,1) or (phase,delay)!=(0,0) or repeat not in range(8):
            raise ValueError(f'Invalid kind42 profile/observer descriptor {key}')
        if hw['launch_beam']!=emu['launch_beam']:
            raise ValueError(f'Kind42 launch position differs for {key}')
        preset=presets[target]
        hseq,eseq=samples(hw),samples(emu)
        output.append(dict(target=target,repeat=repeat,observer=('early','postbusy')[observer],
            profile=preset['profile'],a_data=f"0x{preset['a_data']:04x}",
            c_first=f"0x{preset['c_first']:04x}",bshift=4,minterm='0xcc',
            pixels=2,launch_beam=hw['launch_beam'],end_beam=hw['end_beam'],
            presample_beam=hw['second_counter_or_beam'],postbusy_beam=hw['second_icr_or_level'],
            hardware_samples=list(hseq),emulator_samples=list(eseq),
            hardware_sample6_bzero=bool(hseq[6]&0x2000),
            emulator_sample6_bzero=bool(eseq[6]&0x2000),
            raw_mismatch=(hseq!=eseq or hw['launch_beam']!=emu['launch_beam'] or
                hw['end_beam']!=emu['end_beam'] or
                hw['second_counter_or_beam']!=emu['second_counter_or_beam'] or
                hw['second_icr_or_level']!=emu['second_icr_or_level'])))
    if seen!=expected:
        raise ValueError(f'Incomplete kind42 descriptor matrix; missing {sorted(expected-seen)[:3]}')
    return dict(kind=42,groups=sorted(output,key=lambda row:(row['target'],row['observer'],row['repeat'])),
        record_layout=dict(launch_beam=12,samples_offset=20,sample_count=8,sample6_offset32=32,
            presample_beam=36,postread_beam=16,postbusy_beam=38),
        note='Kind42 reads DMACONR eight times consecutively inside one blit; early and post-BBUSY observer slots are repeated eight times per preset.')


def compare(hw_folder, emu_folder, expected_emulator_binary=None, expected_emulator_sha256=None):
    provenance = capture_provenance(emu_folder, expected_emulator_binary, expected_emulator_sha256)
    hm, hr = load(hw_folder)
    em, er = load(emu_folder)
    if hm['source_id'] != em['source_id']:
        raise ValueError('Different measured ROMs')
    pairs = _paired_rows(hr, er)
    kinds = {key[0] for key, _, _ in pairs}
    reports = []
    funcs = {18: _compare_cpu, 19: _compare_observers, 20: _compare_div_irq, 21: _compare_aligned, 22: _compare_bzero, 23: _compare_irq_paths, 24: _compare_bzero_line, 25: _compare_line_logic, 26: _compare_line_logic_fine, 27: _compare_line_logic_followup, 28: _compare_line_pipeline, 29: _compare_line_truth_table, 30: _compare_line_stage, 31: lambda rows: _compare_line_b_hold(rows,0), 32: lambda rows: _compare_line_b_hold(rows,1), 33: _compare_line_b_mask, 34: _compare_line_b_prime, 35: _compare_line_word_control, 36: _compare_line_shift_truth, 37: _compare_line_wrap, 38: _compare_line_c_cross, 39: _compare_line_c_words, 40: _compare_line_c_tomography, 41: _compare_line_c_onset, 42: _compare_line_c_read_sequence}
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
