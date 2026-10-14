import importlib.util,struct,unittest
from pathlib import Path
import build_rom,rom_results,compare_phase,compare_continuous

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
        routine=source.split('line_logic_trial:',1)[1].split('divirq_handler:',1)[0]
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
