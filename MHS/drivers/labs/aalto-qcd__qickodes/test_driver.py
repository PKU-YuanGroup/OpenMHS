"""Acceptance run of the QICKoDeS driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.  Since the model review of 2026-11-05 the e-stop clears the macro
list and reports SAFE_STATE_UNREACHED with the latch held (the clone has no stop, abort or disarm method), so the
gate fails G6.ESTOP_FAILED and the package is blocked; the cases below keep that honest outcome exercised.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONFIGURE = "cap.device.configure.v1"
ARM_DDR4 = "x-cap.aalto-qcd.arm_ddr4.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QickodesCases(unittest.TestCase):
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

    def test_the_reads_return_the_fake_scalar_values(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(state["final_delay"], 1e-6)     # placeholder
        self.assertEqual(state["final_wait"], 0.0)       # placeholder
        self.assertEqual(state["initial_delay"], 1e-6)   # placeholder
        self.assertEqual(state["hard_avgs"], 1000)       # placeholder
        self.assertEqual(state["soft_avgs"], 1)          # placeholder

    def test_a_delay_write_reaches_the_fake_and_is_read_back(self) -> None:
        client, fake = self.serve()
        applied = client.invoke(CONFIGURE, {"final_delay": 2.5e-6}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["final_delay"], 2.5e-6)
        self.assertEqual(fake.final_delay.get_raw(), 2.5e-6)

    def test_a_count_write_reaches_the_fake(self) -> None:
        client, fake = self.serve()
        applied = client.invoke(CONFIGURE, {"hard_avgs": 7, "soft_avgs": 2}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(fake.hard_avgs.get(), 7)
        self.assertEqual(fake.soft_avgs.get(), 2)

    def test_a_delay_below_the_manifest_bound_is_refused_without_a_native_write(self) -> None:
        client, fake = self.serve()
        before = fake.final_delay.get_raw()
        refused = client.invoke(CONFIGURE, {"final_delay": -1e-6}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake.final_delay.get_raw(), before)

    def test_a_negative_average_count_is_refused(self) -> None:
        client, fake = self.serve()
        refused = client.invoke(CONFIGURE, {"soft_avgs": -1}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake.soft_avgs.get(), 1)        # placeholder, unchanged

    def test_arming_the_ddr4_buffer_reaches_the_module(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(ARM_DDR4, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"armed": True})
        self.assertEqual(fake.ddr4_buffer.arm_calls, 1)

    def test_the_estop_clears_the_macro_list_but_reports_unreached(self) -> None:
        client, fake = self.serve()
        fake.macro_list = [object()]                     # placeholder sequence, not a Macro
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertEqual(fake.macro_list, [])
        refused = client.invoke(CONFIGURE, {"final_delay": 2e-6}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_a_failed_native_set_is_a_failed_receipt(self) -> None:
        client, fake = self.serve()

        def rejected(value):
            raise RuntimeError("placeholder: Pyro4 call failed")

        fake.final_delay.set_raw = rejected
        receipt = client.invoke(CONFIGURE, {"final_delay": 2e-6}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)


if __name__ == "__main__":
    unittest.main()
