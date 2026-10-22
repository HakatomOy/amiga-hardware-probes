import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import build_playfield_boundary_rom as probe
import build_playfield_gate_rom as gate
from tools.playfield_boundary_report import report
from tools.playfield_gate_report import summarize
from tools.playfield_gate_fixture import consensus


class BoundaryProbeTests(unittest.TestCase):
    def test_gate_fixture_rejects_conflicts_missing_repeats_and_failed_witness(self):
        row = dict(kind=104, status=0, target=4, phase=3, variant=0, delay=0,
                   repeat=0, counter=1, end_beam=4, icr=0)
        rows = [row, dict(row, repeat=1)]
        expected = {(104, 4, 0, 3, 0)}
        self.assertEqual(consensus([rows, rows], expected), {next(iter(expected)): 1})
        for changed in ([dict(row, counter=0), rows[1]], [row],
                        [dict(row, end_beam=0), rows[1]]):
            with self.assertRaises(ValueError):
                consensus([rows, changed], expected)

    def test_gate_summary_does_not_hide_missing_or_conflicting_measurements(self):
        row = dict(kind=104, status=0, target=4, phase=3, variant=0, delay=0,
                   repeat=0, counter=1, end_beam=4, icr=0)
        rows = [row, dict(row, counter=0, repeat=1), dict(row, delay=2)]
        result = summarize(rows)
        self.assertEqual(result['groups'][0]['bits'], '?-1')
        self.assertEqual(result['invalid_witness'], 0)
        self.assertEqual(len(result['groups'][0]['details'][0]['ids']), 2)

    def test_gate_descriptors_and_marker(self):
        self.assertEqual(len(set(gate.trials())), 1024)
        self.assertIn('move.w $1e(a6),16(a4)', gate.OBSERVER)
        self.assertIn('move.w #$8380,$96(a6)', gate.OBSERVER)

    def test_controls_and_thresholds_cover_each_descriptor(self):
        rows = probe.trials()
        self.assertEqual(len(rows), 768)
        self.assertEqual(len(set(rows)), 768)
        self.assertEqual({r[2] for r in rows}, {0, 1, 2, 4})
        text = probe.observer()
        for delay in range(24):
            self.assertIn(f'cmpi.w #${0x4400+delay*2:04x},d0', text)
        for forbidden in ('a3', 'd7'):
            self.assertNotIn(forbidden, text)

    def test_report_retains_conflicting_values_and_distinct_brackets(self):
        row = dict(kind=103, status=0, target=4, phase=3, variant=0, delay=0,
                   launch_ref=0x4420, end_beam=0x4430, irq_level=0x443a,
                   aux=0x444a, counter=1, icr=0)
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / 'results.bin'
            packet.write_bytes(b'placeholder')
            out = Path(directory) / 'windows.csv'
            with patch('tools.playfield_boundary_report.rom_results.decode',
                       return_value=({}, [row, dict(row, aux=0x444b)])):
                result = report(packet, out)
                self.assertEqual(result['conflicting_collision_groups'], 0)
                self.assertEqual(result['varying_bracket_groups'], 1)
                self.assertIn('444a', out.read_text())
                self.assertIn('444b', out.read_text())
            with patch('tools.playfield_boundary_report.rom_results.decode',
                       return_value=({}, [row, dict(row, counter=0)])):
                self.assertEqual(report(packet, out)['conflicting_collision_groups'], 1)
