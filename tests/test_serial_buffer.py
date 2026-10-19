import copy
import unittest
from pathlib import Path
import build_serial_buffer_rom as builder
import compare_serial_buffer as compare
import rom_results


def row():
    r = dict.fromkeys(rom_results.FIELDS, 0)
    r.update(kind=63, delay=32, launch_beam=65535, launch_ref=65535,
             end_beam=65535, end_ref=65535, irq_level=18,
             saved_pc_offset=(18 << 16) | 32, aux=32,
             second_counter_or_beam=56, second_icr_or_level=56, counter=8)
    return r


class SerialBufferTests(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(builder.trials()), 320)
        self.assertEqual(len(set(builder.trials())), 320)
        self.assertEqual(len(builder.trials(first_boundary=True)), 40)
        self.assertEqual({r[2] for r in builder.trials(first_boundary=True)}, {0})

    def test_drain_precedes_measured_transfer(self):
        source = (Path(builder.__file__).parent / 'src/rom/cia_serial_buffer_kernel.i').read_text()
        start = source.index('move.b #$a5,$c00(a0)')
        self.assertLess(source.index('.drain:'), start)
        self.assertLess(source.index('tst.b $d00(a0)'), start)
        self.assertIn('andi.w #8,d0\n        move.w d0,32(a4)', source)

    def test_mutations(self):
        original = row()
        self.assertEqual(compare.compare([original], [original])['counts']['matches'], 1)
        changed = copy.copy(original)
        changed['counter'] = 0
        self.assertEqual(compare.compare([original], [changed])['counts']['mismatches'], 1)
        self.assertEqual(compare.compare([original], [])['counts']['missing_results'], 1)
        changed = copy.copy(original)
        changed['aux'] += 1
        self.assertEqual(compare.compare([original], [changed])['counts']['no_identical_bracket'], 1)

    def test_unstable_reference(self):
        original = row()
        changed = dict(original, repeat=1, counter=0)
        self.assertEqual(compare.compare([original, changed], [original])['counts']['unstable_reference'], 1)

    def test_invalid(self):
        original = row()
        for mutation in ({'status': 8}, {'aux': 31}, {'launch_beam': 2}):
            with self.subTest(mutation=mutation):
                self.assertEqual(compare.compare([], [dict(original, **mutation)])['counts']['invalid_captures'], 1)


if __name__ == '__main__':
    unittest.main()
