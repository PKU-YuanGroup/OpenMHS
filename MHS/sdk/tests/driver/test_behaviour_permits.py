"""Positive G6 overlays need real input-bound permits on the simulated endpoint."""
import copy
import unittest

from mhs.driver.behaviour import BehaviourRun
from mhs.driver.check import _Context
from mhs.driver.build import hardware_device_id
from mhs.server import action_digest
from tests.driver import gate_support as gs

CAP = 'cap.thermal.setpoint.v1'


class OperatorOverlayPermitTests(unittest.TestCase):
    def context(self, *, gated=True, companions=False):
        directory = gs.copy_tutorial(self)
        source = (directory / 'driver.py').read_text()
        if gated:
            source = source.replace('@action(cap="cap.thermal.setpoint.v1",',
                                    '@action(cap="cap.thermal.setpoint.v1", requires_permit=True,')
        old = 'limit=Limit(min=5, max=80, source="vendor_doc", ref="MANUAL.md:9"))})'
        assert source.count(old) == 1
        replacement = 'limit=Limit.operator_required("controlled regression"))'
        if companions:
            replacement += ', "rate": Field(limit=Limit.operator_required("controlled rate"))'
            source = source.replace('def go_to(self, target_temperature):',
                                    'def go_to(self, target_temperature, rate):')
            source = source.replace('        self.native.set_setpoint(target_temperature)',
                                    '        self.native.set_zone_trim(target_temperature, rate)\n'
                                    '        self.native.set_setpoint(target_temperature)')
        source = source.replace(old, replacement + '})')
        (directory / 'driver.py').write_text(source)
        ctx = _Context(directory, 'fake', None, None, False)
        self.addCleanup(ctx.close)
        return ctx

    def run_probe(self, ctx, *, fail_permit=False):
        calls = []
        def endpoint(**options):
            result = ctx.endpoint(**options)
            original = result.session.rpc
            def capture(method, params):
                if method == 'mhs.safety.permit' and fail_permit:
                    raise RuntimeError('controlled permit service refusal')
                value = original(method, params)
                calls.append((method, copy.deepcopy(params), copy.deepcopy(value)))
                return value
            result.session.rpc = capture
            return result
        run = BehaviourRun(endpoint=endpoint, model=ctx.model, hardware_view=None,
                           hardware_id=hardware_device_id(ctx.model))
        _, bindings = run._with(run._discover)
        run._operator_path(bindings[CAP], 'target_temperature')
        return run.findings, calls

    def test_positive_overlay_uses_one_exact_input_single_use_stock_permit(self):
        findings, calls = self.run_probe(self.context())
        self.assertEqual(findings, [])
        permits = [(p, result) for method, p, result in calls if method == 'mhs.safety.permit']
        self.assertEqual(len(permits), 1)
        request, permit = permits[0]
        self.assertEqual(request['ttl_s'], 30)
        self.assertNotIn('approvals', request)
        self.assertEqual(request['input_digest'], action_digest(CAP, request['resource'], request['input']))
        commands = [(p, result) for method, p, result in calls if method == 'mhs.command']
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][1]['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET')
        self.assertNotIn('permit_id', commands[0][0])
        positive, receipt = commands[1]
        self.assertEqual(positive['permit_id'], permit['permit_id'])
        self.assertEqual(positive['input'], request['input'])
        self.assertEqual(positive['resource'], request['resource'])
        self.assertEqual(positive['session_id'], request['session_id'])
        self.assertEqual(receipt['status'], 'completed')

    def test_missing_and_partial_overlays_still_refuse_before_any_permit(self):
        findings, calls = self.run_probe(self.context(companions=True))
        self.assertEqual(findings, [])
        commands = [(p, r) for m, p, r in calls if m == 'mhs.command']
        self.assertEqual(len(commands), 3)
        for params, receipt in commands[:2]:
            self.assertEqual(receipt['status'], 'rejected')
            self.assertEqual(receipt['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET')
            self.assertNotIn('permit_id', params)
            self.assertEqual(receipt['state_revision_before'], receipt['state_revision_after'])
        self.assertEqual(commands[2][1]['status'], 'completed')
        self.assertEqual(sum(m == 'mhs.safety.permit' for m, _, _ in calls), 1)

    def test_ungated_overlay_does_not_create_a_permit(self):
        findings, calls = self.run_probe(self.context(gated=False))
        self.assertEqual(findings, [])
        self.assertFalse(any(m == 'mhs.safety.permit' for m, _, _ in calls))

    def test_failed_permit_is_an_overlay_error_and_never_dispatched(self):
        findings, calls = self.run_probe(self.context(), fail_permit=True)
        self.assertEqual([f[0] for f in findings], ['G6.OPERATOR_REQUIRED_OVERLAY'])
        self.assertIn('controlled permit service refusal', findings[0][1])
        commands = [r for m, _, r in calls if m == 'mhs.command']
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET')

    def test_hardware_view_cannot_obtain_test_approval_or_dispatch(self):
        ctx = self.context()
        endpoint = ctx.hardware_endpoint()
        self.addCleanup(endpoint.close)
        self.assertEqual(endpoint.session.mode, 'hardware')
        mark = endpoint.mark()
        with self.assertRaisesRegex(RuntimeError, 'hardware approvals are not invented'):
            endpoint.session.command(CAP, {'target_temperature': 37}, test_permit=True)
        self.assertEqual([len(v) for v in endpoint.actuations(mark)], [0, 0])
        self.assertEqual(endpoint.server._permits, {})


if __name__ == '__main__':
    unittest.main()
