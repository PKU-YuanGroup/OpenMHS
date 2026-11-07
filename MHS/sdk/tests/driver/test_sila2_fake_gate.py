"""Controlled static source proof is distinct from native factory admission."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from mhs.driver.check import Gate, _Context, run_check
from mhs.driver.sila2_check import check_sila2_surface
from tests.driver.sila2_support import FIXTURE


class SilaControlledGateTests(unittest.TestCase):
    def package(self):
        holder = tempfile.TemporaryDirectory(prefix='mhs-sila-controlled-gate-')
        self.addCleanup(holder.cleanup)
        directory = Path(holder.name) / FIXTURE.name
        shutil.copytree(FIXTURE, directory, ignore=shutil.ignore_patterns('__pycache__', 'check-report.json'))
        return directory

    def test_packaged_static_fake_contract_passes_without_native_admission(self):
        report = run_check(FIXTURE, backend='fake', gates=['G1', 'G2', 'G3', 'G4', 'G5', 'G7'], write_report=False)
        self.assertEqual(report['failed'], [], report)
        self.assertEqual(next(g for g in report['gates'] if g['id'] == 'G7')['status'], 'pass')
        lock = json.loads((FIXTURE / 'driver.lock.json').read_text())
        self.assertIsNone(lock['reviewed_by'])
        self.assertIsNone(lock['upstream'])
        self.assertEqual(lock['authored_by']['kind'], 'model')

    def test_each_exact_primary_blob_is_required_even_in_a_synthetic_fixture(self):
        provenance = json.loads((FIXTURE / 'source-provenance.json').read_text())
        for row in provenance['files']:
            with self.subTest(path=row['path']):
                directory = self.package()
                target = directory / 'upstream' / row['path']
                target.write_bytes(target.read_bytes() + b'\n')
                report = run_check(directory, backend='fake', gates=['G7'], write_report=False)
                self.assertEqual(report['failed'], ['G7'], report)
                self.assertIn('G7.SILA_SOURCE_UNPROVEN', [f['code'] for g in report['gates'] for f in g['findings']])

    def test_wrong_task_pin_is_refused_for_non_synthetic_source(self):
        directory = self.package()
        card = json.loads((directory / 'task.json').read_text())
        card['upstream'] = {'repo_url': 'https://github.com/anguyen-23/sila-testing',
                            'commit': '1' * 40, 'license_spdx': 'NOASSERTION'}
        card['local_path'] = str(directory / 'upstream')
        (directory / 'task.json').write_text(json.dumps(card))
        report = run_check(directory, backend='fake', gates=['G7'], write_report=False)
        findings = [f for g in report['gates'] for f in g['findings'] if f['code'] == 'G7.SILA_SOURCE_UNPROVEN']
        self.assertEqual(report['failed'], ['G7'])
        self.assertTrue(any('task pin differs' in f['message'] for f in findings), report)

    def test_g7_native_mode_remains_unresolved_without_executing_factory(self):
        ctx = _Context(FIXTURE, 'fake', None, None, False)
        self.addCleanup(ctx.close)
        # Only the report context changes; no native constructor or source import.
        ctx.backend = 'hardware'
        gate = Gate('G7', 'source')
        check_sila2_surface(ctx, gate)
        self.assertEqual([f.code for f in gate.findings], ['G7.SILA_NATIVE_UNRESOLVED'])


if __name__ == '__main__':
    unittest.main()
