"""Acceptance run of the pyhamilton package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

ASPIRATE = "x-cap.dgretton.aspirate.v1"
DISPENSE = "x-cap.dgretton.dispense.v1"
INITIALIZE = "x-cap.dgretton.initialize.v1"
MOVE_PLATE = "x-cap.dgretton.move_plate.v1"
SET_PROPERTY = "x-cap.dgretton.set_labware_property.v1"
REENABLE = "x-cap.dgretton.start_interface.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PyhamiltonCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    @staticmethod
    def payload(volume):
        return {"labware": "plate_1", "well": "A1", "volume": volume, "liquid_class": "Tip_50ulFilter_Water"}

    def test_the_interface_opens_and_initializes(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertIs(state["is_open"], True)
        self.assertIs(state["server_exited"], False)
        receipt = client.invoke(INITIALIZE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"initialized": True})

    def test_the_volume_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(ASPIRATE, self.payload(50), **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertIs(self.state(client)["is_open"], True)

    def test_the_example_overlay_supplies_the_volume_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        aspirated = client.invoke(ASPIRATE, self.payload(50), **self.ids)
        self.assertEqual(aspirated["status"], "completed", aspirated)
        self.assertEqual(aspirated["output"]["aspirated_volume"], 50.0)
        self.assertEqual(aspirated["output"]["labware"], "plate_1")
        dispensed = client.invoke(DISPENSE, self.payload(25), **self.ids)
        self.assertEqual(dispensed["status"], "completed", dispensed)
        self.assertEqual(dispensed["output"]["dispensed_volume"], 25.0)
        for value in (0, 201):
            refused = client.invoke(ASPIRATE, self.payload(value), **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)

    def test_the_plate_move_and_the_labware_property(self) -> None:
        client = self.serve()
        moved = client.invoke(MOVE_PLATE, {"source_sequence": "source_1", "target_sequence": "target_1"},
                              **self.ids)
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(moved["output"], {"moved": True, "location": "target_1",
                                           "source_sequence": "source_1"})
        written = client.invoke(SET_PROPERTY, {"labware_id": "plate_1", "property_name": "barcode",
                                              "property_value": "abc123"}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(written["output"], {"labware_id": "plate_1", "property_name": "barcode",
                                             "property_value": "abc123"})

    def test_the_estop_stops_the_interface_and_latches(self) -> None:
        client = self.serve()
        client.invoke(INITIALIZE, {}, **self.ids)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertIs(state["is_open"], False)
        self.assertIs(state["server_exited"], True)
        refused = client.invoke(INITIALIZE, {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def serve_driver(self):
        """A server over a driver this test keeps, so the native start() calls are visible."""
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.assertIs(self.state(client)["is_open"], True)      # setup() started it once
        starts = []
        original = driver.native.start
        driver.native.start = lambda: (starts.append("start"), original())[1]   # counts later native starts
        return driver, client, starts

    def test_the_reenable_is_refused_while_latched_with_nothing_started(self) -> None:
        driver, client, starts = self.serve_driver()
        client.estop("test", **self.ids)
        refused = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(starts, [])
        self.assertIs(driver.native.is_open(), False)

    def test_the_reset_starts_nothing_and_names_the_reenable(self) -> None:
        driver, client, starts = self.serve_driver()
        client.estop("test", **self.ids)
        receipt = client.reset(**self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)   # simulated: an agent may reset
        self.assertEqual(receipt["output"]["reenable"], REENABLE)
        self.assertIs(receipt["output"]["resumed"], False)
        self.assertEqual(starts, [])                                # SAFE-042: the OEM process is not relaunched
        state = self.state(client)
        self.assertIs(state["is_open"], False)
        self.assertIs(state["server_exited"], True)

    def test_the_reenable_starts_the_interface_and_then_initialize_completes(self) -> None:
        driver, client, starts = self.serve_driver()
        client.estop("test", **self.ids)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        started = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual(started["status"], "completed", started)
        self.assertEqual(started["output"], {"started": True})
        self.assertEqual(starts, ["start"])
        self.assertIs(self.state(client)["is_open"], True)
        self.assertEqual(client.invoke(INITIALIZE, {}, **self.ids)["status"], "completed")

    def test_the_driver_declares_no_reset_hook(self) -> None:
        driver = load_driver(HERE, "fake")
        self.assertIsNone(driver.reset_hook)                        # a re-enable excludes an @reset hook (CORE-086)
        self.assertEqual(type(driver).driver_model().reenable, REENABLE)


if __name__ == "__main__":
    unittest.main()
