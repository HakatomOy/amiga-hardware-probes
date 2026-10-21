import base64
import json
from pathlib import Path
import struct
import tempfile
import unittest

import run_rom
from tools import profile_case_window


class CaseProfileTests(unittest.TestCase):
    def test_selection_uses_header_and_exact_unique_descriptor(self):
        manifest = dict(trials=[[96, 3, 1550, 0, 0, 0], [96, 3, 1550, 0, 0, 1]],
                        record_bytes=40, result_bytes=144, result_address=0x40000)
        spec = run_rom.case_profile_spec(manifest, '96,3,1550,0,0,1', 0xffbf80)
        self.assertEqual(spec['record_address'], 0x40068)
        for case, entry in ((None, 123), ('96,3,1550,0,0,2', 123), ('96,3,1550,0,0,1', None)):
            with self.assertRaises(ValueError):
                run_rom.case_profile_spec(manifest, case, entry)

    def test_profile_validates_entry_descriptor_before_arming(self):
        calls = []
        spec = dict(case=[96, 3, 1550, 0, 0, 0], entry=0xffbf80, record_address=0x40040, index=0)

        def rpc(method, params):
            calls.append((method, params))
            return {'break.add': dict(id=7),
                    'run_until': dict(pc=spec['entry'], reason='breakpoint'),
                    'mem.read': dict(data=base64.b64encode(struct.pack('>6H', *spec['case'])).decode())}.get(method, {})

        with tempfile.TemporaryDirectory() as folder:
            run_rom.arm_case_profile(rpc, spec, Path(folder), 160)
        self.assertEqual([method for method, _ in calls],
                         ['break.add', 'run_until', 'mem.read', 'break.remove', 'profile.start'])
        self.assertEqual(calls[0][1]['ignore'], 0)
        self.assertEqual(calls[-1][1]['frames'], 1)

    def test_packet_difference_is_a_failed_trace_not_a_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            actual, expected = out/'actual.bin', out/'expected.bin'
            actual.write_bytes(b'one')
            expected.write_bytes(b'two')
            with self.assertRaisesRegex(RuntimeError, 'not qualified'):
                run_rom.verify_packet_identity(actual, expected, out)
            self.assertFalse(json.loads((out/'trace-verification.json').read_text())['byte_identical'])
            actual.write_bytes(b'two')
            run_rom.verify_packet_identity(actual, expected, out)
            self.assertTrue(json.loads((out/'trace-verification.json').read_text())['byte_identical'])

    def test_slot_window_wraps_rows_and_bounds_output_without_alignment(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            profile = out/'case-profile'
            profile.mkdir()
            (out/'trace-verification.json').write_text(json.dumps(dict(byte_identical=True, actual_sha256='packet')))
            (out/'case-profile-selection.json').write_text(json.dumps(dict(case=[96,3,1550,0,0,0])))
            (profile/'profile.jsonl').write_text(json.dumps(dict(frame=7, rows=2, line_cck=4,
                                                   slots_file='slots.bin', slots_record_bytes=24))+'\n')
            raw = b''.join(profile_case_window.SLOT.pack(0x8c,3,0,2,0,0,i*2,i,0) for i in range(8))
            (profile/'slots.bin').write_bytes(raw)
            report = profile_case_window.window(out,'0:3',3,limit=2)
            self.assertEqual([event['beam'] for event in report['events']], ['00:03','01:00'])
            self.assertEqual(report['omitted_events'],1)
            with self.assertRaises(ValueError):
                profile_case_window.window(out,'1:3',2)


if __name__ == '__main__':
    unittest.main()
