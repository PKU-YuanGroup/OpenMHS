"""Acceptance run of the niscope-mcp package: the gate, plus cases specific to this driver.

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


class NiscopeCases(unittest.TestCase):
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

    def test_the_fake_state_and_the_scalar_measurement(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["device_model"], "PXIe-5160")
        self.assertEqual((state["channel_enabled"], state["vertical_coupling"]), (True, "DC"))
        self.assertEqual((state["vertical_range"], state["sample_rate"]), (5.0, 1000000.0))
        result = client.invoke("x-cap.ymzds.measure_waveform.v1", {}, **self.ids)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output"]["num_samples"], 8)
        self.assertEqual(result["output"]["frequency_hz"], 1000000.0)

    def test_the_operator_bounds_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, vertical_offset=-0.5, trigger_level=1.5, record_length=20000)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["vertical_offset"], 0.0)
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, vertical_offset=-0.5, trigger_level=1.5,
                                        record_length=20000)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["vertical_offset"], state["trigger_level"], state["record_length"]),
                         (-0.5, 1.5, 20000))

    def test_the_sourced_values_are_enforced_and_applied(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, vertical_range=2.0, sample_rate=2.5e8,
                                        input_impedance=50, probe_attenuation=10)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["vertical_range"], state["sample_rate"]), (2.0, 2.5e8))
        self.assertEqual((state["input_impedance"], state["probe_attenuation"]), (50.0, 10.0))
        for patch, value in (({"vertical_range": 0.01}, ENVELOPE),
                             ({"vertical_range": 51}, ENVELOPE),
                             ({"sample_rate": 9e5}, ENVELOPE),
                             ({"sample_rate": 2e9}, ENVELOPE),
                             ({"input_impedance": 75}, ENVELOPE),
                             ({"probe_attenuation": 5}, ENVELOPE)):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], value, patch)
        self.assertEqual(self.state(client)["vertical_range"], 2.0)

    def test_auto_setup_and_the_estop(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.ymzds.auto_setup.v1", {}, **self.ids)["output"],
                         {"configured": True})
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.ymzds.auto_setup.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
