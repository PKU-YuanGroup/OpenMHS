"""Acceptance run of the ALBA EM2 package: the gate, plus cases for what is specific to this driver.

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


class Albaem2Cases(unittest.TestCase):
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

    def test_the_state_reads_the_four_channels(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["acquisition_state"], "ON")             # placeholder test data of the fake
        self.assertEqual(state["nb_points_ready"], 0)                   # placeholder test data of the fake
        self.assertEqual(state["identity"], "FAKE,ALBAEM2,0,0.0.0")     # placeholder test data of the fake
        for index in range(1, 5):
            self.assertAlmostEqual(state[f"current_ch{index}"], 1.0e-9 * index)

    def test_the_integration_time_is_bounded_and_converted(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, integration_time=10.0)["status"], "completed")
        self.assertAlmostEqual(self.state(client)["integration_time"], 10.0)
        for value in (0.09, 2621.1):
            refused = self.configure(client, integration_time=value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertAlmostEqual(self.state(client)["integration_time"], 10.0)

    def test_the_point_count_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, nb_points=50)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

        overlaid = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(overlaid, nb_points=50)["status"], "completed")
        self.assertEqual(self.state(overlaid)["nb_points"], 50)
        for value in (0, 100001):
            refused = self.configure(overlaid, nb_points=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(overlaid)["nb_points"], 50)

    def test_the_channel_action_sets_the_range_and_inversion(self) -> None:
        client = self.serve()
        applied = client.invoke(
            "x-cap.maxiv-kitscontrols.configure_channel.v1",
            {"channel": "1", "amplifier_range": "10nA", "inversion": True}, **self.ids)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"]["amplifier_range"], "10nA")
        self.assertTrue(applied["output"]["inversion"])
        self.assertEqual(self.state(client)["range_ch1"], "10nA")
        self.assertTrue(self.state(client)["inversion_ch1"])

        refused = client.invoke("x-cap.maxiv-kitscontrols.configure_channel.v1",
                                {"channel": "5"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = client.invoke("x-cap.maxiv-kitscontrols.configure_channel.v1",
                                {"channel": "1", "amplifier_range": "2A"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["range_ch1"], "10nA")

    def test_the_trigger_settings_are_writable(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, trigger_mode="HARDWARE")["status"], "completed")
        self.assertEqual(self.state(client)["trigger_mode"], "HARDWARE")
        self.assertEqual(self.configure(client, trigger_precision=True)["status"], "completed")
        self.assertTrue(self.state(client)["trigger_precision"])

    def test_the_current_capability_measures_one_channel(self) -> None:
        client = self.serve()
        first = client.invoke("cap.measure.current.v1", {"channel": "1"}, **self.ids)
        self.assertEqual(first["status"], "completed")
        self.assertAlmostEqual(first["output"]["current"], 1.0e-9)
        second = client.invoke("cap.measure.current.v1", {"channel": "2"}, **self.ids)
        self.assertEqual(second["status"], "completed")
        self.assertAlmostEqual(second["output"]["current"], 2.0e-9)
        refused = client.invoke("cap.measure.current.v1", {"channel": "5"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_stops_the_acquisition_and_latches(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.maxiv-kitscontrols.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"]["acquisition_state"], "RUNNING")  # placeholder test data of the fake
        triggered = client.invoke("x-cap.maxiv-kitscontrols.software_trigger.v1", {}, **self.ids)
        self.assertEqual(triggered["status"], "completed")
        self.assertEqual(self.state(client)["nb_points_ready"], 1)

        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["acquisition_state"], "ON")      # placeholder test data of the fake
        refused = client.invoke("x-cap.maxiv-kitscontrols.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
