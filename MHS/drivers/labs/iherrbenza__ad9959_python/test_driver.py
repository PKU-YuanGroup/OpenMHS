"""Acceptance run of the AD9959 package: the gate, plus cases for what is specific to this driver.

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


class AD9959Cases(unittest.TestCase):
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

    def test_the_frequency_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, frequency=[1e6, 2e6, 3e6, 4e6])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertNotIn("frequency", self.state(client))

    def test_the_example_overlay_supplies_the_band(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        band = [1e6, 1e7, 5e7, 1e8]
        self.assertEqual(self.configure(client, frequency=band)["status"], "completed")
        self.assertEqual(self.state(client)["frequency"], band)
        refused = self.configure(client, frequency=[1e9, 1e9, 1e9, 1e9])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["frequency"], band)

    def test_the_amplitude_and_phase_words(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, amplitude=[0, 512, 1023, 100])["status"], "completed")
        self.assertEqual(self.configure(client, phase=[0, 90, 180, 360])["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["amplitude"], [0, 512, 1023, 100])
        self.assertEqual(state["phase"], [0, 90, 180, 360])
        for patch in ({"amplitude": [0, 0, 0, 1024]}, {"phase": [0, 0, 0, 361]},
                      {"amplitude": [-1, 0, 0, 0]}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertEqual(state["amplitude"], [0, 512, 1023, 100])
        self.assertEqual(state["phase"], [0, 90, 180, 360])

    def test_the_mute_action_and_the_estop(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, amplitude=[1, 2, 3, 4])["status"], "completed")
        muted = client.invoke("x-cap.iherrbenza.mute.v1", {}, **self.ids)
        self.assertEqual(muted["status"], "completed")
        self.assertEqual(muted["output"], {"amplitude": [0, 0, 0, 0]})
        # No state assertion here: the upstream has no register read, so the resource state is the last configure
        # write and not the value the mute action sent.  The action's output is its observable effect.
        self.assertEqual(self.configure(client, amplitude=[5, 6, 7, 8])["status"], "completed")
        client.estop("test", **self.ids)
        refused = self.configure(client, amplitude=[9, 9, 9, 9])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
