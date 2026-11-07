"""E4 (companion preflight 2, 2026-11-05): a success predicate may select one element of a list by the values of its
fields, as ``controller_manager``'s ``list_controllers`` answer needs (``controller[]`` in load order, each with a
``name`` and a ``state``): ``{path, where, field, equals}``. Exactly one element must match ``where``; its ``field``
must equal ``equals``. None, several, a value that is not a list or a missing field fail, at both bridge sites (a
service answer and an action result) and as the read-back of a stop.
"""
from __future__ import annotations

import copy
import unittest

from mhs.bridge.ros import RosBridge, RecordingRosTransport, _passes
from mhs.errors import MHSError
from mhs import signals

LIST = {"path": "controller", "where": {"name": "joint_trajectory_controller"}, "field": "state",
        "equals": "inactive"}
SWITCH = {"service": "/controller_manager/switch_controller", "type": "controller_manager_msgs/srv/SwitchController",
          "request": {"deactivate_controllers": ["joint_trajectory_controller"], "strictness": 2},
          "success": {"path": "ok", "equals": True}, "timeout_ms": 600}
READBACK = {"service": "/controller_manager/list_controllers", "type": "controller_manager_msgs/srv/ListControllers",
            "request": {}, "success": LIST, "timeout_ms": 400}


def controllers(*states):
    names = ("joint_state_broadcaster", "joint_trajectory_controller", "gripper_controller")
    return {"controller": [{"name": name, "state": state, "type": "x"} for name, state in zip(names, states)]}


class PredicateTests(unittest.TestCase):
    def test_exactly_one_selected_element_is_compared(self) -> None:
        self.assertTrue(_passes(controllers("active", "inactive", "active"), LIST))
        self.assertFalse(_passes(controllers("active", "active", "inactive"), LIST))
        reordered = {"controller": list(reversed(controllers("active", "inactive", "active")["controller"]))}
        self.assertTrue(_passes(reordered, LIST))

    def test_none_several_wrong_type_and_missing_field_fail(self) -> None:
        none = {"controller": [{"name": "other", "state": "inactive"}]}
        twice = {"controller": [{"name": "joint_trajectory_controller", "state": "inactive"}] * 2}
        not_list = {"controller": {"name": "joint_trajectory_controller", "state": "inactive"}}
        no_field = {"controller": [{"name": "joint_trajectory_controller"}]}
        not_objects = {"controller": ["joint_trajectory_controller"]}
        for name, values in (("none", none), ("several", twice), ("not a list", not_list), ("no field", no_field),
                             ("not objects", not_objects), ("no path", {})):
            with self.subTest(name=name):
                self.assertFalse(_passes(values, LIST))
        typed = dict(LIST, where={"id": 1})
        self.assertFalse(_passes({"controller": [{"id": True, "state": "inactive"}]}, typed))  # True is not 1
        self.assertTrue(_passes({"controller": [{"id": 1, "state": "inactive"}]}, typed))
        nested = dict(LIST, field="status.state")
        self.assertTrue(_passes({"controller": [{"name": "joint_trajectory_controller",
                                                 "status": {"state": "inactive"}}]}, nested))

    def test_the_plain_predicate_is_unchanged(self) -> None:
        self.assertTrue(_passes({"ok": True}, {"path": "ok", "equals": True}))
        self.assertFalse(_passes({"ok": 1}, {"path": "ok", "equals": True}))
        self.assertFalse(_passes({}, {"path": "ok", "equals": True}))


