import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import experiment as e


def field(name, **kwargs):
    return dict(field=name, unit='CCK', meaning='test observation', **kwargs)


def policy():
    return dict(alignment='exact', measurements=[field('counter')], qualification=[field('launch_beam')])


def row(**kwargs):
    result = dict.fromkeys(e.rom_results.FIELDS, 0)
    result.pop('pc_hi')
    result.pop('pc_lo')
    result.update(saved_pc_offset=0, counter=10, **kwargs)
    return result


def packet(counter=10, complete=1, status=0):
    header = bytearray(64)
    header[:8] = b'A5RBCP01'
    struct.pack_into('>HHIII', header, 8, 1, 40, 1, 104, 0)
    struct.pack_into('>4H', header, 56, 0xa000, 0xffff, 1, complete)
    words = [0] * 20
    words[10], words[16] = counter, status
    data = header + struct.pack('>20H', *words)
    struct.pack_into('>I', data, 20, -sum(struct.unpack('>26I', data)) & 0xffffffff)
    return bytes(data)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(e, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root / 'rom').mkdir()
        (self.root / 'rom/a500-timing-rom.bin').write_bytes(b'test ROM')
        self.build = dict(source_id='00' * 32, trial_count=1, trials=[[0]*6],
                          rom_sha256=e.digest(b'test ROM'))
        e.write(self.root / 'rom/manifest.json', self.build)
        (self.root / 'emulator.exe').write_bytes(b'test executable')
        (self.root / 'machine.toml').write_text('')
        (self.root / 'baseline').mkdir()
        (self.root / 'baseline/results.bin').write_bytes(packet(11))
        self.reference = self.root / 'reference'
        self.reference.mkdir()
        (self.reference / 'results.bin').write_bytes(packet())
        e.write(self.reference / 'manifest.json', dict(source_id=self.build['source_id'],
                test_rom_sha256=self.build['rom_sha256'], results_sha256=e.digest(packet()),
                hardware={'machine': 'fixture'}, capture_method='test', repeatability='test',
                restoration=dict(restored_verified=True, reset_release_verified=True, errors=[])))
        self.spec = dict(version=1, id='fixture', hypothesis='buffer', competitor='restart',
                         test='active write', next_question='boundary?', outcomes={'first': 'buffer', 'late': 'restart'},
                         investigation='record.json', binary='emulator.exe', config='machine.toml', romdir='rom',
                         capture=dict(minimum_seconds=500, seconds=30, expected_cases=1),
                         comparison=policy(), references=['reference'], baseline='baseline',
                         validation=[dict(name=t, tier=t, argv=['unused']) for t in e.TIERS])

    def test_manifest_contract(self):
        e.validate_spec(self.spec)
        for change in ('alignment', 'unit', 'order', 'hypothesis', 'cache'):
            spec = copy.deepcopy(self.spec)
            if change == 'alignment':
                spec['comparison']['alignment'] = 'auto'
            elif change == 'unit':
                del spec['comparison']['measurements'][0]['unit']
            elif change == 'order':
                spec['validation'].reverse()
            elif change == 'hypothesis':
                spec['hypothesis'] = ''
            else:
                spec['validation'][0]['cache'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                e.validate_spec(spec)

    def test_comparison_mutations_and_delta(self):
        hw = [row()]
        base = row()
        base['counter'] = 11
        _, before = e.compare(hw, [base], policy())
        report, after = e.compare(hw, hw, policy())
        self.assertEqual(report['counts']['matches'], 1)
        self.assertEqual(e.delta(before, after)['counts']['repairs'], 1)
        self.assertEqual(e.delta(after, before)['counts']['regressions'], 1)
        self.assertEqual(e.delta(before, before)['counts']['unchanged_differences'], 1)
        removed, missing = e.compare(hw, [], policy())
        self.assertEqual(removed['counts']['missing_results'], 1)
        self.assertEqual(e.delta(after, missing)['counts']['missing_results'], 1)
        shifted = dict(base, launch_beam=1)
        report, excluded = e.compare(hw, [shifted], policy())
        self.assertEqual(report['counts']['excluded'], 1)
        self.assertEqual(e.delta(after, excluded)['counts']['qualification_regressions'], 1)
        report, _ = e.compare(hw + [dict(base, repeat=1)], hw, policy())
        self.assertEqual(report['counts']['unstable_reference'], 1)
        self.assertEqual(report['counts']['reference_conflicting_cohorts'], 1)

    def test_invalid_capture_and_provenance(self):
        for data in (packet()[:-4], packet(complete=0), packet(status=1)):
            (self.root / 'baseline/results.bin').write_bytes(data)
            with self.assertRaises(ValueError):
                e.load_capture(self.root / 'baseline', self.build, self.spec['capture'])
        wrong = dict(self.build, source_id='ff' * 32)
        with self.assertRaises(ValueError):
            e.load_capture(self.reference, wrong, self.spec['capture'])
        manifest = e.read(self.reference / 'manifest.json')
        manifest['results_sha256'] = 'wrong'
        e.write(self.reference / 'manifest.json', manifest)
        with self.assertRaises(ValueError):
            e.load_capture(self.reference, self.build, self.spec['capture'], reference=True)

    def fake_command(self, calls, counter=10, fail=None):
        def run(spec, out, variables, cache):
            calls.append(spec)
            if spec['name'] == 'preflight':
                destination = out / 'candidate'
                destination.mkdir()
                (destination / 'results.bin').write_bytes(packet(counter))
            return dict(name=spec['name'], exit=1 if spec['name'] == fail else 0,
                        reused=False, duration=0)
        return run

    def execute(self, name='run', **kwargs):
        e.write(self.root / 'experiment.json', self.spec)
        return e.run(self.root / 'experiment.json', name, **kwargs)

    def test_batch_duration_ladder_acceptance_and_restart(self):
        calls = []
        with patch.object(e, 'command_run', self.fake_command(calls)):
            result = self.execute()
        self.assertEqual(result['status'], 'review')
        self.assertEqual(calls[0]['argv'][-1], '500')
        self.assertEqual([c['name'] for c in calls], ['preflight'] + list(e.TIERS))
        e.decide('run', 'accept', 'one repair, no regressions', ['run/comparison.json'])
        record = e.restart('record.json')
        self.assertEqual(record['decision'], 'accept')
        self.assertIn('identity', record)
        self.assertLess(len(json.dumps(record)), 8000)
        e.archive('run', 'versioned')
        self.assertEqual(sorted(p.name for p in (self.root/'versioned/run1').iterdir()),
                         ['manifest.json', 'results.bin'])
        with self.assertRaises(ValueError):
            e.archive('run', 'versioned')
        with patch.object(e, 'command_run', self.fake_command([])):
            self.execute('newer', through='comparison')
        with self.assertRaises(ValueError):
            e.decide('run', 'preserve', 'stale evidence', ['run/comparison.json'])

    def test_regression_and_failed_tier_stop_batch(self):
        calls = []
        (self.root / 'baseline/results.bin').write_bytes(packet())
        with patch.object(e, 'command_run', self.fake_command(calls, counter=11)):
            result = self.execute()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual([c['name'] for c in calls], ['preflight'])
        calls.clear()
        (self.root / 'baseline/results.bin').write_bytes(packet(11))
        with patch.object(e, 'command_run', self.fake_command(calls, fail='neighbor')):
            result = self.execute('failed-tier')
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('broad', [c['name'] for c in calls])
        with self.assertRaises(ValueError):
            e.decide('failed-tier', 'accept', 'bad', ['failed-tier/summary.json'])
        self.spec['build'] = [dict(name='compile', argv=['unused'])]
        calls.clear()
        with patch.object(e, 'command_run', self.fake_command(calls, fail='compile')):
            result = self.execute('failed-build')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual([c['name'] for c in calls], ['compile'])

    def test_partial_run_cannot_be_accepted_and_stall_requires_revision(self):
        with patch.object(e, 'command_run', self.fake_command([])):
            self.execute('one', through='comparison')
            with self.assertRaises(ValueError):
                e.decide('one', 'accept', 'partial', ['one/comparison.json'])
            self.execute('two', through='comparison')
            self.execute('three', through='comparison')
            with self.assertRaises(ValueError):
                self.execute('four', through='comparison')
            self.spec['hypothesis'] = 'revised phase explanation'
            self.assertEqual(self.execute('revised', through='comparison')['status'], 'review')

    def test_cache_logs_and_actual_exit_status(self):
        source = self.root / 'source.rs'
        source.write_text('first')
        output = self.root / 'generated'
        script = 'from pathlib import Path; Path("generated").write_text("built")'
        command = dict(name='build', argv=[sys.executable, '-c', script], cache=True,
                       inputs=['source.rs'], outputs=['generated'])
        variables = dict(root=str(self.root))
        for name in ('a', 'b', 'c', 'd'):
            (self.root/name).mkdir()
        first = e.command_run(command, self.root/'a', variables, self.root/'cache')
        self.assertEqual(first['exit'], 0)
        self.assertFalse(first['reused'])
        self.assertTrue(e.command_run(command, self.root/'b', variables, self.root/'cache')['reused'])
        source.write_text('changed')
        self.assertFalse(e.command_run(command, self.root/'c', variables, self.root/'cache')['reused'])
        output.write_text('tampered')
        self.assertFalse(e.command_run(command, self.root/'d', variables, self.root/'cache')['reused'])
        failure = dict(name='failure', argv=[sys.executable, '-c',
                       'import sys; print("error: original failure", file=sys.stderr); print("noise\\n"*5000); sys.exit(7)'])
        result = e.command_run(failure, self.root, variables, self.root/'cache')
        self.assertEqual(result['exit'], 7)
        self.assertIn('original failure', result['excerpt'])
        self.assertLess(len(result['excerpt']), 1801)
        self.assertGreater(Path(result['stdout']).stat().st_size, 20000)

    def test_preflight_reuse_and_binary_change(self):
        self.spec['reuse_preflight'] = True
        calls = []
        with patch.object(e, 'command_run', self.fake_command(calls)):
            self.execute('initial', through='comparison')
            calls.clear()
            self.execute('reused', through='comparison')
            self.assertEqual(calls, [])
            self.assertTrue((self.root/'reused/candidate/reuse.json').exists())
            cached = next((self.root/'captures/.experiment-cache').glob('replay-*/results.bin'))
            cached.write_bytes(packet(11))  # Valid checksum, wrong immutable packet hash.
            self.assertEqual(self.execute('corrupt', through='comparison')['status'], 'failed')
            (self.root/'emulator.exe').write_bytes(b'changed binary')
            self.execute('changed', through='comparison')
            self.assertEqual([c['name'] for c in calls], ['preflight'])

    def test_packet_gate_rejects_changes_and_missing_suites(self):
        for name in ('old', 'new'):
            p = self.root/name/'cia'
            p.mkdir(parents=True)
            (p/'results.bin').write_bytes(packet())
        self.assertEqual(e.packets('old','new',['cia'])['status'], 'unchanged')
        (self.root/'new/cia/results.bin').write_bytes(packet(11))
        report = e.packets('old','new',['cia'])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['counts']['changed_cases'], 1)
        self.assertIn('counter', report['representatives'][0]['fields'])
        self.assertEqual(e.packets('old','new',['absent'])['counts']['missing_suites'], 1)

    def test_trace_shift_is_not_aligned_away(self):
        case = [0]*6
        left, right = self.root/'left.jsonl', self.root/'right.jsonl'
        left.write_text('\n'.join(json.dumps(dict(case=case, time=t, event='read')) for t in (10,12,14)))
        right.write_text('\n'.join(json.dumps(dict(case=case, time=t, event='read')) for t in (10,13,15)))
        result = e.trace_window(str(left), str(right), case, 1)
        self.assertEqual(result['first_divergent_event'], 1)
        self.assertEqual(result['hardware'][1]['time'], 12)
        self.assertEqual(result['candidate'][1]['time'], 13)

    def test_timeout_is_bounded_and_record_is_required_to_stay_small(self):
        result = e.command_run(dict(name='timeout', timeout_seconds=0.05,
                    argv=[sys.executable, '-c', 'import time; time.sleep(30)']),
                    self.root, {}, self.root/'cache')
        self.assertEqual(result['exit'], 124)
        self.assertIn('timed out', Path(result['stderr']).read_text())
        e.write(self.root/'record.json', dict(confirmed_facts=['x'*9000]))
        with self.assertRaises(ValueError):
            e.restart('record.json')

    def test_hardware_is_explicit_and_repeats_keep_restoration_provenance(self):
        from tools import run_onerom_live
        self.spec['hardware'] = dict(onerom='fixture.exe', repeats=2, limitations='fixture')
        calls = []
        def collect(onerom, romdir, out, timeout, serial):
            self.assertEqual(romdir.name, 'rom')
            self.assertTrue((romdir/'a500-timing-rom.bin').exists())
            out.mkdir()
            (out/'capture').mkdir()
            e.write(out/'build-manifest.json', self.build)
            e.write(out/'restoration.json', dict(restored_verified=True, reset_release_verified=True, errors=[]))
            (out/'capture/results.bin').write_bytes(packet())
            print('raw hardware diagnostics\n' * 1000)
        with patch.object(e, 'command_run', self.fake_command(calls)), \
                patch.object(run_onerom_live, 'collect_live', side_effect=collect) as physical:
            self.execute('saved', through='comparison')
            physical.assert_not_called()
            result = self.execute('physical', hardware=True, through='comparison')
            self.assertEqual(result['status'], 'review')
            self.assertEqual(physical.call_count, 2)
        report = e.read(self.root/'physical/comparison.json')
        self.assertTrue(report['repeatability']['packets_identical'])
        self.assertEqual(report['repeatability']['runs'], 2)
        self.assertTrue(e.read(self.root/'physical/reference-1/manifest.json')['restoration']['restored_verified'])
        self.assertGreater((self.root/'physical/hardware-1.log').stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
