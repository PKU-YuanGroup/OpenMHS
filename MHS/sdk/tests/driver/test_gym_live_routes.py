"""GymnasiumDriver declarations for asynchronous, dm_env and settling-reset backends, through the stock server.

Synthetic in-process peers only; nothing here runs a remote simulator, dm_control, SAPIEN or hardware.
"""
from __future__ import annotations

import copy
import time
import unittest

from mhs.client import MHSClient
from mhs.driver import DriverDefinitionError, GymnasiumDriver, build_manifest, build_reference, build_server, close_server
from mhs.schema.store import default_store
from tests.bridges.test_gym_async import PROFILE, STOPPING, AsyncPeer
from tests.bridges.test_gym_dm_env import DM, PianoLike
from tests.bridges.test_gymnasium_timing_reset import SETTLING, SettlingEnv

NS = "openmhs_simulation_timing"
STEP, RESET, SEED = "cap.world.step.v1", "cap.world.reset.v1", "cap.world.seed.v1"


def async_driver(profile=STOPPING, env=None):
    native = env or AsyncPeer()

    class AsyncSim(GymnasiumDriver):
        device_id = "live-routes/async"
        backends = {"fake": lambda: native}
        async_by_backend = {"fake": copy.deepcopy(profile)}
        safe_state = "the steppable synthetic world is paused and no native work is owned"
    return AsyncSim(backend="fake"), native


def dm_driver(env=None):
    native = env or PianoLike(horizon=2, final_discount=1.0)

    class Composer(GymnasiumDriver):
        device_id = "live-routes/dm"
        backends = {"fake": lambda: native}
        dm_env_by_backend = {"fake": dict(DM)}
        safe_state = "software latch; the synthetic composer task does not advance without a step"
    return Composer(backend="fake"), native


def settling_driver(env=None, *, opt_out=True):
    native = env or SettlingEnv(settle=25)

    class Settling(GymnasiumDriver):
        device_id = "live-routes/settling"
        backends = {"sim": lambda: native, "fake": SettlingEnv}
        timing_by_backend = {"sim": copy.deepcopy(SETTLING)}
        checkpoint_by_backend = ({"sim": {"profile": "none", "reason": "synthetic native state omits its RNG"}}
                                 if opt_out else {})
        safe_state = "software latch; the synthetic world advances only inside a step or reset"
    return Settling(backend="sim"), native


def serve(driver):
    server = build_server(driver)
    client = MHSClient(server)
    client.hello()
    device = next(iter(server.devices.values()))
    client.open_session([device.device_id], mode="simulated")
    return server, client, device.device_id


def valid(testcase, document, schema):
    testcase.assertEqual(default_store().validate(dict(document), schema), [])


class AsyncDriverTests(unittest.TestCase):
    def test_manifest_declares_the_owned_loop_honestly(self):
        driver, _native = async_driver()
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        valid(self, manifest, "device.schema.json")
        ids = [item["capability_id"] for item in manifest["capabilities"]]
        self.assertEqual(sorted(ids), [RESET, STEP])
        reset = next(item for item in manifest["capabilities"] if item["capability_id"] == RESET)
        self.assertEqual(sorted(reset["input_schema"]["properties"]), ["seed"])
        self.assertIn("not used", reset["input_schema"]["properties"]["seed"]["description"])
        self.assertFalse(reset["input_schema"]["additionalProperties"])
        self.assertEqual(manifest["fidelity"]["determinism"], {"kind": "none", "seed_control": "none"})
        notes = " ".join(manifest["profile"]["operating_notes"])
        self.assertIn("asyncio_owned_loop_v1", notes)
        self.assertIn("world.pause", notes)
        self.assertEqual(driver.estop_native, "world.pause")
        reference = build_reference(driver)
        valid(self, reference, "reference.schema.json")

    def test_stock_server_step_estop_and_reset(self):
        driver, native = async_driver()
        server, client, device = serve(driver)
        self.addCleanup(close_server, server)
        receipt = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        stop = client.estop("test", device_id=device)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual(stop["output"]["estop"], "engaged", stop)
        self.assertGreaterEqual(native.world.pauses, 1)
        latched = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}}, device_id=device)
        self.assertEqual(latched["status"], "rejected", latched)
        self.assertEqual(client.reset(device_id=device)["status"], "completed")

    def test_stock_server_timeout_is_unknown_and_work_stays_owned(self):
        driver, native = async_driver(PROFILE)
        server, client, device = serve(driver)
        self.addCleanup(close_server, server)
        client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}}, device_id=device)
        native.remote_delay = 3.0                 # outlives the 0.5 s step bound and the 1 s e-stop budget
        receipt = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}}, device_id=device)
        self.assertEqual(receipt["status"], "unknown", receipt)
        valid(self, receipt, "receipt.schema.json")
        busy = client.invoke(RESET, {}, device_id=device)
        self.assertEqual((busy["status"], busy["error"]["mhs_code"]), ("rejected", "MHS.DEVICE.BUSY"), busy)
        started = time.monotonic()
        stop = client.estop("owned work", device_id=device)   # no remote stop declared: honest, not "engaged"
        self.assertLess(time.monotonic() - started, 2.5)       # bounded by the e-stop budget, no deadlock
        self.assertEqual((stop["status"], stop["error"]["mhs_code"]), ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"))
        self.assertIn(stop["error"]["details"]["reason"], ("bridge_reports_unsafe", "timeout"))
        self.assertTrue(stop["error"]["details"]["retrying"])
        self.assertEqual((stop["output"]["estop"], stop["output"]["latched"]), ("software_only", True))
        self.assertTrue(driver.inner._owned_loop.wait_idle(5))
        native.remote_delay = 0.0
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and client.reset(device_id=device)["status"] != "completed":
            time.sleep(0.05)
        self.assertEqual(client.invoke(RESET, {}, device_id=device)["status"], "completed")
        self.assertEqual(client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}},
                                       device_id=device)["status"], "completed")


    def test_stock_server_estop_waits_for_owned_work_that_settles_within_the_budget(self):
        driver, native = async_driver(PROFILE)
        server, client, device = serve(driver)
        self.addCleanup(close_server, server)
        client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}}, device_id=device)
        native.remote_delay = 0.7                 # past the 0.5 s step bound, inside the 1 s e-stop budget
        receipt = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}}, device_id=device)
        self.assertEqual(receipt["status"], "unknown", receipt)
        stop = client.estop("owned work that ends soon", device_id=device)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"])
        self.assertIsNone(driver.inner._owned_loop.owned())


