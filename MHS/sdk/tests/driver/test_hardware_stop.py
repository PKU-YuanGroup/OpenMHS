"""A user-authorized hardware stop may cite one fetched companion (user decision 4, 2026-11-05).

The exception is narrow: mode hardware, family direct or python-object, a non-ROS profile, a lock
companion whose card ref is the full commit, and two members (stop, then a read-back) called only
during the e-stop. A ROS companion keeps the old rules. The citation does not waive reviewed_by.
"""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.adapter import LoadError, load_driver
from mhs.driver.check import Gate, _g7
from mhs.driver.hardware_stop import check_hardware_stop, declares_companion_stop
from mhs.driver.loader import review_problem
from mhs.driver.source_gate import check_explicit_source
from mhs.driver.source_selector import parse_selector
from mhs.driver.upstream import companion_sources
from mhs.testing.recorder import RecordLog
from tests.driver import support
from tests.driver.test_upstream import tree_with

COMMIT = "a" * 40
SHORT = COMMIT[:12]
LOCK = f"micro-manager__mmCoreAndDevices@{SHORT}"
TEXT = "void CMMCore::stop(const char* label) {}\nbool CMMCore::deviceBusy(const char* label) { return false; }\n"


def _entry(**changes):
    item = {
        "alias": "mmcore",
        "package_id": "gh.micro-manager/mmcoreanddevices",
        "commit": COMMIT,
        "profile": "micromanager-2.0-gamma-20230120",
        "reason": "this hardware package stop cites the fetched companion",
        "version_evidence": [
            {"side": "package", "ref": "requirements.txt:2", "token": "gamma"},
            {"side": "companion", "ref": "MMCore/MMCore.cpp:1", "token": "MMCore"},
        ],
        "hardware_stop": True,
        "lock": LOCK,
        "ref": COMMIT,
        "local_path": f"work/companions/micro-manager__mmCoreAndDevices@{SHORT}",
        "repo_url": "https://github.com/micro-manager/mmCoreAndDevices.git",
        "license_spdx": "NOASSERTION",
    }
    item.update(changes)
    return item


def _card(entry):
    return {
        "package_id": "gh.rplab/wil_pycro_control_app",
        "family": "python-object",
        "safety": {"expected_mode": "hardware"},
        "companions": [entry],
    }


class _Tree:
    def read_text(self, path):
        return TEXT


def _source():
    return SimpleNamespace(hardware_stop=True, lock=LOCK, tree=_Tree())


def _declaration():
    return (
        {"role": "stop", "member": "stop_stages",
         "ref": "companion:mmcore/MMCore/MMCore.cpp:1", "shows": "CMMCore::stop"},
        {"role": "readback", "member": "stages_settled",
         "ref": "companion:mmcore/MMCore/MMCore.cpp:2", "shows": "deviceBusy"},
    )


def _ctx(calls, *, family="direct", mode="hardware"):
    return SimpleNamespace(
        cls=SimpleNamespace(companion_stop=_declaration(), mode=mode),
        model=SimpleNamespace(mode=mode),
        family=family,
        companions={"mmcore": _source()},
        logs=[SimpleNamespace(calls=calls)],
    )


def _call(name, phase):
    return SimpleNamespace(name=name, phase=phase, kind="call")


def _codes(gate):
    return [item.code for item in gate.findings]


