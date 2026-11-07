"""Acceptance run of the ManiSkill2 real2sim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call. The cases run on the fake backend (fake.py): SAPIEN, PyTorch and
the upstream package are not installed where the gate runs, so nothing here compares the fake with the clone.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ACTION = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ManiSkillCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(action or ACTION)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0] * 7)["status"], "completed")
        refused = self.step(client, [1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        short = self.step(client, [0.0] * 6)
        self.assertEqual(short["status"], "rejected")
        self.assertEqual(short["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_has_an_observable_effect(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)
        self.assertEqual(first["status"], "completed")
        before = first["output"]["observation"]["values"]
        self.assertEqual(len(before), 48)
        receipt = self.step(client, [0.5, -0.25, 0.0, 0.0, 0.0, 0.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertNotEqual(output["observation"]["values"], before)
        self.assertEqual(output["observation"]["values"][22], 1.0)              # the gripper target follows the action

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                    # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5])["output"]["state_hash"]
                    for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_80_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        long = self.step(client, ticks=79)
        self.assertEqual(long["status"], "completed")
        self.assertEqual((long["output"]["tick"], long["output"]["truncated"]), (79, False))
        last = self.step(client)
        self.assertEqual(last["status"], "completed")
        # gymnasium.make wraps GraspSingleCokeCanInScene-v0 in a TimeLimit of 80 steps
        self.assertEqual((last["output"]["tick"], last["output"]["truncated"]), (80, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("python:openmhs-simplerenv-grasp-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


class CheckpointCases(unittest.TestCase):
    def serve(self, budget=None):
        from mhs.client import MHSClient, InProcessTransport
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device])
        driver = server.devices[device].bridge
        if budget is not None:
            # A small operator lifetime budget for this test, using the same
            # production bridge guard. No checkpoint supplies this value.
            driver.inner._max_steps = budget
        return client, device, driver

    def command(self, client, device, cap="cap.world.step.v1", payload=None):
        return client.invoke(cap, payload if payload is not None else {
            "ticks": 1, "action": {"values": [0.25, 0, 0, 1.2, 0, 0, 0.5]}}, device_id=device)

    def test_stock_snapshot_hash_and_step_reset_rng_continuation(self):
        from mhs import canonical
        from mhs.schema import default_store
        client, device, driver = self.serve()
        self.command(client, device, "cap.world.reset.v1", {"seed": 71})
        self.command(client, device)
        saved = client.snapshot(device)
        state = client.read("world", device_id=device)["state"]
        self.assertEqual(saved["state"]["world"], state)
        self.assertEqual(saved["state"], saved["snapshot"])
        self.assertEqual(saved["state_hash"], canonical.state_hash(state))
        self.assertEqual(saved["snapshot_digest"], canonical.digest(saved["state"]))
        self.assertEqual(default_store().validate(saved, "snapshot.schema.json"), [])
        expected_step = self.command(client, device)["output"]
        expected_reset = self.command(client, device, "cap.world.reset.v1", {})["output"]
        expected_followup = self.command(client, device)["output"]
        restored = client.restore(saved, device)
        self.assertEqual(restored["status"], "completed", restored)
        self.assertEqual(client.read("world", device_id=device)["state"], state)
        self.assertEqual(self.command(client, device)["output"], expected_step)
        self.assertEqual(self.command(client, device, "cap.world.reset.v1", {})["output"], expected_reset)
        self.assertEqual(self.command(client, device)["output"], expected_followup)
        values = expected_followup["observation"]["values"]
        self.assertEqual(len(values), 48)
        self.assertTrue(all(type(value) in (int, float) for value in values))

    def test_pending_seed_and_time_limit_restore(self):
        client, device, driver = self.serve()
        self.command(client, device, "cap.world.reset.v1", {"seed": 1})
        self.command(client, device, payload={"ticks": 79, "action": {"values": ACTION}})
        self.command(client, device, "cap.world.seed.v1", {"seed": 19})
        saved = client.snapshot(device)
        self.assertTrue(self.command(client, device)["output"]["truncated"])
        expected = self.command(client, device, "cap.world.reset.v1", {})["output"]
        self.command(client, device, "cap.world.seed.v1", {"seed": 99})
        self.assertEqual(client.restore(saved, device)["status"], "completed")
        self.assertTrue(self.command(client, device)["output"]["truncated"])
        replay = self.command(client, device, "cap.world.reset.v1", {})["output"]
        self.assertEqual(replay, expected)
        self.assertEqual(replay["seed"], 19)

    def test_restore_and_reset_never_replenish_lifetime_budget(self):
        client, device, driver = self.serve(budget=3)
        self.command(client, device, "cap.world.reset.v1", {"seed": 2})
        saved = client.snapshot(device)
        self.assertEqual(self.command(client, device, payload={"ticks": 3, "action": {"values": ACTION}})["status"],
                         "completed")
        native = driver.native
        from unittest.mock import patch
        with patch.object(type(native), "step", wraps=native.step) as dispatch:
            for _ in range(2):
                self.assertEqual(client.restore(saved, device)["status"], "completed")
                self.assertEqual(self.command(client, device, "cap.world.reset.v1", {})["status"], "completed")
                self.assertNotEqual(self.command(client, device)["status"], "completed")
                self.assertEqual(driver.inner._total_steps, 3)
            self.assertEqual(dispatch.call_count, 0)

    def test_fake_codec_is_atomic_and_preserves_gaussian_cache(self):
        import copy
        client, device, driver = self.serve()
        native = driver.native
        native._rng.gauss(0, 1)  # exercise the optional cached Gaussian value too
        saved = native.get_state()
        expected = native.reset()[0]
        native.set_state(saved)
        self.assertEqual(native.reset()[0], expected)
        before = native.get_state()
        changes = [lambda x: x["rng"].update(version=2),
                   lambda x: x["rng"].update(words=[0]),
                   lambda x: x["rng"]["words"].__setitem__(0, True),
                   lambda x: x["rng"]["words"].__setitem__(-1, 625),
                   lambda x: x["rng"].update(gaussian=float("nan")),
                   lambda x: x.update(tick=True), lambda x: x.update(truncated=True),
                   lambda x: x.update(observation=[0.0]), lambda x: x.update(extra=1)]
        for mutate in changes:
            candidate = copy.deepcopy(before); mutate(candidate)
            with self.assertRaises(ValueError):
                native.set_state(candidate)
            self.assertEqual(native.get_state(), before)

    def test_tampered_native_checkpoint_cannot_succeed_and_restores_prestate(self):
        import copy
        from mhs import canonical
        client, device, driver = self.serve()
        self.command(client, device, "cap.world.reset.v1", {"seed": 4})
        saved = client.snapshot(device)
        self.command(client, device)
        before = client.read("world", device_id=device)["state"]
        corrupted = copy.deepcopy(saved)
        native = corrupted["state"]["world"]["native_checkpoint"]["native_state"]
        native["rng"]["words"][-1] = 625
        corrupted["snapshot"] = copy.deepcopy(corrupted["state"])
        corrupted["snapshot_digest"] = canonical.digest(corrupted["state"])
        corrupted["state_hash"] = canonical.state_hash(corrupted["state"]["world"])
        receipt = client.restore(corrupted, device)
        self.assertIn(receipt["status"], ("failed", "rejected"), receipt)
        self.assertEqual(client.read("world", device_id=device)["state"], before)

    def test_live_path_opens_lazily_and_opts_out_of_snapshots(self):
        from mhs.driver import DriverDefinitionError, build_manifest
        client, device, driver = self.serve()
        sim = _package_module(driver, "sim")
        with self.assertRaises(DriverDefinitionError):
            sim.connect(obs_mode="image")              # refused before any upstream import
        self.assertFalse(type(driver).fidelity_by_backend["sim"]["snapshot_restore"])
        self.assertEqual(type(driver).checkpoint_by_backend["sim"]["profile"], "none")
        self.assertIn("sapien_env.py:653-680", type(driver).checkpoint_by_backend["sim"]["reason"])
        with self.assertRaises(DriverDefinitionError):
            build_manifest(driver, backend="sim")     # a timed, opted-out backend needs its own instance

    def test_counting_subclass_counts_each_completed_physics_substep(self):
        from mhs.adapter import load_driver
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        counted = _package_module(driver, "sim").counting_subclass(_TaskStandIn)()
        self.assertEqual((counted.mhs_physics_ticks, counted._scene.steps), (1250, 1250))   # construction reset
        counted.step_action(None)
        self.assertEqual((counted.mhs_physics_ticks, counted._scene.steps), (1275, 1275))
        self.assertAlmostEqual(counted.mhs_physics_clock_s, 1275 * 0.002)
        counted.unsettled = False
        counted.reset()
        self.assertEqual((counted.mhs_physics_ticks, counted._scene.steps), (1775, 1775))

    def test_live_timing_measures_control_and_settling_ticks(self):
        from mhs.adapter import load_driver
        from mhs.bridge.base import BridgeContext
        from mhs.bridge.gymnasium import GymnasiumBridge
        from mhs.bridge.simulation_timing import CONTEXT_KEY, SimulationTimingReport
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        timing = type(driver).timing_by_backend["sim"]
        env = _package_module(driver, "sim").counting_subclass(_TaskStandIn)()
        bridge = GymnasiumBridge(env=env, timing=timing, device_id="test/simpler-live")
        self.addCleanup(bridge.close)
        context = BridgeContext()
        report = SimulationTimingReport(bridge.timing_descriptor(), None)
        context.extra[CONTEXT_KEY] = report
        bridge.call("cap.world.reset.v1", {}, context)
        self.assertEqual(report.snapshot()["reset_integrated_ticks"], 1250)      # settled while still moving
        step = BridgeContext()
        step_report = SimulationTimingReport(bridge.timing_descriptor(), 50)
        step.extra[CONTEXT_KEY] = step_report
        out = bridge.call("cap.world.step.v1", {"ticks": 50, "action": {"values": [0.0] * 7}}, step)
        self.assertEqual((out["tick"], step_report.snapshot()["completed_ticks"], env.calls), (50, 50, 2))
        env.extra_settle = 0.2                                                    # settles past the declared bound
        with self.assertRaises(Exception) as caught:
            bridge.call("cap.world.reset.v1", {}, BridgeContext())
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.DEVICE.FAULTED")

    def test_snapshot_restore_cannot_clear_the_estop_latch(self):
        client, device, driver = self.serve()
        self.command(client, device, "cap.world.reset.v1", {"seed": 9})
        saved = client.snapshot(device)
        before = client.read("world", device_id=device)["state"]
        client.estop("snapshot safety regression", device_id=device)
        restored = client.restore(saved, device)
        self.assertEqual(restored["status"], "rejected", restored)
        self.assertEqual(restored["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.read("world", device_id=device)["state"], before)
        self.assertEqual(self.command(client, device)["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.reset(device)["status"], "completed")
        self.assertEqual(client.restore(saved, device)["status"], "completed")

    def test_rotation_box_keeps_unnormalized_arm_and_50ms_fake_control(self):
        client, device, driver = self.serve()
        accepted = self.command(client, device)
        self.assertEqual(accepted["status"], "completed", accepted)  # arm rotation 1.2 is valid
        refused = self.command(client, device, payload={"ticks": 1,
            "action": {"values": [0, 0, 0, 1.6, 0, 0, 0]}})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(client.read("world", device_id=device)["state"]["tick"], 1)
        fidelity = client.inspect(device)["fidelity"]
        self.assertEqual(fidelity["timestep_ms"], 50.0)
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")


class LiveDeclarationCases(unittest.TestCase):
    def test_the_live_declarations_are_consistent(self):
        # The sim backend's own manifest, built over the package's counter applied to a stand-in task (the live
        # factory imports SAPIEN): timing, settling resets, the checkpoint opt-out and fidelity must agree.
        from mhs.adapter import load_driver
        from mhs.driver import build_manifest
        fake_driver = load_driver(HERE, "fake")
        self.addCleanup(fake_driver.close)
        cls = type(fake_driver)
        counted = _package_module(fake_driver, "sim").counting_subclass(_TaskStandIn)

        class StandInLive(cls):
            backends = {"fake": cls.backends["fake"], "sim": counted}
        driver = StandInLive(backend="sim")
        self.addCleanup(driver.close)
        manifest = build_manifest(driver)
        fidelity = manifest["fidelity"]
        self.assertEqual((fidelity["timestep_ms"], fidelity["fidelity_level"], fidelity["snapshot_restore"]),
                         (2.0, "F1", False))
        self.assertTrue(any("explicit checkpoint opt-out" in gap for gap in fidelity["gaps"]))
        self.assertIn("no wall-clock pacing", fidelity["gaps"])
        bindings = {item["capability_id"]: item for item in manifest["capabilities"]}
        step = bindings["cap.world.step.v1"]["x-vendor"]["openmhs_simulation_timing"]
        reset = bindings["cap.world.reset.v1"]["x-vendor"]["openmhs_simulation_timing"]
        self.assertEqual((step["control_decimation"], step["control_period_ms"]), (25, 50.0))
        self.assertEqual((reset["reset_clock"], reset["max_reset_ticks"]), ("continue", 1250))
        self.assertEqual(bindings["cap.world.step.v1"]["input_schema"]["properties"]["ticks"]["multipleOf"], 25)


def _package_module(driver, name):
    """The package's own module ``name``, imported beside driver.py."""
    import importlib
    return importlib.import_module(type(driver).__module__.rsplit(".", 1)[0] + "." + name)


