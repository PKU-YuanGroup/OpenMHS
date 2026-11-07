"""Package-local smoke and the stock acceptance oracle; no upstream imports."""
from pathlib import Path
import unittest
from mhs.driver.loader import import_driver_module
from mhs.testing import check_driver

HERE=Path(__file__).resolve().parent


class FixtureTests(unittest.TestCase):
    def test_stock_gate(self):
        self.assertEqual(check_driver(HERE,backend='fake')['failed'],[])

    def test_selected_authority_and_real_controlled_transition(self):
        module=import_driver_module(HERE)
        driver=module.Driver(backend='fake',base_dir=HERE)
        try:
            self.assertEqual(len(driver._model.bindings),16)
            self.assertEqual(driver.call(module.CAPS['run_control'],{'action':'run'})['text'],'Sent :RUN. Trigger status: RUN')
            self.assertEqual(driver.read('main')['trigger_status'],'RUN')
            self.assertTrue(driver.estop()['safe_state_achieved'])
            self.assertEqual(driver.read('main')['trigger_status'],'STOP')
        finally:driver.close()
