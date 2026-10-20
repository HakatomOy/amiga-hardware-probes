import unittest

import rom_results
from tools.summarize_collision_trace import index_trace


class CollisionTraceTests(unittest.TestCase):
    def test_producer_precedes_first_read_trace_and_keeps_real_scanline(self):
        row = dict(zip(rom_results.FIELDS[:6], (73, 2, 4, 9, 0, 0)))
        lines = ['CLXPROBE dma v=041 from=28 to=dc first_word=0',
                 'CPUBUS kind=custom addr=00dff00e v=042 h=20',
                 'CLXPROBE dma v=042 from=28 to=dc first_word=20',
                 'CPUBUS kind=custom addr=00dff00e v=043 h=40',
                 'CPUBUS kind=custom addr=00dff00e v=043 h=46',
                 'CPUBUS kind=custom addr=00dff00e v=044 h=30']
        result = index_trace(lines, [row], {'73,2,4,9,0,0'})['73,2,4,9,0,0']
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['events'][0]['stage'], 1)
        self.assertIn('v=042', result['events'][0]['text'])
        self.assertEqual(len(result['reads']), 4)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            index_trace(lines[:-1], [row], {'73,2,4,9,0,0'})

    def test_kind72_uses_three_reads_and_other_kinds_are_rejected(self):
        row = dict(zip(rom_results.FIELDS[:6], (72, 1, 4, 20, 0, 0)))
        lines = ['CPUBUS kind=custom addr=00dff00e v=042 h=20'] * 3
        self.assertEqual(len(index_trace(lines, [row], {'72,1,4,20,0,0'})), 1)
        row['kind'] = 85
        with self.assertRaisesRegex(ValueError, 'uniform'):
            index_trace(lines, [row], set())