class _Space:
    def __init__(self, low, high):
        self.low, self.high, self.shape, self.dtype = list(low), list(high), (len(low),), "float32"


class _Scene:
    def __init__(self):
        self.steps = 0

    def step(self):
        self.steps += 1


class _TaskStandIn:
    """Stand-in with the upstream integration structure (not SAPIEN): BaseEnv.step_action (sapien_env.py:569-573),
    CustomSceneEnv._settle (base_env.py:220-224) and the grasp task's settling (grasp_single_in_scene.py:302-316)."""

    _sim_freq, _control_freq = 500, 20

    def __init__(self):
        self._scene = _Scene()
        self._sim_steps_per_control = self._sim_freq // self._control_freq
        self.action_space = _Space([-1.0] * 7, [1.0] * 7)
        self.observation_space = _Space([-1e9] * 48, [1e9] * 48)
        self.unsettled, self.extra_settle, self.calls = True, 0.0, 0
        self.reset(seed=2022)                       # BaseEnv.__init__ resets once while constructing

    @property
    def sim_freq(self):
        return self._sim_freq

    @property
    def sim_timestep(self):
        return 1.0 / self._sim_freq

    def _after_simulation_step(self):
        pass

    def _settle(self, t):
        for _ in range(int(self.sim_freq * t)):
            self._scene.step()

    def reset(self, seed=None, options=None):
        self._settle(0.5)
        self._settle(0.5)
        if self.unsettled:
            self._settle(1.5)
        if self.extra_settle:
            self._settle(self.extra_settle)
        return [0.0] * 48, {}

    def step_action(self, action):
        for _ in range(self._sim_steps_per_control):
            self._scene.step()
            self._after_simulation_step()

    def step(self, action):
        self.calls += 1
        self.step_action(action)
        return [0.0] * 48, 0.0, False, False, {}


if __name__ == "__main__":
    unittest.main()
