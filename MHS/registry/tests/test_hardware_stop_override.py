"""User decision 4 of 2026-11-05: one hardware override may set hardware_stop on a lock companion.

The profile is not a ROS profile. The card stores the full commit as ref. A ROS companion does not
gain the flag, and a card that sets the flag without the override is refused.
"""

from __future__ import annotations

import copy
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, HERE)

import build_registry as BR  # noqa: E402
import triage as T  # noqa: E402
import validate as V  # noqa: E402
from test_build_pipeline import STORE  # noqa: E402

COMMIT = "b" * 40
SHORT = COMMIT[:12]
PID = "gh.rplab/wil_pycro_control_app"


def _override(**changes):
    item = {
        "package_id": PID,
        "strategy": "direct-driver",
        "role": "device-driver",
        "family": "python-object",
        "reason_code": "override:direct-driver",
        "justification": "the package clone has no stage halt; the stop cites the fetched companion",
        "companions": [{
            "alias": "mmcore",
            "package_id": "gh.micro-manager/mmcoreanddevices",
            "commit": COMMIT,
            "profile": "micromanager-2.0-gamma-20230120",
            "reason": "user decision: this hardware stop may cite the fetched companion",
            "version_evidence": [
                {"side": "package", "ref": "requirements.txt:2", "token": "20230120"},
                {"side": "companion", "ref": "MMCore/MMCore.cpp:116", "token": "MMCore_versionMajor"},
            ],
            "lock": f"micro-manager__mmCoreAndDevices@{SHORT}",
            "hardware_stop": True,
        }],
    }
    item.update(changes)
    return item


def _schema_card():
    """A minimal task card whose one companion sets hardware_stop on a non-ROS profile."""
    return {
        "card_version": "0.9",
        "package_id": "gh.example/stage",
        "track": "labs",
        "local_path": "labs/example/stage",
        "driver_dir": "MHS/drivers/labs/example__stage",
        "upstream": {
            "repo_url": "https://github.com/example/stage",
            "commit": COMMIT,
            "license_spdx": "MIT",
            "license_class": "permissive",
        },
        "decision": "direct-driver",
        "reason_code": "override:direct-driver",
        "role": "device-driver",
        "family": "python-object",
        "helper": "PythonObjectDriver",
        "helper_status": "available",
        "blocked_on": [],
        "quarantine": False,
        "variant_of": None,
        "wave": 5,
        "rank": 1,
        "exemplar": None,
        "entry_symbols": [],
        "install": {"python": None, "commands": [], "system_deps": [], "gpu": False, "platform": "any"},
        "mock_strategy": {"preferred": "fake", "hints": [], "upstream_tests": None},
        "hints": {"reads": [], "writes": [], "actions": [], "candidate_classes": []},
        "safety": {"expected_mode": "hardware", "risk_floor": "R1", "limit_hints": []},
        "needs_recon": [],
        "timebox_min": 60,
        "acceptance": "python3 -m mhs.driver check MHS/drivers/labs/example__stage --backend fake",
        "skip_reason": None,
        "publish_review": "not_required",
        "companions": [_card_entry({
            "alias": "mmcore",
            "package_id": "gh.micro-manager/mmcoreanddevices",
            "commit": COMMIT,
            "profile": "micromanager-2.0-gamma-20230120",
            "reason": "this hardware package stop cites the fetched companion",
            "version_evidence": [
                {"side": "package", "ref": "requirements.txt:2", "token": "gamma"},
                {"side": "companion", "ref": "MMCore/MMCore.cpp:1", "token": "MMCore"},
            ],
            "lock": f"micro-manager__mmCoreAndDevices@{SHORT}",
        })],
    }


def _card_entry(override_entry):
    return {
        "alias": override_entry["alias"],
        "package_id": override_entry["package_id"],
        "commit": override_entry["commit"],
        "profile": override_entry["profile"],
        "reason": override_entry["reason"],
        "version_evidence": override_entry["version_evidence"],
        "hardware_stop": True,
        "lock": override_entry["lock"],
        "ref": COMMIT,
        "local_path": f"work/companions/micro-manager__mmCoreAndDevices@{SHORT}",
        "repo_url": "https://github.com/micro-manager/mmCoreAndDevices.git",
        "license_spdx": "NOASSERTION",
    }