class DmEnvDriverTests(unittest.TestCase):
    def test_manifest_and_stock_server_episode(self):
        driver, native = dm_driver()
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        valid(self, manifest, "device.schema.json")
        self.assertEqual(sorted(item["capability_id"] for item in manifest["capabilities"]), [RESET, STEP])
        step = next(item for item in manifest["capabilities"] if item["capability_id"] == STEP)
        self.assertEqual(step["limits"]["action.values"]["max"], [1.0, 1.0, 1.0])
        self.assertIn("dm_env_v1", " ".join(manifest["profile"]["operating_notes"]))
        server, client, device = serve(driver)
        self.addCleanup(close_server, server)
        receipt = client.invoke(STEP, {"ticks": 3, "action": {"values": [0.0, 0.0, 0.5]}}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, True))
        refused = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 2.0]}}, device_id=device)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")


class SettlingResetDriverTests(unittest.TestCase):
    def test_reset_receipt_reports_integrated_physics(self):
        driver, native = settling_driver()
        manifest = build_manifest(driver)
        valid(self, manifest, "device.schema.json")
        reset = next(item for item in manifest["capabilities"] if item["capability_id"] == RESET)
        self.assertTrue(reset["x-vendor"][NS]["reset_advances_physics"])
        self.assertFalse(manifest["fidelity"]["snapshot_restore"])
        self.assertTrue(any("explicit checkpoint opt-out" in gap for gap in manifest["fidelity"]["gaps"]))
        server, client, device = serve(driver)
        self.addCleanup(close_server, server)
        receipt = client.invoke(RESET, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        note = receipt["x-vendor"][NS]
        self.assertEqual((note["reset_integrated_ticks"], note["reset_calls_verified"]), (25, 1))
        self.assertEqual(note["completed_ticks"], 0)
        valid(self, receipt, "receipt.schema.json")
        step = client.invoke(STEP, {"ticks": 10, "action": {"index": 1}}, device_id=device)
        self.assertEqual(step["status"], "completed", step)
        self.assertEqual((step["x-vendor"][NS]["completed_ticks"], step["x-vendor"][NS]["reset_integrated_ticks"]),
                         (10, 0))
        valid(self, step, "receipt.schema.json")

    def test_opt_out_contradictions_are_definition_errors(self):
        class Contradiction(GymnasiumDriver):
            device_id = "live-routes/contradiction"
            backends = {"fake": SettlingEnv}
            checkpoint_by_backend = {"fake": {"profile": "none", "reason": "no state API"}}
            fidelity = {"snapshot_restore": True}
        with self.assertRaises(DriverDefinitionError):
            Contradiction(backend="fake")

        class Projection(GymnasiumDriver):
            device_id = "live-routes/projection"
            backends = {"fake": SettlingEnv, "sim": SettlingEnv}
            checkpoint_by_backend = {"fake": {"profile": "json_state_v1", "getter": "get_state", "setter": "set_state"},
                                     "sim": {"profile": "none", "reason": "native state incomplete"}}
        fake = Projection(backend="fake")
        self.addCleanup(fake.close)
        with self.assertRaises(DriverDefinitionError):
            build_manifest(fake, backend="sim")
        with self.assertRaises(DriverDefinitionError):
            class Bad(GymnasiumDriver):
                device_id = "live-routes/bad"
                backends = {"fake": SettlingEnv}
                checkpoint_by_backend = {"fake": {"profile": "none"}}
            Bad(backend="fake")


if __name__ == "__main__":
    unittest.main()
