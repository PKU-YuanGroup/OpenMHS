"""TagDriver (registry family tag-bridge): compiler, codecs, bridge safety semantics, admission and gate checks.

The three fixtures under tests/fixtures/tag_* are synthetic packages with original vendor text; no upstream
code, vendor library, device or network is used.
"""
import contextlib
import copy
import importlib
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mhs.adapter import LoadError, load_driver
from mhs.bridge.tag_fake import request_key
from mhs.bridge.tags import TagBridge
from mhs.driver import Action, DriverDefinitionError, Field, Limit, TagDriver
from mhs.driver.check import Gate, run_check
from mhs.driver.loader import import_driver_module
from mhs.bridge.base import BridgeContext
from mhs.driver.tag_check import address_findings, check_tag_surface
from mhs.driver.tag_config import compile_tags, decode, encode, plain
from mhs.testing import Recorder, log_of
from tests.driver import support

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MODBUS, EPICS, ALPACA = (FIXTURES / name for name in ("tag_modbus", "tag_epics", "tag_alpaca"))
modbus, epics, alpaca = (import_driver_module(path) for path in (MODBUS, EPICS, ALPACA))
fakes = {name: importlib.import_module(module.__package__ + ".fake") for name, module in
         (("modbus", modbus), ("epics", epics), ("alpaca", alpaca))}
GATES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]


def code(exc):
    return getattr(exc, "code", None)


def compiled(module, **changes):
    cls = module.Driver
    raw = copy.deepcopy(dict(cls.tag_config))
    raw.update(changes)
    return compile_tags(raw, reads=cls.reads, writes=cls.writes, commands=cls.commands,
                        safety_bindings=cls.safety_bindings)


def key(request):
    return request_key(request)


class CompilerTests(unittest.TestCase):
    def test_each_profile_compiles_to_a_detached_json_config(self):
        for module in (modbus, epics, alpaca):
            raw = copy.deepcopy(dict(module.Driver.tag_config))
            config = compile_tags(raw, reads=module.Driver.reads, writes=module.Driver.writes,
                                  commands=module.Driver.commands, safety_bindings=module.Driver.safety_bindings)
            first = next(iter(raw["points"].values()))
            first["source_ref"] = "elsewhere.py:1"
            self.assertNotEqual(next(iter(config["points"].values()))["source_ref"], "elsewhere.py:1")
            self.assertEqual(json.loads(json.dumps(config)), config)
            self.assertIsNotNone(config["estop"])

    def test_unsupported_profiles_are_refused_by_name(self):
        for profile in ("opcua", "OPC-UA", "tango", "ads", "s7", "discover"):
            with self.subTest(profile=profile), self.assertRaises(DriverDefinitionError):
                compiled(modbus, profile=profile)

    def test_modbus_point_grammar(self):
        base = {"access": "read", "source_ref": "a.py:1"}
        bad = [
            {"table": "register", "register": 1, "type": "uint16"},
            {"table": "holding", "register": 70000, "type": "uint16"},
            {"table": "holding", "register": 1, "type": "uint32"},                       # no word_order
            {"table": "holding", "register": 1, "type": "uint16", "words": 2},
            {"table": "holding", "register": 65535, "type": "int32", "word_order": "big"},
            {"table": "holding", "register": 1, "type": "float32", "word_order": "big", "decimals": 1},
            {"table": "coil", "register": 1, "type": "uint16"},
            {"table": "holding", "register": 1, "type": "uint16", "decimals": 7},
            {"table": "holding", "register": 1, "type": "uint16", "word_order": "big"},
            dict(table="input", register=1, type="uint16", access="write"),
            dict(table="holding", register=1, type="uint32", word_order="big", access="read-write"),
            {"table": "holding", "register": 1, "type": "uint16", "unexpected": True},
        ]
        for spec in bad:
            point = dict(base, **spec)
            with self.subTest(point=point), self.assertRaises(DriverDefinitionError):
                compile_tags({"profile": "modbus", "points": {"p": point}})

    def test_epics_and_alpaca_point_grammar(self):
        for profile, point in [
            ("epics-ca", {"pv": "bad pv", "type": "integer", "access": "read", "source_ref": "a.py:1"}),
            ("epics-ca", {"pv": "state", "type": "boolean", "access": "read", "source_ref": "a.py:1"}),
            ("alpaca", {"member": "Azimuth", "type": "number", "access": "read", "source_ref": "a.py:1"}),
            ("alpaca", {"member": "slewing", "type": "boolean", "access": "read-write", "source_ref": "a.py:1"}),
            ("alpaca", {"member": "park", "method": True, "access": "read", "source_ref": "a.py:1"}),
            ("alpaca", {"member": "park", "method": True, "params": {"lower": "number"}, "source_ref": "a.py:1"}),
        ]:
            raw = {"profile": profile, "points": {"p": point}}
            if profile == "alpaca":
                raw.update(device_type="dome", device_number=0, device_type_ref="a.py:2")
            with self.subTest(profile=profile, point=point), self.assertRaises(DriverDefinitionError):
                compile_tags(raw)
        with self.assertRaises(DriverDefinitionError):
            compile_tags({"profile": "alpaca", "points": {"p": {"member": "azimuth", "type": "number",
                                                                  "access": "read", "source_ref": "a.py:1"}}})
        with self.assertRaises(DriverDefinitionError):
            compile_tags({"profile": "modbus", "device_type": "dome", "points": {"p": {
                "table": "holding", "register": 1, "type": "uint16", "access": "read", "source_ref": "a.py:1"}}})

    def test_duplicate_addresses_and_source_references(self):
        point = {"table": "holding", "register": 1, "type": "uint16", "access": "read", "source_ref": "a.py:1"}
        with self.assertRaises(DriverDefinitionError):
            compile_tags({"profile": "modbus", "points": {"a": point, "b": dict(point)}})
        for ref in ("/abs/a.py:1", "../a.py:1", "a.py", "a.py:1-100", "a.py:9-1"):
            with self.subTest(ref=ref), self.assertRaises(DriverDefinitionError):
                compile_tags({"profile": "modbus", "points": {"a": dict(point, source_ref=ref)}})

    def test_steps_confirmation_and_stop_grammar(self):
        cls = modbus.Driver
        cases = [
            ({"x-cap.a.b.v1": {"steps": [{"write": "door", "value": True}]}}, {}),            # read-only point
            ({"x-cap.a.b.v1": {"steps": [{"write": "setpoint", "value": 21.55}]}}, {}),       # between steps
            ({"x-cap.a.b.v1": {"steps": [{"write": "setpoint", "value": 1, "input": "x"}]}}, {}),
            ({"x-cap.a.b.v1": {"steps": []}}, {}),
            ({"x-cap.a.b.v1": {"steps": [{"write": "heater", "value": True}] * 9}}, {}),
            ({"x-cap.a.b.v1": {"steps": [{"invoke": "heater"}]}}, {}),
            ({"x-cap.a.b.v1": {"steps": [{"write": "heater", "value": True}],
                               "confirm": [{"point": "flow", "equals": 1.5}]}}, {}),    # float confirmation
            ({"x-cap.a.b.v1": {"read": {"t": "setpoint"}}}, {}),                           # write-only read
            ({}, {"estop": {"steps": [{"write": "setpoint", "input": "x"}], "confirm": [{"point": "heater", "equals": False}]}}),
            ({}, {"estop": {"steps": [{"write": "heater", "value": False}], "confirm": []}}),
            ({}, {"estop": {"steps": [{"write": "heater", "value": False}]}}),
            ({}, {"interlocks": []}),
            ({}, {"reset": {"steps": []}}),
        ]
        for commands, safety in cases:
            with self.subTest(commands=commands, safety=safety), self.assertRaises(DriverDefinitionError):
                compile_tags(cls.tag_config, reads=cls.reads, writes=cls.writes, commands=commands,
                             safety_bindings=safety)

    def test_request_and_confirmation_bounds(self):
        for key_, low, high in (("timeout_ms", 1, 10000), ("confirm_ms", 0, 1500), ("poll_ms", 10, 500)):
            self.assertEqual(compiled(modbus, **{key_: high})[key_], high)
            self.assertEqual(compiled(modbus, **{key_: low})[key_], low)
            for bad in (low - 1, high + 1, True, 1.5):
                with self.subTest(key=key_, value=bad), self.assertRaises(DriverDefinitionError):
                    compiled(modbus, **{key_: bad})

    def test_only_concrete_bounded_json_is_accepted(self):
        class Text(str):
            pass

        cycle = []
        cycle.append(cycle)
        for value in (Text("x"), {"x": float("nan")}, {"x": object()}, cycle, {1: "x"}, ["x"] * 257):
            with self.subTest(kind=type(value).__name__), self.assertRaises(DriverDefinitionError):
                plain(value)


