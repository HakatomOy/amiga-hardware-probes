from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import compare_timing_sweeps as compare
import rom_results


class TimingSweepComparisonTests(unittest.TestCase):
    def _write_capture(self, root, name, descriptors, source_id='11' * 32, mutate=None):
        """Write the smallest complete checksummed capture accepted by the strict loader."""
        folder = root / name
        folder.mkdir()
        data = bytearray(64 + 40 * len(descriptors))
        data[:8] = b'A5RBCP01'
        struct.pack_into('>HHIII', data, 8, 1, 40, len(descriptors), len(data), 0)
        data[24:56] = bytes.fromhex(source_id)
        struct.pack_into('>4H', data, 56, 0xa000, 0xffff, 1, 1)
        records = []
        for index, descriptor in enumerate(descriptors):
            values = dict(launch_beam=0x4242, launch_ref=0x1000,
                          end_beam=0x424a, end_ref=0x0ff0, counter=0,
                          icr=0, irq_beam=0x424b, irq_level=1,
                          pc_hi=0, pc_lo=0x0100, status=0, aux=0,
                          second_counter_or_beam=0x424c, second_icr_or_level=0)
            if mutate:
                values.update(mutate(index, descriptor) or {})
            raw = list(descriptor) + [values[name] for name in rom_results.FIELDS[6:]]
            struct.pack_into('>20H', data, 64 + 40 * index, *raw)
            records.append(list(descriptor))
        words = struct.unpack('>' + str(len(data) // 4) + 'I', data)
        struct.pack_into('>I', data, 20, (-sum(words)) & 0xffffffff)
        (folder / 'results.bin').write_bytes(data)
        (folder / 'build-manifest.json').write_text(json.dumps({
            'source_id': source_id, 'trial_count': len(descriptors), 'trials': records
        }))
        return folder

    def _pair(self, temp, descriptors, hardware_mutate=None, emulator_mutate=None,
              hardware_source='11' * 32, emulator_source='11' * 32):
        root = Path(temp)
        hw = self._write_capture(root, 'hardware', descriptors, hardware_source, hardware_mutate)
        emu = self._write_capture(root, 'emulator', descriptors, emulator_source, emulator_mutate)
        return hw, emu

    def test_kind18_reports_cpu_groups_and_marks_ambiguous_beam_samples(self):
        descriptors = [(18, 0, 0, 0, 1, 0)]
        def endpoints(index, descriptor):
            return {'launch_beam': 0x4204, 'end_beam': 0x4203,
                    'launch_ref': 7, 'end_ref': 5}
        with tempfile.TemporaryDirectory() as td:
            hw, emu = self._pair(td, descriptors, endpoints, endpoints)
            report = compare.compare(hw, emu)
        group = report['groups'][0]
        self.assertEqual(group['kind'], 18)
        self.assertEqual(len(group['groups']), 1)
        self.assertEqual(group['groups'][0]['hardware_ambiguous_beam_samples'], 1)
        self.assertEqual(group['groups'][0]['emulator_ambiguous_beam_samples'], 1)
        json.dumps(report)

    def test_kind19_and20_include_observer_and_pc_marker_comparisons(self):
        descriptors = ([(19, target, variant, 0, 0, 0)
                        for target in range(5) for variant in (1, 2, 22)]
                       + [(20, target, 0, 0, 0, 0) for target in range(4)])
        def observations(index, descriptor):
            if descriptor[0] == 20:
                return {'pc_hi': 0, 'pc_lo': 0x1234, 'aux': 1}
            return {'counter': 0x0240, 'icr': 0x0040, 'aux': 0xffff}
        with tempfile.TemporaryDirectory() as td:
            hw, emu = self._pair(td, descriptors, observations, observations)
            report = compare.compare(hw, emu)
        kinds = {g['kind']: g for g in report['groups']}
        self.assertEqual(len(kinds[19]['groups']), 15)
        self.assertIn('dmaconr', kinds[19]['groups'][0]['observables'])
        self.assertIn('intreqr_second_read', kinds[19]['groups'][0]['timings'])
        self.assertEqual(len(kinds[20]['targets']), 4)
        self.assertIn('pc_marker_classifications', kinds[20]['targets'][0])
        json.dumps(report)

    def test_beam_conversion_rejects_unreliable_horizontal_endpoints(self):
        with self.assertRaisesRegex(ValueError, 'ambiguous beam'):
            compare._beam_elapsed(0x4102, 0x4108)
        with self.assertRaisesRegex(ValueError, 'ambiguous beam'):
            compare._beam_elapsed(0x41e0, 0x41e8)
        self.assertIsNone(compare._beam_elapsed(0x4102, 0x4108, False))

    def test_kind21_reports_state_and_timing_differences_per_target(self):
        descriptors = [(21, 0, 22, 0, 0, 0)]
        def hw_values(index, descriptor):
            return {'launch_beam': 0x4242, 'end_beam': 0x424a, 'counter': 0x4000}
        def emu_values(index, descriptor):
            return {'launch_beam': 0x4242, 'end_beam': 0x424b, 'counter': 0}
        with tempfile.TemporaryDirectory() as td:
            hw, emu = self._pair(td, descriptors, hw_values, emu_values)
            report = compare.compare(hw, emu)
        first = report['groups'][0]['targets'][0]
        self.assertEqual(first['state_mismatches'], 1)
        self.assertEqual(first['timing_mismatches'], 1)
        self.assertEqual(first['observers']['0']['state_mask'], '0x4000')

    def test_kind21_decodes_priority_bit_and_observer_separately(self):
        def row(repeat):
            return ((21, 0, 22, 0, 0, repeat),
                    {'launch_beam': 0x4242, 'end_beam': 0x424a, 'counter': 0x4000},
                    {'launch_beam': 0x4242, 'end_beam': 0x424a, 'counter': 0x4000})
        report = compare._compare_aligned([row(4)])
        self.assertTrue(report['bltpri_enabled'])
        target = report['targets'][0]
        self.assertTrue(target['bltpri_enabled'])
        self.assertTrue(target['observers']['4']['bltpri_enabled'])
        self.assertEqual(target['observers']['4']['observer'], 0)
        self.assertEqual(target['observers']['4']['state_mask'], '0x4000')
        with self.assertRaisesRegex(ValueError, 'Unknown aligned-channel'):
            compare._compare_aligned([row(3)])
        with self.assertRaisesRegex(ValueError, 'mixes BLTPRI'):
            compare._compare_aligned([row(0), row(4)])

    def test_kind22_compares_bzero_busy_and_valid_dmaconr_by_variant_repeat(self):
        descriptors = [(22, 8, 1, 0, 3, repeat) for repeat in (0, 4)]
        def readings(index, descriptor):
            prio = 0x0400 if descriptor[5] == 4 else 0
            return {'launch_beam': 0x4242, 'end_beam': 0x424a,
                    'counter': 0x6000 | prio}
        with tempfile.TemporaryDirectory() as td:
            hw, emu = self._pair(td, descriptors, readings, readings)
            report = compare.compare(hw, emu)
        group = report['groups'][0]
        self.assertEqual(group['kind'], 22)
        self.assertEqual(len(group['groups']), 1)
        item = group['groups'][0]
        self.assertEqual((item['target'], item['variant']), (8, 1))
        self.assertEqual(set(item['repeats']), {'0', '4'})
        self.assertFalse(item['repeats']['0']['bltpri_enabled'])
        self.assertTrue(item['repeats']['4']['bltpri_enabled'])
        self.assertEqual(item['repeats']['0']['bzero_busy_mask'], '0x6000')
        self.assertEqual(item['repeats']['4']['dmaconr_valid_mask'], '0x67ff')
        self.assertEqual(item['repeats']['4']['bzero_busy_mismatches'], 0)
        with self.assertRaisesRegex(ValueError, 'Unknown BZERO priority repeat'):
            bad = {'launch_beam':0x4242, 'end_beam':0x424a, 'counter':0}
            compare._compare_bzero([((22, 8, 1, 0, 0, 1), bad, bad)])

    def test_kind23_reports_stop_irq_delta_level_and_saved_pc_by_path(self):
        descriptors=[(23,0,0,0,0,0),(23,6,1,1,3,4)]
        def stop_pc(_index, descriptor):
            _, _, _, phase, delay, _ = descriptor
            pc=0xfe0000+phase*0x1000+delay*0x100+20+2*delay
            return {'pc_hi':pc>>16,'pc_lo':pc&0xffff}
        with tempfile.TemporaryDirectory() as td:
            hw,emu=self._pair(td,descriptors,hardware_mutate=stop_pc,emulator_mutate=stop_pc)
            report=compare.compare(hw,emu)['groups'][0]
            self.assertEqual(report['kind'],23)
            self.assertEqual(len(report['groups']),2)
            native,soft=report['groups']
            self.assertEqual((native['target'],native['handler'],native['phase_pad_cck']), (0,'RAM',2))
            self.assertEqual((soft['target'],soft['handler'],soft['phase_pad_cck']), (6,'ROM',3))
            self.assertEqual(native['hardware_irq_elapsed_cck'], {9:1})
            self.assertEqual(soft['irq_elapsed_mismatches'],0)
            self.assertEqual(soft['saved_pc_mismatches'],0)
            self.assertEqual(soft['emulator_irq_level'], {1:1})
            self.assertEqual(soft['expected_post_stop_pc_mismatches'], {'hardware':0,'emulator':0})

    def test_kind23_rejects_mismatched_launch_beams(self):
        descriptors=[(23,0,0,0,0,0)]
        with tempfile.TemporaryDirectory() as td:
            hw,emu=self._pair(td,descriptors,
                              emulator_mutate=lambda *_:{'launch_beam':0x4342})
            with self.assertRaisesRegex(ValueError,'launch position differs'):
                compare.compare(hw,emu)

    def test_kind24_compares_line_bzero_for_b_use_and_pixel_position(self):
        descriptors=[(24,32,1,0,0,0),(24,33,0x108,1,31,4)]
        def data_values(_index, _descriptor):
            return {'icr':0x8000,'irq_beam':0x8000,'irq_level':0x1000,
                    'pc_hi':0x0100,'pc_lo':0}
        with tempfile.TemporaryDirectory() as td:
            hw,emu=self._pair(td,descriptors,data_values,data_values)
            report=compare.compare(hw,emu)['groups'][0]
            self.assertEqual(report['kind'],24)
            self.assertEqual(len(report['groups']),2)
            self.assertFalse(report['groups'][0]['b_use_enabled'])
            self.assertEqual(report['groups'][1]['b_pattern'],8)
            self.assertTrue(report['groups'][1]['bdat_written_after_bltcon1'])
            self.assertEqual(report['groups'][1]['samples'],1)
            self.assertEqual(report['groups'][1]['elapsed_mismatches'],0)
            self.assertEqual(report['groups'][1]['destination_memory']['destination_or']['mismatches'],0)
            self.assertEqual(report['groups'][1]['destination_memory']['destination_100a0']['hardware'],{0x100:1})


    def test_emulator_binary_provenance_path_and_hash_are_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            binary = root / 'candidate.exe'
            binary.write_bytes(b'candidate build')
            capture = root / 'capture'
            capture.mkdir()
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            (capture / 'invocation.json').write_text(json.dumps({
                'command': [str(binary)], 'binary_sha256': digest
            }))
            provenance = compare.capture_provenance(capture, binary, digest)
            self.assertTrue(provenance['expected_binary_verified'])
            with self.assertRaisesRegex(ValueError, 'Unexpected emulator invocation SHA256'):
                compare.capture_provenance(capture, binary, '0' * 64)
            with self.assertRaisesRegex(ValueError, 'must be supplied together'):
                compare.capture_provenance(capture, binary, None)

    def test_damaged_binary_is_rejected(self):
        descriptors = [(21, 0, 22, 0, 0, 0)]
        with tempfile.TemporaryDirectory() as td:
            folder = self._write_capture(Path(td), 'capture', descriptors)
            data = bytearray((folder / 'results.bin').read_bytes())
            data[-1] ^= 1
            (folder / 'results.bin').write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                compare.load(folder)

    def test_valid_capture_of_different_rom_is_rejected(self):
        descriptors = [(21, 0, 22, 0, 0, 0)]
        with tempfile.TemporaryDirectory() as td:
            hw, emu = self._pair(td, descriptors,
                                 hardware_source='11' * 32, emulator_source='22' * 32)
            with self.assertRaisesRegex(ValueError, 'Different measured ROMs'):
                compare.compare(hw, emu)


if __name__ == '__main__':
    unittest.main()
