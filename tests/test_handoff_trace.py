import unittest
from tools import summarize_handoff_trace as trace


class HandoffTraceTests(unittest.TestCase):
    def test_explicit_pal_wrap_is_not_packed_subtraction(self):
        self.assertEqual(trace.beam_delta(0x4300,0x42e2),1)
        self.assertEqual(trace.beam_delta(0x42e2,0x4300),-1)
        with self.assertRaises(ValueError):
            trace.beam_delta(0xffe2,0x0000)
        with self.assertRaises(ValueError):
            trace.beam_delta(0x42ff,0x4200)

    def test_trace_order_and_width_must_match_immutable_descriptors(self):
        rows=[dict(kind=71,target=3,variant=v,phase=0,delay=0,repeat=0) for v in (0,8)]
        lines=['BLTP 1 66 126 START con0=09f0 size=0041 dmacon=0340\n',
               'BLTP 1 66 128 TICK A bus=1\n','CPUBUS kind=custom addr=00dff002\n']
        bound=trace.bind_trace(lines,rows)
        self.assertEqual(len(bound),1)
        self.assertEqual(bound[0]['case'],[71,3,0,0,0,0])
        self.assertEqual(len(bound[0]['slots']),1)
        with self.assertRaises(ValueError):trace.bind_trace([],rows)
        with self.assertRaises(ValueError):trace.bind_trace(lines+lines,rows)
        with self.assertRaises(ValueError):trace.bind_trace([lines[0].replace('0041','0042')],rows)

    def test_start_grant_belongs_to_following_start_not_previous_case(self):
        rows = [dict(kind=71,target=3,variant=0,phase=0,delay=0,repeat=r) for r in (0,1)]
        grant = 'CPUBUS addr=00dff058 granted={}'
        start = 'BLTP 1 66 {} START size=0041'
        blocks = trace.bind_trace([grant.format(124), start.format(126),
                                  grant.format(140), start.format(142)], rows)
        self.assertIn('granted=124', blocks[0]['start_grant']['text'])
        self.assertIn('granted=140', blocks[1]['start_grant']['text'])
        self.assertFalse(blocks[0]['accesses'])
