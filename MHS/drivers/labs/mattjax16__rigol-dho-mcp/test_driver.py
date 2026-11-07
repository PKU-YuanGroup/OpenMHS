"""Acceptance gate plus repository-specific cases for the rigol-dho-mcp package.

Every case runs the package's controlled MCP peer (fake.py) through the stock loader,
server and artifact store. Nothing imports the upstream server or an MCP library.
"""
import importlib
import json
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server, close_server
from mhs.driver.loader import import_driver_module
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
MODULE = import_driver_module(HERE)
CAPS = MODULE.CAPS
OVERLAY = json.loads((HERE / 'site-limits.example.json').read_text())


class DriverGate(unittest.TestCase):
    def test_gate(self):
        report = check_driver(HERE, backend='fake')
        self.assertEqual(report['failed'], [], report)


class StockServerCases(unittest.TestCase):
    def open(self, overlay=True):
        driver = load_driver(HERE, backend='fake')
        peer = driver.native
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = build_server(driver, site_limits=OVERLAY if overlay else None, artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        self.addCleanup(client.close)
        device = next(iter(server.devices))
        session = client.open_session([device], mode=server.devices[device].mode)['session_id']
        return peer, client, device, session

    def invoke(self, client, device, cap, args=None):
        receipt = client.invoke(cap, args or {}, device_id=device)
        if receipt['status'] in ('accepted', 'running'):
            receipt = client.wait(receipt['operation_id'], timeout=5)
        return receipt

    def tool_calls(self, peer, name):
        return [call for call in peer.calls
                if call['message']['method'] == 'tools/call' and call['message']['params']['name'] == name]

    def test_measurement_waveform_and_screenshot_keep_complete_primary_results(self):
        peer, client, device, session = self.open()
        receipt = self.invoke(client, device, CAPS['get_measurement'], {'item': 'VPP', 'channel': 2})
        self.assertEqual(receipt['status'], 'completed', receipt)
        self.assertEqual(receipt['output']['item'], 'VPP')
        self.assertEqual(receipt['output']['channel'], 2)
        receipt = self.invoke(client, device, CAPS['get_waveform'], {'mode': 'screen', 'max_points': 100})
        self.assertEqual(receipt['status'], 'completed', receipt)
        data = json.loads(client.read_artifact(receipt['output']['artifact_ref'], session_id=session)['data'])
        # Floor decimation can return more points than max_points; every returned sample is kept.
        self.assertEqual(data['points_captured'], len(peer.raw_screen))
        self.assertEqual(len(data['time_s']), data['points_returned'])
        self.assertEqual(len(data['voltage_V']), data['points_returned'])
        self.assertGreater(data['points_returned'], 100)
        receipt = self.invoke(client, device, CAPS['get_screenshot'])
        self.assertEqual(receipt['status'], 'completed', receipt)
        self.assertEqual((receipt['output']['width'], receipt['output']['height']), (3, 2))
        self.assertEqual(receipt['output']['media_type'], 'image/png')

    def test_estop_sends_stop_and_needs_a_fresh_stop_status(self):
        peer, client, device, session = self.open()
        receipt = self.invoke(client, device, CAPS['run_control'], {'action': 'run'})
        self.assertEqual(receipt['status'], 'completed', receipt)
        self.assertEqual(peer.trigger_status, 'RUN')
        stopped = client.estop('test', device_id=device, session_id=session)
        self.assertEqual(stopped['status'], 'completed', stopped)
        self.assertTrue(stopped['output']['safe_state_achieved'], stopped)
        self.assertEqual(peer.trigger_status, 'STOP')
        protective = [call for call in peer.calls if call['lane'] == 'protective']
        self.assertEqual([call['message']['params']['name'] for call in protective][:2], ['run_control', 'get_status'])
        self.assertEqual(protective[0]['message']['params']['arguments'], {'action': 'stop'})
        self.assertTrue(client.safety_status(device)['status']['safe_state']['achieved'])
        self.assertEqual(client.reset(device, session_id=session)['status'], 'completed')

    def test_estop_is_not_achieved_when_the_scope_keeps_running(self):
        peer, client, device, session = self.open()
        self.invoke(client, device, CAPS['run_control'], {'action': 'run'})

        def stuck(message, response, lane):
            # The scope ignores :STOP: the fresh status still reads RUN.
            if message['method'] == 'tools/call' and message['params']['name'] == 'run_control':
                peer.trigger_status = 'RUN'
                response['result']['content'][0]['text'] = 'Sent :STOP. Trigger status: RUN'
            if message['method'] == 'tools/call' and message['params']['name'] == 'get_status':
                peer.trigger_status = 'RUN'
                response['result']['content'][0]['text'] = json.dumps(peer.status(), separators=(',', ':'))
            return response
        peer.after = stuck
        stopped = client.estop('test', device_id=device, session_id=session)
        self.assertNotEqual(stopped['status'], 'completed', stopped)
        self.assertFalse(client.safety_status(device)['status']['safe_state']['achieved'])
        self.assertNotEqual(client.reset(device, session_id=session)['status'], 'completed')

    def test_memory_waveform_requires_a_fresh_stop_and_never_stops_implicitly(self):
        peer, client, device, _session = self.open()
        self.invoke(client, device, CAPS['run_control'], {'action': 'run'})
        receipt = self.invoke(client, device, CAPS['get_waveform'], {'mode': 'memory'})
        self.assertEqual(receipt['status'], 'failed', receipt)
        self.assertEqual(receipt['error']['mhs_code'], 'MHS.DEVICE.PRECONDITION_UNMET')
        self.assertEqual(self.tool_calls(peer, 'get_waveform'), [])
        self.assertEqual([call['message']['params']['arguments'] for call in self.tool_calls(peer, 'run_control')],
                         [{'action': 'run'}])
        self.invoke(client, device, CAPS['run_control'], {'action': 'stop'})
        receipt = self.invoke(client, device, CAPS['get_waveform'], {'mode': 'memory', 'include_data': False})
        self.assertEqual(receipt['status'], 'completed', receipt)

    def test_operator_required_bounds_refuse_before_any_tool_call(self):
        peer, client, device, _session = self.open(overlay=False)
        receipt = self.invoke(client, device, CAPS['configure_channel'], {'channel': 1, 'scale': 0.5})
        self.assertEqual(receipt['error']['mhs_code'], 'MHS.SAFETY.LIMITS_UNSET', receipt)
        receipt = self.invoke(client, device, CAPS['configure_channel'], {'channel': 5})
        self.assertEqual(receipt['error']['mhs_code'], 'MHS.SAFETY.ENVELOPE_VIOLATION', receipt)
        self.assertEqual(self.tool_calls(peer, 'configure_channel'), [])
        peer, client, device, _session = self.open(overlay=True)
        receipt = self.invoke(client, device, CAPS['configure_channel'], {'channel': 1, 'scale': 50})
        self.assertEqual(receipt['error']['mhs_code'], 'MHS.SAFETY.ENVELOPE_VIOLATION', receipt)
        receipt = self.invoke(client, device, CAPS['configure_channel'], {'channel': 1, 'scale': 0.5})
        self.assertEqual(receipt['status'], 'completed', receipt)
        self.assertEqual(receipt['output']['scale_V_per_div'], '0.5')

    def test_unconfirmed_effect_blocks_new_effects_until_estop_and_reset(self):
        peer, client, device, session = self.open()
        peer.measurement_value = '****'  # the handler returns the raw string when float() fails
        receipt = self.invoke(client, device, CAPS['get_measurement'], {'item': 'VPP'})
        self.assertEqual(receipt['status'], 'unknown', receipt)
        receipt = self.invoke(client, device, CAPS['run_control'], {'action': 'run'})
        self.assertEqual(receipt['error']['mhs_code'], 'MHS.SAFETY.ESTOP_ENGAGED', receipt)
        self.assertEqual(self.tool_calls(peer, 'run_control'), [])
        self.assertEqual(client.estop('settle', device_id=device, session_id=session)['status'], 'completed')
        self.assertEqual(client.reset(device, session_id=session)['status'], 'completed')
        peer.measurement_value = 1.5  # placeholder
        self.assertEqual(self.invoke(client, device, CAPS['get_measurement'], {'item': 'VPP'})['status'], 'completed')

    def test_error_text_and_discovery_drift_are_failures(self):
        peer, client, device, _session = self.open()

        def error_text(message, response, lane):
            if message['method'] == 'tools/call' and message['params']['name'] == 'identify':
                response['result']['content'][0]['text'] = 'Error: Could not connect to the oscilloscope'
            return response
        peer.after = error_text
        receipt = self.invoke(client, device, CAPS['identify'])
        self.assertEqual(receipt['status'], 'failed', receipt)
        peer, client, device, _session = self.open()
        rows = [{'name': name, 'inputSchema': spec['input']} for name, spec in MODULE.CONFIG['tools'].items()]
        rows.append({'name': 'scpi_command', 'inputSchema': {'type': 'object', 'properties': {}}})
        peer.discovery = {'tools': rows}
        receipt = self.invoke(client, device, CAPS['identify'])
        self.assertEqual(receipt['status'], 'failed', receipt)
        self.assertFalse(any(call['message']['method'] == 'tools/call' for call in peer.calls))


class NativeRefusal(unittest.TestCase):
    def test_every_native_path_refuses_before_import_or_connection(self):
        with self.assertRaisesRegex(RuntimeError, 'native admission blocked'):
            MODULE.RigolDhoMcp(backend='hardware')
        native = importlib.import_module('.native', MODULE.__package__)
        with self.assertRaisesRegex(RuntimeError, 'native admission blocked'):
            native.connect()


if __name__ == '__main__':
    unittest.main()
