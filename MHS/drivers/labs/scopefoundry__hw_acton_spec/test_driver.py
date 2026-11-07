"""Acceptance run of the Acton driver package: the gate, plus cases for what is specific to this driver.

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


class ActonCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def configure(self, client, ids, **patch):
        return client.invoke("cap.device.configure.v1", patch, **ids)

    def state(self, client, ids):
        return client.read("main", **ids)["state"]

    def test_the_reads(self) -> None:
        client, ids = self.serve()
        state = self.state(client, ids)
        self.assertEqual(state["center_wl"], 500.0)                 # fake placeholder
        self.assertEqual(state["grating_id"], 1)                    # fake placeholder
        self.assertEqual(state["grating_name"], "300 g/mm BLZ=500NM")   # fake placeholder
        self.assertEqual(state["turret"], 1)                        # fake placeholder
        self.assertEqual(state["exit_mirror"], "SIDE")              # fake placeholder
        self.assertEqual(state["entrance_slit"], 100)               # fake placeholder, um
        self.assertEqual(state["exit_slit"], 100)                   # fake placeholder, um
        self.assertTrue(state["done_status"])                       # fake placeholder

    def test_the_writes_reach_the_fake_and_change_the_state(self) -> None:
        client, ids = self.serve()
        receipt = self.configure(client, ids, entrance_slit=250, exit_slit=150,
                                 exit_mirror="FRONT", grating_id=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client, ids)
        self.assertEqual(state["entrance_slit"], 250)
        self.assertEqual(state["exit_slit"], 150)
        self.assertEqual(state["exit_mirror"], "FRONT")
        self.assertEqual(state["grating_id"], 2)
        self.assertEqual(state["grating_name"], "300 g/mm BLZ=1.0UM")   # fake placeholder

    def test_the_sourced_limits_refuse_out_of_range_values(self) -> None:
        client, ids = self.serve()
        for patch in ({"entrance_slit": 4}, {"entrance_slit": 3001},
                      {"exit_slit": 4}, {"exit_slit": 3001},
                      {"grating_id": 0}, {"grating_id": 10},
                      {"exit_mirror": "TOP"}):
            refused = self.configure(client, ids, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client, ids)
        self.assertEqual(state["entrance_slit"], 100)               # fake placeholder, untouched
        self.assertEqual(state["exit_slit"], 100)                   # fake placeholder, untouched

    def test_the_center_wavelength_waits_for_the_site(self) -> None:
        client, ids = self.serve()
        refused = self.configure(client, ids, center_wl=500)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

        overlaid, overlaid_ids = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.configure(overlaid, overlaid_ids, center_wl=600.0)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(self.state(overlaid, overlaid_ids)["center_wl"], 600.0)
        for value in (299.9, 900.1):
            refused = self.configure(overlaid, overlaid_ids, center_wl=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(overlaid, overlaid_ids)["center_wl"], 600.0)

    def test_the_estop_latches(self) -> None:
        client, ids = self.serve()
        estop = client.estop("test", **ids)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(estop["output"]["estop"], "engaged")
        refused = self.configure(client, ids, entrance_slit=200)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
