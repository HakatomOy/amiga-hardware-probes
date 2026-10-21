import threading
import unittest
from unittest.mock import patch

from tools import experiment


class ParallelValidationTests(unittest.TestCase):
    def test_only_adjacent_explicit_groups_within_a_tier_overlap(self):
        commands = [dict(name=str(i), tier=tier, argv=[], **group)
                    for i, (tier, group) in enumerate([
                        ('focused', {}), ('focused', {'parallel_group': 'a'}),
                        ('focused', {'parallel_group': 'a'}),
                        ('neighbor', {'parallel_group': 'a'}), ('neighbor', {})])]
        self.assertEqual([len(batch) for batch in experiment.validation_batches(commands)],
                         [1, 2, 1, 1])

    def test_group_runs_concurrently_and_retains_every_result_in_declared_order(self):
        barrier = threading.Barrier(2)
        def command_run(command, *_):
            barrier.wait(timeout=5)
            return dict(name=command['name'], exit=command['exit'])
        batch = [dict(name='failed', exit=1), dict(name='passed', exit=0)]
        with patch.object(experiment, 'command_run', command_run):
            results = experiment.run_validation_batch(batch, None, None, None)
        self.assertEqual(results, [dict(name='failed', exit=1), dict(name='passed', exit=0)])

    def test_live_hardware_cannot_be_grouped(self):
        with self.assertRaisesRegex(ValueError, 'hardware'):
            list(experiment.validation_batches([
                dict(tier='neighbor', parallel_group='a', argv=['run', '--hardware'])]))


if __name__ == '__main__':
    unittest.main()
