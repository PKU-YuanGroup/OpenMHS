"""Acceptance gate plus repository cases for the gh.anguyen-23/sila-testing Phenix package.

Every case loads the package through the stock loader on its controlled peer (fake.py). Nothing imports the upstream
server, a SiLA library or comtypes, and no case reaches a network or an instrument.
"""
import importlib
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver.loader import import_driver_module
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
MODULE = import_driver_module(HERE)
CAPS, EXAMPLES = MODULE.CAPS, MODULE.EXAMPLES


class DriverGate(unittest.TestCase):
    def test_gate(self):
        report = check_driver(HERE, backend='fake')
        self.assertEqual(report['failed'], [], report)
        self.assertTrue(report['passed'], report)


class ControlledPhenixCases(unittest.TestCase):
    def open(self, **options):
        driver = load_driver(HERE, 'fake', options=options or None)
        self.addCleanup(driver.close)
        return driver

    def test_a_fresh_endpoint_is_disconnected_and_its_estop_is_not_achieved(self):
        driver = self.open()
        state = driver.read('main')
        self.assertFalse(state['IsConnected'])
        self.assertEqual(state['DeviceState'], 'Offline')
        self.assertEqual(state['AvailableProtocols'], [])
        # nothing was ever connected, so no fresh retirement proof exists: the e-stop does not claim a safe state
        self.assertFalse(driver.estop()['safe_state_achieved'])

    def test_explicit_connect_and_the_complete_command_scope(self):
        driver = self.open()
        self.assertEqual(driver.call(CAPS['Connect'], EXAMPLES['Connect']), {'DeviceName': 'Opera Phenix (Simulated)'})
        for name in ('StageIn', 'StageOut', 'GoIdle', 'GoStandby'):
            self.assertEqual(driver.call(CAPS[name], EXAMPLES.get(name, {})), {})
        output = driver.call(CAPS['RunAcquisitionProtocol'], EXAMPLES['RunAcquisitionProtocol'])
        self.assertEqual(output['Status'], "Acquisition 'BrightField_10x' completed successfully")
        values = driver.read('main')
        self.assertTrue(values['IsConnected'])
        self.assertTrue(values['execution_known'])
        self.assertEqual(values['acquisition_progress'], 1.0)
        self.assertEqual(values['last_progress_info'], 'Well R1C1 - 100%')
        self.assertEqual(values['StagePosition'], 'Transfer')
        self.assertTrue(driver.call(CAPS['Stop'])['stopped'])
        driver.reset()
        self.assertEqual(driver.call(CAPS['Disconnect']), {})
        state = driver.read('main')
        self.assertEqual((state['IsConnected'], state['DeviceState'], state['AvailableProtocols']), (False, 'Offline', []))

    def test_stage_out_leaves_the_plate_detected_as_the_simulation_does(self):
        driver = self.open()
        driver.call(CAPS['Connect'], EXAMPLES['Connect'])
        driver.call(CAPS['StageIn'], EXAMPLES['StageIn'])
        state = driver.read('main')
        self.assertEqual((state['StagePosition'], state['PlateDetected']), ('Operate', True))
        driver.call(CAPS['StageOut'], EXAMPLES['StageOut'])
        state = driver.read('main')
        self.assertEqual((state['StagePosition'], state['PlateDetected'], state['DeviceState']), ('Transfer', True, 'Idle'))

    def test_a_cached_idle_state_proves_neither_an_outcome_nor_the_safe_state(self):
        # the native DeviceState is a cached status (pheniximager_impl.py:158-162); a peer whose observation is not
        # authoritative cannot confirm that even Connect retired, and an Idle reading never makes the e-stop succeed
        driver = self.open(cached_idle=True)
        with self.assertRaisesRegex(Exception, 'no confirmed complete outcome'):
            driver.call(CAPS['Connect'], EXAMPLES['Connect'])
        self.assertEqual(driver.read('main', ['DeviceState'])['DeviceState'], 'Idle')
        self.assertFalse(driver.estop()['safe_state_achieved'])

    def test_an_acknowledged_stop_that_changes_nothing_is_not_a_safe_state(self):
        # the native Stop is an RCI STOP whose reply is only checked for a REJECT (rci_transport.py:241-243, 278-285): a
        # peer that acknowledges Stop and keeps acquiring leaves the e-stop unachieved and the latch held
        driver = self.open(ack_only=True, auto_complete=False)
        driver.call(CAPS['Connect'], EXAMPLES['Connect'])
        peer = driver.native.peer  # the lease registers its peer when the first request is made
        with self.assertRaises(Exception):  # the acquisition never completes within its bounded execution
            driver.call(CAPS['RunAcquisitionProtocol'], EXAMPLES['RunAcquisitionProtocol'])
        self.assertTrue(peer.active)
        self.assertFalse(driver.estop()['safe_state_achieved'])
        self.assertTrue(any(r['operation'] == 'invoke' and r['member'] == 'Stop' for r in peer.requests))
        self.assertTrue(peer.active)
        with self.assertRaises(Exception):
            driver.reset()

    def test_a_stale_idle_reading_is_no_proof_while_an_execution_is_active(self):
        # DeviceState Idle passes the declaration's unsafe_properties rule, but the authoritative observation still
        # lists the running execution, so the e-stop is not achieved (a native DeviceState is a cached value,
        # pheniximager_impl.py:158-162)
        driver = self.open(ack_only=True, auto_complete=False, stale_idle=True)
        driver.call(CAPS['Connect'], EXAMPLES['Connect'])
        peer = driver.native.peer
        with self.assertRaises(Exception):
            driver.call(CAPS['RunAcquisitionProtocol'], EXAMPLES['RunAcquisitionProtocol'])
        self.assertTrue(peer.active)
        self.assertEqual(driver.read('main', ['DeviceState'])['DeviceState'], 'Idle')
        self.assertFalse(driver.estop()['safe_state_achieved'])
        self.assertTrue(peer.active)

    def test_a_disconnect_by_another_client_during_a_run_leaves_the_estop_unachieved(self):
        # the upstream Disconnect checks only the connection (pheniximager_impl.py:207-215) and Stop then raises
        # NotConnected (:78-85, 263-265): once another client disconnects a running acquisition, nothing stops it
        driver = self.open(auto_complete=False)
        driver.call(CAPS['Connect'], EXAMPLES['Connect'])
        peer = driver.native.peer
        with self.assertRaises(Exception):  # the bounded call ends; the acquisition keeps running remotely
            driver.call(CAPS['RunAcquisitionProtocol'], EXAMPLES['RunAcquisitionProtocol'])
        self.assertTrue(peer.active)
        peer.foreign_disconnect()
        self.assertFalse(driver.estop()['safe_state_achieved'])
        self.assertTrue(any(r['operation'] == 'invoke' and r['member'] == 'Stop' for r in peer.requests))
        self.assertTrue(peer.active)
        with self.assertRaises(Exception):
            driver.reset()

    def test_an_unknown_protocol_fails_and_starts_no_acquisition(self):
        driver = self.open()
        driver.call(CAPS['Connect'], EXAMPLES['Connect'])
        with self.assertRaises(Exception):
            driver.call(CAPS['RunAcquisitionProtocol'], dict(EXAMPLES['RunAcquisitionProtocol'], ProtocolName='NotAProtocol'))
        state = driver.read('main', ['DeviceState', 'StagePosition', 'execution_known'])
        self.assertEqual((state['DeviceState'], state['StagePosition'], state['execution_known']), ('Idle', 'Transfer', False))


class NativeRefusal(unittest.TestCase):
    def test_every_native_path_refuses_before_any_import_or_connection(self):
        with self.assertRaisesRegex(RuntimeError, 'native admission refused'):
            MODULE.Driver(backend='hardware')
        native = importlib.import_module('.native', MODULE.__package__)
        with self.assertRaisesRegex(RuntimeError, 'native SiLA 2 admission is refused'):
            native.connect()


if __name__ == '__main__':
    unittest.main()
