"""Acceptance run of the Project AirSim drone-landing package: the gate plus local cases.

Add cases, never remove the check_driver call. The cases run on the fake backend (fake.py), which keeps the
native calling convention (coroutine step, argument-free reset, world.pause/is_paused); no Project AirSim
client, server or Unreal scene is imported or contacted.
"""

import asyncio
import copy
import importlib
import inspect
import math
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.driver import DriverDefinitionError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
STEP = "cap.world.step.v1"


def package_module(driver, name):
    """The package's own module ``name`` (fake or sim), imported beside driver.py."""
    return importlib.import_module(type(driver).__module__.rsplit(".", 1)[0] + "." + name)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ProjectAirSimCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.server = server
        return client

    def test_step_advances_the_placeholder_environment(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            STEP,
            {"ticks": 2, "action": {"values": [0.0, 0.0, 0.0]}},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(len(output["observation"]["values"]), 4)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_step_refuses_an_action_outside_the_space(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            STEP,
            {"ticks": 1, "action": {"values": [1.5, 0.0, 0.0]}},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertIsNone(receipt.get("output"))

    def test_velocity_moves_the_pose_through_the_awaited_command(self) -> None:
        client = self.serve()
        receipt = client.invoke(STEP, {"ticks": 1, "action": {"values": [1.0, -1.0, 0.5]}}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        values = receipt["output"]["observation"]["values"]
        self.assertAlmostEqual(values[0], 5.0 + 0.1)        # placeholder start pose plus v * dt
        self.assertAlmostEqual(values[1], 5.0 - 0.1)
        self.assertAlmostEqual(values[2], -5.0 + 0.05)

    def test_reset_takes_no_seed_and_no_seed_capability_is_served(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        ids = sorted(item["capability_id"] for item in device["capabilities"])
        self.assertEqual(ids, ["cap.world.reset.v1", STEP])
        self.assertEqual(device["fidelity"]["determinism"]["kind"], "none")
        reset = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["seed"], 0)         # accepted for the class contract, never used
        self.assertEqual(len(reset["output"]["observation"]["values"]), 4)
        seeded = client.invoke("cap.world.seed.v1", {"seed": 7}, **self.ids)
        self.assertEqual(seeded["status"], "rejected", seeded)

    def test_estop_pauses_the_world_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0]}},
                                       **self.ids)["status"], "completed")
        native = self.server.devices[self.ids["device_id"]].bridge.native
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertGreaterEqual(native.world.pauses, 1)
        self.assertTrue(native.world.is_paused())
        refused = client.invoke(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0]}}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_fake_keeps_the_native_calling_convention(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = package_module(driver, "fake").FakeProjectAirSimDroneLanding
        self.assertTrue(inspect.iscoroutinefunction(fake.step))
        self.assertEqual(list(inspect.signature(fake.reset).parameters), ["self"])
        env = fake()
        observation = env.reset()
        self.assertEqual(len(observation), 4)
        next_observation, reward, done, info = asyncio.run(env.step([0.0, 0.0, 0.0]))
        self.assertEqual(len(next_observation), 4)
        self.assertTrue(math.isfinite(reward))
        self.assertGreater(reward, 0.0)
        self.assertFalse(done)
        self.assertEqual(info, {"status": "Running"})
        self.assertTrue(env.world.is_paused())               # the steppable clock pauses after each step
        env.close()

    def test_the_coroutine_step_is_entered_and_awaited_on_one_owned_loop(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        native = driver.native
        threads = []
        original = native.step

        async def observed(action):
            threads.append(threading.current_thread().name)
            return await original(action)

        native.step = observed   # controlled peer only: records the thread that runs the coroutine
        receipt_output = driver.call(STEP, {"ticks": 2, "action": {"values": [0.25, 0.0, 0.0]}})
        self.assertEqual(receipt_output["tick"], 2)
        self.assertEqual(len(threads), 2)
        self.assertEqual(len(set(threads)), 1)
        self.assertNotEqual(threads[0], threading.current_thread().name)

    def test_live_factory_imports_nothing_until_it_opens(self) -> None:
        with patch("socket.create_connection", side_effect=AssertionError("connection attempted")) as connect:
            driver = load_driver(HERE, "fake")
            self.addCleanup(driver.close)
            sim = package_module(driver, "sim")
            with self.assertRaises(DriverDefinitionError):
                sim.make_env(scene="other.jsonc")
        connect.assert_not_called()
        self.assertEqual(type(driver).async_by_backend["sim"], type(driver).async_by_backend["fake"])
        self.assertEqual(type(driver).backends["sim"], ".sim:make_env")

    def test_constructor_unwind_disconnects_a_connected_client(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        sim = package_module(driver, "sim")
        disconnected = []

        class Client:
            def disconnect(self):
                disconnected.append(True)

        class FailsAfterConnect:
            def __init__(self):
                self.client = Client()          # connected first, as gym_env.py:27-28
                raise RuntimeError("World construction failed")   # then World raises, as gym_env.py:29 may

        with self.assertRaisesRegex(RuntimeError, "World construction failed"):
            sim.construct(FailsAfterConnect)
        self.assertEqual(disconnected, [True])

        class Fine:
            def __init__(self):
                self.client = Client()
        self.assertIsInstance(sim.construct(Fine), Fine)
        self.assertEqual(disconnected, [True])

    def test_an_owned_step_past_its_bound_stays_owned_and_the_estop_is_honest(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake_module = package_module(driver, "fake")
        release = threading.Event()

        class Slow(fake_module.FakeProjectAirSimDroneLanding):
            def __init__(self):
                super().__init__()
                world = self.world
                advance = world.continue_for_sim_time

                def blocking_continue(delta, wait_until_complete=True):
                    release.wait(5)               # like the native blocking ContinueForSimTime
                    return advance(delta, wait_until_complete)
                world.continue_for_sim_time = blocking_continue

        profile = copy.deepcopy(type(driver).async_by_backend["fake"])
        profile.update(step_timeout_s=0.2, stop_timeout_s=0.2, settle_timeout_s=0.5)
        env = Slow()
        bridge = GymnasiumBridge(env=env, asynchronous=profile, device_id="test/slow")
        self.addCleanup(release.set)
        self.addCleanup(bridge.close)
        with self.assertRaises(Exception) as caught:
            bridge.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")
        with self.assertRaises(Exception) as caught:
            bridge.estop("loop blocked inside ContinueForSimTime")
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(env.world.pauses, 0)                 # queued behind the blocking call, not dropped
        release.set()
        deadline = time.monotonic() + 3
        while bridge._owned_loop.owns_any() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(env.world.pauses, 1)
        self.assertTrue(bridge.estop("fresh stop")["confirmed"])
        bridge.reset()
        with self.assertRaises(Exception):
            bridge.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}})   # explicit reset required
        bridge.call("cap.world.reset.v1", {})
        self.assertEqual(bridge.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.0, 0.0]}})["tick"], 1)

    def test_the_live_declarations_are_consistent(self) -> None:
        # The sim backend's own manifest, built over a stand-in factory (the live factory imports upstream code).
        from mhs.driver import build_manifest
        fake_driver = load_driver(HERE, "fake")
        self.addCleanup(fake_driver.close)
        cls = type(fake_driver)
        stand_in = package_module(fake_driver, "fake").FakeProjectAirSimDroneLanding

        class StandInLive(cls):
            backends = {"fake": cls.backends["fake"], "sim": stand_in}
        driver = StandInLive(backend="sim")
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        fidelity = manifest["fidelity"]
        self.assertEqual((fidelity["fidelity_level"], fidelity["snapshot_restore"]), ("F1", False))
        self.assertTrue(fidelity["engine"].startswith("projectairsim"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertTrue(any(gap.startswith("not run") for gap in fidelity["gaps"]))
        self.assertEqual(manifest["safety"]["estop"]["native"], "world.pause")
        self.assertIn("asyncio_owned_loop_v1", " ".join(manifest["profile"]["operating_notes"]))
        self.assertEqual(sorted(item["capability_id"] for item in manifest["capabilities"]),
                         ["cap.world.reset.v1", STEP])

    def test_close_pauses_the_world_then_closes_on_the_owned_loop(self) -> None:
        driver = load_driver(HERE, "fake")
        native = driver.native
        driver.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0, 0.0]}})
        before = native.world.pauses
        driver.close()
        self.assertTrue(driver.inner._cleanup_done.wait(5))
        self.assertEqual(native.world.pauses, before + 1)
        self.assertTrue(native._closed)
        self.assertEqual(driver.inner.async_status()["close"], "settled")


if __name__ == "__main__":
    unittest.main()
