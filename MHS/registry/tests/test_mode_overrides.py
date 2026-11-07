#!/usr/bin/env python3
"""An override's reviewed ``modes`` replace the record's scanned modes (RUNTIME-AND-GATE-FIXES).

A README-head scan recorded real hardware (mrw-code/ros_morphology_robot, mgreiff/crazyflie-project) as simulated and
no override field could correct it. ``modes`` is the record's complete mode set, hardware first; the card's expected
mode, ``simulation``, ``hardware_free`` and the device plan follow it.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, HERE)

import triage as T  # noqa: E402
from test_build_pipeline import STORE, catalog_row, run  # noqa: E402
from test_triage import decide, facts  # noqa: E402
import validate as V  # noqa: E402

SIM_ROW = dict(simulation_available="yes", hardware_free="yes", adapter_role="仿真环境")  # a README that says simulation


def override(**extra):
    item = {"package_id": "gh.acme/bath", "strategy": "direct-driver", "role": "device-driver",
            "family": "python-object", "justification": "Model review: the code writes G-code to a real stage."}
    item.update(extra)
    return item


class ModeOverrideCheckTests(unittest.TestCase):
    def test_valid_mode_sets_pass(self):
        for modes in (["hardware"], ["simulated"], ["hardware", "simulated"], ["simulated", "replay"],
                      ["hardware", "simulated", "replay"], ["replay"]):
            with self.subTest(modes=modes):
                T.check_override(override(modes=modes))
                doc = {"overrides_version": "0.9", "title": "t", "overrides": [override(modes=modes)]}
                self.assertEqual(STORE.validate(doc, "overrides.schema.json"), [])

    def test_invalid_mode_sets_are_refused(self):
        for modes in ([], ["hybrid"], ["simulated", "hardware"], ["hardware", "hardware"], "hardware",
                      ["hardware", "simulated", "replay", "hardware"], [1]):
            with self.subTest(modes=modes):
                with self.assertRaises(T.OverrideError):
                    T.check_override(override(modes=modes))
        for modes in ([], ["hybrid"], ["hardware", "hardware"], "hardware"):
            with self.subTest(schema=modes):
                doc = {"overrides_version": "0.9", "title": "t", "overrides": [override(modes=modes)]}
                self.assertTrue(STORE.validate(doc, "overrides.schema.json"))

    def test_modes_pass_through_the_decision_but_stay_off_the_decision_record(self):
        f = facts(name="bath")
        d = decide(f, overrides={f.package_id: override(modes=["hardware"])})
        self.assertEqual(d.modes, ["hardware"])
        self.assertNotIn("modes", d.to_json())
        self.assertEqual(decide(f, overrides={f.package_id: override()}).modes, [])


class ModeOverrideBuildTests(unittest.TestCase):
    def assert_valid(self, rec, lock):
        self.assertEqual(STORE.validate(rec, "registry-record.schema.json"), [])
        errors, _ = V.check_record_semantics(rec, V.load_core_capabilities(), None, lock)
        self.assertEqual(errors, [])

    def test_a_scan_that_says_simulated_is_corrected_to_hardware(self):
        row = catalog_row(**SIM_ROW)
        sim_override = override(strategy="family-config", role="sim-env", family="gymnasium")
        rec, card, _decision, lock = run(row=row, overrides={"gh.acme/bath": sim_override})
        self.assertIn("simulated", rec["modes"])  # the scan and the role default: a simulator
        rec, card, decision, lock = run(row=row, overrides={"gh.acme/bath": dict(sim_override, modes=["hardware"])})
        self.assertEqual(decision.modes, ["hardware"])
        self.assertEqual(rec["modes"], ["hardware"])
        self.assertFalse(rec["simulation"])
        self.assertFalse(rec["hardware_free"])
        self.assertEqual(card["safety"]["expected_mode"], "hardware")
        self.assertEqual([device["mode"] for device in rec["x-vendor"]["device_plan"]], ["hardware"])
        meta = rec["x-vendor"]["classification"]["mode_override"]
        self.assertEqual((meta["rule"], meta["modes"]), ("override:modes", ["hardware"]))
        self.assertEqual(meta["scanned_modes"], ["simulated"])
        self.assertIn("Model review: the code writes G-code", meta["evidence"])
        self.assert_valid(rec, lock)

    def test_a_dual_mode_record_loses_a_simulated_mode_the_clone_cannot_serve(self):
        rec, _card, _decision, _lock = run(row=catalog_row())
        self.assertEqual(rec["modes"], ["hardware", "simulated"])  # the catalogue row says partial simulation
        rec, card, _decision, lock = run(row=catalog_row(), overrides={"gh.acme/bath": override(modes=["hardware"])})
        self.assertEqual(rec["modes"], ["hardware"])
        self.assertFalse(rec["hardware_free"])
        self.assertEqual(card["safety"]["expected_mode"], "hardware")
        self.assert_valid(rec, lock)

    def test_an_override_never_drops_a_hardware_mode_the_scan_found(self):
        # S9-08: dropping hardware would lift the hardware rules (SAFE-045 e-stop evidence, the gate's hardware view)
        # on one model-written line; a modes override may only correct a record towards hardware.
        rec, _card, _decision, _lock = run(row=catalog_row())
        self.assertIn("hardware", rec["modes"])
        for modes in (["simulated"], ["simulated", "replay"], ["replay"]):
            with self.subTest(modes=modes):
                with self.assertRaisesRegex(ValueError, "drop the hardware mode the scan found"):
                    run(row=catalog_row(), overrides={"gh.acme/bath": override(modes=modes)})

    def test_the_validator_refuses_a_record_whose_override_dropped_hardware(self):
        rec, _card, _decision, lock = run(row=catalog_row(), overrides={"gh.acme/bath": override(modes=["hardware"])})
        self.assertEqual(V.check_mode_override(rec), [])
        meta = rec["x-vendor"]["classification"]["mode_override"]
        dropped = json.loads(json.dumps(rec))
        dropped["modes"] = ["simulated"]
        dropped["x-vendor"]["classification"]["mode_override"]["modes"] = ["simulated"]
        self.assertTrue(any("drops the hardware mode" in e for e in V.check_mode_override(dropped)))
        errors, _ = V.check_record_semantics(dropped, V.load_core_capabilities(), None, lock)
        self.assertTrue(any("drops the hardware mode" in e for e in errors), errors)
        unrecorded = json.loads(json.dumps(rec))
        del unrecorded["x-vendor"]["classification"]["mode_override"]["scanned_modes"]
        self.assertTrue(any("scanned modes" in e for e in V.check_mode_override(unrecorded)))
        other = json.loads(json.dumps(rec))
        other["modes"] = ["hardware", "simulated"]
        self.assertTrue(any("are not the reviewed override" in e for e in V.check_mode_override(other)))
        self.assertEqual(meta["scanned_modes"], ["hardware", "simulated"])

    def test_a_record_without_devices_refuses_modes(self):
        import build_registry as BR
        base = BR.make_record("labs", "acme", "bath", catalog_row(), "exact", {"files": 0}, [], None, None)
        self.assertIn(base["tier"], ("D", "X"))  # an empty clone plans no device
        decision = T.Decision(package_id="gh.acme/bath", strategy="skip", role="not-device",
                              reason_code="skip:empty", rule="override", modes=["hardware"],
                              evidence=["override (t.json): test"])
        with self.assertRaisesRegex(ValueError, "plans no device"):
            BR.finalize_record(base, decision, facts(name="bath"), None, None, None, None)


if __name__ == "__main__":
    unittest.main()
