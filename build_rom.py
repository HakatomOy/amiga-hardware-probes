#!/usr/bin/env python3
"""Build the standalone 68000 measurement ROM, with pinned RBCP sources."""
import argparse, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def line_pipeline_presets():
    """Controlled kind28 presets; each entry changes one baseline axis.

    The 24 core controls cross A=0/$8000, minterm CA/CC, USEB off/on and
    size 1/2/22. Remaining rows vary one register input from the baseline.
    A few B=0 controls repeat with reversed BLTBDAT preseed order.
    """
    base=dict(a=1,ashift=0,b=0,bshift=0,c=0,minterm=2,use=5,used=1,
              sing=0,sign=0,error=0,size=1)
    rows=[]
    for a in (0,1):
        for minterm in (2,4):
            for use in (5,7):
                for size in range(3):
                    rows.append(dict(base,a=a,minterm=minterm,use=use,size=size))
    for field,values in (
        ('a',range(4)),('ashift',(1,8,15)),('b',range(1,6)),
        ('bshift',(1,8,15)),('c',range(1,4)),('minterm',range(9)),
        ('use',range(8)),('used',(0,)),('sing',(1,)),('sign',(1,)),
        ('error',range(1,4))):
        for value in values:
            candidate=dict(base,**{field:value})
            if candidate not in rows:
                rows.append(candidate)
    # B-shift controls need actual nonzero source bits. These cross low-bit,
    # high-bit and $1000 textures with each tested shift and USEB state.
    for b in (1,3,4):
        for bshift in (0,1,8,15):
            for use in (5,7):
                candidate=dict(base,b=b,bshift=bshift,use=use)
                if candidate not in rows:
                    rows.append(candidate)
    # A=1 with shifts 1/15 exposes low-bit-to-high-bit shifter movement.
    for ashift in (1,15):
        candidate=dict(base,a=2,ashift=ashift)
        if candidate not in rows:
            rows.append(candidate)
    candidate=dict(base,sing=1,sign=1,error=0)
    if candidate not in rows:
        rows.append(candidate)
    # Paired order controls retain the same B=0 input while changing only the
    # two explicit BLTBDAT preseed writes.
    duplicate_keys=(
        dict(a=1,minterm=2,use=5,size=1), dict(a=0,minterm=2,use=5,size=1),
        dict(a=1,minterm=4,use=5,size=1), dict(a=0,minterm=4,use=5,size=1),
        dict(a=1,minterm=2,use=7,size=1), dict(a=1,minterm=2,use=5,size=0),
        dict(a=1,minterm=2,use=5,size=2))
    presets=[dict(row,seed_order=0) for row in rows]
    for key in duplicate_keys:
        match=next(row for row in rows if all(row[k]==v for k,v in key.items()))
        presets.append(dict(match,seed_order=1))
    minterms=(0x00,0xff,0xca,0xf0,0xcc,0xaa,0x3c,0x5a,0x0f)
    a_patterns=(0,0x8000,0x0001,0xffff)
    b_patterns=(0,0x0001,0x0002,0x8000,0x1000,0xffff)
    c_patterns=(0,0xffff,0x8000,0xaaaa)
    for index,preset in enumerate(presets):
        size_word=(0x0042,0x0082,0x0582)[preset['size']]
        use_hw=((preset['use']&1)<<11)|((preset['use']&2)<<9)|((preset['use']&4)<<7)
        bltcon0=(preset['ashift']<<12)|use_hw|(preset['used']<<8)|minterms[preset['minterm']]
        bltcon1=1|(preset['sing']<<1)|(preset['sign']<<6)|(preset['bshift']<<12)
        preset.update(index=index,a_word=a_patterns[preset['a']],b_word=b_patterns[preset['b']],
                       c_word=c_patterns[preset['c']],minterm_word=minterms[preset['minterm']],
                       bltcon0=bltcon0,bltcon1=bltcon1,
                       bltapt=(-80,-1,0,80)[preset['error']],bltsize=size_word)
    return presets


def line_truth_profiles():
    """Five kind29 input profiles, each recorded at 1- and 2-pixel sizes."""
    profiles=(('zero',0,0,0),('a_first',0x8000,0,0),
              ('b_full',0x8000,0xffff,0),('c_full',0x8000,0,0xffff),
              ('a_zero_c_full',0,0,0xffff))
    return [dict(index=profile_index*2+size,profile=name,a=a,b=b,c=c,size=size,
             bltcon0=0x0b00,bltcon1=1,bltapt=-80,bltsize=(0x0042,0x0082)[size])
        for profile_index,(name,a,b,c) in enumerate(profiles) for size in (0,1)]


