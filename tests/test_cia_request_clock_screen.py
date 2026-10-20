import unittest
from tools import cia_request_clock_screen as screen


class RequestClockTests(unittest.TestCase):
    def test_parse_retains_nine_clock_interval_and_rejects_missing_read(self):
        trace=''.join(f'CPUBUS kind=custom addr=00dff01e size=2 v=044 h={h:02x} wait=0\n' for h in (2,10,19,27,40))
        rows=[dict(launch_ref=0x4400)]
        self.assertEqual(screen.read_clocks(trace,rows),[(2,10,19,27)])
        with self.assertRaises(ValueError):
            screen.read_clocks(trace.rsplit('CPUBUS',1)[0],rows)

    def test_actual_spacing_and_common_support(self):
        fields=[dict(name=n,field=n) for n in screen.NAMES]
        policy=dict(measurements=fields,qualification=[])
        rows=[dict(kind=68,target=4,variant=0,phase=0,delay=k,**{n:int(t>=25+5*k) for n,t in zip(screen.NAMES,(2,10,19,27))}) for k in range(8)]
        clocks=[(2,10,19,27)]*len(rows)
        result=screen.screen(rows,rows,policy,clocks,delays=(0,1))
        self.assertEqual(result['results'][0]['different_fields'],0)
        self.assertLessEqual(result['common_fields'],result['results'][1]['compared_fields'])
        # The 9-clock interval permits 5*2-9=1; a nominal 8-clock model misses this alias.
        self.assertGreater(result['results'][1]['compared_fields'],0)

    def test_known_source_shift_is_detected_without_changing_read_clocks(self):
        fields=[dict(name=n,field=n) for n in screen.NAMES]
        policy=dict(measurements=fields,qualification=[])
        times=(2,10,19,27)
        def row(k, extra=0):
            return dict(kind=68,target=4,variant=0,phase=0,delay=k,
                        **{n:int(t>=5+5*k+extra) for n,t in zip(screen.NAMES,times)})
        candidate=[row(k) for k in range(8)]
        hardware=[row(k,5) for k in range(8)]
        result=screen.screen(hardware,candidate,policy,[times]*8,delays=(0,5))
        self.assertGreater(result['results'][0]['different_fields'],0)
        self.assertEqual(result['results'][1]['different_fields'],0)
        self.assertGreater(result['common_fields'],0)
        self.assertGreater(result['results'][1]['unavailable_or_ambiguous'],0)

    def test_aperture_kind_and_qualification_failure(self):
        fields = [dict(name=n, field=n) for n in screen.NAMES]
        policy = dict(measurements=fields, qualification=[dict(field='cal')])
        row = dict(kind=84, target=4, variant=0, phase=0, delay=0, cal=1,
                   **{n:0 for n in screen.NAMES})
        self.assertEqual(screen.screen([row], [row], policy, [(2,10,19,27)], (0,))['common_fields'], 4)
        with self.assertRaisesRegex(ValueError, 'no exact qualified'):
            screen.screen([dict(row, cal=3)], [row], policy, [(2,10,19,27)], (0,))
        with self.assertRaisesRegex(ValueError, 'uniform'):
            screen.screen([dict(row, kind=68)], [row], policy, [(2,10,19,27)], (0,))