class HardwareStopOverrideTests(unittest.TestCase):
    def test_the_non_ros_profile_is_accepted(self) -> None:
        T.check_override(_override(), "waiting-routing.json")

    def test_a_ros_profile_with_the_flag_is_refused(self) -> None:
        item = _override()
        item["companions"][0]["profile"] = "ros1-noetic-gazebo11"
        with self.assertRaises(T.OverrideError) as caught:
            T.check_override(item, "waiting-routing.json")
        self.assertIn("non-ROS", str(caught.exception))

    def test_the_flag_is_only_true(self) -> None:
        item = _override()
        item["companions"][0]["hardware_stop"] = False
        with self.assertRaises(T.OverrideError):
            T.check_override(item, "waiting-routing.json")

    def test_lock_shape_stores_the_full_commit(self) -> None:
        entry = _override()["companions"][0]
        card = {"companions": [_card_entry(entry)]}
        self.assertEqual(V.lock_shape_problems(PID, [entry], card), [])
        short = copy.deepcopy(card)
        short["companions"][0]["ref"] = SHORT
        problems = V.lock_shape_problems(PID, [entry], short)
        self.assertEqual(len(problems), 1)
        self.assertIn("full", problems[0])

    def test_a_card_flag_without_the_override_is_refused(self) -> None:
        entry = _override()["companions"][0]
        declared = {key: value for key, value in entry.items() if key != "hardware_stop"}
        declared["profile"] = "ros1-noetic-gazebo11"
        card = {"companions": [_card_entry(entry)]}
        card["companions"][0]["profile"] = "ros1-noetic-gazebo11"
        card["companions"][0]["ref"] = SHORT
        problems = V.lock_shape_problems(PID, [declared], card)
        self.assertTrue(any("hardware_stop" in item for item in problems))

    def test_attach_copies_the_flag_before_the_lock_fields(self) -> None:
        entry = _override()["companions"][0]
        decision = type("Decision", (), {"companions": [entry]})()
        cards = {PID: {}}
        line = {
            "ref": COMMIT,
            "path": f"work/companions/micro-manager__mmCoreAndDevices@{SHORT}",
            "repo_url": "https://github.com/micro-manager/mmCoreAndDevices.git",
            "licence": "MIT",
        }
        with mock.patch.object(T, "companion_problems", return_value=[]), \
             mock.patch.object(T, "read_companion_lock", return_value=({entry["lock"]: line}, None)):
            errors = BR.attach_companions(cards, {PID: decision}, {}, {})
        self.assertEqual(errors, [])
        built = cards[PID]["companions"][0]
        self.assertIs(built["hardware_stop"], True)
        self.assertEqual(built["ref"], COMMIT)
        self.assertLess(list(built).index("hardware_stop"), list(built).index("lock"))

    def test_check_companions_requires_the_flag_on_the_card(self) -> None:
        entry = _override()["companions"][0]
        note = "not an spdx expression here"
        line = {
            "ref": COMMIT,
            "path": f"work/companions/micro-manager__mmCoreAndDevices@{SHORT}",
            "repo_url": "https://github.com/micro-manager/mmCoreAndDevices.git",
            "licence": note,
        }
        present = _card_entry(entry)
        present["licence_note"] = note
        missing = copy.deepcopy(present)
        missing.pop("hardware_stop")
        overrides = {PID: {"companions": [entry]}}
        with mock.patch.object(T, "companion_problems", return_value=[]), \
             mock.patch.object(T, "read_companion_lock", return_value=({entry["lock"]: line}, None)):
            self.assertEqual(V.check_companions(overrides, {PID: {"companions": [present]}}, {}, {}, "/tmp"), [])
            problems = V.check_companions(overrides, {PID: {"companions": [missing]}}, {}, {}, "/tmp")
        self.assertTrue(any("hardware_stop" in item or "differ" in item for item in problems))

    def test_the_task_card_schema_rejects_a_ros_profile_on_the_flag(self) -> None:
        # An in-memory card. The shipped wil task card is the snapshot-7 card and has no
        # hardware_stop companion. The schema rule is what this test checks.
        card = _schema_card()
        self.assertEqual(STORE.validate(card, "taskcard.schema.json"), [])
        ros = copy.deepcopy(card)
        ros["companions"][0]["profile"] = "ros1-noetic-gazebo11"
        problems = STORE.validate(ros, "taskcard.schema.json")
        self.assertTrue(problems)
        plain = copy.deepcopy(card)
        plain["companions"][0].pop("hardware_stop")
        problems = STORE.validate(plain, "taskcard.schema.json")
        self.assertTrue(problems, "a non-ROS profile still needs the hardware_stop flag")


if __name__ == "__main__":
    unittest.main()
