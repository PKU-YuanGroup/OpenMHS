"""Acceptance run of the Lake Shore 336 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.driver.loader import driver_class
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
THERMAL = "cap.thermal.setpoint.v1"
ENABLE = "x-cap.jdmax.enable_heater.v1"
HEATER_OFF = "x-cap.jdmax.heater_off.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ls336Cases(unittest.TestCase):
    def serve(self, site_limits=None, **options):
        """Serve the fake through the stock loader and server; keep the fake object in self.fake."""
        driver = load_driver(HERE, backend="fake", options=options)
        self.fake = driver.native
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    @staticmethod
    def code(receipt):
        return receipt["error"]["mhs_code"]

    def test_the_setpoint_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, setpoint=30.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.code(refused), LIMITS_UNSET)
        # 300 K is the fake's placeholder setpoint, converted to the published Celsius.
        self.assertAlmostEqual(self.state(client)["setpoint"], 26.85)

    def test_the_example_overlay_supplies_the_setpoint(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=30.0)["status"], "completed")
        self.assertAlmostEqual(self.state(client)["setpoint"], 30.0)
        for value in (14.99, 60.01):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(self.code(refused), ENVELOPE, value)
        self.assertAlmostEqual(self.state(client)["setpoint"], 30.0)

    def test_the_thermal_class_sets_the_setpoint(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(THERMAL, {"target_temperature": 30.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertAlmostEqual(receipt["output"]["setpoint"], 30.0)
        # 295 K is the fake's placeholder first sensor reading.
        self.assertAlmostEqual(receipt["output"]["actual_temperature"], 21.85)
        self.assertAlmostEqual(self.state(client)["setpoint"], 30.0)

    def test_the_reads_and_the_control_writes(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        state = self.state(client)
        self.assertEqual(state["temperature"], 295.0)
        self.assertEqual(len(state["temperatures"]), 4)
        self.assertEqual(state["pid"], [10.0, 1.0, 0.0])
        self.assertEqual((state["output_mode"], state["heater_range"]), ("Off", "High"))
        self.assertEqual(self.configure(client, heater_range="Low")["status"], "completed")
        self.assertEqual(self.state(client)["heater_range"], "Low")
        self.assertEqual(self.configure(client, manual_heater=25.0)["status"], "completed")
        self.assertEqual(self.state(client)["manual_heater"], 25.0)

    def test_the_manual_heater_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, manual_heater=50.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.code(refused), LIMITS_UNSET)

    def test_the_estop_off_and_the_reenable(self) -> None:
        client = self.serve()
        enabled = client.invoke(ENABLE, {}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(self.state(client)["output_mode"], "Closed Loop")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(self.state(client)["output_mode"], "Off")
        refused = client.invoke(ENABLE, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.code(refused), ESTOP)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        # The reset only releases the latch: the output stays Off until the declared re-enable is sent.
        self.assertEqual(self.state(client)["output_mode"], "Off")
        self.assertEqual(client.invoke(ENABLE, {}, **self.ids)["status"], "completed")
        off = client.invoke(HEATER_OFF, {}, **self.ids)
        self.assertEqual(off["status"], "completed", off)
        self.assertEqual(self.state(client)["output_mode"], "Off")

    def test_the_stop_and_the_reenable_set_the_control_input_of_the_configured_output_only(self) -> None:
        client = self.serve(channel=2)
        self.fake._mode[1] = 1           # placeholder: output 1 in Closed Loop, outside this resource
        self.fake._input[2] = 4          # placeholder: output 2 controlled by input 4 before any OUTMODE
        self.assertEqual(client.invoke(ENABLE, {}, **self.ids)["status"], "completed")
        self.assertEqual((self.fake._mode[2], self.fake._input[2], self.fake._powerup[2]), (1, 2, 0))
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        # OUTMODE 2,0,2,0: output 2 Off, its control input set to input 2 and powerup enable to 0.
        self.assertEqual((self.fake._mode[2], self.fake._input[2], self.fake._powerup[2]), (0, 2, 0))
        # The other output is not commanded: it keeps its mode (it would keep heating).
        self.assertEqual(self.fake._mode[1], 1)

    def test_an_off_command_the_controller_ignores_leaves_the_estop_unconfirmed(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(ENABLE, {}, **self.ids)["status"], "completed")
        fake = self.fake
        # A controller that keeps its mode: OUTMODE changes nothing and the readback still says Closed Loop.
        fake.set_outmode = lambda channel, mode, in_channel, powerup_on: float(fake._mode[channel])
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(self.code(stopped), UNREACHED)
        # Neither the native stop (its OUTMODE? reply) nor the safe-state action (a fresh read) reports Off.
        self.assertEqual(stopped["error"]["details"]["native"], "failed", stopped)
        self.assertEqual([item["capability_id"] for item in stopped["error"]["details"]["failed_actions"]],
                         [HEATER_OFF])
        self.assertEqual(fake._mode[1], 1)
        self.assertEqual(self.code(client.invoke(ENABLE, {}, **self.ids)), ESTOP)

    def test_a_controller_that_does_not_answer_fails_the_estop(self) -> None:
        client = self.serve()

        def silent(channel, mode, in_channel, powerup_on):
            # The upstream raises OSError when no reply matches within its 2 s read (instruments/ls336.py:193-205).
            raise OSError("LS336 outmode set")

        self.fake.set_outmode = silent
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(self.code(stopped), UNREACHED)
        self.assertEqual(self.code(client.invoke(ENABLE, {}, **self.ids)), ESTOP)

    def test_the_hardware_backend_needs_the_setpoint_unit(self) -> None:
        # The class is built directly around a fresh fake object with the hardware backend name only: nothing is
        # opened or connected.  This reaches the option rule that the gate's fake backend cannot reach.
        self.serve()
        fake_class, cls = type(self.fake), driver_class(HERE)
        unset = cls(backend="hardware", native=fake_class(), base_dir=HERE)
        self.addCleanup(unset.close)
        self.assertTrue(unset.is_hardware)
        for call in (unset.setpoint, lambda: unset.set_setpoint(30.0), lambda: unset.set_temperature(30.0)):
            with self.assertRaises(DriverFailed) as caught:
                call()
            self.assertEqual(caught.exception.code, PRECONDITION)
        # The stop path does not depend on the unit.
        unset.stop()
        self.assertEqual(unset.heater_off(), {"output_mode": "Off"})
        declared = cls(backend="hardware", native=fake_class(), base_dir=HERE, options={"setpoint_unit": "Cel"})
        self.addCleanup(declared.close)
        # 300 is the fake's placeholder setpoint, read in the declared unit.
        self.assertAlmostEqual(declared.setpoint(), 300.0)
        self.assertAlmostEqual(declared.set_setpoint(30.0), 30.0)


if __name__ == "__main__":
    unittest.main()
