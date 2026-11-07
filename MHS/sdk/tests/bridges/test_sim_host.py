"""The isolated simulator host (isolated_process_v1): real child processes running a synthetic environment.

Every case starts a child process with :mod:`tests.bridges.sim_host_fixture`; nothing here runs ROS, Gazebo or any
other simulator.
"""
from __future__ import annotations

import ast
import copy
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from functools import partial
from pathlib import Path

from mhs import signals
from mhs.bridge import sim_host
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.bridge.sim_host import (ChildCallError, HostAfterEffect, HostBusy, HostFenced, HostTimeout,
                                 HostUnavailable, ProcessHost, ProcessProfile, ProcessProfileError)

HERE = Path(__file__).resolve().parent
STEP, RESET = "cap.world.step.v1", "cap.world.reset.v1"
PROFILE = {
    "mode": "isolated_process_v1", "reset_kwargs": ["seed", "options"],
    "start_timeout_s": 20.0, "step_timeout_s": 2.0, "reset_timeout_s": 2.0, "close_timeout_s": 3.0,
    "stop": "conn.pause", "readback": {"path": "conn.properties", "field": "paused", "equals": True},
    "stop_timeout_s": 1.0, "settle_timeout_s": 2.0, "source_refs": ["synthetic.py:1"],
}


def host(test, entry=".sim_host_fixture:make", profile=None, start=True, **options):
    created = ProcessHost(package_dir=HERE, entry=entry, options=options, profile=copy.deepcopy(profile or PROFILE),
                          label="test")
    test.addCleanup(created.close)
    if start:
        created.start()
    return created


def code(exc):
    return getattr(exc, "code", None)


def wait_for(predicate, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class ProfileTests(unittest.TestCase):
    def test_a_valid_profile_and_its_notes(self):
        profile = ProcessProfile.resolve(PROFILE)
        self.assertEqual((profile.stop, profile.readback_path, profile.readback_field), ("conn.pause",
                                                                                         "conn.properties", "paused"))
        self.assertTrue(profile.confirms(True))
        for value in (1, "True", None, [True], 1.0):
            self.assertFalse(profile.confirms(value), value)
        notes = " ".join(profile.notes())
        for text in ("isolated_process_v1", "conn.pause", "conn.properties().paused", "unreached"):
            self.assertIn(text, notes)

    def test_refused_declarations(self):
        bad = [
            {**PROFILE, "mode": "isolated_process"}, {**PROFILE, "extra": 1}, {**PROFILE, "reset_kwargs": ["render"]},
            {**PROFILE, "reset_kwargs": ["seed", "seed"]}, {**PROFILE, "step_timeout_s": 0},
            {**PROFILE, "step_timeout_s": True}, {**PROFILE, "close_timeout_s": float("inf")},
            {**PROFILE, "start_timeout_s": 0.01}, {**PROFILE, "stop": "conn.pause()"}, {**PROFILE, "stop": "_conn.x"},
            {**PROFILE, "stop": ""}, {**PROFILE, "readback": {"path": "conn.properties"}},
            {**PROFILE, "readback": {"path": "conn.properties", "equals": True, "other": 1}},
            {**PROFILE, "readback": {"path": "conn.pause", "equals": True}},
            {**PROFILE, "readback": {"path": "conn.properties", "field": "success", "equals": True}},
            {**PROFILE, "readback": {"path": "conn.properties", "field": "status_message", "equals": "ok"}},
            {**PROFILE, "readback": {"path": "conn.status", "equals": True}},
            {**PROFILE, "readback": {"path": "conn.properties", "field": "paused", "equals": 1.0}},
            {**PROFILE, "readback": {"path": "conn.properties", "field": "paused", "equals": None}},
            {**PROFILE, "readback": {"path": "conn.properties", "field": "paused", "equals": [True]}},
            {**PROFILE, "source_refs": "x.py:1"},
            {key: value for key, value in PROFILE.items() if key != "settle_timeout_s"},
            {key: value for key, value in PROFILE.items() if key != "stop"},
        ]
        for config in bad:
            with self.assertRaises(ProcessProfileError, msg=config):
                ProcessProfile.resolve(config)

    def test_the_entry_and_options_are_checked_before_any_process_starts(self):
        for entry in ("fixture:make", ".sim_host_fixture", "pkg.mod:make", ".a:b()"):
            with self.assertRaises(ProcessProfileError, msg=entry):
                ProcessHost(package_dir=HERE, entry=entry, profile=PROFILE)
        with self.assertRaises(ProcessProfileError):
            ProcessHost(package_dir=HERE, entry=".sim_host_fixture:make", options={"x": object()}, profile=PROFILE)
        with self.assertRaises(ProcessProfileError):
            ProcessHost(package_dir=HERE / "missing", entry=".sim_host_fixture:make", profile=PROFILE)

    def test_the_child_script_is_python_3_8_and_standard_library_only(self):
        source = sim_host.CHILD_SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=(3, 8))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertNotIn("mhs", imported)
        self.assertLessEqual(imported, set(sys.stdlib_module_names))


