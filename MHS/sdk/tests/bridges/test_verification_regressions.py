"""Regressions found by the independent WP-05 verification (each failed first).

Ported verifier probes (scratch/verify-WP-05/probes/):

* p3_paths.py, p6_psu_server.py (blocker): ``get_path`` re-checked the root
  words after stripping one prefix, so ``input.output``, ``input.result``,
  ``output.result`` and ``output.output`` named the *whole* value.  Through
  ``MHSServer`` a request for ``output: false`` passed the whole input dict to
  ``set_output`` (truthy), switched the PSU output ON and the receipt was
  ``completed``; ``result.x`` and ``$.x`` silently changed meaning too;
* p1_clamp.py (major): a clamp/envelope ``unit`` was accepted and ignored, so
  ``{max: 500, unit: "mm"}`` on an argument converted mm -> m accepted 1000 mm;
* p2_targets.py: result targets were checked only against a *closed* output
  schema, and ``validate_binding`` accepted ``"$"`` as an output field;
* p5_misc.py: a recorded response that was never read passed replay, and an
  interlock with the default ``closed_when`` and a text parse could never
  read ``closed``;
* a call queued on the bridge (transaction) lock ran after ``estop()``
  returned; unmapped native exceptions of a legacy error map defaulted to
  ``MHS.DEVICE.FAULTED`` with the native text; ``python -m mhs.bridge.<x>``
  printed a runpy ``RuntimeWarning``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import unittest
import warnings
from pathlib import Path

from tests.bridges import support

from mhs.bridge.base import ErrorMap, FieldMapping, MappingError, get_path
from mhs.bridge.bindings import validate_binding
from mhs.bridge.python import PythonObjectBridge
from mhs.bridge.scpi import ScpiBridge
from mhs.bridge.serial import FakeSerial, SerialBridge
from mhs.bridge.transcript import Transcript, TranscriptDivergence
from mhs.server import Resource

SDK_SRC = Path(__file__).resolve().parents[2] / "src"
PSU = "tests.bridges.test_verification_regressions:Psu"
HEATER = "tests.bridges.support:Heater"


def code_of(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


class Psu:
    """A power supply whose ``set_output(enabled)`` returns ``{result, status}`` (probe p6)."""

    def __init__(self) -> None:
        self.enabled: bool | None = None
        self.calls: list = []

    def set_output(self, enabled):
        self.calls.append(enabled)
        self.enabled = bool(enabled)
        return {"result": self.enabled, "status": "ok"}

    def reading(self):
        return {"result": 22.0, "status": "ok"}


def psu_entry(args: dict, result_map: dict, native: str = "set_output") -> dict:
    return {"bridge": "python-object", "native": native, "args": args, "result": {"map": result_map},
            "concurrency": "exclusive", "timeout_ms": 1000}


class GetPathRegressionTests(unittest.TestCase):
    def test_root_words_after_a_prefix_are_ordinary_field_names(self) -> None:
        cases = [
            ("input.output", {"output": False, "channel": 1}, False),
            ("input.result", {"result": 3}, 3),
            ("input.args", {"args": [1, 2]}, [1, 2]),
            ("input.input", {"input": "x", "other": 1}, "x"),
            ("output.result", {"result": 22.0, "status": "ok"}, 22.0),
            ("output.output", {"output": 1, "status": "ok"}, 1),
            ("args.output", {"output": 5}, 5),
            ("output.args", {"args": "a"}, "a"),
        ]
        for path, obj, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(get_path(obj, path), expected)

    def test_result_and_dollar_prefixes_are_not_stripped(self) -> None:
        # baseline meaning: ``result.x`` is obj["result"]["x"], ``$.x`` is obj["$"]["x"]
        self.assertEqual(get_path({"result": {"x": 1}, "x": 2}, "result.x"), 1)
        self.assertEqual(get_path({"$": {"x": 1}, "x": 2}, "$.x"), 1)
        with self.assertRaises(MappingError):
            get_path({"x": 2}, "result.x")

    def test_roots_still_name_the_whole_value(self) -> None:
        obj = {"a": 1}
        for path in ("", "$", "input", "output", "args", "result", "output.$", "input.$", "args.$",
                     "output."):
            with self.subTest(path=path):
                self.assertIs(get_path(obj, path), obj)
        self.assertEqual(get_path(22.0, "output.$"), 22.0)

    def test_boolean_false_reaches_the_native_argument(self) -> None:
        for rule in ({"from": "input.output"}, {"from": "input.output", "type": "boolean"}):
            with self.subTest(rule=rule):
                mapping = FieldMapping({"enabled": rule}, direction="input")
                self.assertEqual(mapping.map({"output": False}), {"enabled": False})


class PsuEndToEndTests(unittest.TestCase):
    """Probe p6 through the current MHSServer: output=false must switch the PSU off."""

    def setUp(self) -> None:
        config = {"target": PSU, "capabilities": {
            "x-cap.psu.output.v1": psu_entry({"enabled": {"from": "input.output"}}, {"on": "output.result"}),
            "x-cap.psu.reading.v1": psu_entry({}, {"value": "output.result", "status": "output.status"},
                                              native="reading"),
        }}
        self.bridge = PythonObjectBridge(config, device_id="mhs://localhost:7799/lab/psu")
        self.native: Psu = self.bridge._ensure_loaded()
        device = support.simulated_device(
            "mhs://localhost:7799/lab/psu",
            resources=[Resource("psu", "instrument.psu")],
            capabilities=[support.open_capability(cap, "psu") for cap in config["capabilities"]],
            bridge=self.bridge,
        )
        self.harness = support.Harness(device)

    def tearDown(self) -> None:
        self.bridge.close()

    def test_output_false_switches_the_output_off(self) -> None:
        receipt = self.harness.command("x-cap.psu.output.v1", {"output": True})
        self.assertEqual((receipt["status"], receipt["output"]), ("completed", {"on": True}), receipt)
        receipt = self.harness.command("x-cap.psu.output.v1", {"output": False})
        self.assertEqual((receipt["status"], receipt["output"]), ("completed", {"on": False}), receipt)
        self.assertEqual(self.native.calls, [True, False])
        self.assertIs(self.native.enabled, False)

    def test_output_result_maps_the_result_field_not_the_whole_return(self) -> None:
        receipt = self.harness.command("x-cap.psu.reading.v1", {})
        self.assertEqual(receipt["output"], {"value": 22.0, "status": "ok"}, receipt)

    def test_legacy_result_prefix_keeps_reading_the_native_return(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            bridge = PythonObjectBridge({"target": PSU, "grammar": "legacy", "capabilities": {
                "x-cap.psu.reading.v1": {"native": "reading",
                                         "result": {"value": {"from": "result.result"},
                                                    "status": {"from": "$.status"}}}}})
        try:
            self.assertEqual(bridge.call("x-cap.psu.reading.v1", {}), {"value": 22.0, "status": "ok"})
        finally:
            bridge.close()


class ClampUnitTests(unittest.TestCase):
    """Probe p1: a clamp/envelope ``unit`` is the unit the value has when it is checked."""

    def test_a_clamp_unit_that_differs_from_the_converted_unit_is_a_load_error(self) -> None:
        with self.assertRaises(MappingError) as caught:
            FieldMapping({"pos": {"from": "input.pos_mm", "unit": {"from": "mm", "to": "m"},
                                  "clamp": {"max": 500, "unit": "mm"}}}, direction="input")
        self.assertIn("'mm'", str(caught.exception))
        self.assertIn("'m'", str(caught.exception))

    def test_a_matching_clamp_unit_is_checked_in_that_unit(self) -> None:
        mapping = FieldMapping({"pos": {"from": "input.pos_mm", "unit": {"from": "mm", "to": "m"},
                                        "clamp": {"max": 0.5, "unit": "m"}}}, direction="input")
        self.assertEqual(mapping.map({"pos_mm": 400}), {"pos": 0.4})
        with self.assertRaises(Exception) as caught:
            mapping.map({"pos_mm": 1000})
        self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(caught.exception.data["details"]["unit"], "m")

    def test_envelope_units_are_checked_too(self) -> None:
        with self.assertRaises(MappingError):
            FieldMapping({"pos": {"from": "input.p", "unit": {"from": "mm", "to": "m"},
                                  "clamp": {"max": 0.5, "unit": "m", "envelope": {"max": 900, "unit": "mm"}}}},
                         direction="input")
        with self.assertRaises(MappingError):   # no conversion: the two sources disagree
            FieldMapping({"pos": {"from": "input.p", "clamp": {"max": 500, "unit": "mm",
                                                               "envelope": {"max": 1, "unit": "m"}}}},
                         direction="input")
        mapping = FieldMapping({"pos": {"from": "input.p", "clamp": {"max": 500, "unit": "mm"}}},
                               direction="input")
        self.assertEqual(mapping.map({"p": 400}), {"pos": 400})

    def test_a_clamp_unit_after_a_legacy_scale_is_refused(self) -> None:
        with self.assertRaises(MappingError):
            FieldMapping({"pos": {"from": "p", "scale": 0.001, "clamp": {"max": 0.5, "unit": "m"}}},
                         direction="input")

    def test_the_validator_and_the_bridge_refuse_the_mismatch(self) -> None:
        inline = psu_entry({"pos": {"from": "input.pos_mm", "unit": {"from": "mm", "to": "m"},
                                    "clamp": {"max": 500, "unit": "mm"}}}, {"ok": "output.$"}, native="move")
        errors = validate_binding(inline)
        self.assertTrue(any("unit" in error and "'mm'" in error for error in errors), errors)
        folded = psu_entry({"pos": {"from": "input.pos_mm"}}, {"ok": "output.$"}, native="move")
        folded["units"] = {"input.pos_mm": {"from": "mm", "to": "m"}}
        folded["clamp"] = {"input.pos_mm": {"max": 500, "unit": "mm"}}
        errors = validate_binding(folded)
        self.assertTrue(any("unit" in error and "'mm'" in error for error in errors), errors)
        folded["clamp"] = {"input.pos_mm": {"max": 0.5, "unit": "m"}}
        self.assertEqual(validate_binding(folded), [])
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": PSU, "capabilities": {"x-cap.psu.move.v1": inline}}, load=False)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


class OutputContractTests(unittest.TestCase):
    """Probe p2: result targets are checked against any provided output schema."""

    OPEN = {"type": "object", "properties": {"temperature": {"type": "number"}}, "required": ["temperature"]}

    def bridge(self, result_map: dict, schema: dict) -> PythonObjectBridge:
        return PythonObjectBridge(
            {"target": "tests.bridges.support:Thermometer", "capabilities": {
                "x-cap.t.v1": psu_entry({}, result_map, native="read_temperature")}},
            capability_schemas={"x-cap.t.v1": {"output_schema": schema}},
        )

    def test_a_stray_target_is_refused_without_additional_properties_false(self) -> None:
        with self.assertRaises(Exception) as caught:
            self.bridge({"temp_c": "output.$"}, self.OPEN)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertIn("temp_c", json.dumps(caught.exception.data))

    def test_an_explicitly_open_schema_accepts_extra_targets(self) -> None:
        bridge = self.bridge({"temperature": "output.$", "raw": "output.$"}, dict(self.OPEN, **{"x-mhs-open": True}))
        try:
            self.assertEqual(bridge.call("x-cap.t.v1", {}), {"temperature": 22.0, "raw": 22.0})
        finally:
            bridge.close()

    def test_a_required_output_property_must_be_mapped(self) -> None:
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"temperature": {"type": "number"}, "stable": {"type": "boolean"}},
                  "required": ["temperature", "stable"]}
        with self.assertRaises(Exception) as caught:
            self.bridge({"temperature": "output.$"}, schema)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        self.assertIn("stable", json.dumps(caught.exception.data))

    def test_sampled_at_is_stamped_by_the_bridge_when_the_class_requires_it(self) -> None:
        schema = support.class_schema("cap.measure.temperature.v1")["output_schema"]
        bridge = self.bridge({"temperature": "output.$"}, schema)
        try:
            output = bridge.call("x-cap.t.v1", {})
            self.assertEqual(output["temperature"], 22.0)
            self.assertRegex(output["sampled_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z$")
            self.assertEqual(set(output), {"temperature", "sampled_at"})
        finally:
            bridge.close()

    def test_validator_refuses_inverted_result_maps(self) -> None:
        for target in ("$", "output.code", "$.x", "input.x"):
            with self.subTest(target=target):
                errors = validate_binding(psu_entry({}, {target: "output"}, native="read_temperature"))
                self.assertTrue(any("result.map" in error and repr(target) in error for error in errors), errors)
        self.assertEqual(validate_binding(psu_entry({}, {"result": "output.$"}, native="read_temperature")), [])
        with self.assertRaises(MappingError):
            FieldMapping({"map": {"$": "output"}}, direction="output")


class TranscriptStrictnessTests(unittest.TestCase):
    """Probe p5: a recorded response that is never read is a divergence."""

    def test_an_unread_response_diverges_at_the_next_request(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "FREQ 2000", "recv": "OK"},
                                                         {"send": "FREQ?", "recv": "2000"}]})
        transport = transcript.line_transport()
        transport.write("FREQ 2000")
        with self.assertRaises(TranscriptDivergence):
            transport.query("FREQ?")

    def test_an_unread_last_response_fails_assert_complete(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "FREQ 2000", "recv": "OK"}]})
        transcript.line_transport().write("FREQ 2000")
        with self.assertRaises(TranscriptDivergence):
            transcript.assert_complete()

    def test_recv_optional_allows_an_ignored_response(self) -> None:
        transcript = Transcript.from_json({"exchanges": [
            {"send": "FREQ 2000", "recv": "OK", "recv_optional": True}, {"send": "FREQ?", "recv": "2000"}]})
        transport = transcript.line_transport()
        transport.write("FREQ 2000")
        self.assertEqual(transport.query("FREQ?"), "2000")
        transcript.assert_complete()
        self.assertTrue(transcript.to_json()["exchanges"][0]["recv_optional"])


class InterlockConfigTests(unittest.TestCase):
    """Probe p5: ``closed_when: true`` can only match a boolean parse."""

    def test_serial_and_scpi_refuse_a_text_interlock_with_the_default_closed_when(self) -> None:
        serial = FakeSerial({"DOOR?": "1\n"})
        for spec in ({"id": "door", "command": "DOOR?"},
                     {"id": "door", "command": "DOOR?", "parse": {"kind": "int"}}):
            with self.subTest(spec=spec):
                with self.assertRaises(Exception) as caught:
                    SerialBridge({"port": "/dev/fake", "safety_bindings": {"interlocks": [spec]}},
                                 serial_factory=lambda **kw: serial)
                self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        with self.assertRaises(Exception) as caught:
            ScpiBridge({"safety_bindings": {"interlocks": [{"id": "door", "query": "DOOR?"}]}},
                       transport=Transcript([]).line_transport())
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        bridge = SerialBridge({"port": "/dev/fake", "safety_bindings": {"interlocks": [
            {"id": "door", "command": "DOOR?", "parse": {"kind": "bool", "true": "1"}}]}},
            serial_factory=lambda **kw: serial)
        try:
            self.assertEqual(bridge.interlocks()[0]["state"], "closed")
        finally:
            bridge.close()

    def test_python_object_refuses_a_non_boolean_parse_with_the_default_closed_when(self) -> None:
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": HEATER, "safety_bindings": {"interlocks": [
                {"id": "lid", "native": "lid_closed", "invoke": "get", "parse": {"kind": "int"}}]}},
                load=False)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


class EstopPreemptsQueuedCallsTests(unittest.TestCase):
    """A call queued on the bridge lock when the e-stop fires never reaches the native."""

    def _run_queued(self, lock, call) -> dict:
        holder: dict = {}

        def run() -> None:
            try:
                holder["result"] = call()
            except BaseException as exc:  # noqa: BLE001
                holder["error"] = exc

        lock.acquire()
        worker = threading.Thread(target=run)
        try:
            worker.start()
            time.sleep(0.1)   # the call is now waiting for the lock
            holder["estop"] = self.estop()
        finally:
            lock.release()
        worker.join(5.0)
        return holder

    def test_python_object_call_and_write(self) -> None:
        from tests.bridges.test_safety_bindings import heater_config

        config = heater_config()
        config["writes"] = {"heater": {"params": {"setpoint": {"native": "set_point", "invoke": "call",
                                                               "type": "number"}}}}
        bridge = PythonObjectBridge(config)
        native = bridge._ensure_loaded()
        self.estop = lambda: bridge.estop("queued")
        try:
            holder = self._run_queued(bridge._lock, lambda: bridge.call(
                "cap.thermal.setpoint.v1", {"target_temperature": 80}))
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
            holder = self._run_queued(bridge._lock, lambda: bridge.write("heater", {"setpoint": 70}))
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
            self.assertNotIn("set_point", [name for name, _ in native.calls])
            # calls issued after the e-stop (the server owns the latch) run normally
            self.assertEqual(bridge.call("cap.thermal.setpoint.v1", {"target_temperature": 60}),
                             {"setpoint": 60})
            self.assertEqual(bridge.write("heater", {"setpoint": 65}), {"applied": {"setpoint": 65}})
            self.assertEqual(native.setpoint, 65)
        finally:
            bridge.close()

    def test_python_object_without_safety_bindings(self) -> None:
        bridge = PythonObjectBridge({"target": HEATER, "capabilities": {
            "cap.thermal.setpoint.v1": psu_entry({"celsius": {"from": "input.t"}}, {"s": "output.setpoint"},
                                                 native="set_point")}})
        native = bridge._ensure_loaded()
        self.estop = lambda: bridge.estop("queued")
        try:
            holder = self._run_queued(bridge._lock, lambda: bridge.call("cap.thermal.setpoint.v1", {"t": 80}))
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
            self.assertEqual(native.calls, [])
        finally:
            bridge.close()

    def test_serial_transaction(self) -> None:
        serial = FakeSerial({"HEAT 80": "OK\n"})
        bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.3, "capabilities": {
            "x-cap.test.heat.v1": {"resource": "instrument", "command": "HEAT {value}",
                                   "args": {"value": {"from": "input.value"}}}},
            "safety_bindings": {"estop": {"command": "STOP"}}}, serial_factory=lambda **kw: serial)
        self.estop = lambda: bridge.estop("queued")
        try:
            holder = self._run_queued(bridge._txn_lock, lambda: bridge.call("x-cap.test.heat.v1", {"value": 80}))
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
            self.assertIn(b"STOP\n", serial.written)
            self.assertNotIn(b"HEAT 80\n", serial.written)
        finally:
            bridge.close()

    def test_scpi_exchange(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "OUTP OFF"}]})
        bridge = ScpiBridge({"idn": False, "commands": {"x-cap.test.volt.v1": {
            "resource": "psu", "write": "VOLT {value:g}", "args": {"value": {"from": "input.volts"}}}},
            "safety_bindings": {"estop": {"write": "OUTP OFF"}}}, transport=transcript.line_transport())
        self.estop = lambda: bridge.estop("queued")
        try:
            holder = self._run_queued(bridge._txn_lock, lambda: bridge.call("x-cap.test.volt.v1", {"volts": 5}))
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
            transcript.assert_complete()   # "VOLT 5" was never sent
        finally:
            bridge.close()


class ErrorDefaultTests(unittest.TestCase):
    """Plan 3.7: any unmapped native exception is SHIM_FAILED with a redacted message."""

    def test_error_map_defaults(self) -> None:
        for spec in (None, {"ValueError": "MHS.CAPABILITY.INPUT_INVALID"}, []):
            with self.subTest(spec=spec):
                self.assertEqual(ErrorMap(spec).translate(OSError("secret path"))[0], "MHS.ADAPTER.SHIM_FAILED")
        self.assertEqual(ErrorMap({"*": "MHS.DEVICE.FAULTED"}).translate(OSError("x"))[0], "MHS.DEVICE.FAULTED")

    def test_legacy_unmapped_native_error_is_redacted(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            bridge = PythonObjectBridge({"target": PSU, "grammar": "legacy", "capabilities": {
                "x-cap.psu.output.v1": {"native": "set_output", "args": {"enabled": {"from": "input.on"}},
                                        "errors": {"ValueError": "MHS.CAPABILITY.INPUT_INVALID"}}}})
        native = bridge._ensure_loaded()

        def explode(enabled):
            raise OSError("/home/operator/secret.conf")

        native.set_output = explode
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("x-cap.psu.output.v1", {"on": True})
            self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.SHIM_FAILED")
            self.assertNotIn("secret", str(caught.exception))
            self.assertNotIn("secret", json.dumps(caught.exception.data))
        finally:
            bridge.close()


class LaunchGuardNoiseTests(unittest.TestCase):
    def test_python_m_prints_no_runpy_warning(self) -> None:
        env = dict(os.environ, PYTHONPATH=str(SDK_SRC), PYTHONDONTWRITEBYTECODE="1", PYTHONWARNINGS="default")
        for name in ("python", "scpi", "base", "gymnasium"):
            with self.subTest(module=name):
                completed = subprocess.run([sys.executable, "-m", f"mhs.bridge.{name}"], capture_output=True,
                                           text=True, env=env, timeout=60)
                self.assertEqual(completed.returncode, 2)
                self.assertNotIn("RuntimeWarning", completed.stderr)

    def test_package_exports_stay_importable(self) -> None:
        import mhs.bridge as package

        self.assertIs(package.PythonObjectBridge, PythonObjectBridge)
        self.assertIs(package.ScpiBridge, ScpiBridge)
        self.assertIn("scpi-visa", package.available_bridges())
        self.assertIn("python-object", package.BRIDGE_FAMILIES)
        from mhs.bridge import GymnasiumBridge, Transcript as Exported  # noqa: F401

        self.assertIs(Exported, Transcript)


if __name__ == "__main__":
    unittest.main()
