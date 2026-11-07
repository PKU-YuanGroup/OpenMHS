"""OP-011 positive authorization is exact-binding and never weakens refusal."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.conformance.inprocess import client_for
from mhs.conformance.tests_core import RunOptions, SuiteContext, cap_009_cancellation
from mhs.driver.check import _Context
from tests.driver import gate_support as gs

CAP = 'cap.thermal.setpoint.v1'


class CancellationPermitTests(unittest.TestCase):
    def endpoint(self, *, gated=True, hardware=False):
        path = gs.copy_tutorial(self)
        needle = '@action(cap="cap.thermal.setpoint.v1",'
        gs.edit(path, 'driver.py', needle, needle + ' long_running=True, cancellable=True, max_duration_ms=5000,' +
                (' requires_permit=True,' if gated else ''))
        ctx = _Context(path, 'fake', None, None, False)
        self.addCleanup(ctx.close)
        ep = ctx.hardware_endpoint() if hardware else ctx.endpoint()
        self.addCleanup(ep.close)
        return ep

    def suite(self, ep, *, allow=False):
        suite = SuiteContext(client_for(ep.server), profile='MHS-Sim', requested_level='CL3',
            harness=ep.harness, options=RunOptions(allow_actuation=allow))
        suite.load(); suite.ensure_session()
        return suite

    def test_stock_gated_cancellation_uses_exact_binding_input_and_session_permit(self):
        ep = self.endpoint(); suite = self.suite(ep)
        with patch.object(suite.client, 'permit', wraps=suite.client.permit) as permit:
            result = cap_009_cancellation(suite)
        self.assertEqual(result.status, 'pass', result)
        self.assertEqual(permit.call_count, 1)
        args, kwargs = permit.call_args
        self.assertEqual(args[0], CAP)
        self.assertEqual(kwargs['resource'], ep.session.resource_id)
        self.assertEqual(kwargs['session_id'], suite.session_id)
        self.assertEqual(kwargs['device_id'], ep.device_id)
        self.assertEqual(len(suite.run_log.permits), 1)

    def test_selected_resource_not_earlier_same_capability_decoy_supplies_permission(self):
        ep = self.endpoint(); suite = self.suite(ep)
        target = suite.binding(ep.device_id, CAP)
        decoy = replace(target, capability={**target.capability, 'resource': 'other'}, requires_permit=False,
                        schema={'type': 'object', 'properties': {}, 'additionalProperties': False})
        suite.bindings.insert(0, decoy)
        with patch.object(suite.client, 'permit', wraps=suite.client.permit) as permit:
            result = cap_009_cancellation(suite)
        self.assertEqual(result.status, 'pass', result)
        self.assertEqual(permit.call_args.kwargs['resource'], target.resource)
        self.assertIn('target_temperature', permit.call_args.args[1])

    def test_ungated_cancellation_does_not_request_permission(self):
        ep = self.endpoint(gated=False); suite = self.suite(ep)
        with patch.object(suite.client, 'permit', side_effect=AssertionError('not required')):
            self.assertEqual(cap_009_cancellation(suite).status, 'pass')
        self.assertEqual(suite.run_log.permits, [])

    def test_failed_and_malformed_permits_do_not_dispatch_positive_command(self):
        for response in (None, {}, {'permit_id': ''}, {'permit_id': 1}, RuntimeError('controlled denial')):
            with self.subTest(response=response):
                ep = self.endpoint(); suite = self.suite(ep); mark = ep.mark()
                kwargs = {'side_effect': response} if isinstance(response, BaseException) else {'return_value': response}
                with patch.object(suite, 'permit', **kwargs), patch.object(suite, 'invoke', side_effect=AssertionError('no dispatch')):
                    result = cap_009_cancellation(suite)
                self.assertEqual(result.status, 'fail', result)
                self.assertIn('permit', result.detail)
                self.assertEqual([len(v) for v in ep.actuations(mark)], [0, 0])

    def test_hardware_view_without_operator_approval_is_not_granted_or_dispatched(self):
        ep = self.endpoint(hardware=True); suite = self.suite(ep, allow=True); mark = ep.mark()
        with patch.object(suite, 'invoke', side_effect=AssertionError('no command without approval')):
            result = cap_009_cancellation(suite)
        self.assertEqual(result.status, 'skip', result)
        self.assertIn('never invents permits on hardware', result.detail)
        self.assertEqual([len(v) for v in ep.actuations(mark)], [0, 0])
        self.assertEqual(suite.run_log.permits, [])

    def test_missing_wrong_and_reused_permits_still_refuse_with_zero_native_or_bridge_actuation(self):
        ep = self.endpoint(); payload = {'target_temperature': 20}
        def reject(params):
            mark = ep.mark()
            result = ep.session.rpc('mhs.command', params)
            self.assertEqual(result['status'], 'rejected', result)
            self.assertEqual(result['error']['mhs_code'], 'MHS.SAFETY.PERMIT_INVALID')
            self.assertEqual([len(v) for v in ep.actuations(mark)], [0, 0])
        base = {'session_id': ep.session.session_id, 'device_id': ep.device_id, 'resource': ep.session.resource_id,
                'capability_id': CAP, 'input': payload, 'deadline_ms': 500}
        reject({**base, 'command_id': canonical.ulid()})
        permit = ep.session._test_permit(CAP, payload)
        reject({**base, 'input': {'target_temperature': 21}, 'permit_id': permit, 'command_id': canonical.ulid()})
        result = ep.session._final(ep.session.rpc('mhs.command', {**base, 'permit_id': permit, 'command_id': canonical.ulid()}))
        self.assertEqual(result['status'], 'completed', result)
        reject({**base, 'permit_id': permit, 'command_id': canonical.ulid()})


if __name__ == '__main__': unittest.main()
