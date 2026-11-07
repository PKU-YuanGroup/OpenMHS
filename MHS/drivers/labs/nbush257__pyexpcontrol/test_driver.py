"""Acceptance run of the pyexpcontrol package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PyexpcontrolCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def call(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_laser_amplitude_write_and_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["laser_amplitude"], 0.0)     # the driver's starting shadow
        applied = self.configure(client, laser_amplitude=0.37)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"]["applied"]["laser_amplitude"], 0.37)
        self.assertEqual(self.state(client)["laser_amplitude"], 0.37)
        refused = self.configure(client, laser_amplitude=1.01)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["laser_amplitude"], 0.37)

    def test_olfactometer_valves(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["valves"], [False] * 8)
        opened = self.call(client, "x-cap.nbush257.set_valve.v1", {"valve": 3, "state": "open"})
        self.assertEqual(opened["status"], "completed")
        self.assertEqual(opened["output"], {"valve": 3, "state": "open"})
        self.assertTrue(self.state(client)["valves"][2])
        closed = self.call(client, "x-cap.nbush257.set_valve.v1", {"valve": 3, "state": "closed"})
        self.assertEqual(closed["status"], "completed")
        self.assertFalse(self.state(client)["valves"][2])
        refused = self.call(client, "x-cap.nbush257.set_valve.v1", {"valve": 9, "state": "open"})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        pattern = self.call(client, "x-cap.nbush257.set_all_valves.v1", {"pattern": "10100000"})
        self.assertEqual(pattern["status"], "completed")
        self.assertEqual(self.state(client)["valves"], [True, False, True, False, False, False, False, False])
        bad = self.call(client, "x-cap.nbush257.set_all_valves.v1", {"pattern": "1010"})
        self.assertEqual(bad["status"], "rejected")

    def test_gpio_and_camera(self) -> None:
        client = self.serve()
        gpio = self.call(client, "x-cap.nbush257.set_gpio.v1", {"pin": 2, "mode": "high"})
        self.assertEqual(gpio["status"], "completed")
        self.assertEqual(self.state(client)["gpio"][2], "high")
        refused = self.call(client, "x-cap.nbush257.set_gpio.v1", {"pin": 8, "mode": "high"})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        started = self.call(client, "x-cap.nbush257.start_camera_trigger.v1")
        self.assertEqual(started["output"], {"camera_triggering": True})
        self.assertTrue(self.state(client)["camera_triggering"])
        stopped = self.call(client, "x-cap.nbush257.stop_camera_trigger.v1")
        self.assertEqual(stopped["output"], {"camera_triggering": False})
        self.assertFalse(self.state(client)["camera_triggering"])

    def test_safe_state_and_estop(self) -> None:
        client = self.serve()
        self.call(client, "x-cap.nbush257.set_valve.v1", {"valve": 1, "state": "open"})
        self.call(client, "x-cap.nbush257.start_camera_trigger.v1")
        safe = self.call(client, "x-cap.nbush257.safe_state.v1")
        self.assertEqual(safe["output"], {"safe": True})
        state = self.state(client)
        self.assertEqual(state["valves"], [False] * 8)
        self.assertFalse(state["camera_triggering"])
        self.assertEqual(state["laser_amplitude"], 0.0)

        client.estop("test", **self.ids)
        refused = self.call(client, "x-cap.nbush257.set_valve.v1", {"valve": 1, "state": "open"})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["laser_amplitude"], 0.0)


if __name__ == "__main__":
    unittest.main()