class BridgeSiteTests(unittest.TestCase):
    def make(self, config, handler):
        bridge = RosBridge(config, transport=RecordingRosTransport(handler=handler))
        self.addCleanup(bridge.close)
        return bridge

    def test_a_controller_switch_confirmed_by_its_list_read_back(self) -> None:
        state = {"jtc": "active"}

        def handler(message):
            if message.get("op") != "call_service":
                return None
            if message["service"] == SWITCH["service"]:
                state["jtc"] = "inactive"
                values = {"ok": True}
            else:
                values = controllers("active", state["jtc"], "active")
            return {"op": "service_response", "service": message["service"], "result": True, "values": values}

        bridge = self.make({"safety_bindings": {"estop": SWITCH, "safe_state": READBACK}}, handler)
        self.assertTrue(bridge.estop("test")["safe_state_achieved"])
        state["jtc"] = "active"  # another client re-activated it
        with self.assertRaises(MHSError) as raised:
            bridge.safe_state()
        self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_read_that_lists_the_controller_twice_never_confirms(self) -> None:
        def handler(message):
            if message.get("op") != "call_service":
                return None
            values = ({"ok": True} if message["service"] == SWITCH["service"] else
                      {"controller": [{"name": "joint_trajectory_controller", "state": "inactive"}] * 2})
            return {"op": "service_response", "service": message["service"], "result": True, "values": values}

        bridge = self.make({"safety_bindings": {"estop": SWITCH, "safe_state": READBACK}}, handler)
        with self.assertRaises(MHSError):
            bridge.estop("test")

    def test_a_command_service_answer_uses_the_list_predicate(self) -> None:
        answers = [controllers("active", "inactive", "active"), controllers("active", "active", "active")]

        def handler(message):
            if message.get("op") != "call_service":
                return None
            return {"op": "service_response", "service": message["service"], "result": True,
                    "values": answers.pop(0)}

        command = {"service": "/controller_manager/list_controllers",
                   "type": "controller_manager_msgs/srv/ListControllers", "request": {}, "success": LIST}
        bridge = self.make({"commands": {"x-cap.a.check.v1": command}}, handler)
        bridge.call("x-cap.a.check.v1", {})
        with self.assertRaises(signals.DriverFailed):
            bridge.call("x-cap.a.check.v1", {})


BOTH = {"path": "controller",
        "where": [{"name": "joint_trajectory_controller"}, {"name": "gripper_controller"}],
        "field": "state", "equals": "inactive"}
BOTH_READBACK = dict(READBACK, success=BOTH)
BOTH_SWITCH = {"service": "/controller_manager/switch_controller",
               "type": "controller_manager_msgs/srv/SwitchController",
               "request": {"deactivate_controllers": ["joint_trajectory_controller", "gripper_controller"],
                           "strictness": 2},
               "success": {"path": "ok", "equals": True}, "timeout_ms": 600}


