"""Acceptance run of the ARI M1 mirror-section driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
PHOTOCURRENT = "x-cap.nsls-ii-ari.m1_photocurrent.v1"
READS = (
    "ry_coarse", "ry_fine", "rz", "x", "y",
    "slit_top", "slit_bottom", "slit_inboard", "slit_outboard",
    "diag_blade", "diag_filter",
    "diag_current1", "diag_current2", "diag_current3", "diag_current4",
    "slit_current1", "slit_current2", "slit_current3", "slit_current4",
    "vacuum_ccg", "vacuum_tcg", "vacuum_ip",
    "locations",
)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AriM1Cases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_every_read_is_published_with_the_fake_value(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(READS))
        self.assertEqual(state["ry_coarse"], 10.0)      # placeholder
        self.assertEqual(state["slit_top"], 1.0)        # placeholder
        self.assertEqual(state["diag_blade"], 5.0)      # placeholder
        self.assertEqual(state["diag_current1"], 0.5)   # placeholder
        self.assertEqual(state["slit_current2"], 0.2)   # placeholder
        self.assertEqual(state["vacuum_ccg"], 1.1e-7)   # placeholder
        self.assertEqual(state["locations"], ["park"])  # placeholder

    def test_every_signal_read_asks_for_a_fresh_value(self) -> None:
        client, fake = self.serve()
        self.state(client)
        signals = [
            fake.Ry_coarse.user_readback, fake.Ry_fine.user_readback, fake.Rz.user_readback,
            fake.x.user_readback, fake.y.user_readback,
            fake.slits.top.user_readback, fake.slits.bottom.user_readback,
            fake.slits.inboard.user_readback, fake.slits.outboard.user_readback,
            fake.diag.blade.user_readback, fake.diag.filter.user_readback,
            fake.diag.currents.current1.mean_value, fake.diag.currents.current2.mean_value,
            fake.diag.currents.current3.mean_value, fake.diag.currents.current4.mean_value,
            fake.slits.currents.current1.mean_value, fake.slits.currents.current2.mean_value,
            fake.slits.currents.current3.mean_value, fake.slits.currents.current4.mean_value,
            fake.vacuum.AriSxnC.ccg, fake.vacuum.AriSxnC.tcg, fake.vacuum.AriSxnC.ip,
        ]
        for signal in signals:
            self.assertTrue(signal.use_monitor_calls, "the read did not reach the native signal")
            self.assertTrue(all(value is False for value in signal.use_monitor_calls),
                            f"a read used the monitor cache: {signal.use_monitor_calls}")

    def test_locations_reads_the_parent_location_signal(self) -> None:
        client, fake = self.serve()
        self.assertEqual(self.state(client)["locations"], ["park"])  # placeholder
        self.assertEqual(fake.locations.gets, 1)

    def test_photocurrent_is_a_fresh_read_of_the_diagnostic_current1_mean(self) -> None:
        # Model review: the observation replaces the unstaged M1.trigger the author served.
        client, fake = self.serve()
        signal = fake.diag.currents.current1.mean_value
        before = signal.gets
        receipt = client.invoke(PHOTOCURRENT, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"photocurrent": 0.5})   # placeholder
        self.assertGreater(signal.gets, before)
        self.assertIs(signal.use_monitor_calls[-1], False)

    def test_a_failed_native_read_gives_a_failed_receipt(self) -> None:
        client, fake = self.serve()

        def broken(*, use_monitor=None):
            raise RuntimeError("placeholder: the Channel Access get timed out")

        fake.diag.currents.current1.mean_value.get = broken
        receipt = client.invoke(PHOTOCURRENT, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_the_package_offers_no_trigger(self) -> None:
        client, fake = self.serve()
        refused = client.invoke("x-cap.nsls-ii-ari.m1_trigger.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")
        self.assertFalse(hasattr(fake, "trigger"))

    def test_the_package_offers_no_write(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"ry_coarse": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")


if __name__ == "__main__":
    unittest.main()
