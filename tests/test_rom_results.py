import importlib.util,struct,unittest,json,re
from pathlib import Path
import build_rom,rom_results,compare_phase,compare_continuous,compare_timing_sweeps

class RomFormatTests(unittest.TestCase):
    def test_running_load_and_blitter_sweep_coverage(self):
        loads=build_rom.trials(loads=True)
        self.assertEqual(len(loads),1280)
        self.assertEqual({r[1] for r in loads},{0,1,2,3})
        self.assertEqual(sum(r[2]==1 for r in loads),640)
        blits=build_rom.trials(blits=True)
        self.assertEqual(len(blits),540)
        self.assertEqual({(r[1],r[2]) for r in blits},{(t,v) for t in range(3) for v in range(3)})
        self.assertLess(0x40000+64+len(blits)*40,0x7e000)

    def packet(self):
        h=bytearray(64);h[:8]=b'A5RBCP01'
        struct.pack_into('>HHIII',h,8,1,40,1,104,0)
        struct.pack_into('>4H',h,56,0xa001,0xffff,1,1)
        data=h+bytes(40)
        struct.pack_into('>I',data,20,(-sum(struct.unpack('>26I',data)))&0xffffffff)
        return bytes(data)
    def test_complete_frame_and_integrity(self):
        data=self.packet();text=b'USB log\r\nA5RBCP-BEGIN\r\n'+data.hex().encode()+b'\r\nA5RBCP-END\r\n'
        self.assertEqual(rom_results.from_transcript(text),data)
        meta,rows=rom_results.decode(data)
        self.assertEqual(meta['record_count'],1);self.assertTrue(meta['slow_ram'])
        with self.assertRaises(ValueError): rom_results.from_transcript(text.split(b'A5RBCP-END')[0])
        bad=bytearray(data);bad[-1]^=1
        with self.assertRaises(ValueError): rom_results.decode(bytes(bad))
        with self.assertRaises(ValueError): rom_results.decode(data[:-4])
    def test_rom_footer_and_fault_rejection(self):
        rom=Path(build_rom.ROOT/'build/rom/a500-timing-rom.bin')
        if not rom.exists(): self.skipTest('Build the ROM to validate its interrupt footer')
        if rom.exists():
            self.assertEqual(rom.read_bytes()[-16:],bytes.fromhex('00180019001a001b001c001d001e001f'))
        capsule=bytearray(512);capsule[:8]=b'A5FAULT1'
        struct.pack_into('>H',capsule,8,4)
        struct.pack_into('>I',capsule,12,(-sum(struct.unpack('>128I',capsule)))&0xffffffff)
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fault.bin';path.write_bytes(capsule)
            with self.assertRaises(RuntimeError): rom_results.extract(path,Path(directory)/'out')
            self.assertTrue((Path(directory)/'out/fault.json').exists())

    def test_phase_validator_rejects_wrong_latency_and_rerouting(self):
        def packet(irq_beam=0x6065, irq_level=1):
            h=bytearray(64);h[:8]=b'A5RBCP01'
            struct.pack_into('>HHIII',h,8,1,40,2,144,0)
            struct.pack_into('>4H',h,56,0xa000,0xffff,1,1)
            stop=[0]*20;stop[0]=5;stop[10]=92;stop[17]=100;stop[18]=92
            phase=[0]*20;phase[0]=10;phase[1]=3;phase[2]=5
            phase[12]=irq_beam;phase[13]=irq_level;phase[17]=0x40cf
            data=h+struct.pack('>40H',*(stop+phase))
            struct.pack_into('>I',data,20,(-sum(struct.unpack('>36I',data)))&0xffffffff)
            return bytes(data)
        self.assertEqual(compare_phase.check(packet())['phase_matches'],1)
        self.assertEqual(compare_phase.check(packet())['stop_matches'],1)
        self.assertEqual(compare_phase.check(packet(0x6066))['phase_matches'],0)
        self.assertEqual(compare_phase.check(packet(irq_level=6))['phase_matches'],0)

    def test_continuous_suite_matrices(self):
        for flags,count,kinds in [
            ({'continuous':True},5976,{6,7,8,9,12}),
            ({'modes':True},600,{13}),
            ({'pulses':True},1728,{14}),
            ({'reads':True},6240,{9}),
        ]:
            rows=build_rom.trials(**flags)
            self.assertEqual(len(rows),count)
            self.assertEqual(len(set(rows)),count)
            self.assertEqual({r[0] for r in rows},kinds)
            self.assertLess(0x40000+64+count*40,0x7e000)

    def test_continuous_comparison_rejects_provenance_and_counter_errors(self):
        def packet(counter=3,source=0,variant=3,status=0):
            data=bytearray(self.packet())
            data[24]=source
            row=[0]*20;row[0]=9;row[2]=variant;row[10]=counter;row[16]=status
            struct.pack_into('>20H',data,64,*row)
            struct.pack_into('>I',data,20,0)
            struct.pack_into('>I',data,20,(-sum(struct.unpack('>26I',data)))&0xffffffff)
            return bytes(data)
        self.assertEqual(compare_continuous.compare(packet(),packet())['counter_mismatch_records'],0)
        self.assertEqual(compare_continuous.compare(packet(),packet(counter=2))['counter_mismatch_records'],1)
        for bad in (packet(source=1),packet(variant=4),packet(status=1)):
            with self.assertRaises(ValueError):compare_continuous.compare(packet(),bad)

    def test_aligned_channel_priority_repeat_matrix(self):
        normal=build_rom.trials(channels=True,observe=0)
        priority=build_rom.trials(priority=True,observe=0)
        self.assertEqual(len(normal),3456)
        self.assertEqual(len(priority),3456)
        self.assertEqual({r[5] for r in normal},{0})
        self.assertEqual({r[5] for r in priority},{4})
        self.assertEqual({(r[0],r[1],r[2],r[3],r[4]) for r in normal},
                         {(r[0],r[1],r[2],r[3],r[4]) for r in priority})
        for observer in range(3):
            self.assertEqual({r[5] for r in build_rom.trials(priority=True,observe=observer)},
                             {observer|4})
    def test_bzero_trial_matrix_coverage_and_ram_bound(self):
        rows=build_rom.trials(bzero=True)
        targets=[*range(32),32,33]
        expected=set()
        for target in targets:
            variants=(0,1,4) if target<32 and target&8 else (0,)
            if target in (0,1,9,15,25,32):
                variants=(*variants,0x100)
            expected.update((22,target,variant,phase,delay,repeat)
                            for variant in variants for phase in range(2)
                            for delay in range(16) for repeat in (0,4))
        self.assertEqual(len(rows),4608)
        self.assertEqual(len(rows),len(set(rows)))
        self.assertEqual(set(rows),expected)
        self.assertNotIn(34,{row[1] for row in rows})
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)

    def test_irq_paths_trial_matrix_coverage(self):
        rows=build_rom.trials(irq_paths=True)
        self.assertEqual(len(rows),896)
        self.assertEqual(len(set(rows)),896)
        self.assertEqual({r[0] for r in rows},{23})
        self.assertEqual({r[1] for r in rows},set(range(7)))
        self.assertEqual({r[2] for r in rows},{0,1})
        self.assertEqual({r[3] for r in rows},{0,1})
        self.assertEqual({r[4] for r in rows},set(range(16)))
        self.assertEqual({r[5] for r in rows},{0,4})

    def test_line_bzero_matrix_coverage(self):
        rows=build_rom.trials(bzero_line=True)
        self.assertEqual(len(rows),2560)
        self.assertEqual(len(set(rows)),2560)
        self.assertEqual({r[0] for r in rows},{24})
        self.assertEqual({r[1] for r in rows},{32,33})
        self.assertEqual({r[2] for r in rows},{0,1,4,8,16,0x100,0x101,0x104,0x108,0x110})
        self.assertEqual({r[3] for r in rows},{0,1})
        self.assertEqual({r[4] for r in rows},set(range(32)))
        self.assertEqual({r[5] for r in rows},{0,4})
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        self.assertNotRegex(source,r'(?im)^\s*(?:ori|andi|eori)\.w\s+[^\n]*\$40\(a6\)')

    def test_line_logic_matrix_coverage_and_direct_write_only_register_setup(self):
        rows=build_rom.trials(line_logic=True)
        self.assertEqual(len(rows),3456)
        self.assertEqual(len(set(rows)),3456)
        self.assertEqual({r[0] for r in rows},{25})
        self.assertEqual({r[1] for r in rows},{32,33})
        self.assertEqual({r[3] for r in rows},{0,1})
        self.assertEqual({r[4] for r in rows},{0,1,2,4,8,16})
        self.assertEqual({r[5] for r in rows},{0})
        variants={r[2] for r in rows}
        self.assertEqual(len(variants),144)
        self.assertEqual({v&3 for v in variants},{0,1,2,3})
        self.assertEqual({(v>>2)&1 for v in variants},{0,1})
        self.assertEqual({(v>>3)&3 for v in variants},{0,1,2})
        self.assertEqual({(v>>5)&1 for v in variants},{0,1})
        self.assertEqual({(v>>6)&3 for v in variants},{0,1,2})
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        routine=source.split('line_logic_trial:',1)[1].split('line_pipeline_trial:',1)[0]
        self.assertNotRegex(routine,r'(?im)^\s*(?:ori|andi|eori|add|sub|clr|neg|not|bset|bclr|bchg)\.w?\s+[^\n]*\$(?:40|42|44|46|60|62|64|66|70|72|74)\(a6\)')
        c_setup=routine.split('.c_ready:',1)[1].split('move.w #1023,d7',1)[0]
        self.assertIn('move.w d0,$70(a6)',c_setup)
        self.assertRegex(routine,r'(?s)move\.w #\$8240,\$96\(a6\).*?btst #2,11\(a4\).*?move\.w #\$8640,\$96\(a6\)')
        self.assertIn('        jsr (a2)',routine)
        self.assertNotIn('        jmp (a2)',routine)
        self.assertIn('move.l #-80,$50(a6)',routine)
        self.assertNotIn('move.l #$15000,$50(a6)',routine)

    def test_fine_line_bzero_matrix_is_544_bounded_trials(self):
        rows=build_rom.trials(line_logic_fine=True)
        self.assertEqual(len(rows),544)
        self.assertEqual(len(set(rows)),544)
        self.assertEqual({r[0] for r in rows},{26})
        self.assertEqual({r[1] for r in rows},{32,33})
        self.assertEqual({r[2] for r in rows},{0,1,2,3})
        self.assertEqual({r[3] for r in rows},{0,1})
        self.assertEqual({r[4] for r in rows},set(range(17)))
        self.assertEqual({r[5] for r in rows},{0,4})
        for target in (32,33):
            for variant in range(4):
                for phase in (0,1):
                    for repeat in (0,4):
                        subset=[r for r in rows if r[1:4]==(target,variant,phase) and r[5]==repeat]
                        self.assertEqual([r[4] for r in subset],list(range(17)))
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        routine=source.split('line_logic_trial:',1)[1].split('divirq_handler:',1)[0]
        self.assertRegex(routine,r'(?s)move\.w #\$8240,\$96\(a6\).*?btst #2,11\(a4\).*?move\.w #\$8640,\$96\(a6\)')

    def test_kind27_followup_matrix_drives_line_inputs_and_bdat_order(self):
        rows=build_rom.trials(line_logic_followup=True)
        self.assertEqual(len(rows),3360)
        self.assertEqual(len(set(rows)),3360)
        self.assertEqual({r[0] for r in rows},{27})
        self.assertEqual({r[1] for r in rows},{32,33})
        variants={r[2] for r in rows}
        self.assertEqual({v&7 for v in variants},set(range(7)))
        self.assertEqual({(v>>3)&3 for v in variants},set(range(3)))
        self.assertEqual({(v>>5)&1 for v in variants},{0,1})
        self.assertEqual({(v>>6)&1 for v in variants},{0,1})
        self.assertEqual({r[3] for r in rows},{0,1})
        self.assertEqual({r[4] for r in rows},set(range(5)))
        self.assertEqual({r[5] for r in rows},{0,1})
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        routine=source.split('line_logic_trial:',1)[1].split('divirq_handler:',1)[0]
        self.assertIn('move.l #-80,$50(a6)',routine)
        self.assertIn('move.w d0,$70(a6)',routine)
        self.assertIn('move.w d0,$74(a6)',routine)
        self.assertIn('move.w d1,$72(a6)',routine)
        self.assertRegex(routine,r'(?s)move\.l d7,-\(sp\)\s+cmpi\.w #27,\(a4\)\s+bne\.s \.bdat_seed_ready\s+move\.w #\$0001,\$42\(a6\)\s+move\.w #\$ffff,\$72\(a6\).*?btst #0,11\(a4\).*?move\.w d1,\$72\(a6\)')
        self.assertIn('btst #0,11(a4)',routine)
        self.assertIn('dc.w 0,$0001,$0002,$0004,$8000,$1000,$ffff',routine)
        self.assertIn('dc.w 0,$8000,$ffff',routine)

    def test_kind28_pipeline_matrix_encodes_every_axis_and_explicit_controls(self):
        rows=build_rom.trials(line_pipeline=True)
        presets=build_rom.line_pipeline_presets()
        self.assertEqual(len(rows),len(presets)*34)
        self.assertLessEqual(len(rows),4096)
        self.assertEqual(len(rows),3060)
        self.assertEqual(len(set(rows)),3060)
        self.assertEqual(len(presets),90)
        self.assertEqual({r[0] for r in rows},{28})
        self.assertEqual({r[1] for r in rows},set(range(len(presets))))
        self.assertEqual({r[2] for r in rows},{0})
        self.assertEqual({r[3] for r in rows},{0,1})
        self.assertEqual({r[4] for r in rows},set(range(17)))
        self.assertEqual({r[5] for r in rows},{0})
        for field,expected in [('a',set(range(4))),('ashift',{0,1,8,15}),
                ('b',set(range(6))),('bshift',{0,1,8,15}),('c',set(range(4))),
                ('minterm',set(range(9))),('use',set(range(8))),('used',{0,1}),
                ('sing',{0,1}),('sign',{0,1}),('error',set(range(4))),
                ('size',{0,1,2}),('seed_order',{0,1})]:
            self.assertEqual({p[field] for p in presets},expected,field)
        for a in (0,1):
            for minterm in (2,4):
                for use in (5,7):
                    selected=[p for p in presets if p['a']==a and p['b']==0 and p['c']==0
                              and p['ashift']==0 and p['bshift']==0 and p['minterm']==minterm
                              and p['use']==use and p['used']==1 and p['sing']==0 and p['sign']==0
                              and p['error']==0]
                    self.assertEqual({p['size'] for p in selected},{0,1,2})
        baseline=next(p for p in presets if p['a']==1 and p['b']==0 and p['c']==0
                      and p['minterm']==2 and p['use']==5 and p['used']==1
                      and p['sing']==0 and p['sign']==0 and p['error']==0 and p['size']==1)
        self.assertEqual((baseline['bltcon0'],baseline['bltcon1'],baseline['bltapt'],baseline['bltsize']),
                         (0x0bca,0x0001,-80,0x0082))
        self.assertTrue(any(p['a']==2 and p['ashift']==1 for p in presets))
        self.assertTrue(any(p['a']==2 and p['ashift']==15 for p in presets))
        for b in (1,3,4):
            self.assertEqual({p['bshift'] for p in presets if p['b']==b and p['use']==7},
                             {0,1,8,15})
        self.assertTrue(any(p['sing']==1 and p['sign']==1 and p['error']==0 for p in presets))
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        self.assertIn('cmpi.w #28,(a4)',source)
        pipeline=source.split('line_pipeline_trial:',1)[1].split('line_truth_trial:',1)[0]
        self.assertIn('moveq #0,d1\n        move.w 6(a4),d1',pipeline)
        truth=source.split('line_truth_trial:',1)[1].split('line_truth_profiles:',1)[0]
        self.assertIn('move.w #$0b00,d0',truth)
        self.assertIn('move.w #$ffff,$72(a6)\n        clr.w $72(a6)',source)
        self.assertIn('clr.w $72(a6)\n        move.w #$ffff,$72(a6)',source)
        kernel=(Path(__file__).resolve().parents[1]/'src/rom/edge_kernel.asm').read_text()
        for snippet in ('dcb.b $ff0000-*,0','lea $10000,a0','lea $11000,a0',
                        'move.w d2,34(a4)','move.w $11000,30(a4)',
                        'move.w $11050,36(a4)','move.w $110a0,38(a4)'):
            self.assertIn(snippet,kernel)

    def test_kind28_comparator_preserves_complete_raw_pipeline_trace(self):
        pairs=[]
        for descriptor in build_rom.trials(line_pipeline=True):
            _,preset,_,phase,delay,_=descriptor
            row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|(delay&0x1f),
                     icr=delay,irq_beam=preset,irq_level=phase,saved_pc_offset=(delay<<16)|0x1234,
                     aux=delay+1,second_counter_or_beam=delay+2,second_icr_or_level=delay+3)
            pairs.append((tuple(descriptor),row,row.copy()))
        report=compare_timing_sweeps._compare_line_pipeline(pairs)
        self.assertEqual(report['kind'],28)
        self.assertEqual(len(report['groups']),len(build_rom.line_pipeline_presets())*2)
        first=report['groups'][0]
        self.assertEqual(first['samples'],17)
        self.assertEqual(len(first['delay_trace']),17)
        self.assertEqual(first['phase_pad'],'NOP')
        self.assertEqual(first['raw_mismatches'],0)
        self.assertIn('bltcon0',first)
        self.assertEqual(first['delay_trace'][0]['hardware_cpt_words'][0],0x1234)
        with self.assertRaisesRegex(ValueError,'Invalid kind28 descriptor'):
            compare_timing_sweeps._compare_line_pipeline([((28,999,0,0,0,0),{}, {})])
        for bad in ((28,0,1,0,0,0),(28,0,0,2,0,0),(28,0,0,0,17,0),(28,0,0,0,0,1)):
            with self.subTest(descriptor=bad), self.assertRaisesRegex(ValueError,'Invalid kind28 descriptor'):
                compare_timing_sweeps._compare_line_pipeline([(bad,{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind28 descriptor matrix'):
            compare_timing_sweeps._compare_line_pipeline(pairs[:-1])

    def test_kind29_covers_all_8bit_minterms_for_five_profiles_and_two_sizes(self):
        profiles=build_rom.line_truth_profiles()
        rows=build_rom.trials(line_truth_table=True)
        self.assertEqual(len(profiles),10)
        self.assertEqual(len(rows),2560)
        self.assertEqual(len(set(rows)),2560)
        self.assertEqual({r[0] for r in rows},{29})
        self.assertEqual({r[1] for r in rows},set(range(10)))
        self.assertEqual({r[2] for r in rows},set(range(256)))
        self.assertEqual({r[3] for r in rows},{0})
        self.assertEqual({r[4] for r in rows},{16})
        self.assertEqual({r[5] for r in rows},{0})
        self.assertEqual([(p['profile'],p['size']) for p in profiles],
            [('zero',0),('zero',1),('a_first',0),('a_first',1),
             ('b_full',0),('b_full',1),('c_full',0),('c_full',1),
             ('a_zero_c_full',0),('a_zero_c_full',1)])
        self.assertEqual({p['bltcon0'] for p in profiles},{0x0b00})
        self.assertEqual({(p['a'],p['b'],p['c']) for p in profiles},
            {(0,0,0),(0x8000,0,0),(0x8000,0xffff,0),
             (0x8000,0,0xffff),(0,0,0xffff)})
        pairs=[]
        for descriptor in rows:
            _,target,minterm,_,_,_=descriptor
            record=dict(launch_beam=0x2010,end_beam=0x2020,counter=minterm,
                icr=minterm,irq_beam=target,irq_level=minterm,
                saved_pc_offset=(target<<16)|minterm,aux=minterm,
                second_counter_or_beam=minterm^0x55,second_icr_or_level=minterm^0xaa)
            pairs.append((tuple(descriptor),record,record.copy()))
        report=compare_timing_sweeps._compare_line_truth_table(pairs)
        self.assertEqual(report['kind'],29)
        self.assertEqual(len(report['groups']),10)
        self.assertEqual(len(report['groups'][0]['minterm_trace']),256)
        with self.assertRaisesRegex(ValueError,'Invalid kind29 descriptor'):
            compare_timing_sweeps._compare_line_truth_table([((29,10,0,0,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind29 descriptor matrix'):
            compare_timing_sweeps._compare_line_truth_table(pairs[:-1])

    def test_kind30_stage_profiles_and_strict_dual_memory_comparison(self):
        rows=build_rom.trials(line_stage=True)
        profiles=build_rom.line_stage_profiles()
        self.assertEqual(len(rows),2380)
        self.assertEqual(len(set(rows)),2380)
        self.assertEqual({row[0] for row in rows},{30})
        self.assertEqual({row[2] for row in rows},{0x04,0x08,0x40,0x80,0x48})
        self.assertEqual({row[3] for row in rows},{0,1})
        self.assertEqual({row[4] for row in rows},set(range(17)))
        self.assertEqual(len(profiles),14)
        self.assertEqual([(p['c_first'],p['c_second'],p['useb']) for p in profiles],
            [(c1,c2,useb) for c1,c2 in ((0,0),(0,0xffff),(0xffff,0),
                (0x8000,0),(0x4000,0),(0x8000,0x8000),(0,0x8000))
             for useb in (0,1)])
        self.assertEqual({p['bltcon0'] for p in profiles},{0x0b00,0x0f00})
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        stage=source.split('line_stage_trial:',1)[1].split('divirq_handler:',1)[0]
        for snippet in ('move.w d3,$11000','move.w d4,$11050','move.w #$8000,$74(a6)',
                        'move.w #$0b00,d0','ori.w #$0400,d0',
                        'moveq #0,d1\n        move.w 6(a4),d1'):
            self.assertIn(snippet,stage)
        pairs=[]
        for descriptor in rows:
            _,target,minterm,phase,delay,_=descriptor
            row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|minterm,
                icr=delay,irq_beam=target,irq_level=phase,
                saved_pc_offset=(delay<<16)|minterm,aux=delay+1,
                second_counter_or_beam=delay+2,second_icr_or_level=delay+3)
            pairs.append((tuple(descriptor),row,row.copy()))
        report=compare_timing_sweeps._compare_line_stage(pairs)
        self.assertEqual(report['kind'],30)
        self.assertEqual(len(report['groups']),14*5*2)
        first=report['groups'][0]
        self.assertEqual(first['samples'],17)
        self.assertEqual(first['delay_trace'][0]['hardware_cpt_words'],[0x04,2,3])
        with self.assertRaisesRegex(ValueError,'Invalid kind30 descriptor'):
            compare_timing_sweeps._compare_line_stage([((30,14,0x04,0,0,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind30 descriptor matrix'):
            compare_timing_sweeps._compare_line_stage(pairs[:-1])

    def test_kind31_hidden_b_texture_shift_matrix_and_comparator(self):
        rows=build_rom.trials(line_b_hold=True)
        rows_dma=build_rom.trials(line_b_hold_dma=True)
        presets=build_rom.line_b_hold_presets(0)
        presets_dma=build_rom.line_b_hold_presets(1)
        variants=build_rom.line_b_hold_variants()
        self.assertEqual(len(presets),18*16+5)
        self.assertEqual(len(presets_dma),18*16+5)
        self.assertEqual(len(rows),2930)
        self.assertEqual(len(rows_dma),2930)
        self.assertEqual(len(set(rows)),2930)
        self.assertEqual(len(set(rows_dma)),2930)
        self.assertEqual({r[0] for r in rows},{31})
        self.assertEqual({r[0] for r in rows_dma},{32})
        self.assertEqual({r[2] for r in rows},{0,1})
        self.assertEqual({r[3] for r in rows},{1})
        self.assertEqual({r[4] for r in rows},{0,1,2,4,16})
        self.assertEqual({p['b_word'] for p in presets},
            {0,0xffff,*{1<<bit for bit in range(16)}})
        self.assertEqual({p['bshift'] for p in presets},set(range(16)))
        self.assertEqual({p['useb'] for p in presets},{0})
        self.assertEqual({p['useb'] for p in presets_dma},{1})
        for mode_presets in (presets,presets_dma):
            emitted=build_rom.line_b_hold_table(mode_presets)[1:]
            self.assertEqual(len(emitted),len(mode_presets))
            decoded=[[int(word.strip().lstrip('$'),16) for word in line.split('dc.w',1)[1].split(',')]
                     for line in emitted]
            for preset,words in zip(mode_presets,decoded):
                self.assertEqual(words,[preset['b_word'],preset['bltcon1'],
                    preset['useb'],int(preset['bdat_order']=='early')])
                self.assertEqual(words[1],(preset['bshift']<<12)|1)
        self.assertEqual(build_rom.line_b_hold_table(presets)[1:3],
                         ['        dc.w $0000,$0001,$0000,$0000',
                          '        dc.w $0000,$1001,$0000,$0000'])
        self.assertEqual(sum(p['bdat_order']=='early' for p in presets),5)
        self.assertEqual(sum(p['bdat_order']=='late' for p in presets),288)
        self.assertEqual([(v['a_data'],v['minterm']) for v in variants],[(0,0xcc),(0x8000,0xca)])
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        hold=source.split('line_b_hold_trial:',1)[1].split('divirq_handler:',1)[0]
        self.assertLess(hold.index('move.w d4,$42(a6)'),hold.index('move.w d3,$72(a6)'))
        early=hold.split('.hold_early_bdat:',1)[1].split('.hold_bdat_ready:',1)[0]
        self.assertLess(early.index('move.w d3,$72(a6)'),early.index('move.w d4,$42(a6)'))
        for snippet in ('move.w d1,d0','move.w 4(a4),d6','move.w d2,$74(a6)',
                        'move.w #$ffff,$44(a6)','move.w #$ffff,$46(a6)',
                        'move.w #-280,$64(a6)','move.l #$16000,$4c(a6)',
                        'moveq #0,d1\n        move.w 6(a4),d1'):
            self.assertIn(snippet,hold)
        for mode_rows,useb,kind in ((rows,0,31),(rows_dma,1,32)):
            pairs=[]
            for descriptor in mode_rows:
                _,target,variant,phase,delay,_=descriptor
                row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|delay,
                    icr=target,irq_beam=variant,irq_level=phase,
                    saved_pc_offset=(delay<<16)|target,aux=delay+1,
                    second_counter_or_beam=delay+2,second_icr_or_level=delay+3)
                pairs.append((tuple(descriptor),row,row.copy()))
            report=compare_timing_sweeps._compare_line_b_hold(pairs,useb)
            self.assertEqual(report['kind'],kind)
            self.assertEqual(len(report['groups']),586)
            self.assertEqual(report['groups'][0]['samples'],5)
            self.assertEqual(report['groups'][0]['delay_trace'][0]['hardware_cpt_words'],[0,2,3])
            with self.assertRaisesRegex(ValueError,f'Invalid kind{kind} descriptor'):
                compare_timing_sweeps._compare_line_b_hold([(tuple((kind,293,0,1,0,0)),{}, {})],useb)
            with self.assertRaisesRegex(ValueError,f'Incomplete kind{kind} descriptor matrix'):
                compare_timing_sweeps._compare_line_b_hold(pairs[:-1],useb)

    def test_kind33_b_mask_matrix_uses_pipeline_table_and_strict_descriptors(self):
        rows=build_rom.trials(line_b_mask=True)
        presets=build_rom.line_b_mask_presets()
        self.assertEqual(len(rows),1024)
        self.assertEqual(len(set(rows)),1024)
        self.assertEqual(len(presets),1024)
        self.assertEqual({r[0] for r in rows},{33})
        self.assertEqual({r[2] for r in rows},{0})
        self.assertEqual({r[3] for r in rows},{1})
        self.assertEqual({r[4] for r in rows},{16})
        self.assertEqual({p['ashift'] for p in presets},set(range(16)))
        self.assertEqual({p['bshift'] for p in presets},set(range(16)))
        self.assertEqual({p['use'] for p in presets},{5,7})
        self.assertEqual({p['size'] for p in presets},{0,1})
        self.assertEqual({p['a_word'] for p in presets},{0x8000})
        self.assertEqual({p['b_word'] for p in presets},{0})
        self.assertEqual({p['minterm_word'] for p in presets},{0xca})
        self.assertEqual({p['bltcon0']&0x0fff for p in presets},{0x0bca,0x0fca})
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        self.assertIn('cmpi.w #33,(a4)\n        beq .line_pipeline',source)
        pipeline=source.split('line_pipeline_trial:',1)[1].split('.pipeline_a:',1)[0]
        self.assertIn('lea line_pipeline_presets(pc),a0',pipeline)
        self.assertIn('moveq #0,d1\n        move.w 6(a4),d1',pipeline)
        pairs=[]
        for descriptor in rows:
            _,target,_,phase,delay,_=descriptor
            row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|target,
                icr=target,irq_beam=phase,irq_level=delay,
                saved_pc_offset=(target<<16)|delay,aux=target+1,
                second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(descriptor),row,row.copy()))
        report=compare_timing_sweeps._compare_line_b_mask(pairs)
        self.assertEqual(report['kind'],33)
        self.assertEqual(len(report['groups']),1024)
        self.assertEqual(report['groups'][0]['bltcon0'],'0x0bca')
        self.assertEqual(report['groups'][0]['hardware_cpt_words'],[16,2,3])
        with self.assertRaisesRegex(ValueError,'Invalid kind33 descriptor'):
            compare_timing_sweeps._compare_line_b_mask([((33,1024,0,1,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind33 descriptor matrix'):
            compare_timing_sweeps._compare_line_b_mask(pairs[:-1])

    def test_kind34_normal_b_prime_matrix_and_ordering(self):
        rows=build_rom.trials(line_b_prime=True)
        presets=build_rom.line_b_prime_presets()
        modes=build_rom.line_b_prime_modes()
        self.assertEqual(len(presets),256)
        self.assertEqual(len(rows),1024)
        self.assertEqual(len(set(rows)),1024)
        self.assertEqual({r[0] for r in rows},{34})
        self.assertEqual({r[1] for r in rows},set(range(256)))
        self.assertEqual({r[2] for r in rows},set(range(4)))
        self.assertEqual({r[3] for r in rows},{1})
        self.assertEqual({r[4] for r in rows},{16})
        self.assertEqual({p['ashift'] for p in presets},set(range(16)))
        self.assertEqual({p['bshift'] for p in presets},{0,1,8,15})
        self.assertEqual({p['use'] for p in presets},{5,7})
        self.assertEqual({p['size'] for p in presets},{0,1})
        self.assertEqual([(m['kind'],m.get('bltbdat')) for m in modes[:2]],
                         [('none',None),('register',0)])
        self.assertEqual([m['bltbdat'] for m in modes[2:]],[0,0xffff])
        source=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        prime=source.split('line_b_prime_trial:',1)[1].split('divirq_handler:',1)[0]
        for snippet in ('move.w #0,$42(a6)','move.w #0,$72(a6)',
                        'move.w #$05cc,$40(a6)','move.l #$18000,$4c(a6)',
                        'move.l #$19000,$54(a6)','move.w #$8240,$96(a6)',
                        'move.w #$0042,$58(a6)',
                        '.prime_busy: btst #6,$02(a6)','rept 8',
                        'bsr line_pipeline_trial'):
            self.assertIn(snippet,prime)
        self.assertLess(prime.index('move.w #$8240,$96(a6)'),
                        prime.index('move.w #$0042,$58(a6)'))
        self.assertLess(prime.index('.prime_busy:'),prime.index('bsr line_pipeline_trial'))
        pairs=[]
        for descriptor in rows:
            _,target,prime_mode,phase,delay,_=descriptor
            row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|prime_mode,
                icr=target,irq_beam=phase,irq_level=delay,
                saved_pc_offset=(target<<16)|prime_mode,aux=target+1,
                second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(descriptor),row,row.copy()))
        report=compare_timing_sweeps._compare_line_b_prime(pairs)
        self.assertEqual(report['kind'],34)
        self.assertEqual(len(report['groups']),1024)
        self.assertEqual(report['groups'][0]['prime_mode']['name'],'none')
        self.assertEqual(report['groups'][0]['hardware_cpt_words'],[0,2,3])
        with self.assertRaisesRegex(ValueError,'Invalid kind34 descriptor'):
            compare_timing_sweeps._compare_line_b_prime([((34,256,0,1,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind34 descriptor matrix'):
            compare_timing_sweeps._compare_line_b_prime(pairs[:-1])

    def test_kind35_equal_cycle_instruction_word_matrix(self):
        presets=build_rom.line_word_control_presets()
        variants=build_rom.line_word_control_variants()
        delays=build_rom.line_word_control_delays()
        rows=build_rom.trials(line_word_control=True)
        self.assertEqual(len(presets),128)
        self.assertEqual(len(rows),1920)
        self.assertEqual(len(set(rows)),1920)
        self.assertEqual({r[0] for r in rows},{35})
        self.assertEqual({r[1] for r in rows},set(range(128)))
        self.assertEqual({r[2] for r in rows},{0,1,2})
        self.assertEqual({r[3] for r in rows},{0})
        self.assertEqual({r[4] for r in rows},{0,1,2,4,16})
        self.assertEqual({r[5] for r in rows},{0})
        self.assertEqual([(v['name'],v['opcode'],v['cpu_cycles'],v['cck_cycles'])
            for v in variants],[('NOP',0x4e71,4,2),('MOVEQ_0_D6',0x7c00,4,2),
                                ('MOVEQ_m1_D6',0x7cff,4,2)])
        self.assertEqual([d['delay'] for d in delays],[0,1,2,4,16])
        self.assertEqual([p['profile'] for p in presets[::32]],
                         ['A0_CC','A8000_CA','A8000_ASH5_CA','A8000_ASH15_CA'])
        self.assertEqual({p['bshift'] for p in presets},set(range(16)))
        self.assertEqual({p['use'] for p in presets},{5,7})
        for p in presets:
            self.assertEqual(p['b_word'],0)
            self.assertEqual(p['c_word'],0)
            self.assertEqual(p['bltcon1'],(p['bshift']<<12)|1)
            expected_lf=(0xcc if p['profile']=='A0_CC' else 0xca)
            self.assertEqual(p['minterm_word'],expected_lf)
            self.assertEqual(p['bltsize'],0x0082)
            use_hw=((p['use']&1)<<11)|((p['use']&2)<<9)|((p['use']&4)<<7)
            self.assertEqual(p['bltcon0'],(p['ashift']<<12)|use_hw|0x0100|expected_lf)
        source_root=Path(__file__).resolve().parents[1]/'src/rom'
        experiment=(source_root/'experiment.asm').read_text()
        pipeline=experiment.split('line_pipeline_trial:',1)[1].split('line_truth_trial:',1)[0]
        for snippet in ('cmpi.w #35,(a4)','#$ff4000','cmpi.w #16,d0',
                        'move.w 4(a4),d1','lsl.w #4,d1'):
            self.assertIn(snippet,pipeline)
        observer=(source_root/'edge_kernel.asm').read_text()
        word_observer=observer.split('; Kind35 keeps',1)[1]
        for snippet in ('$ff4000+line_word_variant*$1000+line_word_slot*$100',
                        'moveq #0,d6','moveq #-1,d6','rept line_word_delay',
                        'move.w $11050,36(a4)','dcb.b $ff6500-*,0'):
            self.assertIn(snippet,word_observer)
        pairs=[]
        for descriptor in rows:
            _,target,variant,phase,delay,_=descriptor
            row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|variant,
                icr=target,irq_beam=phase,irq_level=delay,
                saved_pc_offset=target<<16,aux=target+1,
                second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(descriptor),row,row.copy()))
        report=compare_timing_sweeps._compare_line_word_control(pairs)
        self.assertEqual(report['kind'],35)
        self.assertEqual(len(report['groups']),1920)
        self.assertEqual(report['groups'][0]['instruction']['opcode'],0x4e71)
        self.assertEqual(report['groups'][0]['equal_cpu_cycles'],4)
        with self.assertRaisesRegex(ValueError,'Invalid kind35 descriptor'):
            compare_timing_sweeps._compare_line_word_control([((35,128,0,0,0,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind35 descriptor matrix'):
            compare_timing_sweeps._compare_line_word_control(pairs[:-1])

    def test_kind36_shifted_full_truth_matrix_and_literal_table(self):
        profiles=build_rom.line_shift_truth_profiles()
        rows=build_rom.trials(line_shift_truth=True)
        self.assertEqual(len(profiles),16)
        self.assertEqual(len(rows),4096)
        self.assertEqual(len(set(rows)),4096)
        self.assertEqual({r[0] for r in rows},{36})
        self.assertEqual({r[1] for r in rows},set(range(16)))
        self.assertEqual({r[2] for r in rows},set(range(256)))
        self.assertEqual({(r[3],r[4],r[5]) for r in rows},{(1,16,0)})
        self.assertEqual([p['bshift'] for p in profiles[:5]],[0,1,4,8,15])
        self.assertEqual([p['a'] for p in profiles],[0]*5+[0x8000]*10+[0])
        self.assertEqual([p['c'] for p in profiles],[0]*10+[0xffff]*5+[0])
        self.assertEqual([p['size'] for p in profiles], [1]*15+[0])
        for p in profiles:
            self.assertEqual(p['b'],0)
            self.assertEqual(p['useb'],0)
            self.assertEqual(p['bltcon0'],0x0b00)
            self.assertEqual(p['bltcon1'],(p['bshift']<<12)|1)
            self.assertEqual(p['bltsize'],0x0082 if p['size'] else 0x0042)
        build_root=Path(__file__).resolve().parents[1]/'build/rom'
        table=(build_root/'line_shift_truth_profiles.i').read_text()
        self.assertIn('dc.w $0000,$0000,$0000,$0082,$0001',table)
        self.assertIn('dc.w $8000,$0000,$0000,$0082,$f001',table)
        kernel=(build_root/'rom_kernel.bin').read_bytes()
        raw=(build_root/'a500-timing-rom.bin').read_bytes()
        kernel_offset=0x10000
        self.assertEqual(raw[kernel_offset:kernel_offset+len(kernel)],kernel)
        observer_offset=kernel_offset+(0xff3000-0xf90000)
        kernel_observer_offset=0x20000+(0xff3000-0xfb0000)
        self.assertEqual(raw[observer_offset:observer_offset+0x40],
                         kernel[kernel_observer_offset:kernel_observer_offset+0x40])
        src=Path(__file__).resolve().parents[1]/'src/rom/experiment.asm'
        asm=src.read_text()
        routine=asm.split('line_shift_truth_trial:',1)[1].split('line_stage_trial:',1)[0]
        for snippet in ('lsl.w #2,d0','add.w d1,d0','move.w d7,$42(a6)',
                        'move.l #$ff3000,a2','move.w d6,d5',
                        'include "line_shift_truth_profiles.i"'):
            self.assertIn(snippet,routine)
        pairs=[]
        for desc in rows:
            _,target,minterm,phase,delay,_=desc
            row=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|minterm,
                icr=target,irq_beam=phase,irq_level=delay,saved_pc_offset=target<<16,
                aux=target+1,second_counter_or_beam=target+2,
                second_icr_or_level=target+3)
            pairs.append((tuple(desc),row,row.copy()))
        report=compare_timing_sweeps._compare_line_shift_truth(pairs)
        self.assertEqual(report['kind'],36)
        self.assertEqual(len(report['groups']),4096)
        self.assertEqual(report['groups'][0]['bltcon1'],'0x0001')
        self.assertEqual(report['groups'][-1]['minterm'],255)
        with self.assertRaisesRegex(ValueError,'Invalid kind36 descriptor'):
            compare_timing_sweeps._compare_line_shift_truth([((36,16,0,1,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind36 descriptor matrix'):
            compare_timing_sweeps._compare_line_shift_truth(pairs[:-1])

    def test_kind37_length_wrap_matrix_literal_rom_table_and_observer(self):
        presets=build_rom.line_wrap_presets()
        rows=build_rom.trials(line_wrap=True)
        self.assertEqual(len(presets),1152)
        self.assertEqual(len(rows),1152)
        self.assertEqual(len(set(rows)),1152)
        self.assertEqual({r[0] for r in rows},{37})
        self.assertEqual({r[1] for r in rows},set(range(1152)))
        self.assertEqual({(r[2],r[3],r[4],r[5]) for r in rows},{(0,0,96,0)})
        self.assertEqual({p['bshift'] for p in presets},set(range(16)))
        self.assertEqual({p['pixels'] for p in presets},set(range(1,19)))
        self.assertEqual({p['useb'] for p in presets},{0,1})
        self.assertEqual({p['profile'] for p in presets},{'A0_CC','A8000_CA'})
        for p in presets:
            self.assertEqual(p['bltsize'],(p['pixels']<<6)|2)
            self.assertEqual(p['bltcon1'],(p['bshift']<<12)|1)
            self.assertEqual((p['a_data'],p['b_data'],p['c_data']),
                (0 if p['profile']=='A0_CC' else 0x8000,0,0))
            self.assertEqual(p['minterm'],0xcc if p['profile']=='A0_CC' else 0xca)
            use=5|(p['useb']<<1)
            use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)
            self.assertEqual(p['bltcon0'],use_hw|0x0100|p['minterm'])
        root=Path(__file__).resolve().parents[1]/'build/rom'
        manifest=json.loads((root/'manifest.json').read_text())
        # The shared build directory contains only the most recent ROM mode.
        # Keep functional kind37 descriptor/comparator checks above active
        # on every run; inspect mode-specific artifacts only for kind37 builds.
        if 'line_wrap_presets' in manifest:
            self.assertEqual(manifest['line_wrap_presets'],presets)
            literal=[]
            for line in (root/'line_wrap_presets.i').read_text().splitlines()[1:]:
                literal.append([int(word,16) for word in re.findall(r'\$([0-9a-fA-F]{4})',line)])
            expected=[[p[k]&0xffff for k in ('a_data','b_data','c_data','bltsize','bltcon1','bltcon0')]
                      for p in presets]
            self.assertEqual(literal,expected)
            encoded=[tuple(int(word) for word in re.findall(r'\d+',line))
                     for line in (root/'trials.i').read_text().splitlines()[1:]]
            self.assertEqual(encoded,[tuple(row) for row in rows])
            kernel=(root/'rom_kernel.bin').read_bytes()
            raw=(root/'a500-timing-rom.bin').read_bytes()
            rom_offset=0x10000+(0xff7000-0xf90000)
            kernel_offset=0x20000+(0xff7000-0xfb0000)
            stub=kernel[kernel_offset:kernel_offset+0x100]
            self.assertEqual(raw[rom_offset:rom_offset+len(stub)],stub)
            self.assertEqual(raw[rom_offset+len(stub):rom_offset+0x100],bytes(0x100-len(stub)))
            self.assertEqual(stub[:14],bytes.fromhex('2f074eb900fb00003e2e00063285'))
            self.assertEqual(stub[14:14+97*2],bytes.fromhex('4e71'*97))
            self.assertIn(bytes.fromhex('302e0002322e00063947000c3940001439410010'),stub)
            self.assertTrue(stub[14+97*2:14+97*2+4].startswith(bytes.fromhex('302e0002')))
        experiment=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        routine=experiment.split('line_wrap_trial:',1)[1].split('line_stage_trial:',1)[0]
        self.assertIn('lsl.w #2,d0',routine)
        self.assertIn('lsl.w #1,d0',routine)
        self.assertIn('add.w d1,d0',routine)
        self.assertIn('move.w d6,d5',routine)
        pairs=[]
        for desc in rows:
            _,target,variant,phase,delay,_=desc
            record=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x4000|(target&0xff),
                icr=target,irq_beam=phase,irq_level=delay,saved_pc_offset=target<<16,
                aux=target+1,second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(desc),record,record.copy()))
        report=compare_timing_sweeps._compare_line_wrap(pairs)
        self.assertEqual(report['kind'],37)
        self.assertEqual(len(report['groups']),1152)
        self.assertEqual(report['groups'][0]['pixels'],1)
        self.assertEqual(report['groups'][-1]['b_shift'],15)
        with self.assertRaisesRegex(ValueError,'Invalid kind37 descriptor'):
            compare_timing_sweeps._compare_line_wrap([((37,1152,0,0,96,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind37 descriptor matrix'):
            compare_timing_sweeps._compare_line_wrap(pairs[:-1])

    def test_kind38_c_cross_matrix_and_literal_table(self):
        presets=build_rom.line_c_cross_presets()
        rows=build_rom.trials(line_c_cross=True)
        self.assertEqual(len(presets),1536)
        self.assertEqual(len(rows),1536)
        self.assertEqual(len(set(rows)),1536)
        self.assertEqual({r[0] for r in rows},{38})
        self.assertEqual({r[1] for r in rows},set(range(1536)))
        self.assertEqual({(r[2],r[3],r[4],r[5]) for r in rows},{(0,1,16,0)})
        self.assertEqual({p['bshift'] for p in presets},set(range(16)))
        self.assertEqual({p['c_data'] for p in presets},{0,0xffff,0x8000,1,0x5555,0xaaaa})
        self.assertEqual({(p['useb'],p['usec']) for p in presets},
                         {(0,0),(0,1),(1,0),(1,1)})
        self.assertEqual({p['pixels'] for p in presets},{1,2})
        self.assertEqual({p['a_data'] for p in presets},{0,0x8000})
        for p in presets:
            self.assertIn(p['a_data'],(0,0x8000))
            self.assertEqual(p['b_data'],0)
            self.assertEqual((p['usea'],p['used'],p['minterm']),(1,1,0xcc))
            self.assertEqual(p['bltsize'],(p['pixels']<<6)|2)
            self.assertEqual(p['bltcon1'],(p['bshift']<<12)|1)
            use=1|8|(p['useb']<<1)|(p['usec']<<2)
            use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)|((use&8)<<5)
            self.assertEqual(p['bltcon0'],use_hw|0x0100|0xcc)
        root=Path(__file__).resolve().parents[1]/'build/rom'
        manifest=json.loads((root/'manifest.json').read_text())
        if 'line_c_cross_presets' in manifest:
            self.assertEqual(manifest['line_c_cross_presets'],presets)
            literal=[]
            for line in (root/'line_c_cross_presets.i').read_text().splitlines()[1:]:
                literal.append([int(word,16) for word in re.findall(r'\$([0-9a-fA-F]{4})',line)])
            expected=[[p[k]&0xffff for k in ('a_data','b_data','c_data','bltsize','bltcon1','bltcon0')]
                      for p in presets]
            self.assertEqual(literal,expected)
            kernel=(root/'rom_kernel.bin').read_bytes()
            raw=(root/'a500-timing-rom.bin').read_bytes()
            self.assertEqual(raw[0x10000:0x10000+len(kernel)],kernel)
            raw_obs=0x10000+(0xff3000-0xf90000)
            kernel_obs=0x20000+(0xff3000-0xfb0000)
            self.assertEqual(raw[raw_obs:raw_obs+0x40],kernel[kernel_obs:kernel_obs+0x40])
        experiment=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        self.assertIn('moveq #5,d0',experiment)
        self.assertIn('dbra d0,.desc',experiment)
        routine=experiment.split('line_wrap_trial:',1)[1].split('line_stage_trial:',1)[0]
        self.assertIn('cmpi.w #38,(a4)',routine)
        self.assertIn('movea.l #line_c_cross_presets,a0',routine)
        self.assertIn('move.l #$ff3000,a2',routine)
        pairs=[]
        for desc in rows:
            _,target,variant,phase,delay,_=desc
            dmaconr=0x2000 if target==0 else 0x4000 if target==1 else (target&0x1fff)
            rec=dict(launch_beam=0x2010,end_beam=0x2020,counter=dmaconr,
                icr=target,irq_beam=phase,irq_level=delay,saved_pc_offset=target<<16,
                aux=target+1,second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(desc),rec,rec.copy()))
        report=compare_timing_sweeps._compare_line_c_cross(pairs)
        self.assertEqual(report['kind'],38)
        self.assertEqual(len(report['groups']),1536)
        self.assertEqual(report['groups'][0]['c_data'],'0x0000')
        self.assertEqual(report['groups'][-1]['c_data'],'0xaaaa')
        with self.assertRaisesRegex(ValueError,'Invalid kind38 descriptor'):
            compare_timing_sweeps._compare_line_c_cross([((38,1536,0,1,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind38 descriptor matrix'):
            compare_timing_sweeps._compare_line_c_cross(pairs[:-1])



    def test_kind39_isolated_c_words_and_dat_seed(self):
        presets=build_rom.line_c_word_presets()
        rows=build_rom.trials(line_c_words=True)
        self.assertEqual(len(presets),344)
        self.assertEqual(len(rows),344)
        self.assertEqual(len(set(rows)),344)
        self.assertEqual({r[0] for r in rows},{39})
        self.assertEqual({r[1] for r in rows},set(range(344)))
        self.assertEqual({(r[2],r[3],r[4],r[5]) for r in rows},{(0,1,16,0)})
        self.assertEqual({p['bshift'] for p in presets},{4})
        onehot={0,0xffff,*[1<<bit for bit in range(16)]}
        uniform=onehot|{0x5555,0xaaaa}
        self.assertEqual({p['c_first'] for p in presets},uniform)
        self.assertEqual({p['c_second'] for p in presets},uniform)
        self.assertEqual({(p['useb'],p['usec']) for p in presets},
                         {(0,0),(0,1),(1,0),(1,1)})
        self.assertEqual({p['pixels'] for p in presets},{1,2})
        register_seeds={0xffff,0x5555,0xaaaa,0x8000,0x0001}
        for p in presets:
            self.assertEqual((p['a_data'],p['b_data'],p['ashift']),(0,0,0))
            self.assertEqual((p['usea'],p['used'],p['minterm']),(1,1,0xcc))
            self.assertEqual(p['bltsize'],(p['pixels']<<6)|2)
            self.assertEqual(p['bltcon1'],0x4001)
            use=1|8|(p['useb']<<1)|(p['usec']<<2)
            use_hw=((use&1)<<11)|((use&2)<<9)|((use&4)<<7)|((use&8)<<5)
            self.assertEqual(p['bltcon0'],use_hw|0x0100|0xcc)
            if p['profile'].startswith('cdata_'):
                self.assertEqual((p['c_first'],p['c_second']),(0,0))
                self.assertIn(p['c_data'],register_seeds)
            else:
                self.assertEqual(p['c_data'],0)
        root=Path(__file__).resolve().parents[1]/'build/rom'
        manifest=json.loads((root/'manifest.json').read_text())
        if 'line_c_word_presets' in manifest:
            self.assertEqual(manifest['line_c_word_presets'],presets)
            self.assertEqual(manifest['line_c_word_observer']['c_memory'],[0x11000,0x11050])
            literal=[]
            for line in (root/'line_c_word_presets.i').read_text().splitlines()[1:]:
                literal.append([int(word,16) for word in re.findall(r'\$([0-9a-fA-F]{4})',line)])
            expected=[[p[k]&0xffff for k in
                ('c_first','c_second','c_data','bltsize','bltcon1','bltcon0')] for p in presets]
            self.assertEqual(literal,expected)
            kernel=(root/'rom_kernel.bin').read_bytes()
            raw=(root/'a500-timing-rom.bin').read_bytes()
            self.assertEqual(raw[0x10000:0x10000+len(kernel)],kernel)
            raw_obs=0x10000+(0xff3000-0xf90000)
            kernel_obs=0x20000+(0xff3000-0xfb0000)
            self.assertEqual(raw[raw_obs:raw_obs+0x40],kernel[kernel_obs:kernel_obs+0x40])
        experiment=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        routine=experiment.split('line_wrap_trial:',1)[1].split('line_stage_trial:',1)[0]
        for snippet in ('movea.l #line_c_word_presets,a0','move.w d3,$11000',
                        'move.w d4,$11050','move.w d5,$70(a6)','move.w #0,$74(a6)',
                        'move.w #0,$72(a6)','move.l #$11000,$48(a6)'):
            self.assertIn(snippet,routine)
        pairs=[]
        for desc in rows:
            _,target,variant,phase,delay,_=desc
            dmaconr=0x2000 if target==0 else 0x4000 if target==1 else (target&0x1fff)
            rec=dict(launch_beam=0x2010,end_beam=0x2020,counter=dmaconr,
                icr=target,irq_beam=phase,irq_level=delay,saved_pc_offset=target<<16,
                aux=target+1,second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(desc),rec,rec.copy()))
        report=compare_timing_sweeps._compare_line_c_words(pairs)
        self.assertEqual(report['kind'],39)
        self.assertEqual(len(report['groups']),344)
        self.assertEqual(report['groups'][0]['c_first'],'0x0000')
        self.assertTrue(report['groups'][0]['hardware_bzero'])
        self.assertFalse(report['groups'][1]['hardware_bzero'])
        with self.assertRaisesRegex(ValueError,'Invalid kind39 descriptor'):
            compare_timing_sweeps._compare_line_c_words([((39,344,0,1,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind39 descriptor matrix'):
            compare_timing_sweeps._compare_line_c_words(pairs[:-1])


    def test_kind40_cold_mask_tomography_matrix_and_comparator(self):
        presets=build_rom.line_c_tomography_presets()
        rows=build_rom.trials(line_c_tomography=True)
        self.assertEqual((len(presets),len(rows)),(1344,1344))
        self.assertEqual(len(set(rows)),1344)
        self.assertEqual({r[0] for r in rows},{40})
        self.assertEqual({r[2] for r in rows},{4})
        self.assertEqual({r[3:] for r in rows},{(1,16,0)})
        patterns={0,0xffff,0x5555,0xaaaa,*[1<<bit for bit in range(16)],
                  *[0xffff^(1<<bit) for bit in range(16)]}
        primary=presets[:36*16*2]
        self.assertEqual(len(primary),1152)
        self.assertEqual({p['c_first'] for p in primary},patterns)
        self.assertEqual({p['ashift'] for p in primary},set(range(16)))
        self.assertEqual({(p['useb'],p['usec']) for p in primary},{(0,1)})
        controls=presets[1152:]
        self.assertEqual(len(controls),192)
        self.assertEqual({p['c_first'] for p in controls},{0,0xffff})
        self.assertEqual({(p['useb'],p['usec']) for p in controls},
                         {(0,0),(1,0),(1,1)})
        for p in presets:
            self.assertEqual((p['a_data'],p['b_data'],p['c_second'],p['c_data']),
                             (0x8000,0,0,0))
            self.assertEqual(p['bltcon1'],0x4001)
            self.assertEqual(p['bltsize'],(p['pixels']<<6)|2)
            self.assertEqual(p['bltcon0'],(p['ashift']<<12)|
                (((1<<11)|(p['useb']<<10)|(p['usec']<<9)|(1<<8)))|0xc0)
        shifted=build_rom.line_c_tomography_presets(3)
        self.assertEqual({p['bshift'] for p in shifted},{3})
        self.assertEqual({p['bltcon1'] for p in shifted},{0x3001})
        self.assertEqual({r[2] for r in build_rom.trials(line_c_tomography=True,
            line_c_tomography_shift=3)},{3})
        manifest=json.loads((Path(__file__).resolve().parents[1]/'build/rom/manifest.json').read_text())
        if 'line_c_tomography_presets' in manifest:
            active_shift=manifest['line_c_tomography_observer']['bshift']
            active_presets=build_rom.line_c_tomography_presets(active_shift)
            self.assertEqual(manifest['line_c_tomography_presets'],active_presets)
            root=Path(__file__).resolve().parents[1]/'build/rom'
            literal=[[int(word,16) for word in re.findall(r'\$([0-9a-fA-F]{4})',line)]
                for line in (root/'line_c_tomography_presets.i').read_text().splitlines()[1:]]
            expected=[[p[k]&0xffff for k in ('c_first','c_second','c_data','bltsize','bltcon1','bltcon0')]
                for p in active_presets]
            self.assertEqual(literal,expected)
            kernel=(root/'rom_kernel.bin').read_bytes()
            raw=(root/'a500-timing-rom.bin').read_bytes()
            self.assertEqual(raw[0x10000:0x10000+len(kernel)],kernel)
        asm=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        dispatch=asm.split('main:',1)[1].split('.recorded:',1)[0]
        handlers={28:'.line_pipeline',29:'.line_truth',30:'.line_stage',
            31:'.line_b_hold',32:'.line_b_hold',33:'.line_pipeline',
            34:'.line_b_prime',35:'.line_word_control',36:'.line_shift_truth',
            37:'.line_wrap',38:'.line_wrap',39:'.line_wrap',40:'.line_wrap'}
        for kind,handler in handlers.items():
            self.assertRegex(dispatch,rf'cmpi\.w #{kind},\(a4\)\s+beq(?:\.s)?\s+{re.escape(handler)}')
        routine=asm.split('line_wrap_trial:',1)[1].split('line_stage_trial:',1)[0]
        for snippet in ('cmpi.w #40,(a4)','movea.l #line_c_tomography_presets,a0',
                        'move.w d3,$11000','move.w d4,$11050','move.w #$ffff,$44(a6)',
                        'move.w #$ffff,$46(a6)','move.w #$8000,$74(a6)',
                        'move.w #0,$72(a6)'):
            self.assertIn(snippet,routine)
        tomo_setup=routine.split('.wrap_data_tomography:',1)[1].split('.wrap_data_ready:',1)[0]
        self.assertNotIn('move.w d3,$74(a6)',tomo_setup)
        self.assertNotIn('move.w d4,$72(a6)',tomo_setup)
        pairs=[]
        for desc in rows:
            _,target,variant,phase,delay,_=desc
            rec=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x2000 if target==0 else 0,
                icr=target,irq_beam=phase,irq_level=delay,saved_pc_offset=target<<16,
                aux=target+1,second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(desc),rec,rec.copy()))
        report=compare_timing_sweeps._compare_line_c_tomography(pairs)
        self.assertEqual((report['kind'],report['bshift'],len(report['groups'])),(40,4,1344))
        self.assertEqual(report['groups'][0]['c_first'],'0x0000')
        self.assertTrue(report['groups'][0]['hardware_bzero'])
        with self.assertRaisesRegex(ValueError,'Invalid kind40 descriptor'):
            compare_timing_sweeps._compare_line_c_tomography([((40,1344,4,1,16,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind40 descriptor matrix'):
            compare_timing_sweeps._compare_line_c_tomography(pairs[:-1])


    def test_kind41_c_onset_one_cold_matrix_and_dispatch(self):
        presets=build_rom.line_c_onset_presets()
        rows=build_rom.trials(line_c_onset=True)
        self.assertEqual((len(presets),len(rows)),(76,2584))
        self.assertEqual(len(set(rows)),2584)
        self.assertEqual({r[0] for r in rows},{41})
        self.assertEqual({r[1] for r in rows},set(range(76)))
        self.assertEqual({r[2] for r in rows},{4})
        self.assertEqual({(r[3],r[4],r[5]) for r in rows},
                         {(phase,delay,0) for phase in (0,1) for delay in range(17)})
        cold={0,0xffff,*[0xffff^(1<<bit) for bit in range(16)]}
        primary=presets[:72]
        self.assertEqual({p['c_first'] for p in primary},cold)
        self.assertEqual({p['a_data'] for p in primary},{0,0x8000})
        self.assertEqual({p['pixels'] for p in primary},{1,2})
        self.assertEqual({p['minterm'] for p in primary},{0xcc})
        controls=presets[72:]
        self.assertEqual(len(controls),4)
        self.assertEqual({(p['c_first'],p['minterm']) for p in controls},
                         {(0,0x0c),(0,0xc0),(0xffff,0x0c),(0xffff,0xc0)})
        for p in presets:
            self.assertEqual((p['b_data'],p['cdat'],p['c_second'],p['ashift']),
                             (0,0,0,0))
            self.assertEqual((p['usea'],p['useb'],p['usec'],p['used']),(1,0,1,1))
            self.assertEqual(p['bltcon1'],0x4001)
            self.assertEqual(p['bltsize'],(p['pixels']<<6)|2)
            self.assertEqual(p['bltcon0'],0x0b00|p['minterm'])
        self.assertEqual({p['bshift'] for p in build_rom.line_c_onset_presets(6)},{6})
        self.assertEqual({r[2] for r in build_rom.trials(line_c_onset=True,
            line_c_onset_shift=6)},{6})
        manifest=json.loads((Path(__file__).resolve().parents[1]/'build/rom/manifest.json').read_text())
        if 'line_c_onset_presets' in manifest:
            active_shift=manifest['line_c_onset_observer']['bshift']
            active_presets=build_rom.line_c_onset_presets(active_shift)
            self.assertEqual(manifest['line_c_onset_presets'],active_presets)
            self.assertEqual(manifest['line_c_onset_observer']['table_word3'],'a_data')
            root=Path(__file__).resolve().parents[1]/'build/rom'
            literal=[[int(word,16) for word in re.findall(r'\$([0-9a-fA-F]{4})',line)]
                for line in (root/'line_c_onset_presets.i').read_text().splitlines()[1:]]
            expected=[[p[k]&0xffff for k in
                ('c_first','c_second','a_data','bltsize','bltcon1','bltcon0')]
                for p in active_presets]
            self.assertEqual(literal,expected)
            kernel=(root/'rom_kernel.bin').read_bytes()
            raw=(root/'a500-timing-rom.bin').read_bytes()
            self.assertEqual(raw[0x10000:0x10000+len(kernel)],kernel)
        asm=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        dispatch=asm.split('main:',1)[1].split('.recorded:',1)[0]
        self.assertRegex(dispatch,r'cmpi\.w #41,\(a4\)\s+beq(?:\.s)?\s+\.line_wrap')
        routine=asm.split('line_wrap_trial:',1)[1].split('line_stage_trial:',1)[0]
        for snippet in ('cmpi.w #41,(a4)','movea.l #line_c_onset_presets,a0',
            'move.w d5,$74(a6)','move.w #0,$72(a6)','move.w #0,$70(a6)',
            'move.w d3,$11000','move.w d4,$11050','addi.l #$ff0000,d0'):
            self.assertIn(snippet,routine)
        onset_setup=routine.split('.wrap_data_onset:',1)[1].split('.wrap_data_ready:',1)[0]
        self.assertNotIn('move.w d3,$74(a6)',onset_setup)
        self.assertNotIn('move.w d4,$72(a6)',onset_setup)
        pairs=[]
        for desc in rows:
            _,target,variant,phase,delay,_=desc
            rec=dict(launch_beam=0x2010,end_beam=0x2020,counter=0x2000 if target==0 else 0,
                icr=target,irq_beam=phase,irq_level=delay,saved_pc_offset=target<<16,
                aux=target+1,second_counter_or_beam=target+2,second_icr_or_level=target+3)
            pairs.append((tuple(desc),rec,rec.copy()))
        report=compare_timing_sweeps._compare_line_c_onset(pairs)
        self.assertEqual((report['kind'],report['bshift'],len(report['groups'])),(41,4,2584))
        self.assertEqual(report['groups'][0]['observer_address'],0xff0000)
        self.assertTrue(report['groups'][0]['hardware_bzero'])
        with self.assertRaisesRegex(ValueError,'Invalid kind41 descriptor'):
            compare_timing_sweeps._compare_line_c_onset([((41,76,4,0,0,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind41 descriptor matrix'):
            compare_timing_sweeps._compare_line_c_onset(pairs[:-1])


    def test_kind42_in_blit_dmaconr_read_sequence(self):
        presets=build_rom.line_c_read_sequence_presets()
        rows=build_rom.trials(line_c_read_sequence=True)
        self.assertEqual((len(presets),len(rows)),(10,160))
        self.assertEqual(len(set(rows)),160)
        self.assertEqual({r[0] for r in rows},{42})
        self.assertEqual({r[1] for r in rows},set(range(10)))
        self.assertEqual({r[2] for r in rows},{0,1})
        self.assertEqual({r[3:5] for r in rows},{(0,0)})
        self.assertEqual({r[5] for r in rows},set(range(8)))
        self.assertEqual({p['c_first'] for p in presets},{0,0xffff,0xfffe,0xbfff,0xfeff})
        self.assertEqual({p['a_data'] for p in presets},{0,0x8000})
        self.assertEqual({p['profile']:p['c_first'] for p in presets if p['profile'].startswith('cold_')},
                         {'cold_bit0':0xfffe,'cold_bit14':0xbfff,'cold_bit8':0xfeff})
        for p in presets:
            self.assertEqual((p['c_second'],p['b_data'],p['cdat'],p['bshift'],
                              p['minterm'],p['bltsize'],p['bltcon1'],p['bltcon0']),
                             (0,0,0,4,0xcc,0x0082,0x4001,0x0bcc))
        manifest=json.loads((Path(__file__).resolve().parents[1]/'build/rom/manifest.json').read_text())
        if 'line_c_read_sequence_presets' in manifest:
            self.assertEqual(manifest['line_c_read_sequence_presets'],presets)
            observer=manifest['line_c_read_sequence_observer']
            self.assertEqual((observer['early'],observer['postbusy']),(0xff7400,0xff7500))
            self.assertEqual(observer['samples'],dict(offset=20,count=8,stride=2,source='DMACONR'))
            self.assertEqual(observer['sample6_offset32'],'status')
            root=Path(__file__).resolve().parents[1]/'build/rom'
            literal=[[int(word,16) for word in re.findall(r'\$([0-9a-fA-F]{4})',line)]
                for line in (root/'line_c_read_sequence_presets.i').read_text().splitlines()[1:]]
            expected=[[p[k]&0xffff for k in
                ('c_first','c_second','a_data','bltsize','bltcon1','bltcon0')] for p in presets]
            self.assertEqual(literal,expected)
            kernel=(root/'rom_kernel.bin').read_bytes()
            raw=(root/'a500-timing-rom.bin').read_bytes()
            self.assertEqual(raw[0x10000:0x10000+len(kernel)],kernel)
            for address in (0xff7400,0xff7500):
                ro=0x10000+(address-0xf90000);ko=0x20000+(address-0xfb0000)
                check_bytes=min(0x80,len(kernel)-ko)
                self.assertEqual(raw[ro:ro+check_bytes],kernel[ko:ko+check_bytes])
        asm=(Path(__file__).resolve().parents[1]/'src/rom/experiment.asm').read_text()
        dispatch=asm.split('main:',1)[1].split('.recorded:',1)[0]
        self.assertRegex(dispatch,r'cmpi\.w #42,\(a4\)\s+beq(?:\.s)?\s+\.line_c_read_sequence')
        routine=asm.split('line_c_read_sequence_trial:',1)[1].split('include "line_c_read_sequence_presets.i"',1)[0]
        for text in ('movea.l #line_c_read_sequence_presets,a0','move.w d5,$74(a6)',
                     'move.w #0,$72(a6)','move.w #0,$70(a6)',
                     'move.w d3,$11000','move.w d4,$11050','move.w d6,d5',
                     'movea.l #$ff7400,a2','movea.l #$ff7500,a2','jsr sync_beam'):
            self.assertIn(text,routine)
        self.assertLess(routine.index('move.w #$8240,$96(a6)'),routine.index('jsr sync_beam'))
        self.assertLess(routine.index('jsr sync_beam'),routine.index('movea.l #$ff7400,a2'))
        edge=(Path(__file__).resolve().parents[1]/'src/rom/edge_kernel.asm').read_text()
        for label in ('line_c_read_early:','line_c_read_postbusy:'):
            body=edge.split(label,1)[1].split('\n        dcb.b $ff7',1)[0]
            read_lines=[line.strip() for line in body.splitlines()
                if re.fullmatch(r'move\.w \$02\(a6\),d[0-7]',line.strip())]
            self.assertEqual(read_lines,[f'move.w $02(a6),d{i}' for i in range(8)])
            self.assertIn('movem.w d0-d7,20(a4)',body)
            self.assertIn('move.w 6(a6),36(a4)',body)
            self.assertIn('move.w 6(a6),16(a4)',body)
            self.assertIn('move.w 6(a6),38(a4)',body)
            first=body.index('move.w $02(a6),d0')
            last=body.index('move.w $02(a6),d7')
            between=[line.strip() for line in body[first:last+len('move.w $02(a6),d7')].splitlines()]
            self.assertEqual(between,[f'move.w $02(a6),d{i}' for i in range(8)])
        pairs=[]
        for desc in rows:
            _,target,observer,phase,delay,repeat=desc
            samples=[(target+repeat+i)&0xffff for i in range(8)]
            samples[6]=0x2000 if target==0 else 0x4000
            rec=dict(launch_beam=0x2010,end_beam=0x2020,counter=samples[0],icr=samples[1],
                irq_beam=samples[2],irq_level=samples[3],saved_pc_offset=(samples[4]<<16)|samples[5],
                status=samples[6],aux=samples[7],second_counter_or_beam=0x2030,
                second_icr_or_level=0x2040)
            pairs.append((tuple(desc),rec,rec.copy()))
        report=compare_timing_sweeps._compare_line_c_read_sequence(pairs)
        self.assertEqual((report['kind'],len(report['groups'])),(42,160))
        self.assertEqual(report['groups'][0]['hardware_samples'][6],0x2000)
        self.assertTrue(report['groups'][0]['hardware_sample6_bzero'])
        self.assertEqual(report['record_layout']['presample_beam'],36)
        with self.assertRaisesRegex(ValueError,'Invalid kind42 descriptor'):
            compare_timing_sweeps._compare_line_c_read_sequence([((42,10,0,0,0,0),{}, {})])
        with self.assertRaisesRegex(ValueError,'Incomplete kind42 descriptor matrix'):
            compare_timing_sweeps._compare_line_c_read_sequence(pairs[:-1])

    def test_kind44_line_c_activity_descriptor_and_kernel(self):
        presets=build_rom.line_c_activity_presets()
        rows=build_rom.trials(line_c_activity=True)
        self.assertEqual((len(presets),len(rows)),(10,320))
        self.assertEqual(len(set(rows)),320)
        self.assertEqual({row[0] for row in rows},{44})
        self.assertEqual({row[1] for row in rows},set(range(10)))
        self.assertEqual({row[2] for row in rows},{0,1})
        self.assertEqual({row[3] for row in rows},{0})
        self.assertEqual({row[4] for row in rows},{0,1})
        self.assertEqual({row[5] for row in rows},set(range(8)))
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)

        root=Path(__file__).resolve().parents[1]
        asm=(root/'src/rom/experiment.asm').read_text()
        dispatch=asm.split('main:',1)[1].split('.recorded:',1)[0]
        self.assertRegex(dispatch,r'cmpi\.w #44,\(a4\)\s+beq(?:\.s)?\s+\.line_c_activity')
        routine=asm.split('line_c_activity_trial:',1)[1].split('include "line_c_activity_presets.i"',1)[0]
        self.assertLess(routine.index('move.w #$8240,$96(a6)'),
                        routine.index('move.w #$0088,$58(a6)'))
        fill_a=routine.index('.activity_fill_a:')
        self.assertGreater(routine.rfind('moveq #0,d0',0,fill_a),
                           routine.index('move.w (a0)+,d2'))
        self.assertLess(routine.index('activity_prime_busy'),routine.index('activity_prime_done'))
        self.assertLess(routine.index('.activity_unprimed:'),routine.index('move.w d5,$74(a6)'))
        self.assertLess(routine.index('move.w d3,$11000'),routine.index('jsr sync_beam'))

        edge=(root/'src/rom/edge_kernel.asm').read_text()
        for label in ('line_c_activity_direct:','line_c_activity_poll:'):
            body=edge.split(label,1)[1].split('\n        dcb.b $ff7',1)[0]
            read_lines=[line.strip() for line in body.splitlines()
                if re.fullmatch(r'move\.w \$02\(a6\),d[0-7]',line.strip())]
            self.assertEqual(read_lines,[f'move.w $02(a6),d{i}' for i in range(8)])
            self.assertIn('move.w a2,12(a4)',body)
            self.assertLess(body.index('move.w $02(a6),d7'),body.index('move.w a2,12(a4)'))
            self.assertEqual(body.count('move.w d7,a1'),0)


    def test_kind45_line_c_history_descriptor_and_kernel(self):
        patterns=build_rom.line_c_history_patterns()
        rows=build_rom.trials(line_c_history=True)
        self.assertEqual((len(patterns),len(rows)),(6,960))
        self.assertEqual(len(set(rows)),960)
        self.assertEqual({row[0] for row in rows},{45})
        self.assertEqual({row[1] for row in rows},set(range(10)))
        self.assertEqual({row[2] for row in rows},set(range(6)))
        self.assertEqual({row[3] for row in rows},{0})
        self.assertEqual({row[4] for row in rows},{0,1})
        self.assertEqual({row[5] for row in rows},set(range(8)))
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        self.assertEqual([(p['a'],p['b'],p['c']) for p in patterns], [
            (0,0,0),(0,0,0),(0xffff,0,0),(0,0xffff,0),
            (0,0,0xffff),(0xffff,0xffff,0xffff)])
        self.assertEqual([p['name'] for p in patterns],
                         ['none','all-zero','a-ffff','b-ffff','c-ffff','all-ffff'])
        self.assertEqual([p['blit'] for p in patterns],[False,True,True,True,True,True])
        subset=build_rom.trials(line_c_history=True,line_c_history_subset=[5])
        self.assertEqual(len(subset),160)
        self.assertEqual({row[2] for row in subset},{5})

        root=Path(__file__).resolve().parents[1]
        asm=(root/'src/rom/experiment.asm').read_text()
        dispatch=asm.split('main:',1)[1].split('.recorded:',1)[0]
        self.assertRegex(dispatch,r'cmpi\.w #45,\(a4\)\s+beq(?:\.s)?\s+\.line_c_history')
        routine=asm.split('line_c_history_trial:',1)[1].split('include "line_c_history_presets.i"',1)[0]
        self.assertIn('lea line_c_history_patterns,a2',routine)
        self.assertIn('include \"line_c_history_patterns.i\"',asm)
        for label in ('.history_fill_a:', '.history_fill_b:', '.history_fill_c:'):
            self.assertIn(label,routine)
        self.assertLess(routine.index('history_prime_busy'),routine.index('history_prime_done'))
        self.assertLess(routine.index('.history_reset_c:'),routine.index('move.w d3,$11000'))
        self.assertIn('history_clear_prime_d:',routine)
        edge=(root/'src/rom/edge_kernel.asm').read_text()
        for label in ('line_c_activity_direct:','line_c_activity_poll:'):
            body=edge.split(label,1)[1].split('\n        dcb.b $ff7',1)[0]
            reads=[line.strip() for line in body.splitlines()
                   if re.fullmatch(r'move\.w \$02\(a6\),d[0-7]',line.strip())]
            self.assertEqual(reads,[f'move.w $02(a6),d{i}' for i in range(8)])

    def test_cpu_trial_coverage(self):
        rows=build_rom.trials(cpu=True)
        self.assertEqual(len(rows),1792)
        self.assertEqual(len(set(rows)),1792)
        self.assertEqual({r[0] for r in rows},{18})
        self.assertEqual({r[1] for r in rows},set(range(7)))
        self.assertEqual({r[2] for r in rows},set(range(8)))
        self.assertEqual({r[3] for r in rows},set(range(8)))
        self.assertEqual({r[4] for r in rows},{1,2,16,64})

    def test_focused_trial_coverage(self):
        rows=build_rom.trials(focused=True)
        self.assertEqual(len(rows),576)
        self.assertEqual(len(set(rows)),576)
        self.assertEqual(sum(r[0]==5 for r in rows),320)
        self.assertEqual(sum(r[0]==10 for r in rows),256)
        self.assertEqual({r[2] for r in rows if r[0]==10},{5,6})

    def test_trial_coverage_and_ram_bound(self):
        rows=build_rom.trials();self.assertEqual(len(rows),6240)
        self.assertEqual(len(set(rows)),6240)
        self.assertLess(0x40000+64+len(rows)*40,0x7e000)
        for source in range(4):
            selected=[r for r in rows if r[0]==10 and r[1]==source]
            self.assertEqual(len(selected),960)

if __name__=='__main__': unittest.main()
