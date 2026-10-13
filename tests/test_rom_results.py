import importlib.util,struct,unittest
from pathlib import Path
import build_rom,rom_results,compare_phase

class RomFormatTests(unittest.TestCase):
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