class HostTests(unittest.TestCase):
    def test_start_spaces_reset_and_step(self):
        created = host(self)
        action, observation = created.action_space, created.observation_space
        self.assertEqual((type(action).__name__, action.low, action.high, action.shape), ("Box", [-1.0, -1.0],
                                                                                         [1.0, 1.0], (2,)))
        self.assertEqual(observation.low, [float("-inf")] * 3)
        obs, info = created.reset(seed=3)
        self.assertEqual((obs, info["seed"]), ([0.0, 0.0, 0.0], 3))
        self.assertEqual(info["mhs_modules"], [])        # the host process never imports the SDK
        self.assertFalse(info["sdk_bridge_dir_importable"])   # nor sees the SDK modules next to its script
        obs, reward, terminated, truncated, info = created.step([1.0, -1.0])
        self.assertEqual(obs, [0.1, -0.1, 1.0])
        self.assertEqual(info, {"steps": 1, "object": "<object>"})   # info is sent lossily, never fails the step
        self.assertEqual(created.describe()["state"], "ready")
        self.assertEqual(created.close(), "settled")
        self.assertEqual(created.state()["state"], "closed")

    def test_a_wrapped_environment_is_stopped_on_unwrapped(self):
        created = host(self, entry=".sim_host_fixture:make_wrapped")
        created.step([0.5, 0.5])
        self.assertEqual(created.stop(), {"world_active": False})
        self.assertIs(created.readback(), True)

    def test_a_constructor_that_raises_fails_the_start_and_leaves_no_process(self):
        created = host(self, start=False, construct="raise")
        with self.assertRaisesRegex(HostUnavailable, "could not be built in the simulator host.*ValueError"):
            created.start()
        self.assertEqual(created.state()["state"], "failed")
        self.assertIsNotNone(created._proc.poll())
        with self.assertRaises(HostUnavailable):
            created.step([0.0, 0.0])

    def test_a_constructor_that_exits_is_contained(self):
        created = host(self, start=False, construct="exit")
        with self.assertRaisesRegex(HostUnavailable, "SystemExit"):
            created.start()
        self.assertEqual(created.state()["state"], "failed")

    def test_a_constructor_that_does_not_return_is_terminated_at_its_bound(self):
        created = host(self, start=False, profile={**PROFILE, "start_timeout_s": 0.5}, construct="hang")
        started = time.monotonic()
        with self.assertRaisesRegex(HostUnavailable, "did not start"):
            created.start()
        self.assertLess(time.monotonic() - started, 10.0)
        self.assertTrue(wait_for(lambda: created._proc.poll() is not None))

    def test_a_step_that_exits_is_contained_and_only_close_is_accepted_afterwards(self):
        created = host(self, step="exit")
        created.reset()
        with self.assertRaises(ChildCallError) as caught:
            created.step([0.0, 0.0])
        self.assertTrue(caught.exception.exit_requested)
        self.assertEqual(created.state()["exit_requested"], "SystemExit(4)")
        with self.assertRaisesRegex(HostUnavailable, "only close"):
            created.step([0.0, 0.0])
        self.assertEqual(created.stop(), {"world_active": False})   # the safety path still answers
        self.assertTrue(created.readback())
        self.assertEqual(created.close(), "settled")

    def test_a_step_that_ends_the_process_is_an_unknown_outcome_and_a_dead_host(self):
        created = host(self, step="die")
        created.reset()
        with self.assertRaises(HostUnavailable) as caught:
            created.step([0.0, 0.0])
        self.assertTrue(caught.exception.sent)
        self.assertTrue(wait_for(lambda: created.state()["state"] == "dead"))
        self.assertEqual(created.state()["exit_code"], 9)
        with self.assertRaises(HostUnavailable):
            created.stop()
        self.assertTrue(created.close().startswith("unsettled: the simulator host exited (status 9)"))

    def test_a_step_past_its_bound_stays_owned_until_it_answers(self):
        created = host(self, profile={**PROFILE, "step_timeout_s": 0.2}, step_delay=0.8)
        created.reset()
        with self.assertRaises(HostTimeout) as caught:
            created.step([0.0, 0.0])
        self.assertTrue(caught.exception.sent)
        owned = created.world_owned()
        self.assertEqual((owned["op"], owned["abandoned"]), ("step", True))
        with self.assertRaises(HostBusy):
            created.step([0.0, 0.0])
        self.assertTrue(created.wait_world_idle(3.0))
        self.assertEqual([(item["op"], item["outcome"]) for item in created.late], [("step", "returned")])
        self.assertIsNone(created.world_owned())

    def test_the_stop_fences_both_sides_and_unfence_lifts_both(self):
        created = host(self)
        created.reset()
        self.assertEqual(created.stop(), {"world_active": False})
        with self.assertRaises(HostFenced) as endpoint_side:
            created.step([0.0, 0.0])
        self.assertEqual(endpoint_side.exception.where, "endpoint")
        created._fenced = False                       # white box: the child refuses on its own as well
        with self.assertRaises(HostFenced) as host_side:
            created.step([0.0, 0.0])
        self.assertEqual(host_side.exception.where, "host")
        created.stop()
        created.unfence()
        self.assertEqual(created.step([0.0, 0.0])[0][2], 1.0)
        self.assertEqual(created.ping()["fenced"], False)

    def test_the_stop_reports_a_world_call_that_was_running(self):
        created = host(self, step_delay=0.5)
        created.reset()
        worker = threading.Thread(target=lambda: created.step([0.0, 0.0]), daemon=True)
        worker.start()
        self.assertTrue(wait_for(lambda: created.ping().get("world_active") is True, 3.0))
        self.assertEqual(created.stop(), {"world_active": True})
        self.assertTrue(created.wait_world_idle(3.0))
        worker.join(3.0)

    def test_readback_fields_and_values(self):
        created = host(self, profile={**PROFILE, "readback": {"path": "conn.dictionary", "field": "nested.paused",
                                                              "equals": True}})
        created.stop()
        self.assertIs(created.readback(), True)
        vector = host(self, profile={**PROFILE, "readback": {"path": "conn.vector", "field": "paused",
                                                             "equals": True}})
        with self.assertRaisesRegex(ChildCallError, "not a scalar"):
            vector.readback()

    def test_output_of_the_environment_never_reaches_the_protocol(self):
        created = host(self, loud=True)
        created.reset()
        for _ in range(3):
            self.assertEqual(len(created.step([0.0, 0.0])), 5)

    def test_a_result_that_cannot_be_sent_has_taken_effect(self):
        created = host(self, step="bad_result")
        created.reset()
        with self.assertRaises(HostAfterEffect):
            created.step([0.0, 0.0])

    def test_close_of_a_host_that_does_not_close_terminates_it(self):
        created = host(self, profile={**PROFILE, "close_timeout_s": 0.3}, close="hang")
        started = time.monotonic()
        outcome = created.close()
        self.assertLess(time.monotonic() - started, 10.0)
        self.assertTrue(outcome.startswith("unsettled:"), outcome)
        self.assertIn("terminated", outcome)
        self.assertIsNotNone(created._proc.poll())

    def test_close_contains_the_exit_of_env_close(self):
        self.assertEqual(host(self, close="exit").close(), "settled")

    def test_close_stops_the_world_before_it_closes_the_environment(self):
        log = Path(tempfile.mkdtemp(prefix="mhs-sim-host-log-"))
        self.addCleanup(shutil.rmtree, log, True)
        created = host(self, log=str(log / "events"), unpause_at_end=True)
        created.reset()
        created.step([0.0, 0.0])
        self.assertEqual(created.close(), "settled")
        self.assertEqual((log / "events").read_text().split()[-3:], ["pause", "readback", "close"])

    def test_close_without_a_confirmed_stop_is_unsettled(self):
        created = host(self, ignore_stop=True, unpause_at_end=True)
        created.reset()
        created.step([0.0, 0.0])
        outcome = created.close()
        self.assertTrue(outcome.startswith("unsettled:"), outcome)
        self.assertIn("not the stopped value", outcome)

    def test_the_host_output_never_reaches_the_endpoint_streams(self):
        script = ("import sys\n"
                  "from mhs.bridge.sim_host import ProcessHost\n"
                  f"host = ProcessHost(package_dir={str(HERE)!r}, entry='.sim_host_fixture:make', "
                  "options={'loud': True}, profile=" + repr(PROFILE) + ")\n"
                  "host.start(); host.reset(); host.step([0.0, 0.0]); host.close()\n"
                  "sys.stdout.write('DONE\\n')\n")
        done = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=60,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        self.assertEqual(done.stdout, b"DONE\n")
        self.assertNotIn(b"yyyy", done.stderr)

    def test_an_orphaned_host_stops_and_closes_the_environment_then_exits(self):
        log = Path(tempfile.mkdtemp(prefix="mhs-sim-host-log-"))
        self.addCleanup(shutil.rmtree, log, True)
        created = host(self, log=str(log / "events"))
        created.reset()
        created._close_write_end()                    # the endpoint is gone: no close was sent
        self.assertTrue(wait_for(lambda: created._proc.poll() is not None, 10.0))
        events = (log / "events").read_text().split()
        self.assertEqual(events[-2:], ["pause", "close"])

    def test_the_gate_guard_reaches_the_host_process(self):
        previous = os.environ.get(sim_host.GUARDED_ENV)
        os.environ[sim_host.GUARDED_ENV] = "1"
        try:
            created = host(self, start=False, construct="network")
            with self.assertRaisesRegex(HostUnavailable, "disabled"):
                created.start()
        finally:
            if previous is None:
                os.environ.pop(sim_host.GUARDED_ENV, None)
            else:
                os.environ[sim_host.GUARDED_ENV] = previous

    def test_guard_process_marks_the_process_and_its_hosts(self):
        # guard_process() (the gate's child processes) sets MHS_PROCESS_GUARDED; a host started there applies the
        # same guard before it imports package code.
        script = ("from mhs.driver._repotests import guard_process\n"
                  "guard_process()\n"
                  "from mhs.bridge.sim_host import ProcessHost, HostUnavailable\n"
                  f"host = ProcessHost(package_dir={str(HERE)!r}, entry='.sim_host_fixture:make', "
                  "options={'construct': 'network'}, profile=" + repr(PROFILE) + ")\n"
                  "try:\n    host.start()\nexcept HostUnavailable as exc:\n    print('refused:', exc)\n"
                  "else:\n    print('started')\n")
        env = {key: value for key, value in os.environ.items() if key != sim_host.GUARDED_ENV}
        done = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=60,
                              env=dict(env, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        self.assertIn(b"refused:", done.stdout)
        self.assertIn(b"disabled", done.stdout)

    def test_the_host_interpreter_is_selectable_and_must_be_absolute(self):
        previous = os.environ.get(sim_host.PYTHON_ENV)
        try:
            os.environ[sim_host.PYTHON_ENV] = "python3"
            with self.assertRaisesRegex(HostUnavailable, "absolute path"):
                host(self, start=False).start()
            other = shutil.which("python3", path="/usr/bin")
            if other is None:
                self.skipTest("no /usr/bin/python3 to run the host with another interpreter")
            os.environ[sim_host.PYTHON_ENV] = other
            created = host(self)
            self.assertEqual(created.reset()[0], [0.0, 0.0, 0.0])
            self.assertEqual(created.close(), "settled")
        finally:
            if previous is None:
                os.environ.pop(sim_host.PYTHON_ENV, None)
            else:
                os.environ[sim_host.PYTHON_ENV] = previous


# -- the Gymnasium bridge over a host ------------------------------------------------------------------------------
def bridge(test, profile=None, **options):
    created = host(test, profile=profile, start=False, **options)
    made = GymnasiumBridge(env=created, process=copy.deepcopy(profile or PROFILE), host=created,
                           device_id="sim/hosted")
    test.addCleanup(made.close)
    return made, created


class BridgeTests(unittest.TestCase):
    def test_capabilities_and_notes_name_the_host(self):
        made, _created = bridge(self)
        natives = {item["capability_id"]: item["native"] for item in made.capabilities()}
        self.assertIn("isolated simulator host", natives[STEP])
        self.assertEqual(made.estop_native, "conn.pause")
        self.assertIn("isolated_process_v1", " ".join(made.operating_notes()))
        self.assertEqual(made.reset_inputs(), ("seed", "options"))

    def test_the_bridge_refuses_a_host_of_another_profile_and_combinations(self):
        created = host(self, start=False)
        with self.assertRaises(Exception):
            GymnasiumBridge(env=created, process={**PROFILE, "stop_timeout_s": 0.5}, host=created)
        with self.assertRaises(Exception):
            GymnasiumBridge(env=created, process=PROFILE, host=None)
        with self.assertRaises(Exception):
            GymnasiumBridge(env=created, process=PROFILE, host=created,
                            asynchronous={"mode": "asyncio_owned_loop_v1", "step": "sync", "reset": "sync",
                                          "reset_kwargs": [], "step_timeout_s": 1, "reset_timeout_s": 1,
                                          "close_timeout_s": 1})

    def test_estop_stops_reads_back_and_reset_unfences(self):
        made, created = bridge(self)
        made.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.5]}})
        self.assertEqual(made.estop("test"), {"stop": "conn.pause", "readback": "conn.properties().paused",
                                              "confirmed": True})
        self.assertEqual(made.safety_status(), {})
        self.assertTrue(created.state()["fenced"])
        with self.assertRaises(Exception) as refused:
            made.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.5]}})
        self.assertEqual(code(refused.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(made.world_state()["tick"], 1)   # the refused call did not step
        made.reset()
        self.assertFalse(created.state()["fenced"])
        self.assertEqual(made.call(STEP, {"ticks": 1, "action": {"values": [0.5, 0.5]}})["tick"], 2)

    def test_a_stop_undone_by_the_step_in_flight_is_sent_again(self):
        # The step unpauses at its end, after the first stop: only the stop sent after it settled can confirm.
        made, created = bridge(self, step_delay=0.4, unpause_at_end=True)
        made.call(RESET, {})
        worker = threading.Thread(target=lambda: made.call(STEP, {"ticks": 1, "action": {"values": [0.1, 0.1]}}),
                                  daemon=True)
        worker.start()
        self.assertTrue(wait_for(lambda: created.ping().get("world_active") is True, 3.0))
        self.assertTrue(made.estop("during a step")["confirmed"])
        worker.join(3.0)
        self.assertIs(created.readback(), True)

    def test_a_readback_that_does_not_confirm_is_unknown_and_blocks_reset(self):
        made, _created = bridge(self, ignore_stop=True)
        made.call(RESET, {})
        with self.assertRaises(Exception) as caught:
            made.estop("ignored")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertIn("returned False, not True", str(caught.exception))
        self.assertEqual(made.safety_status(), {"safe_state": {"achieved": False}})
        with self.assertRaises(Exception) as refused:
            made.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")

    def test_failed_and_hung_stops_are_unknown(self):
        for options in ({"stop_error": True}, {"stop_exit": True}, {"stop_hang": 3.0}):
            made, _created = bridge(self, **options)
            made.call(RESET, {})
            started = time.monotonic()
            with self.assertRaises(Exception) as caught:
                made.estop("bad stop")
            self.assertLess(time.monotonic() - started, 2.5)
            self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN", options)
            self.assertEqual(made.safety_status(), {"safe_state": {"achieved": False}}, options)

    def test_a_dead_host_is_an_unreached_safe_state(self):
        made, created = bridge(self)
        made.call(RESET, {})
        os.kill(created.describe()["pid"], signal.SIGKILL)
        self.assertTrue(wait_for(lambda: created.state()["state"] == "dead"))
        self.assertEqual(made.safety_status(), {"safe_state": {"achieved": False}})
        with self.assertRaises(Exception) as caught:
            made.estop("dead")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        with self.assertRaises(Exception) as refused:
            made.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")

    def test_no_world_call_is_sent_after_the_estop(self):
        made, created = bridge(self)
        made.call(RESET, {})
        env = made._ensure_env()
        made._admitted.epoch, made._admitted.context = made.estop_epoch, None
        made._engage_estop()                           # an e-stop between admission and dispatch
        with self.assertRaises(signals.Cancelled):
            made._host_invoke("step", partial(env.step, [1.0, 1.0]))
        self.assertEqual(created.ping()["world_active"], False)
        self.assertEqual(created.step([0.0, 0.0])[0][2], 1.0)   # the refused step never ran: this is the first

    def test_a_step_past_its_bound_is_unknown_owned_and_needs_a_world_reset(self):
        made, created = bridge(self, profile={**PROFILE, "step_timeout_s": 0.2}, step_delay=0.6)
        made.call(RESET, {})
        with self.assertRaises(Exception) as caught:
            made.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0]}})
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(made.safety_status(), {"safe_state": {"achieved": False}})
        with self.assertRaises(Exception) as busy:
            made.call(RESET, {})
        self.assertEqual(code(busy.exception), "MHS.DEVICE.BUSY")
        with self.assertRaises(Exception) as refused:
            made.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.RESET_REFUSED")
        self.assertTrue(made.settle_native_work(3.0))
        with self.assertRaises(Exception) as precondition:
            made.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0]}})
        self.assertEqual(code(precondition.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        made.call(RESET, {})                           # an explicit world reset clears the fault: steps run again
        with self.assertRaises(Exception) as dispatched:
            made.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0]}})
        self.assertEqual(code(dispatched.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertTrue(made.settle_native_work(3.0))

    def test_an_exit_inside_a_step_is_a_fault_not_an_endpoint_exit(self):
        made, created = bridge(self, step="exit")
        made.call(RESET, {})
        with self.assertRaises(Exception) as caught:
            made.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0]}})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        self.assertIn("contained", str(caught.exception))
        self.assertTrue(made.estop("after the exit")["confirmed"])

    def test_an_unsettled_close_leaves_the_estop_unconfirmed(self):
        made, _created = bridge(self, ignore_stop=True, unpause_at_end=True)
        made.call(STEP, {"ticks": 1, "action": {"values": [0.0, 0.0]}})
        made.close()
        self.assertTrue(made.host_status()["close"].startswith("unsettled:"))
        with self.assertRaises(Exception) as caught:
            made.estop("after an unsettled close")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")

    def test_close_records_its_outcome(self):
        made, created = bridge(self, close="exit")
        made.call(RESET, {})
        made.close()
        self.assertEqual(made.host_status()["close"], "settled")
        self.assertEqual(made.estop("after close"), {})   # a settled close left nothing running
        self.assertIsNotNone(created._proc.poll())


if __name__ == "__main__":
    unittest.main()
