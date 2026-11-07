"""Explicit stock Connect preparation, admission isolation and owned cleanup."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.driver import prerequisites
from mhs.driver.behaviour import BehaviourRun
from mhs.driver.check import _Context, run_check
from tests.driver.sila2_support import FIXTURE, fixture


class GatePrerequisiteTests(unittest.TestCase):
    def package(self):
        holder = tempfile.TemporaryDirectory(prefix='mhs-prerequisite-test-')
        self.addCleanup(holder.cleanup)
        path = Path(holder.name) / 'phenix'
        shutil.copytree(FIXTURE, path, ignore=shutil.ignore_patterns('__pycache__', 'check-report.json'))
        return path

    def context(self, directory=FIXTURE):
        ctx = _Context(directory, 'fake', None, None, False)
        self.addCleanup(ctx.close)
        return ctx

    @staticmethod
    def peer(driver):
        # PeerLease construction is intentionally lazy; this original read has
        # no Connect, Stop, reset or acquisition side effect.
        driver.read('main', ['IsConnected'])
        return object.__getattribute__(driver.inner._transport, '_mhs_target').peer

    def closed(self, driver, peer):
        worker = driver.inner._cleanup
        self.assertIsNotNone(worker)
        worker.join(1)
        self.assertFalse(worker.is_alive(), 'retained cleanup did not settle')
        self.assertTrue(peer.closed)

    def test_full_stock_fake_gate_passes_with_explicit_preparation(self):
        report = run_check(FIXTURE, backend='fake', write_report=False)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['failed'], [])
        self.assertEqual(next(g for g in report['gates'] if g['id'] == 'G9')['status'], 'pass')

    def test_closed_declaration_rejects_hidden_effects_and_incomplete_cases(self):
        original = json.loads((FIXTURE / prerequisites.FILE).read_text())
        variants = []
        for name in ('RunAcquisitionProtocol', 'StageIn', 'Stop', 'Disconnect'):
            item = copy.deepcopy(original)
            item['connect'] = {'capability_id': fixture.CAPS[name], 'input': fixture.EXAMPLES.get(name, {})}
            variants.append(item)
        for extra in ({'prepare': 'driver.inner.connect()'}, {'reset': True}, {'native': True}):
            variants.append({**original, **extra})
        for cases in (original['cases'][:-1], original['cases'] + ['unknown'], original['cases'] + ['safety']):
            variants.append({**original, 'cases': cases})
        variants.append({**original, 'profile': 'arbitrary-workflow'})
        variants.append({**original, 'connect': {**original['connect'], 'input': {'PhenixHost': 1}}})
        for document in variants:
            with self.subTest(document=document):
                path = self.package()
                (path / prerequisites.FILE).write_text(json.dumps(document))
                ctx = self.context(path)
                self.assertIsNotNone(ctx.prerequisites_problem)
                with patch.object(ctx, 'open_driver', side_effect=AssertionError('must not open')):
                    with self.assertRaisesRegex(Exception, 'gate-prerequisites'):
                        ctx.endpoint(gate_case='safety')
                report = run_check(path, backend='fake', gates=['G1'], write_report=False)
                self.assertIn('G1', report['failed'])

    def test_duplicate_keys_and_oversized_input_refused_before_open(self):
        for value in ('{"profile":1,"profile":2}', ' ' * 16385):
            path = self.package(); (path / prerequisites.FILE).write_text(value)
            ctx = self.context(path)
            self.assertIsNotNone(ctx.prerequisites_problem)
            self.assertFalse(ctx.logs)

    def test_no_document_and_unselected_paths_keep_original_disconnected_state(self):
        ctx = self.context()
        ep = ctx.endpoint()
        self.addCleanup(ep.close)
        driver = ep.server.devices[ep.device_id].bridge
        peer = self.peer(driver)
        self.assertFalse(peer.connected)
        self.assertEqual(ctx.preparation_runs, [])
        self.assertFalse(any(r['operation'] == 'invoke' for r in peer.requests))
        denied = ep.session.command(fixture.CAPS['Connect'], fixture.EXAMPLES['Connect'])
        self.assertEqual(denied['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET')
        self.assertFalse(any(r['member'] == 'Connect' for r in peer.requests))
        path = self.package(); (path / prerequisites.FILE).unlink()
        old = self.context(path)
        self.assertIsNone(old.prerequisites)
        with self.assertRaisesRegex(Exception, 'no gate prerequisite'):
            old.endpoint(gate_case='safety')

    def test_connect_case_does_not_prepare_itself_or_fill_other_negative_limits(self):
        ctx = self.context()
        ep = ctx.endpoint(gate_case=fixture.CAPS['Connect'])
        self.addCleanup(ep.close)
        self.assertEqual(ctx.preparation_runs, [])
        self.assertEqual(ep.session.command(fixture.CAPS['Connect'], fixture.EXAMPLES['Connect'])['error']['mhs_code'],
                         'MHS.SAFETY.LIMITS_UNSET')
        prepared = ctx.endpoint(gate_case=fixture.CAPS['StageIn'])
        self.addCleanup(prepared.close)
        self.assertEqual(len(ctx.preparation_runs), 1)
        mark = prepared.mark()
        denied = prepared.session.command(fixture.CAPS['StageIn'], fixture.EXAMPLES['StageIn'])
        self.assertEqual(denied['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET')
        self.assertEqual([len(x) for x in prepared.actuations(mark)], [0, 0])

    def test_preparation_session_close_preserves_target_grants_artifact_and_unlatched_state(self):
        ctx = self.context()
        ep = ctx.endpoint(site_limits=ctx.example_overlay)
        self.addCleanup(ep.close)
        driver = ep.server.devices[ep.device_id].bridge
        peer = self.peer(driver)
        cap, payload = fixture.CAPS['StageIn'], fixture.EXAMPLES['StageIn']
        permit = ep.session._test_permit(cap, payload)
        grant_before = copy.deepcopy(ep.server._permits[permit])
        icon = ep.session.command(fixture.CAPS['DisplayIcon'], {})
        self.assertEqual(icon['status'], 'completed', icon)
        uri = icon['artifacts'][0]['uri']
        artifact_before = ep.server.read_artifact(uri, session_id=ep.session.session_id)
        mark = len(peer.requests)
        record = prerequisites.execute(ep.server, ctx.prerequisites)
        self.assertNotEqual(record['session_id'], ep.session.session_id)
        self.assertFalse(record['session_close']['summary']['cancellation_pending'])
        self.assertEqual(record['session_close']['summary']['operation_ids'], [])
        self.assertEqual(ep.server._permits[permit], grant_before)
        self.assertEqual(ep.server.read_artifact(uri, session_id=ep.session.session_id), artifact_before)
        self.assertTrue(peer.connected)
        self.assertFalse(driver.inner._latched)
        self.assertFalse(ep.server._latched.get(ep.device_id, False))
        self.assertEqual([r['member'] for r in peer.requests[mark:] if r['operation'] == 'invoke'], ['Connect'])
        receipt = ep.session.rpc('mhs.command', {'session_id': ep.session.session_id, 'device_id': ep.device_id,
            'resource': ep.session.resource_id, 'capability_id': cap, 'input': payload,
            'permit_id': permit, 'command_id': canonical.ulid(), 'deadline_ms': 500})
        self.assertEqual(receipt['status'], 'completed', receipt)

    def test_denied_connect_and_false_ready_refuse_dependent_case_and_close_owned_driver(self):
        for scenario in ('denied', 'false-ready'):
            with self.subTest(scenario=scenario):
                ctx = self.context(); driver = ctx.open_driver(); peer = self.peer(driver)
                dispatch = peer._dispatch
                def reply(message):
                    if message['operation'] == 'invoke' and message['member'] == 'Connect':
                        if scenario == 'denied': return peer._error('CommunicationError')
                        return {'payload': {'DeviceName': 'false ready'}}
                    return dispatch(message)
                with patch.object(peer, '_dispatch', side_effect=reply), patch.object(ctx, 'open_driver', return_value=driver), \
                        patch.object(driver, 'close', wraps=driver.close) as close:
                    with self.assertRaisesRegex(ValueError, 'Connect prerequisite'):
                        ctx.endpoint(gate_case='safety')
                    self.assertEqual(close.call_count, 1)
                self.closed(driver, peer)
                self.assertFalse(any(r['member'] in ('Stop', 'StageIn', 'RunAcquisitionProtocol') for r in peer.requests))
                self.assertEqual(ctx.preparation_runs, [])

    def test_late_connect_is_bounded_and_retains_cleanup_until_worker_retires(self):
        ctx = self.context(); driver = ctx.open_driver(); peer = self.peer(driver)
        entered, release = peer.block('after:invoke:Connect')
        start = time.monotonic()
        try:
            with patch.object(ctx, 'open_driver', return_value=driver):
                with self.assertRaisesRegex(ValueError, 'Connect prerequisite did not complete'):
                    ctx.endpoint(gate_case='safety')
            self.assertTrue(entered.is_set())
            self.assertLess(time.monotonic() - start, 1.5)
            self.assertIsNotNone(driver.inner._normal)
            self.assertFalse(peer.closed)
            self.assertFalse(any(r['member'] == 'Stop' for r in peer.requests))
        finally:
            release.set()
        until = time.monotonic() + 1
        while not peer.closed and time.monotonic() < until: time.sleep(.002)
        self.closed(driver, peer)
        self.assertIsNone(driver.inner._normal)

    def test_hardware_projection_borrows_driver_and_closes_it_once(self):
        ctx = self.context(); driver = ctx.open_driver(); peer = self.peer(driver)
        with patch.object(ctx, 'open_driver', return_value=driver), patch.object(driver, 'close', wraps=driver.close) as close:
            ep = ctx.hardware_endpoint()
            self.assertEqual(ep.session.mode, 'hardware')
            self.assertEqual(len(ctx._preparation_servers), 1)
            prep = ctx._preparation_servers[0]
            self.assertTrue(prep._closed)
            self.assertIs(next(iter(prep.devices.values())).bridge, driver)
            self.assertIs(ep.server.devices[ep.device_id].bridge, driver)
            self.assertEqual(close.call_count, 0)
            self.assertFalse(peer.closed)
            self.assertEqual([r['member'] for r in peer.requests if r['operation'] == 'invoke'], ['Connect'])
            ep.close(); ctx.close()
            self.assertEqual(close.call_count, 1)
        self.closed(driver, peer)

    def test_projection_failures_before_and_after_target_server_keep_single_cleanup_owner(self):
        for point in ('store', 'session'):
            with self.subTest(point=point):
                ctx = self.context(); driver = ctx.open_driver(); peer = self.peer(driver)
                target = patch.object(ctx, '_artifact_store', side_effect=RuntimeError('projection fail')) if point == 'store' else \
                    patch('mhs.driver.behaviour.Session', side_effect=RuntimeError('projection fail'))
                with patch.object(ctx, 'open_driver', return_value=driver), patch.object(driver, 'close', wraps=driver.close) as close, target:
                    with self.assertRaisesRegex(RuntimeError, 'projection fail'):
                        ctx.hardware_endpoint()
                    ctx.close()
                    self.assertEqual(close.call_count, 1)
                self.closed(driver, peer)
                self.assertEqual(len(ctx._preparation_servers), 1)
                self.assertTrue(ctx._preparation_servers[0]._closed)
                self.assertFalse(any(r['member'] in ('Stop', 'Disconnect') for r in peer.requests))

    def test_native_mode_refused_before_any_factory_and_preparation(self):
        ctx = self.context(); ctx.backend = 'hardware'
        with self.assertRaisesRegex(ValueError, 'controlled fake'):
            prerequisites.load(ctx)
        self.assertFalse(ctx.logs)
        self.assertEqual(ctx.preparation_runs, [])

    def test_computed_import_mutation_of_prerequisite_function_and_policy_is_caught(self):
        from tests.driver.test_qcodes_integrity import QcodesGateIntegrityTests
        runner = QcodesGateIntegrityTests()
        for mutation, member in [('module.execute=lambda *a: {}', 'execute'), ('module.COMMAND_TIMEOUT_MS=999999', 'COMMAND_TIMEOUT_MS'),
                                 ('module.PROFILE="anything"', 'PROFILE')]:
            source = 'from importlib import import_module\nmodule=import_module(".".join(["mhs","driver","prerequisites"]))\n' + mutation + '\n'
            result = runner.stock(source)
            self.assertEqual(result['static'], [])
            self.assertEqual(result['gate']['status'], 'fail', result)
            self.assertTrue(any(f['code'] == 'G3.GATE_TAMPERED' and member in f['message'] for f in result['gate']['findings']), result)


class StopRecordingTests(unittest.TestCase):
    context = GatePrerequisiteTests.context
    peer = staticmethod(GatePrerequisiteTests.peer)

    def test_only_real_stop_invocation_has_stop_phase_during_concurrent_action_window(self):
        ctx = self.context(); ep = ctx.endpoint(gate_case='safety')
        self.addCleanup(ep.close)
        mark = ep.log.mark()
        with ep.log.window('act'):
            receipt = ep.session.estop()
        self.assertEqual(receipt['status'], 'completed', receipt)
        stops = ep.log.in_phase('estop', mark)
        self.assertTrue(stops)
        self.assertTrue(all(c.name == 'request' and c.args[0]['operation'] == 'invoke' and c.args[0]['member'] == 'Stop' for c in stops))
        self.assertTrue(all(c.phase != 'estop' for c in ep.log.since() if c.kind == 'call' and c.args and
                            isinstance(c.args[0], dict) and c.args[0].get('member') == 'Connect'))
        mark = ep.log.mark(); self.assertEqual(ep.session.reset()['result']['status'], 'completed')
        self.assertEqual(ep.log.in_phase('estop', mark), [])

    def test_noop_protective_method_cannot_borrow_an_ordinary_call_as_stop_evidence(self):
        ctx = self.context()
        def endpoint(**kwargs):
            ep = ctx.endpoint(**kwargs)
            driver = ep.server.devices[ep.device_id].bridge
            driver.inner._invoke_stop = lambda work: None  # explicit fault injection, never production setup
            return ep
        run = BehaviourRun(endpoint=endpoint, model=ctx.model, hardware_view=None,
                           fixtures=ctx.fixtures, has_prerequisites=True)
        published, bindings = run._with(run._discover)
        safety = published['safety']
        run._estop(bindings, safety['safe_state']['achieved_by'], safety['estop']['native'])
        self.assertIn('G6.ESTOP_NO_NATIVE', [row[0] for row in run.findings])

    def test_typed_stop_failure_is_not_hidden_by_recorded_native_call(self):
        ctx = self.context(); ep = ctx.endpoint(gate_case='safety')
        self.addCleanup(ep.close)
        peer = self.peer(ep.server.devices[ep.device_id].bridge); dispatch = peer._dispatch
        def malformed(message):
            if message['operation'] == 'invoke' and message['member'] == 'Stop': return {'payload': {'unexpected': 1}}
            return dispatch(message)
        with patch.object(peer, '_dispatch', side_effect=malformed):
            mark = ep.log.mark(); receipt = ep.session.estop()
            self.assertTrue(ep.log.in_phase('estop', mark))
            self.assertEqual(receipt['status'], 'failed', receipt)
            self.assertFalse(receipt['output']['safe_state_achieved'])


if __name__ == '__main__': unittest.main()