class CodecTests(unittest.TestCase):
    def point(self, **spec):
        base = {"access": "read-write", "source_ref": "a.py:1", "table": "holding", "register": 1}
        base.update(spec)
        if spec.get("type") in ("uint32", "int32", "float32"):
            base.setdefault("word_order", "big")
            base["access"] = "read"
        return compile_tags({"profile": "modbus", "points": {"p": base}})["points"]["p"]

    def test_scaled_registers_round_trip_and_refuse_values_between_steps(self):
        point = self.point(type="uint16", decimals=2)
        self.assertEqual(encode(point, 3.3), [330])
        self.assertEqual(encode(point, 0.3), [30])
        self.assertEqual(encode(point, 655.35), [65535])
        self.assertEqual(encode(point, 5), [500])
        self.assertEqual(decode(point, [330]), 3.3)
        # Exact or refused: no tolerance, so no value is rounded across an operator limit.
        for value in (3.305, 3.30000001, 3.3000000001, 3.2999999999, 0.1 + 0.2, -0.01, 655.36, True,
                      float("inf"), float("nan"), "3", 10 ** 400, -(10 ** 400)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encode(point, value)
        signed = self.point(type="int16", decimals=1)
        self.assertEqual(encode(signed, -20.0), [0xFF38])
        self.assertEqual(decode(signed, [0xFF38]), -20.0)

    def test_two_word_codecs_and_word_order(self):
        big = self.point(type="uint32")
        self.assertEqual(decode(big, [0x0001, 0x0002]), 65538)
        little = self.point(type="int32", word_order="little")
        self.assertEqual(decode(little, [0xFFFF, 0xFFFF]), -1)
        flt = self.point(type="float32", word_order="little")
        self.assertEqual(decode(flt, [0x0000, 0x3FC0]), 1.5)
        self.assertEqual(encode(flt, 1.5), [0x0000, 0x3FC0])
        with self.assertRaises(ValueError):
            encode(flt, 0.1)        # not exactly representable as float32
        for raw in ([1], [1, 70000], [1, True], (1, 2), [0x7FC0, 0x0000]):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                decode(self.point(type="float32"), raw)

    def test_boolean_registers_and_bits_are_strict(self):
        flag = self.point(type="bool")
        self.assertEqual(decode(flag, [1]), True)
        with self.assertRaises(ValueError):
            decode(flag, [2])
        coil = compile_tags({"profile": "modbus", "points": {"c": {"table": "coil", "register": 0, "type": "bool",
                                                                     "access": "read-write",
                                                                     "source_ref": "a.py:1"}}})["points"]["c"]
        self.assertIs(encode(coil, True), True)
        self.assertIs(decode(coil, [False]), False)
        with self.assertRaises(ValueError):
            decode(coil, [0])

    def test_huge_integers_are_invalid_values_not_overflow_errors(self):
        for point in (self.point(type="uint16"), self.point(type="float32"),
                      compile_tags({"profile": "epics-ca", "points": {"n": {"pv": "n", "type": "number",
                                                                              "access": "write",
                                                                              "source_ref": "a.py:1"}}})["points"]["n"]):
            with self.subTest(type=point["type"]), self.assertRaises(ValueError):
                encode(point, 10 ** 400)
        with self.assertRaises(ValueError):
            decode(compile_tags({"profile": "epics-ca", "points": {"n": {"pv": "n", "type": "number", "access": "read",
                                                                         "source_ref": "a.py:1"}}})["points"]["n"],
                   10 ** 400)

    def test_epics_and_alpaca_values(self):
        pv = compile_tags({"profile": "epics-ca", "points": {"s": {"pv": "label", "type": "string", "access": "read-write",
                                                                     "source_ref": "a.py:1"}}})["points"]["s"]
        self.assertEqual(encode(pv, "idle"), "idle")
        for value in ("x" * 41, "caf\u00e9", "line\nbreak"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encode(pv, value)
        config = compiled(alpaca)
        azimuth = config["points"]["azimuth"]
        self.assertEqual(decode(azimuth, {"Value": 12.5, "ErrorNumber": 0, "ErrorMessage": ""}), 12.5)
        for response in ({"Value": 1, "ErrorNumber": 0x407, "ErrorMessage": "not connected"}, {"Value": 1},
                         {"Value": "1", "ErrorNumber": 0}, [1]):
            with self.subTest(response=response), self.assertRaises(ValueError):
                decode(azimuth, response)


class BlockingPlc(fakes["modbus"].FakePlc):
    """Holds a write of the setpoint register until released (an ordinary request in flight)."""

    def __init__(self):
        super().__init__()
        self.entered, self.release = threading.Event(), threading.Event()

    def write_point(self, request, raw, *, timeout_s):
        if request.get("register") == 200:
            self.entered.set()
            self.release.wait(5)
        return super().write_point(request, raw, timeout_s=timeout_s)


class BridgeTests(unittest.TestCase):
    def make(self, module, native=None, path=None):
        driver = module.Driver(backend="fake", base_dir=path or Path(module.__file__).parent,
                               **({"native": native} if native is not None else {}))
        self.addCleanup(driver.close)
        driver.open()
        return driver

    def test_reads_decode_every_codec(self):
        driver = self.make(modbus)
        self.assertEqual(driver.read("main"), {"heater_on": False, "door_closed": True, "temperature": -20.0,
                                               "counter": 65538, "flow": 1.5, "mode": 0})
        self.assertEqual(driver.call(modbus.PROCESS, {}), {"temperature": -20.0, "flow": 1.5})
        with self.assertRaises(Exception) as caught:
            driver.call(modbus.PROCESS, {"fields": ["flow"]})
        self.assertEqual(code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")

    def test_commands_write_and_confirm_and_writes_verify(self):
        driver = self.make(modbus)
        self.assertEqual(driver.call(modbus.ON, {}), {"heater_on": True})
        self.assertIs(driver.native.registers[("coil", 0)], True)
        self.assertEqual(driver.write("main", {"setpoint": 21.5, "mode": 2}), {"applied": {"setpoint": 21.5, "mode": 2}})
        self.assertEqual(driver.native.registers[("holding", 200)], 215)
        state = driver.read("main")
        self.assertEqual((state["setpoint"], state["mode"]), (21.5, 2))

    def test_an_acknowledged_write_that_does_not_confirm_is_unknown_and_fenced(self):
        native = fakes["modbus"].FakePlc()
        native.on_write = lambda request, raw: native.registers.__setitem__(("holding", 500), 3)
        driver = self.make(modbus, native)
        with self.assertRaises(Exception) as caught:
            driver.write("main", {"mode": 1})
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(caught.exception.data["details"]["observed"], {"mode": 3})
        self.assertEqual(driver.read("main")["mode"], 3)
        self.assertTrue(driver.safety_status()["outcome_uncertain"])
        with self.assertRaises(Exception) as fenced:
            driver.call(modbus.ON, {})
        self.assertEqual(code(fenced.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(driver.call(modbus.OFF, {}), {"heater_on": False})
        self.assertEqual(driver.safety_status()["uncertain_points"], [])    # mode is readable: observed, not owed
        self.assertEqual(driver.call(modbus.ON, {}), {"heater_on": True})

    def test_a_lagging_readback_after_an_acknowledged_command_is_unknown_and_fenced(self):
        class Lagging(fakes["modbus"].FakePlc):
            def read_point(self, request, *, timeout_s):
                value = super().read_point(request, timeout_s=timeout_s)
                return [False] if request.get("table") == "coil" else value   # the readback has not caught up

        native = Lagging()
        driver = self.make(modbus, native)
        with self.assertRaises(Exception) as caught:
            driver.call(modbus.ON, {})
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertIs(native.registers[("coil", 0)], True)                    # the device did act
        status = driver.safety_status()
        self.assertEqual((status["outcome_uncertain"], status["uncertain_points"]), (True, ["heater"]))
        with self.assertRaises(Exception) as fenced:
            driver.call(modbus.ON, {})
        self.assertEqual(code(fenced.exception), "MHS.DEVICE.PRECONDITION_UNMET")

    def test_unknown_write_outcome_blocks_effects_until_a_confirmed_stop(self):
        driver = self.make(modbus)
        setpoint = compiled(modbus)["points"]["setpoint"]["request"]
        driver.write("main", {"setpoint": 20.0})
        driver.native.fail.add(key(setpoint))
        with self.assertRaises(Exception) as caught:
            driver.write("main", {"setpoint": 21.0})
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertNotIn("setpoint", driver.read("main"))                  # the cached value left the state
        self.assertEqual(driver.safety_status()["uncertain_points"], ["setpoint"])
        for attempt in (lambda: driver.call(modbus.ON, {}), lambda: driver.write("main", {"mode": 1})):
            with self.assertRaises(Exception) as blocked:
                attempt()
            self.assertEqual(code(blocked.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertIs(driver.native.registers[("coil", 0)], False)
        self.assertEqual(driver.call(modbus.OFF, {}), {"heater_on": False})  # the confirmed stop clears the fence
        status = driver.safety_status()                                       # ... but not the unknown setpoint
        self.assertEqual((status["safe_state"]["achieved"], status["outcome_uncertain"], status["uncertain_points"]),
                         (True, True, ["setpoint"]))
        with self.assertRaises(Exception) as fenced:
            driver.call(modbus.ON, {})                                        # never energise at an unknown setpoint
        self.assertEqual(code(fenced.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertIs(driver.native.registers[("coil", 0)], False)
        driver.native.fail.clear()
        driver.write("main", {"setpoint": 21.0})                              # writes re-establish the value
        self.assertEqual(driver.safety_status()["uncertain_points"], [])
        self.assertFalse(driver.safety_status()["outcome_uncertain"])
        self.assertEqual(driver.call(modbus.ON, {}), {"heater_on": True})

    def test_inexact_or_huge_inputs_are_invalid_before_any_io(self):
        driver = self.make(modbus)
        before = driver.native.registers[("holding", 200)]
        for value in (10 ** 400, 3.30000001, 0.1 + 0.2):
            with self.subTest(value=value), self.assertRaises(Exception) as caught:
                driver.write("main", {"setpoint": value})
            self.assertEqual(code(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(driver.native.registers[("holding", 200)], before)
        self.assertFalse(driver.safety_status()["outcome_uncertain"])
        dome = self.make(alpaca)
        with self.assertRaises(Exception) as huge:
            dome.call(alpaca.SLEW, {"azimuth": 10 ** 400})
        self.assertEqual(code(huge.exception), "MHS.CAPABILITY.INPUT_INVALID")

    def test_unacknowledged_and_refused_writes(self):
        driver = self.make(modbus)
        heater = compiled(modbus)["points"]["heater"]["request"]
        driver.native.refuse.add(key(heater))
        with self.assertRaises(Exception) as caught:
            driver.call(modbus.ON, {})
        self.assertEqual(code(caught.exception), "MHS.DEVICE.FAULTED")
        self.assertFalse(driver.safety_status()["outcome_uncertain"])
        driver.native.refuse.clear()
        driver.native.silent.add(key(heater))
        with self.assertRaises(Exception) as caught:
            driver.call(modbus.ON, {})
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertTrue(driver.safety_status()["outcome_uncertain"])

    def test_estop_is_confirmed_by_a_fresh_read_and_reset_releases_only_a_confirmed_stop(self):
        driver = self.make(modbus)
        with self.assertRaises(Exception) as early:
            driver.reset()
        self.assertEqual(code(early.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        driver.call(modbus.ON, {})
        result = driver.estop("test")
        self.assertTrue(result["safe_state_achieved"])
        self.assertIs(driver.native.registers[("coil", 0)], False)
        self.assertTrue(driver.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception) as latched:
            driver.inner.call(modbus.ON, {})
        self.assertEqual(code(latched.exception), "MHS.SAFETY.ESTOP_ENGAGED")
        driver.native.registers[("coil", 0)] = True                        # the device changed under the latch
        with self.assertRaises(Exception) as refused:
            driver.reset()
        self.assertEqual(code(refused.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(driver.estop("again")["safe_state_achieved"])
        self.assertEqual(driver.reset(), {"reset": True})
        self.assertEqual(driver.call(modbus.ON, {}), {"heater_on": True})

    def test_a_lost_setpoint_does_not_deadlock_the_latch(self):
        driver = self.make(modbus)
        setpoint = compiled(modbus)["points"]["setpoint"]["request"]
        driver.native.fail.add(key(setpoint))
        with self.assertRaises(Exception) as lost:
            driver.write("main", {"setpoint": 21.0})
        self.assertEqual(code(lost.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertTrue(driver.estop("test")["safe_state_achieved"])
        self.assertEqual(driver.reset(), {"reset": True})                 # the stop is confirmed; nothing is owed
        status = driver.safety_status()
        self.assertEqual((status["outcome_uncertain"], status["uncertain_points"]), (True, ["setpoint"]))
        with self.assertRaises(Exception) as fenced:
            driver.call(modbus.ON, {})
        self.assertEqual(code(fenced.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        driver.native.fail.clear()
        driver.write("main", {"setpoint": 21.0})
        self.assertEqual(driver.call(modbus.ON, {}), {"heater_on": True})

    def test_after_a_stop_only_a_command_that_rewrites_the_unknown_point_first_may_run(self):
        driver = self.make(modbus)
        bridge = driver.inner
        driver.native.fail.add(key(compiled(modbus)["points"]["setpoint"]["request"]))
        with self.assertRaises(Exception):
            driver.write("main", {"setpoint": 21.0})
        self.assertEqual(driver.call(modbus.OFF, {}), {"heater_on": False})
        driver.native.fail.clear()
        self.assertEqual(driver.call(modbus.PROCESS, {}), {"temperature": -20.0, "flow": 1.5})   # reads still run
        energise_first = bridge._prepare([{"write": "heater", "value": True}, {"write": "setpoint", "value": 20.0}], {})
        with self.assertRaises(Exception) as refused:
            bridge._ordinary(energise_first, [], BridgeContext(), "energise first")
        self.assertEqual(code(refused.exception), "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertIs(driver.native.registers[("coil", 0)], False)                # nothing was written
        rewrite_first = bridge._prepare([{"write": "setpoint", "value": 20.0}, {"write": "heater", "value": True}], {})
        bridge._ordinary(rewrite_first, [], BridgeContext(), "rewrite first")
        self.assertEqual(driver.native.registers[("holding", 200)], 200)
        self.assertIs(driver.native.registers[("coil", 0)], True)
        self.assertEqual(driver.safety_status()["uncertain_points"], [])

    def test_a_stop_that_is_refused_or_not_confirmed_never_reports_a_safe_state(self):
        driver = self.make(modbus)
        heater = compiled(modbus)["points"]["heater"]["request"]
        driver.native.refuse.add(key(heater))
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(code(caught.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(driver.safety_status()["safe_state"]["achieved"])
        stuck = fakes["modbus"].FakePlc()
        stuck.on_write = lambda request, raw: stuck.registers.__setitem__(("coil", 0), True)
        stuck_driver = self.make(modbus, stuck)
        result = stuck_driver.estop("test")
        self.assertFalse(result["safe_state_achieved"])
        self.assertFalse(stuck_driver.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception) as action:
            stuck_driver.call(modbus.OFF, {})
        self.assertEqual(code(action.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_stop_write_with_an_unknown_outcome_leaves_the_device_owing_a_confirmation(self):
        driver = self.make(modbus)
        heater = compiled(modbus)["points"]["heater"]["request"]
        driver.native.fail.add(key(heater))
        with self.assertRaises(Exception) as caught:
            driver.estop("test")
        self.assertEqual(code(caught.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        status = driver.safety_status()
        self.assertEqual((status["safe_state"]["achieved"], status["outcome_uncertain"], status["uncertain_points"]),
                         (False, True, ["heater"]))
        driver.native.fail.clear()
        self.assertTrue(driver.estop("retry")["safe_state_achieved"])
        self.assertFalse(driver.safety_status()["outcome_uncertain"])

    def test_a_stop_during_an_ordinary_write_is_not_confirmed_and_queued_work_is_refused(self):
        native = BlockingPlc()
        driver = self.make(modbus, native)
        outcome = {}

        def write():
            try:
                outcome["first"] = driver.write("main", {"setpoint": 21.0})
            except Exception as exc:  # noqa: BLE001 - recorded for the assertion
                outcome["first"] = exc

        def queued():
            try:
                outcome["second"] = driver.call(modbus.ON, {})
            except Exception as exc:  # noqa: BLE001
                outcome["second"] = exc

        first = threading.Thread(target=write)
        first.start()
        self.assertTrue(native.entered.wait(5))
        second = threading.Thread(target=queued)
        second.start()
        time.sleep(0.05)
        started = time.monotonic()
        result = driver.estop("test")
        self.assertLess(time.monotonic() - started, 1.0)                 # the stop never waits for the write
        self.assertFalse(result["safe_state_achieved"])                 # an ordinary write is still in flight
        native.release.set()
        first.join(5)
        second.join(5)
        self.assertEqual(outcome["first"], {"applied": {"setpoint": 21.0}})
        self.assertEqual(code(outcome["second"]), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertIs(native.registers[("coil", 0)], False)
        self.assertTrue(driver.estop("retry")["safe_state_achieved"])

    def test_reset_needs_the_stop_of_the_current_epoch_and_no_owed_confirmation(self):
        driver = self.make(modbus)
        bridge = driver.inner
        self.assertTrue(driver.estop("first")["safe_state_achieved"])
        bridge._engage_estop()                                               # a later stop epoch without a stop
        with self.assertRaises(Exception) as stale:
            bridge.reset()
        self.assertEqual(code(stale.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(driver.estop("second")["safe_state_achieved"])
        with bridge._state:
            bridge._debt = True                                              # owed confirmation, white-box
        with self.assertRaises(Exception) as owed:
            bridge.reset()
        self.assertEqual(code(owed.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        with bridge._state:
            bridge._debt = False
        self.assertEqual(bridge.reset(), {"reset": True})

    def test_queued_work_is_refused_after_any_stop_epoch_even_without_the_latch(self):
        driver = self.make(modbus)
        bridge = driver.inner
        outcome = {}
        bridge._txn.acquire()                                                # an earlier operation holds the lane
        try:
            worker = threading.Thread(target=lambda: outcome.setdefault("result", self._attempt(bridge)))
            worker.start()
            time.sleep(0.05)
            bridge._engage_estop()                                           # epoch moves; the latch stays clear
        finally:
            bridge._txn.release()
        worker.join(5)
        self.assertEqual(code(outcome["result"]), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertIs(driver.native.registers[("coil", 0)], False)

    @staticmethod
    def _attempt(bridge):
        try:
            return bridge.call(modbus.ON, {})
        except Exception as exc:  # noqa: BLE001 - returned for the assertion
            return exc

    def test_cancellation_between_steps_after_a_write_is_unknown(self):
        native = fakes["modbus"].FakePlc()
        driver = self.make(modbus, native)
        bridge = driver.inner
        cancel = threading.Event()
        plan = bridge._prepare([{"write": "heater", "value": True}, {"write": "mode", "value": 1}], {})
        original = native.write_point

        def write_point(request, raw, *, timeout_s):
            done = original(request, raw, timeout_s=timeout_s)
            cancel.set()                                                     # the operation is cancelled mid-way
            return done

        native.write_point = write_point
        with self.assertRaises(Exception) as caught:
            bridge._ordinary(plan, [], BridgeContext(cancel_event=cancel), "two-step")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(native.registers[("holding", 500)], 0)
        self.assertTrue(bridge.safety_status()["outcome_uncertain"])

    def test_closing_during_a_stop_never_reports_a_safe_state(self):
        class SlowStop(fakes["modbus"].FakePlc):
            def __init__(self):
                super().__init__()
                self.entered, self.release = threading.Event(), threading.Event()

            def write_point(self, request, raw, *, timeout_s):
                if request.get("table") == "coil" and raw is False:
                    self.entered.set()
                    self.release.wait(5)
                return super().write_point(request, raw, timeout_s=timeout_s)

        native = SlowStop()
        driver = self.make(modbus, native)
        bridge = driver.inner
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.setdefault("stop", bridge.estop("test")))
        worker.start()
        self.assertTrue(native.entered.wait(5))
        bridge.close()
        native.closed = False                                                # let the in-flight write finish
        native.release.set()
        worker.join(5)
        self.assertFalse(outcome["stop"]["safe_state_achieved"])
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_multi_step_command_preempted_after_a_write_is_unknown(self):
        native = fakes["modbus"].FakePlc()
        driver = self.make(modbus, native)
        bridge = driver.inner
        plan = bridge._prepare([{"write": "heater", "value": True}, {"write": "mode", "value": 1}], {})
        original = native.write_point

        def write_point(request, raw, *, timeout_s):
            done = original(request, raw, timeout_s=timeout_s)
            bridge._engage_estop()                                         # a stop fires between the steps
            return done

        native.write_point = write_point
        from mhs.bridge.base import BridgeContext
        with self.assertRaises(Exception) as caught:
            bridge._ordinary(plan, [], BridgeContext.coerce(None), "two-step")
        self.assertEqual(code(caught.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(native.registers[("holding", 500)], 0)             # the second step never left
        self.assertTrue(bridge.safety_status()["outcome_uncertain"])

    def test_closed_bridge_refuses_and_reports_no_safe_state(self):
        driver = self.make(modbus)
        bridge = driver.inner
        driver.estop("test")
        bridge.close()
        self.assertTrue(driver.native.closed)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception) as caught:
            bridge.read("main")
        self.assertEqual(code(caught.exception), "MHS.DEVICE.NOT_READY")

    def test_transport_shape_is_checked_before_use(self):
        config = compiled(alpaca)
        with self.assertRaises(Exception) as caught:
            TagBridge(config, transport=SimpleNamespace(read_point=lambda *a, **k: None,
                                                        write_point=lambda *a, **k: True))
        self.assertIn("invoke_point", str(caught.exception))
        with self.assertRaises(Exception):
            TagBridge(config)

    def test_alpaca_methods_errors_and_stop(self):
        driver = self.make(alpaca)
        self.assertEqual(driver.call(alpaca.SLEW, {"azimuth": 120.0}), {"target_azimuth": 120.0})
        self.assertTrue(driver.read("main")["slewing"])
        self.assertEqual(driver.call(alpaca.ABORT, {}), {"slewing": False})
        native = driver.native
        native.on_invoke = lambda request, args: 0x40B
        with self.assertRaises(Exception) as refused:
            driver.call(alpaca.SLEW, {"azimuth": 10.0})
        self.assertEqual(code(refused.exception), "MHS.DEVICE.FAULTED")
        self.assertFalse(driver.safety_status()["outcome_uncertain"])
        for number in (0x40E, 0x4FF, 0x500, 0x402):
            fresh = self.make(alpaca)
            fresh.native.on_invoke = lambda request, args, number=number: number
            with self.subTest(number=hex(number)), self.assertRaises(Exception) as unknown:
                fresh.call(alpaca.SLEW, {"azimuth": 10.0})
            self.assertEqual(code(unknown.exception), "MHS.OUTCOME.UNKNOWN")
            self.assertTrue(fresh.safety_status()["outcome_uncertain"])
        for number in (0x400, 0x401, 0x407, 0x408, 0x409, 0x40B, 0x40C):
            fresh = self.make(alpaca)
            fresh.native.on_invoke = lambda request, args, number=number: number
            with self.subTest(number=hex(number)), self.assertRaises(Exception) as refused:
                fresh.call(alpaca.SLEW, {"azimuth": 10.0})
            self.assertEqual(code(refused.exception), "MHS.DEVICE.FAULTED")
            self.assertFalse(fresh.safety_status()["outcome_uncertain"])
        native.on_invoke = lambda request, args: 0x500
        with self.assertRaises(Exception) as unknown:
            driver.call(alpaca.SLEW, {"azimuth": 10.0})
        self.assertEqual(code(unknown.exception), "MHS.OUTCOME.UNKNOWN")
        self.assertTrue(driver.safety_status()["outcome_uncertain"])
        with self.assertRaises(Exception) as unreached:
            driver.estop("test")                                           # the abort itself now fails
        self.assertEqual(code(unreached.exception), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_epics_state_and_strings(self):
        driver = self.make(epics)
        self.assertEqual(driver.call(epics.ON, {}), {"lamp_state": 1})
        self.assertEqual(driver.call(epics.READ, {}), {"brightness": 1.0, "label": "on"})
        self.assertTrue(driver.estop("test")["safe_state_achieved"])
        self.assertEqual(driver.native.pvs["state"], 0)


class DriverClassTests(unittest.TestCase):
    def variant(self, module=modbus, **attributes):
        attributes.setdefault("backends", {"fake": fakes["modbus"].FakePlc})
        return type("Variant", (module.Driver,), attributes)

    def test_config_only_classes_cannot_override_methods_or_hooks(self):
        for name in ("call", "read", "write", "estop", "reset", "make_bridge", "bridge_config", "_fill_model",
                     "_check_tag_class", "_driver_model", "_backend_factory", "open_native", "helper"):
            with self.subTest(name=name), self.assertRaises(DriverDefinitionError):
                self.variant(**{name: lambda *args, **kwargs: None})(backend="fake", base_dir=MODBUS)

    def test_declaration_policy(self):
        no_stop = self.variant(safety_bindings={})
        simulated = self.variant(mode="simulated")
        actions = copy.deepcopy(dict(modbus.Driver.actions))
        actions[modbus.OFF] = Action(name="heater_off", safe_state=True, description="off",
                                     input={"x": Field("number", unit="1", description="x",
                                                       limit=Limit.operator_required("x"))},
                                     output={"heater_on": modbus.HEATER})
        input_stop = self.variant(actions=actions)
        observation = copy.deepcopy(dict(modbus.Driver.actions))
        observation[modbus.PROCESS] = Action(name="read_process", description="read",
                                             output={"temperature": Field("number", unit="Cel", description="t"),
                                                     "flow": Field("number", unit="L/min", description="f")})
        no_verb = self.variant(actions=observation)
        commands = copy.deepcopy(dict(modbus.Driver.commands))
        commands[modbus.ON] = {"steps": [{"write": "setpoint", "input": "target"}]}
        undeclared_input = self.variant(commands=commands)
        for cls in (no_stop, simulated, input_stop, no_verb, undeclared_input):
            with self.subTest(cls=cls), self.assertRaises(DriverDefinitionError):
                cls.driver_model()
        with self.assertRaises(ValueError):
            modbus.Driver(backend="sim", base_dir=MODBUS)

    def test_runtime_mutation_of_the_declaration_is_refused(self):
        cls = self.variant(tag_config=copy.deepcopy(dict(modbus.Driver.tag_config)))
        driver = cls(backend="fake", base_dir=MODBUS)
        self.addCleanup(driver.close)
        driver.open()
        cls.tag_config["points"]["setpoint"]["register"] = 201
        with self.assertRaises(DriverDefinitionError):
            driver.write("main", {"setpoint": 1.0})
        driver.options["port"] = "elsewhere"
        with self.assertRaises(DriverDefinitionError):
            driver.read("main")

    def test_hardware_needs_a_human_hardware_review_before_any_factory(self):
        factory = Mock(return_value=fakes["modbus"].FakePlc())
        cls = self.variant(backends={"fake": ".fake:FakePlc", "hardware": factory})
        with self.assertRaises(PermissionError):
            cls(backend="hardware", base_dir=MODBUS)
        contract = support.lock_document(reviewed=True)
        contract["reviewed_by"]["scope"] = "contract"
        for document, problems in ((support.lock_document(), []), (contract, []),
                                   (support.lock_document(reviewed=True), ["schema problem"])):
            # Synthetic in-memory documents, never signatures on driver packages.
            with patch("mhs.driver.loader.read_lock", return_value=(document, problems)):
                with self.assertRaises(PermissionError):
                    cls(backend="hardware", base_dir=MODBUS)
        factory.assert_not_called()
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(MODBUS, "hardware", allow_hardware=True, state_dir=state)
        self.assertEqual(caught.exception.reason, "review_required")

    def test_a_reviewed_hardware_backend_uses_its_factory_transport(self):
        native = fakes["modbus"].FakePlc()
        factory = Mock(return_value=native)
        cls = self.variant(backends={"fake": ".fake:FakePlc", "hardware": factory})
        with patch("mhs.driver.loader.read_lock", return_value=(support.lock_document(reviewed=True), [])):
            driver = cls(backend="hardware", base_dir=MODBUS, options={"port": "/dev/null"})
            self.addCleanup(driver.close)
            driver.open()
            self.assertEqual(driver.call(modbus.ON, {}), {"heater_on": True})
        factory.assert_called_once_with(port="/dev/null")
        self.assertTrue(driver.is_hardware)


class GateTests(unittest.TestCase):
    def copy(self, path):
        holder = tempfile.TemporaryDirectory(prefix="mhs-tag-gate-")
        self.addCleanup(holder.cleanup)
        target = Path(holder.name) / path.name
        shutil.copytree(path, target, ignore=shutil.ignore_patterns("__pycache__", "check-report.json"))
        return target

    def test_synthetic_fixtures_pass_g1_to_g8(self):
        for path in (MODBUS, EPICS, ALPACA):
            report = run_check(path, gates=GATES, write_report=False)
            with self.subTest(fixture=path.name):
                self.assertEqual(report["failed"], [], report)
                g7 = next(gate for gate in report["gates"] if gate["id"] == "G7")
                self.assertEqual([item["code"] for item in g7["findings"]], [])

    def test_g7_refuses_an_address_the_cited_line_does_not_show(self):
        target = self.copy(MODBUS)
        support_text = (target / "driver.py").read_text()
        (target / "driver.py").write_text(support_text.replace('"register": 200,', '"register": 201,'))
        report = run_check(target, gates=["G3", "G7"], write_report=False)
        codes = [item["code"] for gate in report["gates"] for item in gate["findings"]]
        self.assertIn("G7.TAG_ADDRESS_NOT_UPSTREAM", codes)
        target = self.copy(ALPACA)
        app = target / "vendor" / "synthetic_alpaca" / "app.py"
        app.write_text(app.read_text().replace("'dome'", "'focuser'"))
        report = run_check(target, gates=["G3", "G7"], write_report=False)
        codes = [item["code"] for gate in report["gates"] for item in gate["findings"]]
        self.assertIn("G7.TAG_ADDRESS_NOT_UPSTREAM", codes)

    def test_g7_refuses_undeclared_or_disallowed_wire_traffic(self):
        config = compiled(modbus)
        recorder = Recorder(fakes["modbus"].FakePlc())
        for request, raw in ((config["points"]["heater"]["request"], None),
                             ({"profile": "modbus", "table": "holding", "register": 999, "words": 1}, None),
                             (config["points"]["door"]["request"], True),
                             (config["points"]["setpoint"]["request"], [1, 2])):
            with contextlib.suppress(Exception):                      # the fake refuses some; the log keeps all
                if raw is None:
                    recorder.read_point(dict(request), timeout_s=0.5)
                else:
                    recorder.write_point(dict(request), raw, timeout_s=0.5)
        ctx = SimpleNamespace(cls=modbus.Driver, card={}, logs=[log_of(recorder)],
                              tree=SimpleNamespace(read_text=lambda path: (MODBUS / "vendor" / path).read_text()))
        gate = Gate("G7", "Native surface")
        with patch("mhs.driver.tag_check._native"):
            check_tag_surface(ctx, gate)
        codes = sorted({item.code for item in gate.findings})
        self.assertEqual(codes, ["G7.TAG_WIRE_ACCESS", "G7.TAG_WIRE_UNDECLARED", "G7.TAG_WIRE_VALUE"])

    def test_g7_does_not_accept_a_scale_factor_as_an_address(self):
        target = self.copy(MODBUS)
        text = (target / "driver.py").read_text()
        (target / "driver.py").write_text(text.replace('"register": 200,', '"register": 10,'))
        fake = (target / "fake.py").read_text().replace('("holding", 200): 0,', '("holding", 10): 0,')
        (target / "fake.py").write_text(fake)
        report = run_check(target, gates=["G3", "G7"], write_report=False)
        codes = [item["code"] for gate in report["gates"] for item in gate["findings"]]
        self.assertIn("G7.TAG_ADDRESS_NOT_UPSTREAM", codes)    # the cited line writes int(value * 10) to 200

    def test_package_code_cannot_weaken_the_tag_runtime(self):
        for line in ("import mhs.bridge.tags as _tags\n_tags.STOP_BOUND_S = 600.0\n",
                     "from mhs.bridge import tags as _tags\n_tags.TagBridge._confirm = lambda *a, **k: (True, {})\n",
                     "import mhs.driver.tag_config as _config\n_config.MAX_STEPS = 10 ** 6\n"):
            target = self.copy(MODBUS)
            with (target / "driver.py").open("a", encoding="utf-8") as handle:
                handle.write("\n" + line)
            report = run_check(target, gates=["G3"], write_report=False)
            codes = {item["code"] for gate in report["gates"] for item in gate["findings"]}
            with self.subTest(line=line):
                self.assertIn("G3", report["failed"], report)
                self.assertTrue(codes & {"G3.FORBIDDEN", "G3.GATE_TAMPERED"}, codes)

    @staticmethod
    def register_point(register, table="holding", access="write"):
        return compile_tags({"profile": "modbus", "points": {"p": {
            "table": table, "register": register, "type": "bool" if table in ("coil", "discrete") else "uint16",
            "access": access,
            "source_ref": "a.py:1"}}})["points"]["p"]

    def codes(self, point, document, line=1, end=None, path="a.py"):
        errors, warnings = address_findings(point, document, path, line, end or line)
        return [code_ for code_, _message in errors], len(warnings)

    def test_modbus_addresses_are_proved_in_their_role(self):
        write = "x.write_register(0x0031, int(v * 1000), functioncode=6)\n"
        self.assertEqual(self.codes(self.register_point(0x31), write), ([], 0))
        for register in (6, 1000):                                           # function code and scale factor
            self.assertEqual(self.codes(self.register_point(register), write), (["TAG_ADDRESS_NOT_UPSTREAM"], 0))
        commented = "# Voltage should be multiplied by 100\nx.write_register(0x0030, int(v * 100), functioncode=6)\n"
        self.assertEqual(self.codes(self.register_point(100), commented, 1, 2), (["TAG_ADDRESS_NOT_UPSTREAM"], 0))
        self.assertEqual(self.codes(self.register_point(0x30), commented, 1, 2), ([], 0))
        self.assertEqual(self.codes(self.register_point(0x31, access="read"), write), (["TAG_ACCESS_NOT_UPSTREAM"], 0))
        self.assertEqual(self.codes(self.register_point(0x31, table="input", access="read"), write),
                         (["TAG_TABLE_NOT_UPSTREAM", "TAG_ACCESS_NOT_UPSTREAM"], 0))
        read = "v = x.read_register(0x0010, 2, functioncode=3)\n"
        self.assertEqual(self.codes(self.register_point(0x10, access="read"), read), ([], 0))
        both = read + "x.write_register(0x0010, 1, functioncode=6)\n"
        self.assertEqual(self.codes(self.register_point(0x10, access="read-write"), both, 1, 2), ([], 0))
        self.assertEqual(self.codes(self.register_point(0x10, access="read-write"), read),
                         (["TAG_ACCESS_NOT_UPSTREAM"], 0))
        split = "x.write_register(\n    0x0031, int(v * 1000), functioncode=6\n)\n"
        self.assertEqual(self.codes(self.register_point(0x31), split, 2, 2), ([], 0))   # the cited argument line
        self.assertEqual(self.codes(self.register_point(4120), "class R:\n    PUMP_ENABLE = 4120\n", 2), ([], 1))
        self.assertEqual(self.codes(self.register_point(48), "write_reg(0x30, v); /* 48 */\n", path="a.c"), ([], 1))
        self.assertEqual(self.codes(self.register_point(48), "a = (\n", path="a.py"), (["TAG_ADDRESS_NOT_UPSTREAM"], 0))
        for text in ("x.set_input_current(1000)\n", "bus.register_callback(1000)\n", "input(1000)\n"):
            self.assertEqual(self.codes(self.register_point(1000), text), (["TAG_ADDRESS_NOT_UPSTREAM"], 0))
        self.assertEqual(self.codes(self.register_point(0x20, access="read"), "v = x.read_float(0x20)\n"), ([], 1))
        self.assertEqual(self.codes(self.register_point(0x20), "x.write_float(0x20, 1.5)\n"), ([], 0))
        self.assertEqual(self.codes(self.register_point(7, table="coil"), "c.write_single_coil(7, True)\n"), ([], 0))
        self.assertEqual(self.codes(self.register_point(9, table="discrete", access="read"),
                                    "c.read_discrete_inputs(address=9, count=1)\n"), ([], 0))

    def test_epics_and_alpaca_names_are_proved_in_their_role(self):
        state = compiled(epics)["points"]["state"]
        ioc = "class IOC(PVGroup):\n    {}\n"
        self.assertEqual(self.codes(state, ioc.format("state = pvproperty(value=0)"), 2), ([], 0))
        self.assertEqual(self.codes(state, ioc.format("update = pvproperty(name='state')"), 2), ([], 0))
        for line in ("statement = pvproperty(value=0)", "x = 1  # state"):
            self.assertEqual(self.codes(state, ioc.format(line), 2), (["TAG_ADDRESS_NOT_UPSTREAM"], 0))
        self.assertEqual(self.codes(state, "    state = pvproperty(value=0)\n"), ([], 1))   # unparseable: text only
        member = compiled(alpaca)["points"]["abortslew"]
        self.assertEqual(self.codes(member, "class abortslew:\n    pass\n"), ([], 0))
        self.assertEqual(self.codes(member, "x = 1  # abortslew\n"), (["TAG_ADDRESS_NOT_UPSTREAM"], 0))

    def test_family_is_detected(self):
        from mhs.driver.check import _Context
        ctx = _Context(MODBUS, "fake", None, None, False)
        self.addCleanup(ctx.close)
        self.assertEqual(ctx.family, "tag-bridge")
        self.assertTrue(ctx.transport_family)


if __name__ == "__main__":
    unittest.main()