def line_shift_truth_profiles():
    """Kind36 full minterm truth closure across selected BSHIFT states."""
    rows=[]
    profiles=(('A0_C0_BSH0_2px',0,0,0,0,1),
        ('A0_C0_BSH1_2px',0,0,0,1,1),
        ('A0_C0_BSH4_2px',0,0,0,4,1),
        ('A0_C0_BSH8_2px',0,0,0,8,1),
        ('A0_C0_BSH15_2px',0,0,0,15,1),
        ('A8000_C0_BSH0_2px',0x8000,0,0,0,1),
        ('A8000_C0_BSH1_2px',0x8000,0,0,1,1),
        ('A8000_C0_BSH4_2px',0x8000,0,0,4,1),
        ('A8000_C0_BSH8_2px',0x8000,0,0,8,1),
        ('A8000_C0_BSH15_2px',0x8000,0,0,15,1),
        ('A8000_Cffff_BSH0_2px',0x8000,0,0xffff,0,1),
        ('A8000_Cffff_BSH1_2px',0x8000,0,0xffff,1,1),
        ('A8000_Cffff_BSH4_2px',0x8000,0,0xffff,4,1),
        ('A8000_Cffff_BSH8_2px',0x8000,0,0xffff,8,1),
        ('A8000_Cffff_BSH15_2px',0x8000,0,0xffff,15,1),
        ('A0_C0_BSH8_1px_control',0,0,0,8,0))
    for index,(name,a,b,c,bshift,two_pixels) in enumerate(profiles):
        rows.append(dict(index=index,profile=name,a=a,b=b,c=c,bshift=bshift,
            size=int(two_pixels),ashift=0,useb=0,bltcon0=0x0b00,
            bltcon1=(bshift<<12)|1,bltapt=-80,
            bltsize=0x0082 if two_pixels else 0x0042))
    return rows


def line_wrap_presets():
    """Kind37 line lengths across BSHIFT, USEB and two LF/A controls."""
    profiles=(('A0_CC',0,0xcc),('A8000_CA',0x8000,0xca))
    presets=[]
    for bshift in range(16):
        for pixels in range(1,19):
            for useb in (0,1):
                for profile,a,minterm in profiles:
                    use=5|(useb<<1)
                    use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)
                    bltcon0=use_hw|0x0100|minterm
                    presets.append(dict(index=len(presets),profile=profile,a_data=a,
                        b_data=0,c_data=0,pixels=pixels,bshift=bshift,useb=useb,
                        ashift=0,minterm=minterm,bltsize=(pixels<<6)|2,
                        bltcon1=(bshift<<12)|1,bltcon0=bltcon0,bltapt=-80))
    return presets


def line_c_cross_presets():
    """Kind38 isolates C dependence under the B-only CC minterm."""
    presets=[]
    c_patterns=(('zero',0x0000),('ones',0xffff),('first',0x8000),
        ('last',0x0001),('alternating_5',0x5555),('alternating_a',0xaaaa))
    for adata in (0x0000,0x8000):
        for bshift in range(16):
            for cname,cdata in c_patterns:
                for useb in (0,1):
                    for usec in (0,1):
                        for pixels in (1,2):
                            use=1|8|(useb<<1)|(usec<<2) # A and D always enabled
                            use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)|((use&8)<<5)
                            bltcon0=use_hw|0x0100|0xcc
                            presets.append(dict(index=len(presets),a_data=adata,b_data=0,
                                c_data=cdata,c_pattern=cname,adata=adata,bshift=bshift,usea=1,useb=useb,
                                usec=usec,used=1,ashift=0,minterm=0xcc,pixels=pixels,
                                bltsize=(pixels<<6)|2,bltcon1=(bshift<<12)|1,
                                bltcon0=bltcon0,bltapt=-80))
    return presets


def line_stage_profiles():
    """Kind30 pairs of first/second C words crossed with USEB off/on."""
    source_profiles=(('zero_zero',0x0000,0x0000),('zero_full',0x0000,0xffff),
        ('full_zero',0xffff,0x0000),('first_8000',0x8000,0x0000),
        ('first_4000',0x4000,0x0000),('both_8000',0x8000,0x8000),
        ('second_8000',0x0000,0x8000))
    return [dict(index=source_index*2+useb,profile=name,c_first=c1,c_second=c2,
        useb=useb,bltcon0=0x0b00|(0x0400 if useb else 0),bltcon1=1,
        a_data=0x8000,b_data=0,c_data=0,bltapt=-80,bltsize=0x0082)
        for source_index,(name,c1,c2) in enumerate(source_profiles) for useb in (0,1)]


def line_b_hold_presets(useb):
    """Kind31 textures/shifts plus selected early-vs-late BDAT controls."""
    textures=[('zero',0)]+[(f'bit{bit}',1<<bit) for bit in range(16)]+[('ones',0xffff)]
    presets=[dict(index=texture_index*16+shift,
        texture=name,b_word=word,bshift=shift,useb=useb,
        bltcon0=0x0bcc|(0x0400 if useb else 0),bltcon1=0x0001|(shift<<12),
        a_data=0,c_data=0,minterm=0xcc,bltapt=-80,bltsize=0x0082,
        bdat_order='late')
        for texture_index,(name,word) in enumerate(textures)
        for shift in range(16)]
    early=(('bit15',0x8000,1),('bit0',0x0001,1),('bit12',0x1000,8),
           ('zero',0x0000,1),('ones',0xffff,1))
    for name,word,shift in early:
        presets.append(dict(index=len(presets),texture=name,b_word=word,bshift=shift,
            useb=useb,bltcon0=0x0bcc|(0x0400 if useb else 0),
            bltcon1=0x0001|(shift<<12),a_data=0,c_data=0,minterm=0xcc,
            bltapt=-80,bltsize=0x0082,bdat_order='early'))
    return presets


