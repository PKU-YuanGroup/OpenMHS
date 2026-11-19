"""Acceptance run of the MHO98 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  Nothing imports the upstream clone; every case
uses the package fake through the stock loader and server, and no hardware run is claimed.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StateCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_reads_use_the_session_and_feature_queries(self) -> None:
        state = self.driver().read("main")
        self.assertEqual(state["identity"].split(",")[1], "MHO98")
        self.assertIs(state["healthy"], True)
        self.assertEqual(state["last_error"], "")
        self.assertEqual(state["timebase_scale_s_div"], 0.001)
        self.assertEqual(state["timebase_offset_s"], 0.0)
        self.assertEqual(state["ch1_scale_v_div"], 0.5)
        self.assertEqual(state["ch1_offset_v"], 0.0)
        self.assertEqual(state["waveform_source"], "CHAN1")
        self.assertEqual(state["waveform_mode"], "NORM")
        self.assertEqual(state["waveform_format"], "ASC")
        self.assertEqual(state["waveform_points"], 8)

    def test_a_write_changes_the_answer_of_its_query(self) -> None:
        driver = self.driver()
        driver.write("main", {"waveform_source": "CHAN2", "waveform_mode": "MAX", "waveform_format": "BYTE"})
        state = driver.read("main")
        self.assertEqual((state["waveform_source"], state["waveform_mode"], state["waveform_format"]),
                         ("CHAN2", "MAX", "BYTE"))

    def test_the_estop_reaches_the_native_stop(self) -> None:
        driver = self.driver()
        driver.estop("test")
        self.assertIs(driver.read("main")["healthy"], True)


class ServerCases(unittest.TestCase):
    def serve(self, overlay=None, **options):
        server = load(HERE, backend="fake", site_limits=overlay, options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        if receipt["status"] == "rejected":
            return receipt["error"]["mhs_code"]
        return receipt["status"]

    def action(self, client, capability_id, arguments=None):
        return client.invoke(capability_id, arguments or {}, **self.ids)

    def test_the_ascii_waveform_action_returns_the_arrays(self) -> None:
        client = self.serve()
        receipt = self.action(client, "x-cap.kitour.acquire_waveform.v1")
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["source"], output["format"], output["points"]), ("CHAN1", "ASC", 8))
        self.assertEqual(len(output["time"]), 8)
        self.assertEqual(len(output["values"]), 8)
        self.assertAlmostEqual(output["time"][0], -0.004)
        self.assertAlmostEqual(output["values"][0], 0.105)

    def test_the_binary_waveform_action_returns_the_arrays(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, waveform_format="BYTE"), "completed")
        receipt = self.action(client, "x-cap.kitour.acquire_waveform.v1")
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["format"], "BYTE")
        self.assertAlmostEqual(receipt["output"]["values"][0], 0.105)

    def test_the_example_overlay_permits_the_cursor_action(self) -> None:
        client = self.serve(OVERLAY)
        receipt = self.action(client, "x-cap.kitour.set_cursor.v1", {"a_s": 0.001, "b_s": 0.002})
        self.assertEqual(receipt["status"], "completed", receipt)
        read = self.action(client, "x-cap.kitour.read_cursor.v1")
        self.assertEqual(read["output"], {"mode": "MANUAL", "a_s": 0.001, "b_s": 0.002})

    def test_an_operator_required_bound_waits_for_the_site(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, timebase_scale_s_div=0.001), LIMITS_UNSET)
        self.assertEqual(self.action(client, "x-cap.kitour.set_cursor.v1",
                                     {"a_s": 0.001, "b_s": 0.002})["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_bounds_and_permits_the_writes(self) -> None:
        client = self.serve(OVERLAY)
        self.assertEqual(self.configure(client, timebase_scale_s_div=0.001), "completed")
        self.assertEqual(self.configure(client, timebase_scale_s_div=0.0), ENVELOPE)
        self.assertEqual(self.configure(client, ch1_scale_v_div=0.5), "completed")
        self.assertEqual(self.configure(client, ch1_scale_v_div=20.0), ENVELOPE)

    def test_the_safe_state_and_reenable_actions(self) -> None:
        client = self.serve()
        stopped = self.action(client, "x-cap.kitour.stop_acquisition.v1")
        self.assertEqual(stopped["status"], "completed", stopped)
        started = self.action(client, "x-cap.kitour.run_acquisition.v1")
        self.assertEqual(started["status"], "completed", started)

    def test_an_ignored_stop_fails_and_keeps_the_latch(self) -> None:
        client = self.serve(ignore_stop=True)
        self.action(client, "x-cap.kitour.run_acquisition.v1")
        receipt = client.estop("ignored acquisition stop", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(receipt["output"]["latched"])
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        refused = self.action(client, "x-cap.kitour.run_acquisition.v1")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_a_rejected_scpi_write_is_not_completed(self) -> None:
        client = self.serve(OVERLAY, reject_command=":TIMebase:MAIN:SCALe")
        receipt = client.invoke("cap.device.configure.v1", {"timebase_scale_s_div": 0.002}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_an_oversized_waveform_is_refused_before_sample_allocation(self) -> None:
        client = self.serve(waveform_points=100001)  # over the upstream inline transfer ceiling
        receipt = self.action(client, "x-cap.kitour.acquire_waveform.v1")
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_a_nonfinite_waveform_sample_is_refused(self) -> None:
        client = self.serve(ascii_reply=",".join(["NaN"] + ["0"] * 7))  # placeholder malformed reply
        receipt = self.action(client, "x-cap.kitour.acquire_waveform.v1")
        self.assertEqual(receipt["status"], "failed", receipt)


if __name__ == "__main__":
    unittest.main()
