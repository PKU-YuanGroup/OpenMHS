"""Acceptance run of the SynQS Andor Solis package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import os
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AndorSolisCases(unittest.TestCase):
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

    def test_the_reads_are_the_acquisition_attributes(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["acquisition_mode"], "single")
        self.assertEqual(state["trigger_mode"], "internal")
        self.assertEqual(state["trigger_edge"], "rising")
        self.assertEqual(state["frame_width"], 8)
        self.assertEqual(state["frame_height"], 8)
        self.assertEqual(state["x_binning"], 1)
        self.assertEqual(state["cooldown"], True)
        self.assertAlmostEqual(state["exposure_time"], 0.02)

    def test_a_snap_returns_a_pgm_file_with_its_size(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (8, 8))
        path = output["image_ref"]
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as stream:
            self.assertEqual(stream.read(11), b"P5\n8 8\n255\n")

    def test_the_operator_supplies_the_exposure_and_temperature_ranges(self) -> None:
        client = self.serve()
        for patch in ({"exposure_time": 0.5}, {"temperature_setpoint": -20.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure_time=0.5)["status"], "completed")
        self.assertEqual(self.configure(client, temperature_setpoint=-20.0)["status"], "completed")
        state = self.state(client)
        self.assertAlmostEqual(state["exposure_time"], 0.5)
        self.assertAlmostEqual(state["temperature_setpoint"], -20.0)
        for patch in ({"exposure_time": 0.0001}, {"temperature_setpoint": 30.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_mode_words_are_the_clone_allowed_sets(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, acquisition_mode="kinetic_series", trigger_mode="external",
                                        trigger_edge="falling")["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["acquisition_mode"], state["trigger_mode"], state["trigger_edge"]),
                         ("kinetic_series", "external", "falling"))
        refused = self.configure(client, acquisition_mode="burst")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_aborts_the_acquisition_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertTrue(driver.native._abort_acquisition)
        client = self.serve()
        client.estop("test", **self.ids)
        refused = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