def line_b_hold_table(presets):
    """Return the literal words consumed by line_b_hold_trial in order."""
    lines=['line_b_hold_presets:']
    for preset in presets:
        words=(preset['b_word'],preset['bltcon1'],preset['useb'],
               int(preset['bdat_order']=='early'))
        lines.append('        dc.w '+','.join(f'${word&0xffff:04x}' for word in words))
    return lines


def line_b_hold_variants():
    """Pair B-only CC with the A-sensitive CA discriminator."""
    return [dict(index=0,name='B_only_CC_A_zero',a_data=0,minterm=0xcc,bltcon0=0x0bcc),
            dict(index=1,name='A8000_CA',a_data=0x8000,minterm=0xca,bltcon0=0x0bca)]


def line_b_mask_presets():
    """Kind33's complete A/B shift, USEB and line-length matrix."""
    a_patterns=(0,0x8000,0x0001,0xffff)
    b_patterns=(0,0x0001,0x0002,0x8000,0x1000,0xffff)
    presets=[]
    for ashift in range(16):
        for bshift in range(16):
            for useb in (0,1):
                for size in (0,1):
                    use=5|(useb<<1)
                    minterm=0xca
                    size_word=(0x0042,0x0082)[size]
                    use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)
                    bltcon0=(ashift<<12)|use_hw|0x0100|minterm
                    bltcon1=1|(bshift<<12)
                    index=len(presets)
                    presets.append(dict(index=index,a=1,ashift=ashift,b=0,bshift=bshift,
                        c=0,use=use,used=1,minterm=2,minterm_word=minterm,sing=0,sign=0,
                        error=0,size=size,seed_order=0,a_word=a_patterns[1],
                        b_word=b_patterns[0],c_word=0,bltcon0=bltcon0,
                        bltcon1=bltcon1,bltapt=-80,bltsize=size_word))
    return presets


def line_b_prime_presets():
    """Kind34 line settings cross A/B shifts and USEB after four prime modes."""
    a_patterns=(0,0x8000,0x0001,0xffff)
    b_patterns=(0,0x0001,0x0002,0x8000,0x1000,0xffff)
    presets=[]
    for ashift in range(16):
        for bshift in (0,1,8,15):
            for useb in (0,1):
                use=5|(useb<<1)
                use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)
                bltcon0=(ashift<<12)|use_hw|0x0100|0xca
                bltcon1=1|(bshift<<12)
                for size in (0,1):
                    index=len(presets)
                    presets.append(dict(index=index,a=1,ashift=ashift,b=0,bshift=bshift,
                        c=0,use=use,used=1,minterm=2,minterm_word=0xca,sing=0,sign=0,
                        error=0,size=size,seed_order=0,a_word=a_patterns[1],
                        b_word=b_patterns[0],c_word=0,bltcon0=bltcon0,
                        bltcon1=bltcon1,bltapt=-80,bltsize=(0x0042,0x0082)[size]))
    return presets


def line_b_prime_modes():
    return [
        dict(index=0,name='none',kind='none'),
        dict(index=1,name='BDAT0',kind='register',bltcon1=0,bltbdat=0),
        dict(index=2,name='B+D_copy_zero',kind='copy',bltcon0=0x05cc,bltcon1=0,
             bltbdat=0,bltbpt=0x18000,bltdpt=0x19000,bltsize=0x0042),
        dict(index=3,name='B+D_copy_ffff',kind='copy',bltcon0=0x05cc,bltcon1=0,
             bltbdat=0xffff,bltbpt=0x18000,bltdpt=0x19000,bltsize=0x0042)]


def line_word_control_presets():
    """Kind35 shifts and USEB cross four A/minterm controls, with B=0/C=0."""
    profiles=(('A0_CC',0,0,4),('A8000_CA',1,0,2),
              ('A8000_ASH5_CA',1,5,2),('A8000_ASH15_CA',1,15,2))
    minterm_words=(0x00,0xff,0xca,0xf0,0xcc,0xaa,0x3c,0x5a,0x0f)
    presets=[]
    for name,a,ashift,minterm in profiles:
        for bshift in range(16):
            for useb in (0,1):
                use=5|(useb<<1)
                use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)
                bltcon0=(ashift<<12)|use_hw|0x0100|minterm_words[minterm]
                bltcon1=1|(bshift<<12)
                presets.append(dict(index=len(presets),profile=name,a=a,ashift=ashift,
                    b=0,bshift=bshift,c=0,use=use,used=1,minterm=minterm,
                    minterm_word=minterm_words[minterm],sing=0,sign=0,error=0,
                    size=1,seed_order=0,a_word=(0,0x8000)[a],b_word=0,c_word=0,
                    bltcon0=bltcon0,bltcon1=bltcon1,bltapt=-80,bltsize=0x0082))
    return presets


