"""Coherence probes of the phase-3b composition (integrator-v4, claude-opus-5-5, a model; 2026-11-05).

p3-companion-2 (lock companions, the E1 stall read-back, the E4 list predicate) was composed onto the tree after phase
3, where p3-sensed-stop, p3-sdk-gaps-a and p3-sdk-gaps-b had changed the same functions. Each probe pins a place where
two of these changes meet, so that a later edit cannot quietly drop one side of a hand-resolved merge (MERGE-LOG.json
of development/integrator-v4):

* R-V4-03, R-V4-10 and R-V4-13, ``check._g6``: the gate hands ``BehaviourRun`` p3-sensed-stop's ``sensed`` sources,
  p3-companion-2's ``stall`` read-back, p3-companion-3's ``fresh`` topic read-back and p4-sim-host's ``hosted`` flag
  (one ``native_filter`` signature serves every filter; the last two were added when the four later inputs were
  composed, after the full SDK suite found the probe's stand-in context without ``family``);
* R-V4-02, ``BehaviourRun.run``: it runs SENSED_FAIL_OPEN when ``sensed`` is set and STALL_FAIL_OPEN when ``stall``
  is set, each on its own;
* R-V4-04, ``RosBridge._binding``: a compiled binding carries p3-sdk-gaps-b's ``then`` and p3-companion-2's
  ``stall``;
* R-V4-05, ``upstream``: p3-sdk-gaps-a's submodule surface and p3-companion-2's lock surface are both exported;
* R-V4-01, ``show_refs``: both p3-sdk-gaps-a's submodule reader and p3-companion-2's LOCK.json check are present.

A missing ``stall=`` is also caught by tests.driver.test_companion_stall_gate (a real G6 run); a missing ``sensed=``
leaves no finding on a passing package, so only the first probe below catches it.
"""

from __future__ import annotations

import importlib.util
import types
import unittest
from pathlib import Path
from unittest import mock

from mhs.bridge.ros import RecordingRosTransport, RosBridge
from mhs.driver import behaviour as behaviour_module
from mhs.driver import check as gate_check
from mhs.driver import upstream

SHOW_REFS = Path(__file__).resolve().parents[3] / "handoff" / "tools" / "show_refs.py"


class _Recorder:
    """Stands in for BehaviourRun: keeps the keyword arguments the gate passed and finds nothing."""

    seen: dict = {}

    def __init__(self, **kwargs):
        type(self).seen = kwargs
        self.findings = []

    def run(self):
        return []


class _Gate:
    def __init__(self):
        self.findings = []
        self.skipped = None

    def skip(self, reason):
        self.skipped = reason


def _context():
    model = types.SimpleNamespace(mode="simulated", device_id="coherence")
    return types.SimpleNamespace(g3_ok=True, endpoint=object(), model=model, hardware_endpoint=None, fixtures=None,
                                 example_overlay=None, records_native=True, prerequisites=None)


