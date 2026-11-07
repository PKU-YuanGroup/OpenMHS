"""Acceptance run of the Grip PickAndPlaceEnvironment package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): pybullet, NumPy and the
upstream clone are not imported or run where the gate runs, so nothing here compares the fake with upstream.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_JOINTS = [0.0] * 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GripCases(unittest.TestCase):
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
        payload = {"ticks": ticks}
        if action is not None:
            payload["action"] = action
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_the_world_and_returns_the_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, {"joint_position_cmd": [0.2] * 7, "gripper_cmd": -0.01})
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        robot = output["observation"]["robot"]
        self.assertEqual(robot["joint_names"], ["panda_joint{}".format(index) for index in range(1, 8)])
        self.assertEqual(len(robot["positions"]), 7)
        self.assertAlmostEqual(robot["positions"][0], 0.05, places=7)   # 0.25 * (0.2 - 0.0)
        self.assertAlmostEqual(robot["gripper_state"]["displacement"], 0.03, places=7)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_reset_restores_the_start_state_and_echoes_the_constructor_seed(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["seed"], 77)                              # template_env.py:34
        self.assertEqual(output["observation"]["robot"]["positions"], ZERO_JOINTS)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_empty_action_is_accepted_and_only_advances_time(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, {})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["observation"]["robot"]["positions"], ZERO_JOINTS)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_joint_command_must_have_seven_values(self) -> None:
        client = self.serve()
        refused = self.step(client, {"joint_position_cmd": [0.0] * 8})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_unknown_scenario_fails(self) -> None:
        client = self.serve()
        receipt = self.reset(client, scenario="elsewhere")
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:grip PickAndPlaceEnvironment stand-in (no pybullet)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 * 10.0 / 240.0, places=7)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)


class RawGrip:
    """Source-shaped controlled native; no upstream import or physics engine."""
    def __init__(self, *, seed=123, sim_steps=3, time_step=.02, block=False, **kwargs):
        import threading
        self.seed, self.sim_steps, self.time_step = seed, sim_steps, time_step
        self.calls, self.substeps, self.closed, self.disconnected = [], 0, False, False
        self.entered, self.release = threading.Event(), threading.Event()
        if not block:
            self.release.set()
        self.world = self

    def reset(self):
        self.calls.append("reset")
        return {"robot": {"entity": object(), "positions": [0.] * 7}}

    def step(self, action):
        self.calls.append(dict(action))
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("test release was not signalled")
        self.substeps += self.sim_steps
        return {"robot": {"entity": object(), "positions": [0.] * 7}}, 0., False, {}

    def close(self):
        self.closed = True

    def disconnect(self):
        self.disconnected = True


class RawNativeCases(unittest.TestCase):
    def serve_raw(self, native, *, backend="fake"):
        from mhs.adapter import load_driver
        from mhs.driver import build_server
        driver = load_driver(HERE, backend=backend, native=native,
                             options={"seed": native.seed, "sim_steps": native.sim_steps, "time_step": native.time_step})
        driver.setup()  # explicit native injection skips setup by SDK contract
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        did = client.hello()["devices"][0]["device_id"]
        sid = client.open_session(device_ids=[did])["session_id"]
        return driver, client, {"device_id": did, "session_id": sid}

    def test_raw_configuration_projection_and_decimation(self):
        raw = RawGrip()
        driver, client, ids = self.serve_raw(raw)
        receipt = client.invoke("cap.world.reset.v1", {}, **ids)
        self.assertEqual(receipt["output"]["seed"], 123)
        receipt = client.invoke("cap.world.step.v1", {"ticks": 2, "action": {"gripper_cmd": .002}}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt["output"]["tick"], raw.substeps), (2, 6))
        self.assertNotIn("entity", receipt["output"]["observation"]["robot"])
        self.assertEqual(client.inspect(ids["device_id"])["fidelity"]["timestep_ms"], 60.)
        schema = next(c for c in driver.capabilities() if c["capability_id"] == "cap.world.step.v1")
        self.assertEqual(schema["input_schema"]["properties"]["action"]["properties"]["gripper_cmd"]["x-mhs-unit"], "m")

    def test_inflight_stop_does_not_confirm_and_queued_call_never_sends(self):
        import threading
        raw = RawGrip(block=True)
        _, client, ids = self.serve_raw(raw)
        receipts = []
        def invoke():
            receipts.append(client.invoke("cap.world.step.v1", {"ticks": 2, "action": {}}, deadline_ms=3000, **ids))
        first = threading.Thread(target=invoke)
        second = threading.Thread(target=invoke)
        first.start()
        self.assertTrue(raw.entered.wait(1))
        second.start()
        try:
            stopped = client.estop("in-flight test", **ids)
            self.assertIs(stopped.get("output", {}).get("safe_state_achieved"), False, stopped)
            reset = client.reset(**ids)
            self.assertNotEqual(reset["status"], "completed", reset)
            self.assertEqual(raw.substeps, 0)
        finally:
            raw.release.set()
            first.join(3)
            second.join(3)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(len(raw.calls), 1)
        self.assertEqual(raw.substeps, 3)
        stopped = client.estop("native call is now idle", **ids)
        self.assertTrue(stopped["output"]["safe_state_achieved"], stopped)
        self.assertEqual(client.reset(**ids)["status"], "completed")
        final = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {}}, **ids)
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(len(raw.calls), 2)

    def test_invalid_action_and_options_make_no_native_call(self):
        raw = RawGrip()
        _, client, ids = self.serve_raw(raw)
        for cap, value in (("cap.world.step.v1", {"ticks": 1, "action": {"joint_position_cmd": [0.] * 8}}),
                           ("cap.world.reset.v1", {"options": {"seed": 1}})):
            receipt = client.invoke(cap, value, **ids)
            self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertEqual(raw.calls, [])

    def test_lazy_factory_uses_selected_native_and_owned_cleanup(self):
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch
        from mhs.adapter import driver_class, load_driver
        cls = driver_class(HERE)
        factory = importlib.import_module(cls.__module__.rsplit(".", 1)[0] + ".sim")
        calls = []
        raw = RawGrip()
        def construct(**kwargs):
            calls.append(kwargs)
            return raw
        with patch.object(factory, "_load_environment", return_value=SimpleNamespace(PickAndPlaceEnvironment=construct)) as loader:
            with self.assertRaises(ValueError):
                load_driver(HERE, backend="sim", options={"sim_steps": 0})
            loader.assert_not_called()
            driver = load_driver(HERE, backend="sim", options={"seed": 123, "sim_steps": 3, "time_step": .02})
            self.assertEqual(calls[0]["gripper"], "default")
            self.assertEqual(calls[0]["render_mode"], "DIRECT")
            self.assertFalse(calls[0]["enable_texture_randomiser"])
            self.assertEqual(driver._model.fidelity["fidelity_level"], "F1")
            driver.close()
            self.assertTrue(raw.closed and raw.disconnected)

    def test_close_is_irreversible_while_native_cleanup_waits(self):
        import threading
        raw = RawGrip()
        entered, release = threading.Event(), threading.Event()
        counts = {"close": 0, "disconnect": 0}
        def close():
            counts["close"] += 1
            entered.set()
            if not release.wait(3):
                raise RuntimeError("missing cleanup release")
        raw.close = close
        raw.disconnect = lambda: counts.__setitem__("disconnect", counts["disconnect"] + 1)
        driver, client, ids = self.serve_raw(raw, backend="sim")
        thread = threading.Thread(target=driver.close)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            stopped = client.estop("closing", **ids)
            self.assertIs(stopped.get("output", {}).get("safe_state_achieved"), False, stopped)
            self.assertNotEqual(client.reset(**ids)["status"], "completed")
            step = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {}}, **ids)
            self.assertNotEqual(step["status"], "completed")
            self.assertEqual(raw.calls, [])
            driver._adapter.close()  # concurrent/repeated teardown cannot claim cleanup twice
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        driver.close()
        self.assertEqual(counts, {"close": 1, "disconnect": 1})
        with self.assertRaises(Exception):
            driver._adapter.recover()
        with self.assertRaises(Exception):
            driver._adapter.invoke("reset")

    def test_close_during_native_call_defers_exactly_once_owned_cleanup(self):
        import threading
        raw = RawGrip(block=True)
        counts = {"close": 0, "disconnect": 0}
        raw.close = lambda: counts.__setitem__("close", counts["close"] + 1)
        raw.disconnect = lambda: counts.__setitem__("disconnect", counts["disconnect"] + 1)
        driver, client, ids = self.serve_raw(raw, backend="sim")
        results = []
        thread = threading.Thread(target=lambda: results.append(client.invoke(
            "cap.world.step.v1", {"ticks": 1, "action": {}}, deadline_ms=3000, **ids)))
        thread.start()
        try:
            self.assertTrue(raw.entered.wait(1))
            driver.close()
            self.assertTrue(driver.closed)
            self.assertEqual(counts, {"close": 0, "disconnect": 0})
            self.assertNotEqual(client.reset(**ids)["status"], "completed")
        finally:
            raw.release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        driver.close()
        self.assertEqual(counts, {"close": 1, "disconnect": 1})
        self.assertTrue(driver._adapter._closed)
        with self.assertRaises(Exception):
            driver._adapter.invoke("step", {})

    def test_failed_native_close_still_disconnects_owned_world_without_reopen(self):
        raw = RawGrip()
        counts = {"close": 0, "disconnect": 0}
        def close():
            counts["close"] += 1
            raise RuntimeError("controlled cleanup failure")
        raw.close = close
        raw.disconnect = lambda: counts.__setitem__("disconnect", counts["disconnect"] + 1)
        driver, _, _ = self.serve_raw(raw, backend="sim")
        driver.close()
        driver._adapter.close()
        self.assertEqual(counts, {"close": 1, "disconnect": 1})
        self.assertIn("controlled cleanup failure", driver._adapter._close_error)
        with self.assertRaises(Exception):
            driver._adapter.recover()

    def test_configuration_copy_and_instance_fidelity_do_not_mutate_class(self):
        from mhs.adapter import driver_class
        cls = driver_class(HERE)
        baseline = cls.driver_model().fidelity.copy()
        options = {"seed": 12, "sim_steps": 2, "time_step": .01}
        first = cls(options=options)
        options["sim_steps"] = 99
        second = cls()
        try:
            self.assertEqual(first._model.fidelity["timestep_ms"], 20.)
            self.assertAlmostEqual(second._model.fidelity["timestep_ms"], 1000 * 10 / 240)
            self.assertEqual(cls.driver_model().fidelity, baseline)
        finally:
            first.close()
            second.close()


if __name__ == "__main__":
    unittest.main()