def line_word_control_variants():
    """One-word 68000 instructions, all four CPU cycles / two CCKs."""
    return [dict(index=0,name='NOP',opcode=0x4e71,asm='nop',cpu_cycles=4,cck_cycles=2),
            dict(index=1,name='MOVEQ_0_D6',opcode=0x7c00,asm='moveq #0,d6',cpu_cycles=4,cck_cycles=2),
            dict(index=2,name='MOVEQ_m1_D6',opcode=0x7cff,asm='moveq #-1,d6',cpu_cycles=4,cck_cycles=2)]


def line_word_control_delays():
    return [dict(index=index,nops=delay,delay=delay,observer_slot=index)
            for index,delay in enumerate((0,1,2,4,16))]


def trials(focused=False,continuous=False,modes=False,pulses=False,reads=False,loads=False,blits=False,cpu=False,edges=False,channels=False,observe=0,priority=False,bzero=False,irq_paths=False,bzero_line=False,line_logic=False,line_logic_fine=False,line_logic_followup=False,line_pipeline=False,line_truth_table=False,line_stage=False,line_b_hold=False,line_b_hold_dma=False,line_b_mask=False,line_b_prime=False,line_word_control=False,line_shift_truth=False,line_wrap=False,line_c_cross=False):
    if line_c_cross:
        return [(38,preset['index'],0,1,16,0) for preset in line_c_cross_presets()]
    if line_wrap:
        return [(37,preset['index'],0,0,96,0) for preset in line_wrap_presets()]
    if line_shift_truth:
        return [(36,preset['index'],minterm,1,16,0)
                for preset in line_shift_truth_profiles() for minterm in range(256)]
    if line_word_control:
        return [(35,preset['index'],variant,0,delay,0)
                for preset in line_word_control_presets()
                for variant in range(3) for delay in (0,1,2,4,16)]
    if line_b_prime:
        return [(34,preset['index'],prime,1,16,0)
                for preset in line_b_prime_presets() for prime in range(4)]
    if line_b_mask:
        return [(33,preset['index'],0,1,16,0) for preset in line_b_mask_presets()]
    if line_b_hold or line_b_hold_dma:
        kind=32 if line_b_hold_dma else 31
        useb=1 if line_b_hold_dma else 0
        return [(kind,target,variant,1,delay,0)
                for target in range(len(line_b_hold_presets(useb)))
                for variant in range(len(line_b_hold_variants())) for delay in (0,1,2,4,16)]
    if line_stage:
        return [(30,target,minterm,phase,delay,0)
                for target in range(len(line_stage_profiles()))
                for minterm in (0x04,0x08,0x40,0x80,0x48)
                for phase in range(2) for delay in range(17)]
    if line_truth_table:
        return [(29,target,minterm,0,16,0)
                for target in range(len(line_truth_profiles())) for minterm in range(256)]
    if line_pipeline:
        return [(28,index,0,phase,delay,0)
                for index in range(len(line_pipeline_presets())) for phase in range(2) for delay in range(17)]
    if bzero:
        targets=[*range(32),32,33]
        rows=[]
        for target in targets:
            variants=(0,1,4) if target<32 and target&8 else (0,)
            if target in (0,1,9,15,25,32):
                variants=(*variants,0x100)
            rows.extend((22,target,variant,phase,delay,repeat)
                        for variant in variants for phase in range(2)
                        for delay in range(16) for repeat in (0,4))
        return rows
    if irq_paths:
        return [(23,target,variant,phase,delay,repeat)
                for target in range(7) for variant in range(2)
                for phase in range(2) for delay in range(16) for repeat in (0,4)]
    if bzero_line:
        return [(24,target,pattern | (late << 8),phase,delay,repeat)
                for target in (32,33) for pattern in (0,1,4,8,16) for late in (0,1)
                for phase in range(2)
                for delay in range(32) for repeat in (0,4)]
    if line_logic_fine:
        return [(26,target,b_pattern | (long_line << 1),phase,delay,repeat)
                for target in (32,33) for b_pattern in range(2) for long_line in range(2)
                for phase in range(2) for delay in range(17) for repeat in (0,4)]
    if line_logic_followup:
        # variant: B pattern index[0:2], A pattern index[3:4], C full[5],
        # long line[6]. repeat bit 0 selects early (1) vs late (0) BLTBDAT.
        return [(27,target,b_index | (a_index<<3) | (c_full<<5) | (long_line<<6),phase,delay,order)
                for target in (32,33) for b_index in range(7) for a_index in range(3)
                for c_full in range(2) for long_line in range(2) for phase in range(2)
                for delay in range(5) for order in (0,1)]
    if line_logic:
        delays=(0,1,2,4,8,16)
        rows=[]
        for target in (32,33):
            for lf_index in range(4):
                for a_enabled in range(2):
                    for b_index in range(3):
                        for c_full in range(2):
                            for pixel_index in range(3):
                                variant=(lf_index | (a_enabled<<2) | (b_index<<3)
                                         | (c_full<<5) | (pixel_index<<6))
                                rows.extend((25,target,variant,phase,delay,0)
                                            for phase in range(2) for delay in delays)
        return rows
    if channels or priority:
        masks=[*range(16),*(16+m for m in range(1,16,2)),32,33,34]
        repeat=observe | (4 if priority else 0)
        return [(21,t,22,p,d,repeat) for t in masks for p in range(2) for d in range(64)]
    if edges:
        return ([(19,t,w,p,d,0) for t in range(5) for w in (1,2,22) for p in range(4) for d in range(48)]
                + [(20,t,0,p,d,0) for t in range(4) for p in range(4) for d in range(96)])
    if cpu:
        return [(18,t,v,p,n,0) for t in range(7) for v in range(8) for p in range(8) for n in (1,2,16,64)]
    if blits:
        return [(17,t,v,p,h,r) for t in range(3) for v in range(3) for p in range(5) for h in (1,2,8,32,128,220) for r in range(2)]
    if loads:
        return [(16,t,v,p,d,r) for t in range(4) for v in range(2) for p in range(5) for d in range(16) for r in range(2)]
    if reads:
        return [(9,t,l,p,d,r) for t in range(4) for l in (1,3,15,200)
                for p in range(3) for d in (*range(64),127) for r in range(2)]
    if pulses:
        return [(14,t,l,p,d,style) for t in (0,2) for l in (0,1,3,200)
                for p in range(3) for d in (*range(16),31,63) for style in range(4)]
    if modes:
        return [(13,t,v,p,d,r) for t in (1,3) for v in range(5)
                for p in range(3) for d in (0,1,2,3,4,5,6,7,15,31) for r in range(2)]
    if continuous:
        latches=(0,1,2,3,4,7,15,200)
        delays=(0,1,2,3,4,5,6,7,15,31,63,127)
        rows=[(kind,t,l,p,d,r) for kind,targets in ((6,range(4)),(7,(0,2)))
              for t in targets for l in latches for p in range(3) for d in delays for r in range(2)]
        rows += [(8,t,l,p,d,r) for t in (0,2) for l in (0,1,3,15,200)
                 for p in range(3) for d in (0,1,3,7,31,63) for r in range(2)]
        rows += [(9,t,l,p,d,r) for t in range(4) for l in (0,1,3,15,200)
                 for p in range(3) for d in delays for r in range(2)]
        rows += [(12,t,l,p,d,r) for t in (0,2) for l in (0,1,3,15,40)
                 for p in range(3) for d in delays for r in range(2)]
        return rows
    if focused:
        rows=[(5,t,0,p,d,r) for t in range(4) for p in range(5) for d in range(8) for r in range(2)]
        return rows + [(10,3,k,p,m*4,r) for k in (5,6) for p in range(16) for m in range(2) for r in range(4)]
    rows=[]
    for target in range(4):
        for variant in range(2):
            for phase in range(5):
                for delay in range(8):
                    for repeat in range(2):
                        rows.append((1,target,variant,phase,delay,repeat))
    for target in range(4):
        for variant in range(2):
            for phase in range(5):
                for latch in (0,1,3,15):
                    for repeat in range(2):
                        rows.append((2,target,variant,phase,latch,repeat))
    for target in range(4):
        for variant in range(4):
            for phase in range(5):
                for repeat in range(2):
                    rows.append((3,target,variant,phase,4,repeat))
    for target in range(4):
        for variant in range(4):
            for phase in range(5):
                for delay in range(8):
                    for repeat in range(2):
                        rows.append((4,target,variant,phase,delay,repeat))
    for source in range(4):
        for kernel in range(5):
            for phase in range(16):
                for memory in range(2):
                    for dma in range(3):
                        for repeat in range(2):
                            rows.append((10,source,kernel,phase,dma+memory*4,repeat))
    return rows