class SeveralElementsTests(unittest.TestCase):
    def test_every_named_element_must_hold_the_value(self) -> None:
        self.assertTrue(_passes(controllers("active", "inactive", "inactive"), BOTH))
        reordered = {"controller": list(reversed(controllers("active", "inactive", "inactive")["controller"]))}
        self.assertTrue(_passes(reordered, BOTH))
        self.assertFalse(_passes(controllers("active", "inactive", "active"), BOTH))
        self.assertFalse(_passes(controllers("active", "active", "inactive"), BOTH))

    def test_selectors_must_match_distinct_elements(self) -> None:
        same = dict(BOTH, where=[{"name": "joint_trajectory_controller"}, {"name": "joint_trajectory_controller"}])
        self.assertFalse(_passes(controllers("active", "inactive", "inactive"), same))
        overlap = dict(BOTH, where=[{"name": "joint_trajectory_controller"},
                                    {"type": "x", "name": "joint_trajectory_controller"}])
        # the second selector also matches only the trajectory controller
        self.assertFalse(_passes(controllers("active", "inactive", "inactive"), overlap))

    def test_two_response_elements_for_one_selector_fail_closed(self) -> None:
        # A mutant that accepts the first match (len(chosen) != 1 changed to not chosen) returns true here.
        conflict = {"controller": [
            {"name": "joint_trajectory_controller", "state": "inactive", "type": "x"},
            {"name": "joint_trajectory_controller", "state": "active", "type": "x"},
            {"name": "gripper_controller", "state": "inactive", "type": "x"},
        ]}
        self.assertFalse(_passes(conflict, BOTH))
        same_state = {"controller": [
            {"name": "joint_trajectory_controller", "state": "inactive", "type": "x"},
            {"name": "joint_trajectory_controller", "state": "inactive", "type": "x"},
            {"name": "gripper_controller", "state": "inactive", "type": "x"},
        ]}
        self.assertFalse(_passes(same_state, BOTH))
        gripper_conflict = {"controller": [
            {"name": "joint_trajectory_controller", "state": "inactive", "type": "x"},
            {"name": "gripper_controller", "state": "inactive", "type": "x"},
            {"name": "gripper_controller", "state": "active", "type": "x"},
        ]}
        self.assertFalse(_passes(gripper_conflict, BOTH))

    def test_a_missing_element_or_a_non_list_fails(self) -> None:
        self.assertFalse(_passes({"controller": [{"name": "joint_trajectory_controller", "state": "inactive"}]}, BOTH))
        self.assertFalse(_passes({"controller": {"name": "joint_trajectory_controller", "state": "inactive"}}, BOTH))
        self.assertFalse(_passes({}, BOTH))
        typed = dict(BOTH, where=[{"id": 1}, {"id": 2}])
        self.assertFalse(_passes({"controller": [{"id": True, "state": "inactive"},
                                                 {"id": 2, "state": "inactive"}]}, typed))
        self.assertTrue(_passes({"controller": [{"id": 1, "state": "inactive"},
                                                {"id": 2, "state": "inactive"}]}, typed))

    def test_an_empty_selector_list_fails_closed(self) -> None:
        self.assertFalse(_passes(controllers("active", "inactive", "inactive"), dict(BOTH, where=[])))

    def test_three_selectors_and_a_nested_field(self) -> None:
        three = dict(BOTH, where=[{"name": "joint_state_broadcaster"}, {"name": "joint_trajectory_controller"},
                                  {"name": "gripper_controller"}])
        self.assertTrue(_passes(controllers("inactive", "inactive", "inactive"), three))
        nested = dict(BOTH, field="status.state")
        values = {"controller": [{"name": "joint_trajectory_controller", "status": {"state": "inactive"}},
                                 {"name": "gripper_controller", "status": {"state": "inactive"}}]}
        self.assertTrue(_passes(values, nested))
        values["controller"][1]["status"]["state"] = "active"
        self.assertFalse(_passes(values, nested))