class HardwareStopSourceTests(unittest.TestCase):
    def test_a_hardware_stop_entry_keeps_the_full_commit(self) -> None:
        sources, problems = companion_sources(_card(_entry()), Path("/nowhere"))
        self.assertEqual(problems, [])
        source = sources["mmcore"]
        self.assertTrue(source.hardware_stop)
        self.assertEqual(source.ref, COMMIT)
        self.assertEqual(source.lock, LOCK)

    def test_a_ros_profile_is_refused_with_the_flag(self) -> None:
        _sources, problems = companion_sources(_card(_entry(profile="ros1-noetic-gazebo11")), None)
        self.assertEqual(len(problems), 1)
        self.assertIn("non-ROS", problems[0])

    def test_a_suffix_ref_is_refused(self) -> None:
        _sources, problems = companion_sources(_card(_entry(ref=SHORT)), None)
        self.assertEqual(len(problems), 1)
        self.assertIn("full commit", problems[0])

    def test_a_different_full_commit_ref_is_refused(self) -> None:
        other = "b" * 40
        _sources, problems = companion_sources(_card(_entry(ref=other)), None)
        self.assertEqual(len(problems), 1)
        self.assertIn("full commit", problems[0])

    def test_a_simulated_card_is_refused(self) -> None:
        card = _card(_entry())
        card["safety"] = {"expected_mode": "simulated"}
        _sources, problems = companion_sources(card, None)
        self.assertIn("expected_mode", problems[0])

    def test_a_ros_family_is_refused(self) -> None:
        card = _card(_entry())
        card["family"] = "ros"
        _sources, problems = companion_sources(card, None)
        self.assertIn("python-object", problems[0])

    def test_a_ros_lock_companion_still_uses_the_suffix_ref(self) -> None:
        entry = _entry(hardware_stop=True)
        del entry["hardware_stop"]
        entry["profile"] = "ros1-noetic-gazebo11"
        entry["ref"] = SHORT
        entry["lock"] = f"acme__sim@{SHORT}"
        sources, problems = companion_sources(_card(entry), Path("/nowhere"))
        self.assertEqual(problems, [])
        self.assertFalse(sources["mmcore"].hardware_stop)
        self.assertEqual(sources["mmcore"].ref, SHORT)


