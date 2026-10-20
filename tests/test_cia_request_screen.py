import unittest
from tools.screen_cia_request_delay import screen


class DelayScreenTests(unittest.TestCase):
    def test_known_delay_and_disjoint_phase_are_reported_separately(self):
        policy = dict(qualification=[dict(field='launch_beam')],
                      measurements=[dict(name='request1', field='irq_beam')])
        def row(delay, result, launch=10):
            return dict(kind=68, target=4, variant=0, phase=0, delay=delay,
                        repeat=0, launch_beam=launch, irq_beam=result)
        emulator = [row(0, 8), row(1, 8), row(2, 0)]
        hardware = [row(0, 8), row(1, 0), row(0, 8, launch=11)]
        self.assertEqual(screen(hardware, emulator, policy, 0)['different_vectors'], 1)
        delayed = screen(hardware, emulator, policy, 1)
        self.assertEqual(delayed['different_vectors'], 0)
        self.assertEqual(delayed['compared'], 2)
        self.assertEqual(delayed['unavailable_or_ambiguous'], 1)