class G6HandsBothSources(unittest.TestCase):
    def test_the_gate_passes_sensed_and_stall_to_the_behaviour_run(self):
        sensed = {"/pose": ("header.stamp", 2, "pose.position.z")}
        stall = ("/get_model_list", "header.stamp")
        fresh = ("/world/w/stats", "paused", True)
        with mock.patch.object(behaviour_module, "BehaviourRun", _Recorder), \
                mock.patch.object(gate_check, "_sensed_sources", lambda ctx: sensed), \
                mock.patch.object(gate_check, "_stall_source", lambda ctx: stall), \
                mock.patch.object(gate_check, "_fresh_source", lambda ctx: fresh), \
                mock.patch.object(gate_check, "_hosted_api", lambda ctx: frozenset({"step"})):
            gate = _Gate()
            gate_check._g6(_context(), gate)
        self.assertIsNone(gate.skipped)
        self.assertIs(_Recorder.seen.get("sensed"), sensed)
        self.assertIs(_Recorder.seen.get("stall"), stall)
        # R-V4-10 and R-V4-13 (integrator v4, the four later inputs): the fresh read-back and the hosted flag too
        self.assertIs(_Recorder.seen.get("fresh"), fresh)
        self.assertIs(_Recorder.seen.get("hosted"), True)

    def test_the_stall_source_reads_only_a_ros_stall_read_back(self):
        readback = {"service": "/get_model_list", "type": "gazebo_msgs/srv/GetModelList",
                    "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 250, "unchanged": True}}
        cls = types.SimpleNamespace(safety_bindings={"safe_state": readback})
        ros = types.SimpleNamespace(family="ros", cls=cls)
        self.assertEqual(gate_check._stall_source(ros), ("/get_model_list", "header.stamp"))
        self.assertIsNone(gate_check._stall_source(types.SimpleNamespace(family="http", cls=cls)))
        plain = types.SimpleNamespace(safety_bindings={"safe_state": {"service": "/x", "type": "a/srv/B"}})
        self.assertIsNone(gate_check._stall_source(types.SimpleNamespace(family="ros", cls=plain)))

    def test_no_sensed_sources_without_a_declared_confirmation(self):
        ctx = types.SimpleNamespace(model=types.SimpleNamespace(estop_confirmation=None), cls=None)
        self.assertIsNone(gate_check._sensed_sources(ctx))


class BehaviourRunsEachFilterCheck(unittest.TestCase):
    def run_with(self, **fields):
        calls = []
        run = behaviour_module.BehaviourRun(endpoint=lambda **_options: None, model=None, hardware_view=None,
                                            recorded=False, **fields)
        with mock.patch.object(run, "_with", lambda fn, **_options: ({}, {})), \
                mock.patch.object(run, "_reads", lambda bindings: None), \
                mock.patch.object(run, "_estop", lambda *args: None), \
                mock.patch.object(run, "_sensed_fail_open", lambda: calls.append("sensed")), \
                mock.patch.object(run, "_stall_fail_open", lambda: calls.append("stall")):
            run.run()
        return calls

    def test_each_check_runs_when_its_source_is_set(self):
        self.assertEqual(self.run_with(), [])
        self.assertEqual(self.run_with(sensed={"/pose": ("header.stamp", 2, "z")}), ["sensed"])
        self.assertEqual(self.run_with(stall=("/get_model_list", "header.stamp")), ["stall"])
        self.assertEqual(self.run_with(sensed={"/pose": ("header.stamp", 2, "z")},
                                       stall=("/get_model_list", "header.stamp")), ["sensed", "stall"])

    def test_both_filters_are_exported(self):
        self.assertIn("SensedFilter", behaviour_module.__all__)
        self.assertIn("StallFilter", behaviour_module.__all__)
        for name in behaviour_module.__all__:
            self.assertTrue(hasattr(behaviour_module, name), name)


class BindingCarriesThenAndStall(unittest.TestCase):
    def test_a_compiled_binding_keeps_then_and_stall(self):
        pause = {"service": "/pause_physics", "type": "std_srvs/srv/Empty", "request": {},
                 "success": {"path": "$", "equals": {}}, "timeout_ms": 400}
        readback = {"service": "/get_model_list", "type": "gazebo_msgs/srv/GetModelList", "request": {},
                    "success": {"path": "success", "equals": True}, "timeout_ms": 300,
                    "stall": {"path": "header.stamp", "samples": 2, "interval_ms": 150, "unchanged": True}}
        drive = {"topic": "/cmd_vel", "type": "geometry_msgs/msg/Twist",
                 "then": {"step": {"service": "/step", "type": "std_srvs/srv/Empty", "request": {},
                                   "success": {"path": "$", "equals": {}}}}}
        bridge = RosBridge({"commands": {"x-cap.test.drive.v1": drive},
                            "safety_bindings": {"estop": pause, "safe_state": readback}},
                           transport=RecordingRosTransport(handler=lambda message: None))
        self.addCleanup(bridge.close)
        compiled = bridge._safety["safe_state"]
        self.assertEqual(compiled["stall"], {"path": "header.stamp", "samples": 2, "interval_ms": 150.0,
                                             "unchanged": True})
        self.assertIn("then", compiled)
        self.assertIn('"stall"', bridge._stop_request_identity(compiled))
        command = bridge._commands["x-cap.test.drive.v1"]
        self.assertIsNotNone(command["then"])
        self.assertIsNone(command["stall"])


class UpstreamExportsBothSurfaces(unittest.TestCase):
    def test_submodule_and_lock_surfaces(self):
        for name in ("Submodule", "COMPANION_LOCK_ALIAS", "COMPANION_LOCK_FILE", "lock_entry_problems",
                     "lock_package_id", "read_companion_lock"):
            self.assertIn(name, upstream.__all__)
        for name in upstream.__all__:
            self.assertTrue(hasattr(upstream, name), name)


class ShowRefsHasBothReaders(unittest.TestCase):
    def test_submodule_reader_and_lock_check(self):
        spec = importlib.util.spec_from_file_location("phase3b_coherence_show_refs", SHOW_REFS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ("show_submodule", "submodule_paths", "pinned_tree", "lock_entry", "writable_entries"):
            self.assertTrue(callable(getattr(module, name, None)), name)
        self.assertIn("git submodule", module.__doc__)
        self.assertIn("LOCK.json", module.__doc__)


if __name__ == "__main__":
    unittest.main()