class HardwareStopCallTests(unittest.TestCase):
    def test_a_non_hardware_mode_is_not_exempt(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stop_stages", "estop"), _call("stages_settled", "estop")]
        exempt = check_hardware_stop(_ctx(calls, mode="simulated"), gate, set())
        self.assertEqual(exempt, set())
        self.assertIn("G7.HARDWARE_STOP_SCOPE", _codes(gate))
        self.assertTrue(any("hardware" in item.message for item in gate.findings))

    def test_a_source_without_hardware_stop_is_not_exempt(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stop_stages", "estop"), _call("stages_settled", "estop")]
        source = _source()
        source.hardware_stop = False
        ctx = _ctx(calls)
        ctx.companions = {"mmcore": source}
        exempt = check_hardware_stop(ctx, gate, set())
        self.assertEqual(exempt, set())
        self.assertIn("G7.HARDWARE_STOP_SCOPE", _codes(gate))

    def test_a_stop_then_a_read_back_is_exempt(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stop_stages", "estop"), _call("stages_settled", "estop")]
        exempt = check_hardware_stop(_ctx(calls), gate, set())
        self.assertEqual(exempt, {"stop_stages", "stages_settled"})
        self.assertEqual(gate.findings, [])

    def test_a_call_outside_the_estop_is_refused_and_still_exempt(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stop_stages", "act"), _call("stages_settled", "estop"), _call("stop_stages", "estop")]
        exempt = check_hardware_stop(_ctx(calls), gate, set())
        self.assertEqual(exempt, {"stop_stages", "stages_settled"})
        self.assertIn("G7.HARDWARE_STOP_SCOPE", _codes(gate))

    def test_a_read_back_before_the_stop_is_unconfirmed(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stages_settled", "estop"), _call("stop_stages", "estop"), _call("stages_settled", "estop")]
        check_hardware_stop(_ctx(calls), gate, set())
        self.assertIn("G7.HARDWARE_STOP_UNCONFIRMED", _codes(gate))

    def test_a_missing_read_back_is_unconfirmed(self) -> None:
        gate = Gate("G7", "Native surface")
        check_hardware_stop(_ctx([_call("stop_stages", "estop")]), gate, set())
        self.assertIn("G7.HARDWARE_STOP_UNCONFIRMED", _codes(gate))

    def test_a_ros_driver_family_is_out_of_scope(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stop_stages", "estop"), _call("stages_settled", "estop")]
        exempt = check_hardware_stop(_ctx(calls, family="ros"), gate, set())
        self.assertEqual(exempt, set())
        self.assertIn("G7.HARDWARE_STOP_SCOPE", _codes(gate))

    def test_a_member_of_the_package_clone_is_not_exempt(self) -> None:
        gate = Gate("G7", "Native surface")
        calls = [_call("stop_stages", "estop"), _call("stages_settled", "estop")]
        exempt = check_hardware_stop(_ctx(calls), gate, {"stop_stages"})
        self.assertEqual(exempt, set())
        self.assertIn("G7.HARDWARE_STOP_SURFACE", _codes(gate))

    def test_exempt_members_are_not_reported_not_upstream(self) -> None:
        selected = parse_selector("pyfile:stage.py#*")
        tree = tree_with(self, {"stage.py": "def move():\n    return 1\n"})
        log = RecordLog("source fake")
        log.record("stop_stages", "call", (), {}, phase="estop")
        log.record("stages_settled", "call", (), {}, phase="estop")
        ctx = SimpleNamespace(
            tree=tree,
            card={"entry_symbols": [{"symbol": selected.value, "file": "stage.py", "line": 1}]},
            logs=[log],
            cls=SimpleNamespace(companion_stop=_declaration(), mode="hardware"),
            model=SimpleNamespace(mode="hardware"),
            family="direct",
            companions={"mmcore": _source()},
        )

        class Fake:
            def move(self):
                return 1

            def stop_stages(self):
                return None

            def stages_settled(self):
                return True

        gate = Gate("G7", "Native surface")
        members = {name for klass in Fake.__mro__ for name in vars(klass) if not name.startswith("_")}
        check_explicit_source(ctx, gate, selected, Fake, members)
        self.assertNotIn("G7.NOT_UPSTREAM", _codes(gate))
        self.assertEqual(gate.findings, [])

    def test_a_missing_surface_still_checks_the_stop(self) -> None:
        selected = parse_selector("pyfile:missing.py#*")
        tree = tree_with(self, {"stage.py": "def move():\n    return 1\n"})
        ctx = SimpleNamespace(
            tree=tree,
            card={"entry_symbols": [{"symbol": selected.value, "file": "missing.py", "line": 1}]},
            logs=[],
            cls=SimpleNamespace(companion_stop=_declaration(), mode="hardware"),
            model=SimpleNamespace(mode="hardware"),
            family="direct",
            companions={"mmcore": _source()},
        )
        gate = Gate("G7", "Native surface")
        check_explicit_source(ctx, gate, selected, None, set())
        self.assertIn("G7.HARDWARE_STOP_UNCONFIRMED", _codes(gate))

    def test_g7_refuses_another_family_before_its_shortcut(self) -> None:
        ctx = SimpleNamespace(
            cls=SimpleNamespace(companion_stop=_declaration(), native="env:Env"),
            family="gymnasium",
            records_native=False,
        )
        gate = Gate("G7", "Native surface")
        _g7(ctx, gate)
        self.assertIn("G7.HARDWARE_STOP_SCOPE", _codes(gate))

    def test_a_class_surface_exempts_the_companion_stop(self) -> None:
        symbol = "stagepkg.stage:Stage"
        tree = tree_with(self, {"stagepkg/stage.py": "class Stage:\n    def move(self):\n        return 1\n"})
        log = RecordLog("class fake")
        log.record("stop_stages", "call", (), {}, phase="estop")
        log.record("stages_settled", "call", (), {}, phase="estop")
        log.found.add("stop_stages")
        log.found.add("stages_settled")
        ctx = SimpleNamespace(
            cls=SimpleNamespace(companion_stop=_declaration(), mode="hardware", native=symbol),
            model=SimpleNamespace(mode="hardware"),
            family="python-object",
            transport_family=False,
            records_native=True,
            tree=tree,
            card={"entry_symbols": [{"symbol": symbol, "file": "stagepkg/stage.py", "confidence": "ast"}]},
            logs=[log],
            companions={"mmcore": _source()},
            backend="fake",
            fake_entry=lambda: None,
        )
        gate = Gate("G7", "Native surface")
        _g7(ctx, gate)
        self.assertNotIn("G7.NOT_UPSTREAM", _codes(gate))
        self.assertNotIn("G7.HARDWARE_STOP_UNCONFIRMED", _codes(gate))


class HardwareStopReviewTests(unittest.TestCase):
    def test_an_ordinary_r1_lock_is_unchanged(self) -> None:
        model = {"authored_by": {"kind": "model", "model_id": "example"}, "reviewed_by": None}
        self.assertIsNone(review_problem(model, [], risk="R1"))
        self.assertIsNone(review_problem(model, [], risk="R1", companion_stop=False))

    def test_a_companion_stop_needs_a_hardware_signature(self) -> None:
        model = {"authored_by": {"kind": "model", "model_id": "example"}, "reviewed_by": None}
        problem = review_problem(model, [], risk="R1", companion_stop=True)
        self.assertIn("companion", problem)
        self.assertIn("reviewed_by", problem)
        signed = {"authored_by": {"kind": "human"}, "reviewed_by": {"scope": "hardware", "name": "a person"}}
        self.assertIsNone(review_problem(signed, [], risk="R0", companion_stop=True))

    def test_any_non_empty_declaration_counts(self) -> None:
        self.assertFalse(declares_companion_stop(SimpleNamespace()))
        self.assertFalse(declares_companion_stop(SimpleNamespace(companion_stop=())))
        self.assertTrue(declares_companion_stop(SimpleNamespace(companion_stop=("malformed",))))

    def test_load_driver_refuses_hardware_until_a_human_signs(self) -> None:
        # A temp fixture, not a shipped package. The shipped wil driver is the snapshot-7
        # bytes and does not declare companion_stop. review_problem still refuses hardware
        # when any non-empty companion_stop is unsigned.
        driver_py = textwrap.dedent('''
            """A fixture driver whose e-stop cites a companion."""

            from mhs.driver import Driver, Limit, estop, read, write

            from .fake import FakeBath


            class Bath(Driver):
                device_id, device_kind = "lab/bath", "thermal.zone"
                mode, risk = "hardware", "R1"
                native = "julabo.julabo:JulaboCF"
                backends = {"hardware": ".native:connect", "fake": ".fake:FakeBath"}
                safe_state = "heater off"
                estop_physical_ref = "front panel stop switch"
                companion_stop = ("stop", "readback")

                @read("temperature", unit="Cel")
                def temperature(self):
                    return self.native.temperature

                @write("setpoint", unit="Cel", limit=Limit(min=-20, max=150, source="vendor_doc", ref="manual.pdf:4"))
                def set_setpoint(self, value):
                    self.native.setpoint = value

                @estop
                def stop(self):
                    self.native.stopped = True
        ''')
        fake_py = textwrap.dedent('''
            class FakeBath:
                def __init__(self, **options):
                    self.options = options
                    self.temperature = 22.0
                    self.setpoint = 20.0
                    self.stopped = False
        ''')
        native_py = textwrap.dedent('''
            def connect(**options):
                from .fake import FakeBath

                bath = FakeBath(**options)
                bath.hardware = True
                return bath
        ''')
        directory = support.temp_dir(self) / "labs" / "example__bath"
        support.write_package(directory, {
            "driver.py": driver_py,
            "fake.py": fake_py,
            "native.py": native_py,
            "driver.lock.json": json.dumps(support.lock_document(reviewed=False)),
        })
        with tempfile.TemporaryDirectory(prefix="mhs-hw-stop-") as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(directory, "hardware", allow_hardware=True, state_dir=state)
        self.assertEqual(caught.exception.reason, "review_required")
        self.assertIn("companion", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