class SeveralBridgeTests(unittest.TestCase):
    def make(self, config, handler):
        bridge = RosBridge(config, transport=RecordingRosTransport(handler=handler))
        self.addCleanup(bridge.close)
        return bridge

    def test_one_switch_confirmed_only_when_both_are_inactive(self) -> None:
        state = {"arm": "active", "gripper": "active"}

        def handler(message):
            if message.get("op") != "call_service":
                return None
            if message["service"] == BOTH_SWITCH["service"]:
                names = (message.get("args") or {}).get("deactivate_controllers") or []
                if "joint_trajectory_controller" in names:
                    state["arm"] = "inactive"
                if "gripper_controller" in names:
                    state["gripper"] = "inactive"
                values = {"ok": True}
            else:
                values = controllers("active", state["arm"], state["gripper"])
            return {"op": "service_response", "service": message["service"], "result": True, "values": values}

        bridge = self.make({"safety_bindings": {"estop": BOTH_SWITCH, "safe_state": BOTH_READBACK}}, handler)
        self.assertTrue(bridge.estop("test")["safe_state_achieved"])
        state["gripper"] = "active"
        with self.assertRaises(MHSError) as raised:
            bridge.safe_state()
        self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_one_of_two_still_active_never_confirms(self) -> None:
        def handler(message):
            if message.get("op") != "call_service":
                return None
            values = ({"ok": True} if message["service"] == BOTH_SWITCH["service"]
                      else controllers("active", "inactive", "active"))
            return {"op": "service_response", "service": message["service"], "result": True, "values": values}

        bridge = self.make({"safety_bindings": {"estop": BOTH_SWITCH, "safe_state": BOTH_READBACK}}, handler)
        with self.assertRaises(MHSError):
            bridge.estop("test")

    def test_duplicate_matching_elements_never_confirm(self) -> None:
        def handler(message):
            if message.get("op") != "call_service":
                return None
            values = ({"ok": True} if message["service"] == BOTH_SWITCH["service"] else
                      {"controller": [
                          {"name": "joint_trajectory_controller", "state": "inactive"},
                          {"name": "joint_trajectory_controller", "state": "active"},
                          {"name": "gripper_controller", "state": "inactive"},
                      ]})
            return {"op": "service_response", "service": message["service"], "result": True, "values": values}

        bridge = self.make({"safety_bindings": {"estop": BOTH_SWITCH, "safe_state": BOTH_READBACK}}, handler)
        with self.assertRaises(MHSError) as raised:
            bridge.estop("test")
        self.assertEqual(raised.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")


class SeveralValidationTests(unittest.TestCase):
    def refused(self, success) -> None:
        with self.assertRaises(MHSError) as raised:
            RosBridge({"safety_bindings": {"estop": SWITCH, "safe_state": dict(READBACK, success=success)}},
                      transport=RecordingRosTransport(handler=lambda message: None))
        self.assertEqual(raised.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")

    def test_malformed_selector_lists_are_refused(self) -> None:
        one = dict(BOTH, where=[{"name": "joint_trajectory_controller"}])
        five = dict(BOTH, where=[{"name": f"c{n}"} for n in range(5)])
        empty = dict(BOTH, where=[])
        blank = dict(BOTH, where=[{"name": "joint_trajectory_controller"}, {}])
        nested = dict(BOTH, where=[{"name": "arm_controller"}, {"name": ["gripper"]}])
        dotted = dict(BOTH, where=[{"name": "arm_controller"}, {"a.b": 1}])
        duplicate = dict(BOTH, where=[{"name": "arm_controller"}, {"name": "arm_controller"}])
        null = dict(BOTH, where=[{"name": "arm_controller"}, {"name": None}])
        for name, bad in (("one selector", one), ("five selectors", five), ("empty list", empty),
                          ("empty selector", blank), ("list value", nested), ("dotted key", dotted),
                          ("duplicate selectors", duplicate), ("null value", null)):
            with self.subTest(name=name):
                self.refused(bad)

    def test_a_well_formed_selector_list_is_kept_as_declared(self) -> None:
        bridge = RosBridge({"safety_bindings": {"estop": SWITCH, "safe_state": copy.deepcopy(BOTH_READBACK)}},
                           transport=RecordingRosTransport(handler=lambda message: None))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge._safety["safe_state"]["success"], BOTH)


class ValidationTests(unittest.TestCase):
    def refused(self, success) -> None:
        with self.assertRaises(MHSError) as raised:
            RosBridge({"safety_bindings": {"estop": SWITCH, "safe_state": dict(READBACK, success=success)}},
                      transport=RecordingRosTransport(handler=lambda message: None))
        self.assertEqual(raised.exception.code, "MHS.ADAPTER.MANIFEST_INVALID")

    def test_malformed_list_predicates_are_refused(self) -> None:
        for name, bad in (("no field", {k: v for k, v in LIST.items() if k != "field"}),
                          ("extra key", dict(LIST, index=1)), ("empty where", dict(LIST, where={})),
                          ("five where keys", dict(LIST, where={f"k{n}": n for n in range(5)})),
                          ("object value", dict(LIST, where={"name": {"x": 1}})),
                          ("list value", dict(LIST, where={"name": ["a"]})), ("null value", dict(LIST, where={"name": None})),
                          ("dotted key", dict(LIST, where={"a.b": 1})), ("field $", dict(LIST, field="$")),
                          ("field not a path", dict(LIST, field="a..b")), ("where not an object", dict(LIST, where=[1]))):
            with self.subTest(name=name):
                self.refused(bad)

    def test_a_well_formed_list_predicate_is_kept_as_declared(self) -> None:
        bridge = RosBridge({"safety_bindings": {"estop": SWITCH, "safe_state": copy.deepcopy(READBACK)}},
                           transport=RecordingRosTransport(handler=lambda message: None))
        self.addCleanup(bridge.close)
        self.assertEqual(bridge._safety["safe_state"]["success"], LIST)


if __name__ == "__main__":
    unittest.main()
