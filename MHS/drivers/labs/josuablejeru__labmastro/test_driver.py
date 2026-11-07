"""Acceptance run of the labmastro TagDriver: the gate, plus cases specific to this supply.

Add cases, never remove the check_driver call.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ON, OFF = "x-cap.josuablejeru.output_on.v1", "x-cap.josuablejeru.output_off.v1"
OUTPUT = ("holding", 0x0001)
OVERLAY = {"openmhs": "0.9", "site": "test bench", "devices": {"mhs://localhost/hanmatek-hm": {
    "voltage_setpoint": {"min": 0, "max": 12, "unit": "V", "source": "operator", "reason": "test bench"}}}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HanmatekCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_output_commands_write_and_confirm_register_0x0001(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call(ON, {}), {"output_enabled": True})
        self.assertEqual(driver.native.registers[OUTPUT], 1)
        self.assertEqual(driver.call(OFF, {}), {"output_enabled": False})
        self.assertEqual(driver.native.registers[OUTPUT], 0)

    def test_setpoint_is_written_in_register_words_and_shown_as_last_acknowledged(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.write("main", {"voltage_setpoint": 3.3}), {"applied": {"voltage_setpoint": 3.3}})
        self.assertEqual(driver.native.registers[("holding", 0x0030)], 330)
        self.assertEqual(driver.read("main")["voltage_setpoint"], 3.3)

    def test_a_value_between_register_steps_is_refused_before_any_write(self) -> None:
        driver = self.driver()
        before = dict(driver.native.registers)
        with self.assertRaises(Exception) as caught:
            driver.write("main", {"voltage_setpoint": 3.333})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(driver.native.registers, before)

    def test_an_unacknowledged_setpoint_write_blocks_output_on_until_it_is_written_again(self) -> None:
        driver = self.driver()
        setpoint = '{"profile": "modbus", "register": 48, "table": "holding", "words": 1}'
        driver.native.fail.add(setpoint)
        with self.assertRaises(Exception) as caught:
            driver.write("main", {"voltage_setpoint": 5.0})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")
        self.assertNotIn("voltage_setpoint", driver.read("main"))
        with self.assertRaises(Exception) as blocked:
            driver.call(ON, {})
        self.assertEqual(getattr(blocked.exception, "code", None), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(driver.native.registers[OUTPUT], 0)
        self.assertEqual(driver.call(OFF, {}), {"output_enabled": False})       # the confirmed stop clears the fence
        with self.assertRaises(Exception) as still:
            driver.call(ON, {})                                                  # but the setpoint is still unknown
        self.assertEqual(getattr(still.exception, "code", None), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(driver.native.registers[OUTPUT], 0)
        driver.native.fail.discard(setpoint)
        driver.write("main", {"voltage_setpoint": 5.0})                          # re-established and acknowledged
        self.assertEqual(driver.call(ON, {}), {"output_enabled": True})

    def test_an_output_on_whose_readback_lags_is_unknown_and_fences_the_next_one(self) -> None:
        driver = self.driver()
        original = driver.native.read_point

        def lagging(request, *, timeout_s):
            value = original(request, timeout_s=timeout_s)
            return [0] if request.get("register") == 0x0001 else value          # the read-back has not caught up

        driver.native.read_point = lagging
        with self.assertRaises(Exception) as caught:
            driver.call(ON, {})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(driver.native.registers[OUTPUT], 1)                    # the supply did act
        self.assertTrue(driver.safety_status()["outcome_uncertain"])
        with self.assertRaises(Exception) as fenced:
            driver.call(ON, {})
        self.assertEqual(getattr(fenced.exception, "code", None), "MHS.DEVICE.PRECONDITION_UNMET")

    def test_estop_writes_zero_and_reports_the_confirmed_safe_state(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        self.assertEqual(client.invoke(ON, {}, device_id=device, session_id=session)["status"], "completed")
        receipt = client.estop("test", device_id=device, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(ON, {}, device_id=device, session_id=session)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_a_refused_stop_write_never_reports_a_safe_state(self) -> None:
        driver = self.driver()
        driver.call(ON, {})
        driver.native.refuse.add('{"profile": "modbus", "register": 1, "table": "holding", "words": 1}')
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])

    def test_operator_limit_bounds_the_setpoint(self) -> None:
        server = load(HERE, backend="fake", site_limits=OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        inside = client.write("main", {"voltage_setpoint": 5.0}, device_id=device, session_id=session)
        self.assertEqual(inside["status"], "completed", inside)
        outside = client.write("main", {"voltage_setpoint": 24.0}, device_id=device, session_id=session)
        self.assertEqual(outside["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")

    def test_hardware_backend_is_refused_without_a_human_hardware_review(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state, options={"port": "/dev/null"})
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
