"""WP-02 follow-ups: temperature differences, one lifecycle vocabulary, actionable deprecations, e-stop native."""

from __future__ import annotations

import copy
import unittest

from mhs import errors as mhs_errors
from mhs.schema import SchemaStore

from ._support import CAPABILITIES, ERRORS, SCHEMA_DIR, VALID, load_json, load_tool

STORE = SchemaStore(root=SCHEMA_DIR)
CATALOGUE = load_json(CAPABILITIES)
REGISTRY = load_json(ERRORS)
#: Absolute temperature atoms (a level, converted with an offset).
ABSOLUTE = {"K", "Cel", "[degF]"}


def _fields(schema, path=""):
    if not isinstance(schema, dict):
        return
    if path:
        yield path, schema
    if isinstance(schema.get("items"), dict):
        yield from _fields(schema["items"], path + "[*]")
    for name, sub in (schema.get("properties") or {}).items():
        yield from _fields(sub, f"{path}.{name}" if path else name)


def _temperature_fields():
    for entry in CATALOGUE["capabilities"]:
        for section in ("input_schema", "output_schema"):
            for path, field in _fields(entry[section]):
                unit = field.get("x-mhs-unit")
                if isinstance(unit, str) and ("K" in unit.replace("[degF]", "") or "Cel" in unit or "degF" in unit):
                    yield entry["capability_id"], section, path, field


def _release(text):
    return tuple(int(part) for part in str(text).split("."))


class TemperatureDeltaTests(unittest.TestCase):
    def test_setpoint_tolerance_and_rate_are_differences(self):
        entry = next(e for e in CATALOGUE["capabilities"] if e["capability_id"] == "cap.thermal.setpoint.v1")
        properties = entry["input_schema"]["properties"]
        self.assertEqual((properties["tolerance"]["x-mhs-unit"], properties["tolerance"].get("x-mhs-delta")), ("K", True))
        self.assertEqual((properties["rate"]["x-mhs-unit"], properties["rate"].get("x-mhs-delta")), ("K/min", True))
        self.assertNotIn("x-mhs-delta", properties["target_temperature"])

    def test_every_temperature_difference_is_marked(self):
        seen = []
        for capability_id, section, path, field in _temperature_fields():
            unit = field["x-mhs-unit"]
            with self.subTest(field=f"{capability_id} {section} {path}"):
                if unit == "Cel" or unit not in ABSOLUTE:
                    # Celsius fields are levels; compound units (K/min) are always differences
                    self.assertIs(field.get("x-mhs-delta", False), unit not in ABSOLUTE, unit)
                elif unit == "K":
                    # a bare kelvin field in this catalogue is a difference (no class reports a kelvin level)
                    self.assertIs(field.get("x-mhs-delta"), True)
                seen.append(path)
        self.assertIn("tolerance", seen)

    def test_delta_marker_is_a_boolean(self):
        for entry in CATALOGUE["capabilities"]:
            for section in ("input_schema", "output_schema"):
                for path, field in _fields(entry[section]):
                    if "x-mhs-delta" in field:
                        self.assertIs(field["x-mhs-delta"], True, (entry["capability_id"], path))


class LifecycleVocabularyTests(unittest.TestCase):
    def test_errors_and_classes_share_the_lifecycle_words(self):
        error_statuses = {record["status"] for record in REGISTRY["errors"]}
        class_statuses = {entry["status"] for entry in CATALOGUE["capabilities"]}
        self.assertEqual(error_statuses, {"stable", "deprecated", "feature"})
        self.assertEqual(class_statuses, {"stable", "experimental", "deprecated"})
        self.assertNotIn("active", error_statuses | class_statuses)
        for code, spec in mhs_errors.MHS_ERROR_CODES.items():
            self.assertIn(spec.status, ("stable", "deprecated", "retired", "feature"), code)
        self.assertEqual(mhs_errors.ErrorSpec("MHS.X.Y", -32000, False, "X", "m").status, "stable")
        self.assertEqual(mhs_errors.describe_error("MHS.HOST.ADAPTER_MISSING")["status"], "stable")

    def test_pre_0_9_spelling_still_validates(self):
        legacy = copy.deepcopy(REGISTRY)
        for record in legacy["errors"]:
            if record["status"] == "stable":
                record["status"] = "active"
        self.assertEqual(STORE.validate(legacy, "errors.schema.json"), [])
        problems = "\n".join(load_tool("gen_errors").registry_problems(legacy))
        self.assertIn("'active' is the pre-0.9 spelling", problems)

    def test_since_is_a_spec_release_not_the_registry_revision(self):
        spec = _release(REGISTRY["spec_version"])
        for record in REGISTRY["errors"]:
            self.assertLessEqual(_release(record["since"])[: len(spec)], spec, record["code"])
        catalogue_spec = _release(CATALOGUE["spec_version"])
        for entry in CATALOGUE["capabilities"]:
            self.assertLessEqual(_release(entry["since"])[: len(catalogue_spec)], catalogue_spec,
                                 entry["capability_id"])
        later = copy.deepcopy(REGISTRY)
        later["errors"][0]["since"] = "1.0.0"     # the registry/wire revision, not a spec release
        problems = "\n".join(load_tool("gen_errors").registry_problems(later))
        self.assertIn("later than spec_version", problems)
        schema = load_json(SCHEMA_DIR / "errors.schema.json")
        self.assertIn("spec_version", schema["$defs"]["record"]["properties"]["since"]["description"])
        self.assertIn("wire revision", schema["properties"]["mhs_error_registry"]["description"])


class DeprecatedRemediationTests(unittest.TestCase):
    def test_openai4s_missing_tells_the_receiver_what_to_do(self):
        record = next(r for r in REGISTRY["errors"] if r["code"] == "MHS.HOST.OPENAI4S_MISSING")
        remediation = record["remediation"]
        # actionable for the agent that receives it: what to install or change, and how to treat it
        self.assertIn("MHS.HOST.ADAPTER_MISSING", remediation)
        self.assertIn("OpenAI4S", remediation)
        self.assertRegex(remediation, r"[Ii]nstall")
        self.assertIn("PYTHONPATH", remediation)
        self.assertNotRegex(remediation, r"^Emit ")     # not an instruction to the emitter
        wire = mhs_errors.MHSError("MHS.HOST.OPENAI4S_MISSING").to_error_object()
        self.assertEqual(wire["data"]["remediation"], remediation)
        self.assertEqual(wire["data"]["mhs_code"], "MHS.HOST.OPENAI4S_MISSING")


class EstopNativeTests(unittest.TestCase):
    def test_device_schema_carries_the_native_stop(self):
        manifest = load_json(VALID / "device.thermal-bath.json")
        self.assertEqual(manifest["safety"]["estop"]["native"], "stop")
        self.assertEqual(STORE.validate(manifest, "device.schema.json"), [])
        software = copy.deepcopy(manifest)
        software["safety"]["estop"]["native"] = None
        self.assertEqual(STORE.validate(software, "device.schema.json"), [])
        for bad in ("", 3, ["stop"]):
            with self.subTest(native=bad):
                broken = copy.deepcopy(manifest)
                broken["safety"]["estop"]["native"] = bad
                self.assertNotEqual(STORE.validate(broken, "device.schema.json"), [])


if __name__ == "__main__":
    unittest.main()