def build(assembler,wsl=False,focused=False,continuous=False,modes=False,pulses=False,reads=False,loads=False,blits=False,cpu=False,edges=False,channels=False,observe=0,priority=False,bzero=False,irq_paths=False,bzero_line=False,line_logic=False,line_logic_fine=False,line_logic_followup=False,line_pipeline=False,line_truth_table=False,line_stage=False,line_b_hold=False,line_b_hold_dma=False,line_b_mask=False,line_b_prime=False,line_word_control=False,line_shift_truth=False,line_wrap=False,line_c_cross=False):
    hold_mode=line_b_hold or line_b_hold_dma
    hold_useb=1 if line_b_hold_dma else 0
    edge_kernel=any((edges,channels,cpu,priority,bzero,irq_paths,bzero_line,line_logic,
        line_logic_fine,line_logic_followup,line_pipeline,line_truth_table,line_stage,
        hold_mode,line_b_mask,line_b_prime,line_word_control,line_shift_truth,line_wrap,line_c_cross))
    rows=trials(focused,continuous,modes,pulses,reads,loads,blits,cpu,edges,channels,observe,priority,bzero,irq_paths,bzero_line,line_logic,line_logic_fine,line_logic_followup,line_pipeline,line_truth_table,line_stage,line_b_hold,line_b_hold_dma,line_b_mask,line_b_prime,line_word_control,line_shift_truth,line_wrap,line_c_cross)
    build=ROOT/'build/rom'; build.mkdir(parents=True,exist_ok=True)
    sources=sorted([ROOT/'build_rom.py',*list((ROOT/'src/rom').glob('*')),*list((ROOT/'vendor/rbcp').glob('*'))])
    h=hashlib.sha256()
    for source in sources:
        h.update(source.relative_to(ROOT).as_posix().encode()+b'\0'+source.read_bytes().replace(b'\r\n',b'\n'))
    h.update(json.dumps(rows).encode())
    if line_pipeline:
        h.update(json.dumps(line_pipeline_presets(),sort_keys=True).encode())
    if line_b_mask:
        h.update(json.dumps(line_b_mask_presets(),sort_keys=True).encode())
    if line_b_prime:
        h.update(json.dumps(line_b_prime_presets(),sort_keys=True).encode())
        h.update(json.dumps(line_b_prime_modes(),sort_keys=True).encode())
    if line_word_control:
        h.update(json.dumps(line_word_control_presets(),sort_keys=True).encode())
    if line_shift_truth:
        h.update(json.dumps(line_shift_truth_profiles(),sort_keys=True).encode())
    if line_wrap:
        h.update(json.dumps(line_wrap_presets(),sort_keys=True).encode())
    if line_c_cross:
        h.update(json.dumps(line_c_cross_presets(),sort_keys=True).encode())
        h.update(json.dumps(line_word_control_variants(),sort_keys=True).encode())
        h.update(json.dumps(line_word_control_delays(),sort_keys=True).encode())
    if line_truth_table:
        h.update(json.dumps(line_truth_profiles(),sort_keys=True).encode())
    if line_stage:
        h.update(json.dumps(line_stage_profiles(),sort_keys=True).encode())
    if hold_mode:
        h.update(json.dumps(line_b_hold_presets(hold_useb),sort_keys=True).encode())
        h.update(json.dumps(line_b_hold_variants(),sort_keys=True).encode())
    fingerprint=h.hexdigest()
    (build/'trials.i').write_text('trials:\n'+''.join('        dc.w '+','.join(map(str,row))+'\n' for row in rows))
    presets_for_kernel=(line_word_control_presets() if line_word_control else
        line_b_prime_presets() if line_b_prime else
        (line_b_mask_presets() if line_b_mask else line_pipeline_presets()))
    table=['line_pipeline_presets:']
    for preset in presets_for_kernel:
        # Three words keep the full configuration auditable in the listing.
        w0=preset['a']|(preset['ashift']<<2)|(preset['b']<<6)|(preset['bshift']<<9)
        use_hw=((preset['use']&1)<<2)|(preset['use']&2)|((preset['use']&4)>>2)
        w1=preset['c']|(use_hw<<2)|(preset['used']<<5)
        w2=preset['minterm_word']|(preset['sing']<<8)|(preset['sign']<<9)|(preset['error']<<10)|(preset['size']<<12)|(preset['seed_order']<<14)
        table.append(f"        dc.w ${w0:04x},${w1:04x},${w2:04x}")
    (build/'line_pipeline.i').write_text('\n'.join(table)+'\n')
    truth_table=['line_truth_profiles:']
    for profile in line_truth_profiles():
        truth_table.append('        dc.w '+','.join(f'${profile[key]&0xffff:04x}' for key in ('a','b','c','bltsize')))
    (build/'line_truth_profiles.i').write_text('\n'.join(truth_table)+'\n')
    shift_truth=['line_shift_truth_profiles:']
    for profile in line_shift_truth_profiles():
        shift_truth.append('        dc.w '+','.join(f'${profile[key]&0xffff:04x}'
            for key in ('a','b','c','bltsize','bltcon1')))
    (build/'line_shift_truth_profiles.i').write_text('\n'.join(shift_truth)+'\n')
    wrap_table=['line_wrap_presets:']
    wrap_presets=line_wrap_presets() if not line_c_cross else [line_wrap_presets()[0]]
    for preset in wrap_presets:
        wrap_table.append('        dc.w '+','.join(f'${preset[key]&0xffff:04x}'
            for key in ('a_data','b_data','c_data','bltsize','bltcon1','bltcon0')))
    (build/'line_wrap_presets.i').write_text('\n'.join(wrap_table)+'\n')
    c_cross_table=['line_c_cross_presets:']
    c_cross_rows=line_c_cross_presets() if line_c_cross else [line_c_cross_presets()[0]]
    for preset in c_cross_rows:
        c_cross_table.append('        dc.w '+','.join(f'${preset[key]&0xffff:04x}'
            for key in ('a_data','b_data','c_data','bltsize','bltcon1','bltcon0')))
    (build/'line_c_cross_presets.i').write_text('\n'.join(c_cross_table)+'\n')
    stage_table=['line_stage_profiles:']
    for profile in line_stage_profiles():
        stage_table.append('        dc.w '+','.join(f'${profile[key]&0xffff:04x}' for key in ('c_first','c_second','useb')))
    (build/'line_stage_profiles.i').write_text('\n'.join(stage_table)+'\n')
    hold_table=line_b_hold_table(line_b_hold_presets(hold_useb))
    (build/'line_b_hold_presets.i').write_text('\n'.join(hold_table)+'\n')
    hold_variants=['line_b_hold_variants:']
    for variant in line_b_hold_variants():
        hold_variants.append('        dc.w '+','.join(f'${variant[key]&0xffff:04x}' for key in ('a_data','bltcon0')))
    (build/'line_b_hold_variants.i').write_text('\n'.join(hold_variants)+'\n')
    (build/'source_id.i').write_text('        dc.b '+','.join('$'+fingerprint[i:i+2] for i in range(0,64,2))+'\n')
    (build/'rom_layout.i').write_text(f'TRIAL_COUNT equ {len(rows)}\nPAYLOAD_BYTES equ 0\n')
    def assemble(source,out):
        paths=[build,ROOT/'src/rom',ROOT/'vendor/rbcp']
        def path(p):
            if not wsl: return str(p)
            if p.drive: return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
            return str(p)
        command=(['wsl','-d','Ubuntu-24.04','--exec',assembler] if wsl else [assembler])
        command+=['-m68000','-no-opt','-Fbin','-DCONFIG_ROM_KB=512']
        if edge_kernel: command+=['-DEDGE_ROM_KERNEL=1']
        for p in paths: command+=['-I',path(p)]
        command += [path(source),'-o',path(out),'-L',path(out.with_suffix('.lst'))]
        subprocess.run(command,cwd=ROOT,check=True)
    # Raw VHPOSR feedback followed by ROM-only NOP/EXG padding. The
    # table returns on the following line at one fixed horizontal phase.
    alignment = ["        org $fb0000", "rom_align:",
        ".wait:  move.w 6(a6),d0", "        andi.w #$ff,d0",
        "        cmpi.w #$30,d0", "        bcs.s .wait",
        "        cmpi.w #$60,d0", "        bhi.s .wait",
        "        move.w 6(a6),d0", "        andi.w #$ff,d0",
        "        sub.w 6(a4),d0", "        lsl.w #2,d0",
        "        lea rom_align_table(pc),a2", "        move.l 0(a2,d0.w),a2",
        "        jmp (a2)", "rom_align_table:"]
    alignment += [f"        dc.l rom_align_{h}" for h in range(256)]
    for h in range(256):
        clocks = max(0, 227 + 64 - 44 - h)
        alignment.append(f"rom_align_{h}:")
        if clocks % 2:
            alignment.append("        exg d0,d1")
            clocks -= 3
        alignment += [f"        rept {max(0,clocks)//2}", "        nop", "        endr", "        rts"]
    (build/'rom_alignment.i').write_text('\n'.join(alignment)+'\n')
    payload=build/'experiment.bin'
    assemble(ROOT/'src/rom/experiment.asm',payload)
    data=payload.read_bytes(); data+=b'\0'*((-len(data))%4); payload.write_bytes(data)
    assert len(data)<0x20000, 'Payload overlaps result buffer or exceeds boot copy loop'
    assert 0x40000+64+len(rows)*40 < 0x7e000, 'Results overlap stack'
    (build/'rom_layout.i').write_text(f'TRIAL_COUNT equ {len(rows)}\nPAYLOAD_BYTES equ {len(data)}\n')
    out=build/'a500-timing-rom.bin'
    if edge_kernel: assemble(ROOT/'src/rom/edge_kernel.asm',build/'rom_kernel.bin')
    assemble(ROOT/'src/rom/boot.asm',out)
    data=out.read_bytes(); assert len(data)==524288
    if edge_kernel:
        kernel=(build/'rom_kernel.bin').read_bytes()
        kernel_offset=0x10000
        assert data[kernel_offset:kernel_offset+len(kernel)]==kernel, \
            'Raw ROM does not contain the assembled edge kernel at $f90000'
        observer_offset=kernel_offset+(0xff3000-0xf90000)
        kernel_observer_offset=0x20000+(0xff3000-0xfb0000)
        assert data[observer_offset:observer_offset+0x40]==kernel[kernel_observer_offset:kernel_observer_offset+0x40], \
            'Raw ROM FF3000 observer does not match rom_kernel.bin'
    assert data[-16:]==bytes.fromhex('00180019001a001b001c001d001e001f')
    swapped=bytearray(data); swapped[0::2]=data[1::2]; swapped[1::2]=data[0::2]
    (build/'a500-timing-rom-onerom.bin').write_bytes(swapped)
    manifest=dict(version=1,source_id=fingerprint,trial_count=len(rows),record_bytes=40,
                  result_address=0x40000,result_bytes=64+len(rows)*40,
                  collection_done_pc=0x20010,payload_bytes=len(payload.read_bytes()),
                  rom_sha256=hashlib.sha256(data).hexdigest(),
                  onerom_sha256=hashlib.sha256(swapped).hexdigest(),trials=rows)
    if line_pipeline:
        manifest['line_pipeline_presets']=line_pipeline_presets()
    if line_b_mask:
        manifest['line_b_mask_presets']=line_b_mask_presets()
    if line_b_prime:
        manifest['line_b_prime_presets']=line_b_prime_presets()
        manifest['line_b_prime_modes']=line_b_prime_modes()
    if line_word_control:
        manifest['line_word_control_presets']=line_word_control_presets()
        manifest['line_word_control_variants']=line_word_control_variants()
        manifest['line_word_control_delays']=line_word_control_delays()
        manifest['line_word_control_observer']=dict(base=0xff4000,variant_stride=0x1000,
            delay_stride=0x100,phase=0,delay_values=[0,1,2,4,16])
    if line_shift_truth:
        manifest['line_shift_truth_profiles']=line_shift_truth_profiles()
        manifest['line_shift_truth_observer']=dict(address=0xff3000,phase=1,delay=16,
            minterms=list(range(256)),useb=0)
    if line_wrap:
        manifest['line_wrap_presets']=line_wrap_presets()
        manifest['line_wrap_observer']=dict(address=0xff7000,phase=0,delay=96,
            nops=97,maximum_pixels=18,bzero_bit=14)
    if line_c_cross:
        manifest['line_c_cross_presets']=line_c_cross_presets()
        manifest['line_c_cross_observer']=dict(address=0xff3000,phase=1,delay=16,
            usea=1,used=1,minterm=0xcc)
    if line_truth_table:
        manifest['line_truth_profiles']=line_truth_profiles()
    if line_stage:
        manifest['line_stage_profiles']=line_stage_profiles()
    if hold_mode:
        manifest['line_b_hold_presets']=line_b_hold_presets(hold_useb)
        manifest['line_b_hold_variants']=line_b_hold_variants()
    (build/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('ROM built:',len(rows),'trials;',manifest['source_id'])
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--vasm',default='vasmm68k_mot'); p.add_argument('--wsl',action='store_true'); group=p.add_mutually_exclusive_group(); group.add_argument('--focused',action='store_true'); group.add_argument('--continuous',action='store_true'); group.add_argument('--modes',action='store_true'); group.add_argument('--pulses',action='store_true'); group.add_argument('--reads',action='store_true'); group.add_argument('--loads',action='store_true'); group.add_argument('--blits',action='store_true'); group.add_argument('--cpu',action='store_true'); group.add_argument('--edges',action='store_true'); group.add_argument('--channels',action='store_true'); group.add_argument('--priority',action='store_true',help='aligned observer sweep with BLTPRI enabled'); group.add_argument('--bzero',action='store_true',help='BZERO transition observer matrix'); group.add_argument('--irq-paths',action='store_true',help='native and Copper-generated IRQ STOP path matrix'); group.add_argument('--bzero-line',action='store_true',help='line-mode BZERO onset sweep'); group.add_argument('--line-logic',action='store_true',help='line minterm and BZERO/data behavior matrix'); group.add_argument('--line-logic-fine',action='store_true',help='focused 1-CCK line BZERO readback sweep'); group.add_argument('--line-logic-followup',action='store_true',help='focused kind27 line BZERO input/BDAT ordering matrix'); group.add_argument('--line-pipeline',action='store_true',help='kind28 line-mode BZERO pixel-pipeline preset matrix'); group.add_argument('--line-truth-table',action='store_true',help='kind29 line-mode 8-bit minterm truth table'); group.add_argument('--line-stage',action='store_true',help='kind30 line-mode intermediate ALU stage matrix'); group.add_argument('--line-b-hold',action='store_true',help='kind31 line-mode hidden B datapath, USEB off'); group.add_argument('--line-b-hold-dma',action='store_true',help='kind32 line-mode hidden B datapath, USEB on'); group.add_argument('--line-b-mask',action='store_true',help='kind33 BSHIFT/ASHIFT line BZERO mask matrix'); group.add_argument('--line-b-prime',action='store_true',help='kind34 normal-B priming before line BZERO samples'); group.add_argument('--line-word-control',action='store_true',help='kind35 equal-cycle CPU instruction bus-word control'); group.add_argument('--line-shift-truth',action='store_true',help='kind36 shifted B line minterm truth-table closure'); group.add_argument('--line-wrap',action='store_true',help='kind37 BSHIFT and line-length counter-wrap map'); group.add_argument('--line-c-cross',action='store_true',help='kind38 line-mode C dependence with CC minterm'); p.add_argument('--observe',choices=['busy','irq','memory'],default='busy')
    a=p.parse_args(); build(a.vasm,a.wsl,a.focused,a.continuous,a.modes,a.pulses,a.reads,a.loads,a.blits,a.cpu,a.edges,a.channels,['busy','irq','memory'].index(a.observe),a.priority,a.bzero,a.irq_paths,a.bzero_line,a.line_logic,a.line_logic_fine,a.line_logic_followup,a.line_pipeline,a.line_truth_table,a.line_stage,a.line_b_hold,a.line_b_hold_dma,a.line_b_mask,a.line_b_prime,a.line_word_control,a.line_shift_truth,a.line_wrap,a.line_c_cross)
