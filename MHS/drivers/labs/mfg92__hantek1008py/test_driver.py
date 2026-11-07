"""Acceptance run of the Hantek 1008C package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Hantek1008Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_initial_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["active_channels"], [0, 1])
        self.assertEqual(state["vertical_scales"], [1.0] * 8)
        self.assertEqual(state["zero_offsets"], [2048.0] * 8)
        self.assertFalse(state["paused"])
        self.assertEqual(state["generator_waveform_max_length"], 1440)

    def test_the_generator_is_switched_on_and_off(self) -> None:
        client = self.serve()
        switched = self.invoke(client, "x-cap.mfg92.set_generator_on.v1", {"on": True})
        self.assertEqual(switched["status"], "completed")
        self.assertEqual(switched["output"], {"on": True})
        switched = self.invoke(client, "x-cap.mfg92.set_generator_on.v1", {"on": False})
        self.assertEqual(switched["status"], "completed")
        self.assertEqual(switched["output"], {"on": False})

    def test_the_generator_speed_is_bounded(self) -> None:
        client = self.serve()
        applied = self.invoke(client, "x-cap.mfg92.set_generator_speed.v1", {"speed_rpm": 300000})
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"], {"speed_rpm": 300000})
        for value in (0, 750001):
            refused = self.invoke(client, "x-cap.mfg92.set_generator_speed.v1", {"speed_rpm": value})
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)

    def test_the_waveform_bytes_are_bounded(self) -> None:
        client = self.serve()
        applied = self.invoke(client, "x-cap.mfg92.set_generator_waveform.v1",
                              {"waveform": [240, 15]})
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"], {"waveform": [240, 15]})
        for payload in ({"waveform": [-1, 0]}, {"waveform": [0, 256]}):
            refused = self.invoke(client, "x-cap.mfg92.set_generator_waveform.v1", payload)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        too_long = self.invoke(client, "x-cap.mfg92.set_generator_waveform.v1",
                               {"waveform": [0] * 63})
        self.assertEqual(too_long["status"], "rejected")

    def test_the_pause_thread_is_started_and_stopped(self) -> None:
        client = self.serve()
        paused = self.invoke(client, "x-cap.mfg92.set_paused.v1", {"paused": True})
        self.assertEqual(paused["status"], "completed")
        self.assertEqual(paused["output"], {"paused": True})
        self.assertTrue(self.state(client)["paused"])
        resumed = self.invoke(client, "x-cap.mfg92.set_paused.v1", {"paused": False})
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["output"], {"paused": False})
        self.assertFalse(self.state(client)["paused"])

    def test_the_generator_off_action_is_the_safe_state(self) -> None:
        client = self.serve()
        switched = self.invoke(client, "x-cap.mfg92.generator_off.v1")
        self.assertEqual(switched["status"], "completed")
        self.assertEqual(switched["output"], {"on": False})

    def test_the_estop_latches_and_refuses_further_generator_writes(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.invoke(client, "x-cap.mfg92.set_generator_on.v1", {"on": True})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
