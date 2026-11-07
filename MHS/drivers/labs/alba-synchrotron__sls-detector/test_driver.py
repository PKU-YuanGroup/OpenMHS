"""Acceptance run of the SLS Mythen II package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SlsDetectorCases(unittest.TestCase):
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

    def test_the_fake_state_and_identity(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["detector_type"], "MYTHEN")
        self.assertEqual(state["settings"], "STANDARD")
        self.assertEqual(state["run_status"], "IDLE")
        self.assertEqual(state["nb_modules"], 6)
        self.assertEqual(state["module_serial_number"], 0xEE0)
        self.assertEqual(state["energy_threshold"], 9071)
        self.assertEqual(state["exposure_time"], 1.0)
        self.assertEqual((state["nb_frames"], state["nb_cycles"]), (1, 1))
        self.assertEqual((state["frame_period"], state["delay_after_trigger"]), (0.0, 0.0))
        self.assertEqual(state["exposure_time_left"], 0.0)

    def test_every_range_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, energy_threshold=9000)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["energy_threshold"], 9071)

        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, energy_threshold=9000)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["energy_threshold"], 9000)
        refused = self.configure(client, energy_threshold=20001)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["energy_threshold"], 9000)

    def test_the_acquisition_actions_follow_the_fake(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.alba-synchrotron.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"run_status": "RUNNING"})
        self.assertEqual(self.state(client)["run_status"], "RUNNING")
        stopped = client.invoke("x-cap.alba-synchrotron.stop_acquisition.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"run_status": "IDLE"})
        self.assertEqual(self.state(client)["run_status"], "IDLE")

    def test_acquire_returns_the_last_placeholder_frame(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure_time=0.001)["status"], "completed")
        self.assertEqual(self.configure(client, nb_frames=2)["status"], "completed")
        self.assertEqual(self.configure(client, nb_cycles=1)["status"], "completed")
        receipt = client.invoke("x-cap.alba-synchrotron.acquire.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["nb_frames"], 2)
        self.assertEqual(len(receipt["output"]["counts"]), 16)       # placeholder frame length
        self.assertEqual(receipt["output"]["run_status"], "IDLE")
        self.assertEqual(self.state(client)["run_status"], "IDLE")

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.alba-synchrotron.start_acquisition.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["run_status"], "IDLE")
        refused = client.invoke("x-cap.alba-synchrotron.start_acquisition.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_control_port_reads_are_left_out_while_acquire_holds_the_control_connection(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = driver.native
        fake.nb_frames, fake.nb_cycles, fake.exposure_time = 1000, 100, 0.001   # placeholder: a long acquisition
        outcome = {}

        def run():
            try:
                outcome["result"] = driver.call("x-cap.alba-synchrotron.acquire.v1", {})
            except Exception as exc:  # noqa: BLE001 - recorded for the assertion below
                outcome["error"] = exc

        worker = threading.Thread(target=run)
        worker.start()
        deadline = time.monotonic() + 5
        while fake.run_status.name != "RUNNING" and time.monotonic() < deadline:
            time.sleep(0.001)
        during = driver.read("main")
        fake.stop_acquisition()   # ends the fake acquisition
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(set(during), {"run_status", "exposure_time_left"})
        self.assertEqual(during["run_status"], "RUNNING")
        after = driver.read("main")
        self.assertEqual(after["exposure_time"], 0.001)
        self.assertEqual(after["run_status"], "IDLE")

    def test_an_estop_during_acquire_cancels_it_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for name, value in (("exposure_time", 0.001), ("nb_frames", 1000), ("nb_cycles", 100)):
            self.assertEqual(self.configure(client, **{name: value})["status"], "completed")
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.update(
            receipt=client.invoke("x-cap.alba-synchrotron.acquire.v1", {}, **self.ids)))
        worker.start()
        deadline = time.monotonic() + 5
        while self.state(client)["run_status"] != "RUNNING" and time.monotonic() < deadline:
            time.sleep(0.005)
        estop = client.estop("test", **self.ids)
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(estop["status"], "completed", estop)
        self.assertTrue(estop["output"]["safe_state_achieved"])
        self.assertEqual(outcome["receipt"]["status"], "cancelled", outcome)
        self.assertEqual(self.state(client)["run_status"], "IDLE")


if __name__ == "__main__":
    unittest.main()
