"""SDK-local full workflow and explicit-preparation stock fake gate control."""
from pathlib import Path
import unittest
from mhs.adapter import load_driver
from mhs.driver.loader import import_driver_module
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class ControlledPhenixTests(unittest.TestCase):
    def test_complete_fake_gate_with_declared_stock_connect_preparation(self):
        report = check_driver(HERE, backend='fake')
        self.assertEqual(report['failed'], [], report)
        self.assertTrue(report['passed'], report)
        # This fake-only gate declaration never changes ordinary loading.
        driver = load_driver(HERE, 'fake'); self.addCleanup(driver.close)
        self.assertFalse(driver.read('main', ['IsConnected'])['IsConnected'])
        self.assertFalse(driver.estop()['safe_state_achieved'])

    def test_explicit_connect_and_full_command_scope(self):
        module = import_driver_module(HERE)
        driver = load_driver(HERE, 'fake'); self.addCleanup(driver.close)
        for name in ('Connect', 'StageIn', 'StageOut', 'GoIdle', 'GoStandby', 'RunAcquisitionProtocol'):
            output = driver.call(module.CAPS[name], module.EXAMPLES.get(name, {}))
            if name == 'RunAcquisitionProtocol': self.assertIn('stage ejected', output['Status'])
        values = driver.read('main')
        self.assertTrue(values['IsConnected']); self.assertEqual(values['acquisition_progress'], 1.0)
        self.assertTrue(driver.call(module.CAPS['Stop'])['stopped'])
        driver.reset(); self.assertEqual(driver.call(module.CAPS['Disconnect']), {})
        self.assertFalse(driver.read('main', ['IsConnected'])['IsConnected'])


if __name__ == '__main__': unittest.main()
