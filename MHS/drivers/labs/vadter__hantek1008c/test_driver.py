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


class HantekCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
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

    def test_the_state_exposes_the_settings(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["active_channels"], list(range(8)))
        self.assertEqual(len(state["time"]), 500)
        self.assertEqual(len(state["vscales"]), 8)
        self.assertEqual(state["generator_waveform_max_length"], 1440)
        self.assertFalse(state["generator_on"])
        self.assertEqual(state["generator_speed"], 300_000)
        self.assertFalse(state["paused"])

    def test_a_write_reaches_the_fake_and_reads_back(self) -> None:
        client = self.serve()
        receipt = self.configure(client, generator_on=True, generator_speed=600_000)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertTrue(state["generator_on"])
        self.assertEqual(state["generator_speed"], 600_000)

    def test_an_out_of_envelope_speed_is_refused(self) -> None:
        client = self.serve()
        for value in (0, 750_001):
            refused = self.configure(client, generator_speed=value)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["generator_speed"], 300_000)

    def test_the_generator_waveform_action(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.vadter.set_generator_waveform.v1",
                                {"waveform": [0, 15, 255]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"length": 3, "checksum": 270})
        too_long = client.invoke("x-cap.vadter.set_generator_waveform.v1",
                                 {"waveform": [0] * 63}, **self.ids)
        self.assertEqual(too_long["status"], "rejected", too_long)
        self.assertEqual(too_long["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        too_large = client.invoke("x-cap.vadter.set_generator_waveform.v1",
                                  {"waveform": [256]}, **self.ids)
        self.assertEqual(too_large["status"], "rejected", too_large)
        self.assertEqual(too_large["error"]["mhs_code"], ENVELOPE)

    def test_the_pause_thread_actions(self) -> None:
        client = self.serve()
        paused = client.invoke("x-cap.vadter.pause.v1", {}, **self.ids)
        self.assertEqual(paused["status"], "completed", paused)
        self.assertEqual(paused["output"], {"paused": True})
        self.assertTrue(self.state(client)["paused"])
        resumed = client.invoke("x-cap.vadter.resume.v1", {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertEqual(resumed["output"], {"paused": False})
        self.assertFalse(self.state(client)["paused"])

    def test_the_safe_state_action_switches_the_generator_off(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, generator_on=True)["status"], "completed")
        receipt = client.invoke("x-cap.vadter.generator_off.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"generator_on": False})
        self.assertFalse(self.state(client)["generator_on"])

    def test_the_estop_switches_the_generator_off_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, generator_on=True)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["generator_on"])
        refused = self.configure(client, generator_speed=10)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
