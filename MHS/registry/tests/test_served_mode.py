#!/usr/bin/env python3
"""A reviewed ``served_mode`` serves the simulated form and keeps hardware on the record.

A ``modes`` override cannot drop a scanned hardware mode (SAFE-045). ``served_mode`` is the
other field: the record stays hardware-first with ``simulated`` still present, the card's
``safety.expected_mode`` becomes ``simulated``, and ``build_registry.py`` refuses the field
unless both modes are present and hardware is first. ``--companions-root`` selects the
LOCK.json a build reads; clone paths stay under the workspace.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from test_build_pipeline import STORE, catalog_row, run
from test_mode_overrides import override
from test_triage import decide, facts
import taskcards as TC
import triage as T
import validate as V


def served(**extra):
    item = override(served_mode="simulated")
    item.update(extra)
    return item


class ServedModeCheckTests(unittest.TestCase):
    def test_simulated_passes_the_checker_and_the_schema(self):
        T.check_override(served())
        doc = {"overrides_version": "0.9", "title": "t", "overrides": [served()]}
        self.assertEqual(STORE.validate(doc, "overrides.schema.json"), [])

    def test_only_simulated_on_a_dispatchable_strategy_is_accepted(self):
        with self.assertRaisesRegex(T.OverrideError, "can only be 'simulated'"):
            T.check_override(override(served_mode="hardware"))
        with self.assertRaisesRegex(T.OverrideError, "only for"):
            T.check_override(override(strategy="skip", role="not-device", served_mode="simulated"))
        for mode in ("hardware", "replay"):
            doc = {"overrides_version": "0.9", "title": "t",
                   "overrides": [override(served_mode=mode)]}
            self.assertTrue(STORE.validate(doc, "overrides.schema.json"), mode)
        skipped = {"overrides_version": "0.9", "title": "t",
                   "overrides": [override(strategy="skip", role="not-device", served_mode="simulated")]}
        self.assertTrue(STORE.validate(skipped, "overrides.schema.json"))

    def test_the_decision_record_does_not_carry_served_mode(self):
        f = facts(name="bath")
        decision = decide(f, overrides={f.package_id: served()})
        self.assertEqual(decision.served_mode, "simulated")
        self.assertNotIn("served_mode", decision.to_json())
        plain = decide(f, overrides={f.package_id: override()})
        self.assertIsNone(plain.served_mode)


class ServedModeBuildTests(unittest.TestCase):
    def test_dual_mode_card_serves_simulated_and_keeps_hardware_first(self):
        rec, card, decision, lock = run(overrides={"gh.acme/bath": served()})
        self.assertEqual(decision.served_mode, "simulated")
        self.assertNotIn("served_mode", decision.to_json())
        self.assertEqual(rec["modes"], ["hardware", "simulated"])
        self.assertTrue(rec["simulation"])
        self.assertTrue(rec["hardware_free"])
        self.assertEqual(card["safety"]["expected_mode"], "simulated")
        meta = rec["x-vendor"]["classification"]["served_mode"]
        self.assertEqual((meta["rule"], meta["mode"]), ("override:served-mode", "simulated"))
        self.assertIn("Model review: the code writes G-code", meta["evidence"])
        self.assertEqual([device["mode"] for device in rec["x-vendor"]["device_plan"]],
                         ["hardware", "simulated"])
        self.assertEqual(STORE.validate(rec, "registry-record.schema.json"), [])
        errors, _extensions = V.check_record_semantics(rec, V.load_core_capabilities(), None, lock)
        self.assertEqual(errors, [])

    def test_a_plain_dual_mode_card_still_expects_hardware(self):
        rec, card, decision, _lock = run()
        self.assertIsNone(decision.served_mode)
        self.assertEqual(rec["modes"], ["hardware", "simulated"])
        self.assertEqual(card["safety"]["expected_mode"], "hardware")
        self.assertNotIn("served_mode", rec["x-vendor"]["classification"])
        self.assertEqual(TC.expected_mode(rec, decision), "hardware")

    def test_expected_mode_does_not_serve_simulated_when_hardware_is_not_first_with_simulated(self):
        hardware_only = {"modes": ["hardware"]}
        decision = T.Decision(package_id="gh.acme/bath", strategy="direct-driver", role="device-driver",
                              reason_code="override:recon", rule="override", served_mode="simulated")
        self.assertEqual(TC.expected_mode(hardware_only, decision), "hardware")

    def test_finalize_refuses_served_mode_unless_hardware_stays_first_with_simulated(self):
        with self.assertRaisesRegex(ValueError, "hardware first"):
            run(overrides={"gh.acme/bath": served(modes=["hardware"])})
        with self.assertRaisesRegex(ValueError, "hardware first"):
            run(row=catalog_row(), overrides={"gh.acme/bath": served(
                strategy="family-config", role="sim-env", family="gymnasium")})

    def test_the_validator_refuses_a_marker_that_dropped_hardware(self):
        rec, _card, _decision, lock = run(overrides={"gh.acme/bath": served()})
        self.assertEqual(V.check_served_mode(rec), [])
        dropped = json.loads(json.dumps(rec))
        dropped["modes"] = ["simulated"]
        self.assertTrue(any("hardware first" in error for error in V.check_served_mode(dropped)))
        errors, _extensions = V.check_record_semantics(dropped, V.load_core_capabilities(), None, lock)
        self.assertTrue(any("hardware first" in error for error in errors), errors)
        wrong = json.loads(json.dumps(rec))
        wrong["x-vendor"]["classification"]["served_mode"]["mode"] = "hardware"
        self.assertTrue(any("override:served-mode" in error for error in V.check_served_mode(wrong)))


class CompanionLockRootTests(unittest.TestCase):
    def test_companions_root_selects_lock_json_and_the_default_stays_under_the_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = os.path.join(tmp, "workspace")
            root = os.path.join(tmp, "companions-root")
            os.makedirs(os.path.join(workspace, "work", "companions"))
            os.makedirs(root)
            workspace_lock = {"clones": [{"alias": "from-workspace"}]}
            root_lock = {"clones": [{"alias": "from-root"}]}
            with open(os.path.join(workspace, "work", "companions", "LOCK.json"), "w", encoding="utf-8") as fh:
                json.dump(workspace_lock, fh)
            with open(os.path.join(root, "LOCK.json"), "w", encoding="utf-8") as fh:
                json.dump(root_lock, fh)
            selected, problem = T.read_companion_lock(workspace, root)
            self.assertIsNone(problem)
            self.assertEqual(set(selected), {"from-root"})
            default, default_problem = T.read_companion_lock(workspace, None)
            self.assertIsNone(default_problem)
            self.assertEqual(set(default), {"from-workspace"})
            broken = os.path.join(tmp, "broken")
            os.makedirs(broken)
            with open(os.path.join(broken, "LOCK.json"), "w", encoding="utf-8") as fh:
                fh.write("{")
            _mapping, message = T.read_companion_lock(workspace, broken)
            self.assertIn(os.path.join(broken, "LOCK.json"), message)


if __name__ == "__main__":
    unittest.main()
