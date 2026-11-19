"""Acceptance run of the AFG-2225 package: the gate, plus cases for what is specific to this driver.

The gate call is the harness; the cases below exercise the fake backend through the stock strict server.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SET_OFFSET = "x-cap.ilovebacteria.set_offset.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AFG2225Cases(unittest.TestCase):
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

    def write(self, client, **patch):
        return client.write("main", patch, **self.ids)

    def test_the_two_channels_read_from_the_fake(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["ch1_shape"], state["ch2_shape"]), ("sine", "sine"))
        self.assertEqual((state["ch1_freq"], state["ch2_freq"]), (1000.0, 1000.0))
        self.assertEqual((state["ch1_vpp"], state["ch2_vpp"]), (1.0, 1.0))
        self.assertEqual((state["ch1_load"], state["ch2_load"]), ("50ohm", "50ohm"))
        self.assertEqual((state["ch1_output"], state["ch2_output"]), (False, False))
        self.assertEqual(state["last_error"], '0,"No error"')

    def test_a_write_reaches_the_fake_and_is_read_back(self) -> None:
        client = self.serve()
        completed = self.write(
            client,
            ch1_shape="square",
            ch1_freq=2000.0,
            ch1_vpp=2.5,
            ch1_phase=45.0,
            ch1_duty=25.0,
            ch1_sym=60.0,
            ch1_load="highZ",
            ch1_output=True,
        )
        self.assertEqual(completed["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["ch1_shape"], "square")
        self.assertEqual(state["ch1_freq"], 2000.0)
        self.assertEqual(state["ch1_vpp"], 2.5)
        self.assertEqual(state["ch1_phase"], 45.0)
        self.assertEqual(state["ch1_duty"], 25.0)
        self.assertEqual(state["ch1_sym"], 60.0)
        self.assertEqual(state["ch1_load"], "highZ")
        self.assertTrue(state["ch1_output"])

    def test_the_upstream_ranges_refuse_out_of_envelope_writes(self) -> None:
        client = self.serve()
        cases = (
            {"ch1_freq": 0.0},
            {"ch1_freq": 25e6 + 1.0},
            {"ch1_vpp": 0.0},
            {"ch1_vpp": 10.5},
            {"ch1_phase": -361.0},
            {"ch1_phase": 361.0},
            {"ch1_duty": 0.5},
            {"ch1_duty": 100.0},
            {"ch1_sym": -1.0},
            {"ch1_sym": 101.0},
            {"ch1_shape": "triangle"},
            {"ch1_load": "600ohm"},
        )
        for patch in cases:
            refused = self.write(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual(state["ch1_shape"], "sine")
        self.assertEqual(state["ch1_freq"], 1000.0)

    def test_the_offset_waits_for_the_site_overlay(self) -> None:
        client = self.serve()
        refused = client.invoke(SET_OFFSET, {"channel": 1, "offset_v": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["ch1_offset_v"], 0.0)

        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = client.invoke(SET_OFFSET, {"channel": 1, "offset_v": 1.5}, **self.ids)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"], {"offset_v": 1.5})
        self.assertEqual(self.state(client)["ch1_offset_v"], 1.5)
        completed = client.invoke(SET_OFFSET, {"channel": 2, "offset_v": -2.0}, **self.ids)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.state(client)["ch2_offset_v"], -2.0)
        refused = client.invoke(SET_OFFSET, {"channel": 1, "offset_v": 5.01}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_sync_phase_reaches_the_native_call(self) -> None:
        client = self.serve()
        self.assertEqual(self.write(client, ch1_phase=90.0, ch2_phase=-90.0)["status"], "completed")
        receipt = client.invoke("x-cap.ilovebacteria.sync_phase.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"synchronized": True})
        # The native method sends a synchronization command; its cited implementation
        # does not specify the configured phase-register values after that command.

    def test_the_estop_disables_both_outputs_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.write(client, ch1_output=True, ch2_output=True)["status"], "completed")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"])
        state = self.state(client)
        self.assertFalse(state["ch1_output"])
        self.assertFalse(state["ch2_output"])
        refused = self.write(client, ch1_output=True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

        client.reset(**self.ids)
        self.assertEqual(self.write(client, ch1_output=True)["status"], "completed")
        self.assertTrue(self.state(client)["ch1_output"])

    def test_an_ignored_output_off_fails_the_stop(self) -> None:
        class StuckOutput:
            @property
            def output_enabled(self):
                return True

            @output_enabled.setter
            def output_enabled(self, value):
                pass  # fault injection: the instrument ignores the OFF write

        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.ch1 = StuckOutput()
        driver.native.ch2.output_enabled = True
        with self.assertRaises(DriverFailed):
            driver.estop("test ignored output-off")
        self.assertFalse(driver.native.ch2.output_enabled)

    def test_a_channel_one_failure_does_not_skip_channel_two(self) -> None:
        class FailedOutput:
            @property
            def output_enabled(self):
                return True

            @output_enabled.setter
            def output_enabled(self, value):
                raise OSError("channel one write failed")

        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.ch1 = FailedOutput()
        driver.native.ch2.output_enabled = True
        with self.assertRaises(DriverFailed):
            driver.estop("test failed output-off")
        self.assertFalse(driver.native.ch2.output_enabled)


if __name__ == "__main__":
    unittest.main()
