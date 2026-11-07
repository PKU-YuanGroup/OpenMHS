"""Acceptance run of the tecancavro package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
EXAMPLE = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
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

    def test_the_reads_come_from_the_pump(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["plunger_position"], 3000)
        self.assertEqual(state["encoder_position"], 3000)
        self.assertEqual(state["port"], 1)
        self.assertEqual((state["start_speed"], state["top_speed"], state["cutoff_speed"]), (100, 1000, 1000))
        self.assertEqual((state["buffer_status"], state["microstep"]), (0, False))

    def test_a_write_queues_and_executes_the_upstream_command(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.write("main", {"top_speed": 2500})
        self.assertEqual(driver.read("main", ["top_speed"]), {"top_speed": 2500})
        self.assertEqual(driver.native.cmd_chain, "")           # executeChain() sent and cleared the chain
        driver.write("main", {"speed_code": 8})
        self.assertEqual(driver.native.getTopSpeed(), 8)        # the speed code wrote the top speed
        self.assertEqual(driver.native.cmd_chain, "")

    def test_a_microstep_write_is_sent_immediately(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.write("main", {"microstep": True})
        self.assertTrue(driver.native.microstep)
        self.assertEqual(driver.native.cmd_chain, "")
        self.assertEqual(driver.read("main", ["microstep"]), {"microstep": True})

    def test_a_dispense_waits_for_the_site_to_state_the_valve_and_the_syringe(self) -> None:
        client = self.serve()
        before = self.state(client)
        refused = client.invoke("x-cap.benpruitt.dispense.v1", {"port": 3, "volume": 200}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, refused)
        self.assertEqual(self.state(client), before)

    def test_the_actions_move_the_plunger_and_the_valve(self) -> None:
        client = self.serve(EXAMPLE)
        moved = client.invoke("x-cap.benpruitt.move_plunger.v1", {"position": 2400}, **self.ids)
        self.assertEqual(moved["output"], {"position": 2400})
        self.assertEqual(self.state(client)["plunger_position"], 2400)
        dispensed = client.invoke("x-cap.benpruitt.dispense.v1", {"port": 3, "volume": 200}, **self.ids)
        self.assertEqual(dispensed["output"], {"dispensed_volume": 200, "port": 3})
        state = self.state(client)
        self.assertEqual((state["port"], state["plunger_position"]), (3, 1800))   # 200 uL of 1000 uL is 600 steps

    def test_the_limits_refuse_without_reaching_the_pump(self) -> None:
        client = self.serve(EXAMPLE)
        before = self.state(client)
        for payload in ({"port": 0, "volume": 100}, {"port": 7, "volume": 100}, {"port": 2, "volume": -1},
                        {"port": 2, "volume": 501}):
            refused = client.invoke("x-cap.benpruitt.dispense.v1", payload, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        for value in (4, 6001):
            self.assertEqual(self.configure(client, top_speed=value)["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client), before)

    def test_the_example_overlay_only_narrows(self) -> None:
        client = self.serve(EXAMPLE)
        self.assertEqual(self.configure(client, top_speed=3001)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.configure(client, top_speed=3000)["status"], "completed")
        refused = client.invoke("x-cap.benpruitt.dispense.v1", {"port": 7, "volume": 200}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_terminates_the_command_and_latches(self) -> None:
        client = self.serve(EXAMPLE)
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.benpruitt.dispense.v1", {"port": 2, "volume": 100}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
