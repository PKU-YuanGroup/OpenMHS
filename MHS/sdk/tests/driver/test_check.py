"""The acceptance gate ``python -m mhs.driver check`` (WP-06 06b, plan 3.9).

The tutorial package passes; seeded-broken copies of it fail with the named
gate; reversing the declaration order changes nothing; a null driver fails.
"""

from __future__ import annotations

import json
import unittest

from mhs.driver.check import GATES, REPORT_FILE, CheckUsageError, format_report, run_check, stable_digest
from mhs.schema import default_store

from tests.driver import gate_support as gs

ESTOP_BLOCK = "    @estop\n    def stop(self):\n        self.native.emergency_off()\n"
SETPOINT_LIMIT = 'limit=Limit(min=5, max=80, source="vendor_doc", ref="MANUAL.md:9"))\n    def set_setpoint'
TRIM_LIMIT = ('''           limit=Limit(min=[-5, -3], max=[5, 3], names=["front", "back"], source="upstream_code",
                       ref="thermo/controller.py:7"))''')
GO_TO_INPUT = ('input={"target_temperature": Field(description="Target zone temperature",\n'
               '                                               limit=Limit(min=5, max=80, source="vendor_doc", '
               'ref="MANUAL.md:9"))})')


def valid(test: unittest.TestCase, report: dict) -> None:
    problems = default_store().validate(report, "check-report.schema.json")
    test.assertEqual(problems, [], problems)


class TutorialTests(unittest.TestCase):
    """The tutorial thermostat passes every gate, G9 included."""

    def test_the_tutorial_passes_the_whole_gate(self) -> None:
        directory = gs.copy_tutorial(self)
        report = run_check(directory)
        valid(self, report)
        self.assertTrue(report["passed"], report["failed"])
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["evidence_state"], "contract_checked")
        self.assertEqual([item["id"] for item in report["gates"]], [gate_id for gate_id, _ in GATES])
        self.assertTrue(all(item["status"] in ("pass", "warn") for item in report["gates"]))
        # G2 says plainly that this is a synthetic tutorial without an upstream.
        self.assertIn("G2.SYNTHETIC", gs.findings(report, "G2", severity="warning"))
        written = json.loads((directory / REPORT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(written["report_digest"], report["report_digest"])
        valid(self, written)

    def test_the_committed_tutorial_is_current(self) -> None:
        # The committed reference file is fresh (G5) and every other gate but G9 passes in place.
        report = gs.check(gs.TUTORIAL)
        self.assertEqual(report["failed"], [], report)
        self.assertFalse((gs.TUTORIAL / "__pycache__").exists())

    def test_the_tutorial_result_file_validates(self) -> None:
        document = json.loads((gs.TUTORIAL / "RESULT.json").read_text(encoding="utf-8"))
        self.assertEqual(default_store().validate(document, "driver-result.schema.json"), [])
        self.assertEqual(document["status"], "pass")
        self.assertEqual(document["gate"]["failed"], [])

    def test_an_r3_hardware_driver_can_be_checked_on_its_fake(self) -> None:
        # R3 hardware needs an authenticated approval authority; the gate serves the hardware view over the fake and
        # must still exercise it (wave B: a high-voltage supply and an electron microscope failed G6.CRASH).
        directory = gs.broken_copy(self, [("driver.py", 'risk = "R2"', 'risk = "R3"')])
        report = gs.check(directory)
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertNotIn("G6.CRASH", gs.findings(report, "G6"))

    def test_the_gate_approval_authority_serves_only_its_own_fake_backed_r3_view(self) -> None:
        from mhs.driver import check as gate

        self.assertTrue(gate._GATE_APPROVAL_PRINCIPAL.startswith("gate:"))
        attested = gate._gate_approval({"risk_class": "R3", "mode": "hardware", "approvals": []})
        self.assertTrue(attested["verified"])
        self.assertEqual({a["principal"] for a in attested["approvals"]}, {gate._GATE_APPROVAL_PRINCIPAL})

    def test_cli_exit_code_zero_on_the_tutorial(self) -> None:
        directory = gs.copy_tutorial(self)
        done = gs.run_cli("check", str(directory), "--backend", "fake")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PASS: evidence contract_checked", done.stdout)


class StableDigestTests(unittest.TestCase):
    """``RESULT.json`` records a digest that does not change when an unchanged package is checked again."""

    def test_two_runs_differ_in_report_digest_but_not_in_stable_digest(self) -> None:
        directory = gs.copy_tutorial(self)
        first, second = gs.check(directory), gs.check(directory)
        self.assertNotEqual(first["report_digest"], second["report_digest"])        # the clock and the durations
        self.assertEqual(stable_digest(first), stable_digest(second))
        self.assertTrue(stable_digest(first).startswith("sha256:"))
        self.assertNotEqual(stable_digest(first), first["report_digest"])

    def test_it_ignores_the_clock_only(self) -> None:
        report = gs.check(gs.copy_tutorial(self))
        before = json.dumps(report, sort_keys=True)
        clockless = json.loads(before)
        clockless["generated_at"], clockless["duration_ms"] = "2030-01-01T00:00:00.000Z", 1.0
        clockless["report_digest"] = "sha256:" + "0" * 64
        for gate in clockless["gates"]:
            gate["duration_ms"] = 0.0
        self.assertEqual(stable_digest(clockless), stable_digest(report))
        self.assertEqual(json.dumps(report, sort_keys=True), before)                 # the report is not modified
        for edit in (lambda doc: doc["gates"][0].update(status="warn"),
                     lambda doc: doc["gates"][3].update(findings=[{"code": "G4.REF_VALUE", "message": "x",
                                                                   "severity": "warning"}]),
                     lambda doc: doc.update(backend="sim"),
                     lambda doc: doc.update(sdk_version="0.9.1")):
            changed = json.loads(before)
            edit(changed)
            self.assertNotEqual(stable_digest(changed), stable_digest(report))

    def test_a_different_verdict_has_a_different_digest(self) -> None:
        passing = gs.check(gs.copy_tutorial(self))
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "driver.py", ESTOP_BLOCK, "")
        gs.regenerate(directory)
        failing = gs.check(directory)
        self.assertFalse(failing["passed"])
        self.assertNotEqual(stable_digest(passing), stable_digest(failing))

    def test_the_summary_prints_the_digest_of_a_pass_only(self) -> None:
        directory = gs.copy_tutorial(self)
        passing = gs.check(directory)
        lines = format_report(passing).splitlines()
        self.assertEqual(lines[-2], f"gate digest (RESULT.json gate.digest): {stable_digest(passing)}")
        self.assertTrue(lines[-1].startswith("PASS: evidence"), lines[-1])
        gs.edit(directory, "driver.py", ESTOP_BLOCK, "")
        gs.regenerate(directory)
        self.assertNotIn("gate digest", format_report(gs.check(directory)))

    def test_a_warning_gate_names_its_warnings_without_verbose(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit_json(directory, "driver.lock.json", sdk_version="0.0.1")
        report = gs.check(directory)
        self.assertEqual(report["failed"], [])
        text = format_report(report)
        line = next(item for item in text.splitlines() if item.strip().startswith("warnings:"))
        self.assertIn("G2.SDK_VERSION", line)
        self.assertTrue(line.endswith("(--verbose prints the messages)"), line)
        self.assertNotIn("differs from the running SDK", text)
        self.assertIn("differs from the running SDK", format_report(report, verbose=True))

    def test_the_command_line_prints_the_digest_that_a_second_run_reproduces(self) -> None:
        directory = gs.copy_tutorial(self)
        printed = []
        for _ in range(2):
            done = gs.run_cli("check", str(directory), "--backend", "fake")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertTrue(done.stdout.rstrip().endswith("PASS: evidence contract_checked"), done.stdout)
            printed.append([line for line in done.stdout.splitlines() if line.startswith("gate digest")])
        self.assertEqual(len(printed[0]), 1)
        self.assertEqual(printed[0], printed[1])
        written = json.loads((directory / REPORT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(printed[1][0].split()[-1], stable_digest(written))


class OperatorRequiredConformanceTests(unittest.TestCase):
    """G8 serves ``site-limits.example.json``: a driver whose writable parameters all wait for the operator can pass."""

    def all_operator_required(self):
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "driver.py", SETPOINT_LIMIT,
                'limit=Limit.operator_required("the manual lists no range"))\n    def set_setpoint')
        gs.edit(directory, "driver.py", TRIM_LIMIT, '           limit=Limit.operator_required("the manual lists no trim range"))')
        # The configure binding is then the conformance suite's only eligible probe, as it is for a package without
        # an action that takes input (the tutorial's cap.thermal.setpoint.v1 would be preferred otherwise).
        (directory / "fixtures").mkdir()
        (directory / "fixtures" / "conformance.json").write_text('{"probe": "cap.device.configure.v1"}\n',
                                                                 encoding="utf-8")
        gs.regenerate(directory)
        return directory

    def g8_messages(self, report) -> str:
        return " ".join(item["message"] for item in next(g for g in report["gates"] if g["id"] == "G8")["findings"])

    def test_the_example_overlay_fills_the_limits_for_the_conformance_run(self) -> None:
        directory = self.all_operator_required()
        self.assertTrue((directory / "site-limits.example.json").is_file())
        report = gs.check(directory)
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertEqual(gs.findings(report, "G8", severity=None), [])

    def test_without_the_overlay_the_write_is_refused_limits_unset_and_the_finding_says_what_to_add(self) -> None:
        directory = self.all_operator_required()
        (directory / "site-limits.example.json").unlink()
        report = gs.check(directory)
        self.assertEqual(report["failed"], ["G8"])
        messages = self.g8_messages(report)
        self.assertIn("MHS.SAFETY.LIMITS_UNSET", messages)
        self.assertIn("operator_required limits (cap.device.configure.v1 fan_speed, "
                      "cap.device.configure.v1 setpoint, cap.device.configure.v1 zone_trim)", messages)
        self.assertIn("serves site-limits.example.json", messages)

    def test_a_driver_with_sourced_parameters_needs_no_overlay(self) -> None:
        directory = gs.copy_tutorial(self)               # fan_speed waits for the operator, setpoint and trim do not
        (directory / "site-limits.example.json").unlink()
        self.assertEqual(gs.check(directory)["failed"], [])

    def test_an_overlay_that_widens_is_still_refused(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "site-limits.example.json", '"setpoint": {"max": 60,', '"setpoint": {"max": 90,')
        report = gs.check(directory)
        self.assertIn("G6", report["failed"])
        self.assertIn("G6.OVERLAY_INVALID", gs.findings(report, "G6"))


class SeveralOperatorRequiredPathsTests(unittest.TestCase):
    """One input may carry several operator_required paths (a pose has x, y, z): G6 fills them together (WP-11 11b).

    The test overlay of G6 used to fill one path at a time, so the endpoint refused the input for the others
    (``LIMITS_UNSET``) and ``G6.OPERATOR_REQUIRED_OVERLAY`` failed for every such driver.
    """

    GO_TO_TWO = ('input={"target_temperature": Field(description="Target zone temperature",\n'
                 '                                               limit=Limit.operator_required("the manual lists no target"))'
                 ',\n                   "rate": Field(description="Ramp rate", limit=Limit.operator_required('
                 '"the manual lists no ramp rate"))})')
    OVERLAY = {"openmhs": "0.9", "site": "test", "issued_by": {"id": "operator:test"},
               "devices": {"mhs://localhost/tutorial-thermostat": {
                   "cap.thermal.setpoint.v1": {
                       "target_temperature": {"min": 5, "max": 80, "unit": "Cel", "source": "operator", "reason": "test"},
                       "rate": {"min": 0, "max": 10, "unit": "K/min", "source": "operator", "reason": "test"}}}}}

    def two_paths(self):
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "driver.py", GO_TO_INPUT, self.GO_TO_TWO)
        gs.edit(directory, "driver.py", "def go_to(self, target_temperature):", "def go_to(self, target_temperature, rate=None):")
        overlay = json.loads((directory / "site-limits.example.json").read_text(encoding="utf-8"))
        overlay["devices"]["mhs://localhost/tutorial-thermostat"].update(self.OVERLAY["devices"]["mhs://localhost/tutorial-thermostat"])
        (directory / "site-limits.example.json").write_text(json.dumps(overlay, indent=2) + "\n", encoding="utf-8")
        gs.regenerate(directory)
        return directory

    def test_an_input_with_two_operator_required_paths_passes_g6(self) -> None:
        directory = self.two_paths()
        report = gs.check(directory)
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertEqual(gs.findings(report, "G6", severity=None), [])

    def test_the_paths_are_still_refused_without_the_overlay(self) -> None:
        directory = self.two_paths()
        (directory / "site-limits.example.json").unlink()
        report = gs.check(directory)
        self.assertEqual(report["failed"], ["G8"])               # G6 does not need the example overlay

    def test_a_path_the_endpoint_forgets_while_the_others_are_filled_is_found(self) -> None:
        from mhs.driver.behaviour import BehaviourRun
        from mhs.driver.build import hardware_device_id
        from mhs.driver.check import _Context
        from tests.driver.test_behaviour import LyingSession, completed

        directory = self.two_paths()
        ctx = _Context(directory, "fake", None, None, False)
        self.addCleanup(ctx.close)

        def lie(method, result):             # a refusal of LIMITS_UNSET becomes a success
            refused = isinstance(result, dict) and (result.get("error") or {}).get("mhs_code") == "MHS.SAFETY.LIMITS_UNSET"
            return completed(result) if method == "command" and refused else result

        def lying_when_one_path_is_filled(factory):
            def make(**options):
                endpoint = factory(**options)
                site = options.get("site_limits")
                filled = [rules for device in (site or {}).get("devices", {}).values() for rules in device.values()]
                if len(filled) == 1 and len(filled[0]) == 1:     # the overlay of the check "all but this path"
                    endpoint.session = LyingSession(endpoint.session, lie)
                return endpoint

            return make

        run = BehaviourRun(endpoint=lying_when_one_path_is_filled(ctx.endpoint), model=ctx.model,
                           hardware_view=ctx.hardware_endpoint, fixtures=ctx.fixtures,
                           example_overlay=ctx.example_overlay, hardware_id=hardware_device_id(ctx.model),
                           recorded=ctx.records_native)
        errors = [code for code, _message, severity, _path in run.run() if severity == "error"]
        self.assertIn("G6.OPERATOR_REQUIRED_NOT_ENFORCED", errors)


class SeededDefectTests(unittest.TestCase):
    """Each seeded-broken copy fails with the named gate (the reference file is regenerated unless noted)."""

    def broken(self, edits, *, regen: bool = True):
        directory = gs.copy_tutorial(self)
        for file, old, new in edits:
            gs.edit(directory, file, old, new)
        if regen:
            gs.regenerate(directory)
        report = gs.check(directory)
        valid(self, report)
        self.assertFalse(report["passed"])
        self.assertEqual(report["evidence_state"], "none")
        return report

    def test_no_estop_fails_g3(self) -> None:
        report = self.broken([("driver.py", ESTOP_BLOCK, "")])
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.NO_ESTOP", gs.findings(report, "G3"))

    def test_noop_estop_fails_g6(self) -> None:
        report = self.broken([("driver.py", "    def stop(self):\n        self.native.emergency_off()",
                               "    def stop(self):\n        pass")])
        self.assertEqual(report["failed"], ["G6"])
        self.assertIn("G6.ESTOP_NO_NATIVE", gs.findings(report, "G6"))

    def test_garbage_output_fails_g6(self) -> None:
        report = self.broken([("driver.py", 'return {"setpoint": self.native.get_setpoint()}',
                               'return {"setpoint": "hot"}')])
        self.assertIn("G6", report["failed"])
        self.assertIn("G6.NOT_COMPLETED", gs.findings(report, "G6"))

    def test_missing_array_limit_fails_g3(self) -> None:
        report = self.broken([("driver.py", TRIM_LIMIT, ")")])
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.LIMITS_UNSET", gs.findings(report, "G3"))

    def test_limit_key_typo_fails_g3(self) -> None:
        # A limit keyed by a misspelled path ...
        report = self.broken([("driver.py", GO_TO_INPUT,
                               'input={"target_temperature": Field(description="Target zone temperature")},\n'
                               '            limits={"target_temperatur": Limit(min=5, max=80, source="vendor_doc", '
                               'ref="MANUAL.md:9")})')], regen=False)
        self.assertEqual(report["failed"], ["G3"])
        # ... and a misspelled rule member (maxx) never silently drop a bound.
        report = self.broken([("driver.py", SETPOINT_LIMIT, SETPOINT_LIMIT.replace("max=80", "maxx=80"))],
                             regen=False)
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.IMPORT", gs.findings(report, "G3"))

    def test_unsourced_limit_fails_g3(self) -> None:
        report = self.broken([("driver.py", SETPOINT_LIMIT, 'limit=Limit(min=5, max=80))\n    def set_setpoint')])
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.UNSOURCED_LIMIT", gs.findings(report, "G3"))
        # A ref without a source is unsourced too (the source decides what the bound rests on).
        report = self.broken([("driver.py", SETPOINT_LIMIT, SETPOINT_LIMIT.replace('source="vendor_doc", ', ""))])
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.UNSOURCED_LIMIT", gs.findings(report, "G3"))

    def test_operator_limit_in_the_driver_fails_g3(self) -> None:
        report = self.broken([("driver.py", SETPOINT_LIMIT, SETPOINT_LIMIT.replace(
            'source="vendor_doc", ref="MANUAL.md:9"', 'source="operator", ref="MANUAL.md:9"'))])
        self.assertIn("G3.LIMIT_SOURCE", gs.findings(report, "G3"))

    def test_ref_to_a_nonexistent_line_fails_g4(self) -> None:
        report = self.broken([("driver.py", SETPOINT_LIMIT, SETPOINT_LIMIT.replace("MANUAL.md:9", "MANUAL.md:999"))])
        self.assertEqual(report["failed"], ["G4"])
        self.assertIn("G4.REF_LINE", gs.findings(report, "G4"))

    def test_ref_to_a_missing_file_fails_g4(self) -> None:
        report = self.broken([("driver.py", 'ref="thermo/controller.py:39"', 'ref="thermo/nothing.py:39"')])
        self.assertEqual(report["failed"], ["G4"])
        self.assertIn("G4.REF_MISSING", gs.findings(report, "G4"))

    def test_cited_line_without_the_bound_is_a_warning(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "driver.py", SETPOINT_LIMIT, SETPOINT_LIMIT.replace("MANUAL.md:9", "MANUAL.md:10"))
        gs.regenerate(directory)
        report = gs.check(directory)
        self.assertEqual(report["failed"], [])
        self.assertIn("G4.REF_VALUE", gs.findings(report, "G4", severity="warning"))

    def test_stale_reference_fails_g5(self) -> None:
        report = self.broken([("driver.py", 'description="Measured zone temperature"',
                               'description="Measured zone temperature (edited)"')], regen=False)
        self.assertEqual(report["failed"], ["G5"])
        self.assertIn("G5.STALE", gs.findings(report, "G5"))

    def test_fake_attribute_absent_upstream_fails_g7(self) -> None:
        report = self.broken([
            ("fake.py", "    def heater_off(self):", "    def boost(self):\n        self.heating = True\n\n"
                                                       "    def heater_off(self):"),
            ("driver.py", "        self.native.set_setpoint(value)\n",
             "        self.native.set_setpoint(value)\n        self.native.boost()\n"),
        ])
        self.assertEqual(report["failed"], ["G7"])
        self.assertIn("G7.NOT_UPSTREAM", gs.findings(report, "G7"))

    def test_a_fake_method_alone_absent_upstream_fails_g7(self) -> None:
        report = self.broken([("fake.py", "    def heater_off(self):",
                               "    def turbo(self):\n        return True\n\n    def heater_off(self):")])
        self.assertEqual(report["failed"], ["G7"])

    def test_native_must_be_the_cards_ast_entry_symbol(self) -> None:
        directory = gs.copy_tutorial(self)
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        card["entry_symbols"][0]["symbol"] = "thermo.controller:OtherController"
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        self.assertIn("G7.NOT_AN_ENTRY_SYMBOL", gs.findings(gs.check(directory, gates=["G7"]), "G7"))
        card["entry_symbols"][0]["confidence"] = "override"  # confirmed by a maintainer's override: still an error
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        self.assertIn("G7.NOT_AN_ENTRY_SYMBOL", gs.findings(gs.check(directory, gates=["G7"]), "G7"))
        card["entry_symbols"][0]["confidence"] = "recon"  # an unconfirmed entry: only a warning
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        report = gs.check(directory, gates=["G7"])
        self.assertEqual(report["failed"], [])
        self.assertIn("G7.NOT_AN_ENTRY_SYMBOL", gs.findings(report, "G7", severity="warning"))

    def test_an_open_upstream_surface_still_refuses_names_absent_from_the_clone(self) -> None:
        # The upstream class defines __getattr__, so any attribute *may* exist: a name that occurs in the clone is
        # a warning, a name that occurs nowhere in it is still an error.
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "vendor/thermo/controller.py", "    def close(self):",
                "    def __getattr__(self, name):\n        return getattr(self._link, name)\n\n    def close(self):")
        gs.edit(directory, "fake.py", "    def heater_off(self):",
                "    def readline(self):\n        return ''\n\n    def turbo_boost(self):\n        return True\n\n"
                "    def heater_off(self):")
        report = gs.check(directory, gates=["G7"])
        self.assertEqual(report["failed"], ["G7"])
        found = gs.coded(report, "G7")
        self.assertEqual([code for code, _path in found if code == "G7.NOT_UPSTREAM"], ["G7.NOT_UPSTREAM"])
        self.assertIn(("G7.NOT_UPSTREAM", "turbo_boost"), found)
        self.assertIn(("G7.MAYBE_ABSENT", "readline"), found)

    def test_a_python_2_upstream_is_read_leniently_and_named(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "vendor/thermo/controller.py", "    def close(self):\n",
                "    def close(self):\n        print 'closing'\n")
        report = gs.check(directory, gates=["G7"])
        self.assertEqual(report["failed"], [])
        self.assertIn("G7.LEGACY_SOURCE", gs.findings(report, "G7", severity="warning"))

    def test_a_gymnasium_env_whose_base_is_outside_the_clone_has_the_env_interface(self) -> None:
        # A ManiSkill task subclasses BaseEnv, which the clone does not contain: action_space comes from it (wave C).
        directory = gs.copy_tutorial(self)
        (directory / "vendor" / "thermo" / "scene.py").write_text(
            "from mani_skill.envs.sapien_env import BaseEnv\n\n\n"
            "class TableScene(BaseEnv):\n    def evaluate(self):\n        return {}\n", encoding="utf-8")
        (directory / "driver.py").write_text(
            "from mhs.driver import GymnasiumDriver\n\n\n"
            "class Scene(GymnasiumDriver):\n"
            "    device_id = 'scene'\n"
            "    env_id = 'TableScene-v1'\n"
            "    native = 'thermo.scene:TableScene'\n"
            "    backends = {'fake': '.fake:FakeScene'}\n", encoding="utf-8")
        (directory / "fake.py").write_text(
            "class FakeScene:\n"
            "    @property\n    def action_space(self):\n        return None\n\n"
            "    def evaluate(self):\n        return {}\n\n"
            "    def boost(self):\n        return True\n", encoding="utf-8")
        gs.edit_json(directory, "task.json", entry_symbols=[
            {"symbol": "thermo.scene:TableScene", "file": "thermo/scene.py", "line": 4, "confidence": "override"}])
        report = gs.check(directory, gates=["G7"])
        messages = {finding["path"]: (finding["code"], finding["message"]) for gate in report["gates"]
                    if gate["id"] == "G7" for finding in gate["findings"]}
        self.assertEqual(messages["action_space"][0], "G7.MAYBE_ABSENT")
        self.assertIn("Gymnasium environment interface", messages["action_space"][1])
        self.assertEqual(messages["boost"][0], "G7.NOT_UPSTREAM")  # not part of the interface: still an error
        self.assertEqual(report["failed"], ["G7"])

    def test_a_helper_named_like_a_contract_method_still_counts_as_an_action(self) -> None:
        report = self.broken([
            ("driver.py", "    def heater_off(self):\n        self.native.heater_off()\n",
             "    def heater_off(self):\n        self.make_bridge()\n"),
            ("driver.py", "    @estop\n", "    def make_bridge(self):\n        try:\n"
                                          "            self.native.heater_off()\n"
                                          "        except Exception:\n            pass\n\n    @estop\n"),
        ])
        self.assertIn("G6", report["failed"])
        self.assertIn("G6.FAILURE_HIDDEN", gs.findings(report, "G6"))

    def test_swallowed_native_failure_fails_g6(self) -> None:
        report = self.broken([("driver.py", "    def set_setpoint(self, value):\n        self.native.set_setpoint(value)",
                               "    def set_setpoint(self, value):\n        try:\n"
                               "            self.native.set_setpoint(value)\n        except Exception:\n"
                               "            pass")])
        self.assertEqual(report["failed"], ["G6"])
        self.assertIn("G6.FAILURE_HIDDEN", gs.findings(report, "G6"))

    def test_swallowed_failure_followed_by_a_read_back_fails_g6(self) -> None:
        # The failed set_setpoint is swallowed and the old setpoint read back: every native call failing would
        # fail the read-back too, so G6 also fails only the first actuating call.
        report = self.broken([("driver.py", "        self.native.set_setpoint(target_temperature)\n        return",
                               "        try:\n            self.native.set_setpoint(target_temperature)\n"
                               "        except Exception:\n            pass\n        return")])
        self.assertEqual(report["failed"], ["G6"])
        self.assertIn("G6.FAILURE_HIDDEN", gs.findings(report, "G6"))
        self.assertIn("first native call (set_setpoint)", json.dumps(report))

    def test_missing_input_description_fails_g8(self) -> None:
        report = self.broken([("driver.py", 'Field(description="Target zone temperature",', 'Field(')])
        self.assertEqual(report["failed"], ["G8"])
        self.assertIn("G8.NO_DESCRIPTION", gs.findings(report, "G8"))

    def test_conformance_fixtures_are_used(self) -> None:
        directory = gs.copy_tutorial(self)
        (directory / "fixtures").mkdir()
        fixture = {"capabilities": {"cap.thermal.setpoint.v1": {
            "valid": {"target_temperature": 42}, "alternate": {"target_temperature": 43},
            "out_of_envelope": [{"target_temperature": 99}]}}}
        (directory / "fixtures" / "conformance.json").write_text(json.dumps(fixture), encoding="utf-8")
        self.assertEqual(gs.check(directory)["failed"], [])
        # An "out_of_envelope" input the endpoint accepts is a failure, not a silent pass.
        fixture["capabilities"]["cap.thermal.setpoint.v1"]["out_of_envelope"] = [{"target_temperature": 50}]
        (directory / "fixtures" / "conformance.json").write_text(json.dumps(fixture), encoding="utf-8")
        report = gs.check(directory)
        self.assertIn("G6", report["failed"])
        self.assertIn("G6.ENVELOPE_NOT_ENFORCED", gs.findings(report, "G6"))
        (directory / "fixtures" / "conformance.json").write_text("{not json", encoding="utf-8")
        self.assertIn("G1.INVALID_FILE", gs.findings(gs.check(directory, gates=["G1"]), "G1"))

    def test_cli_names_the_failing_gate_with_exit_code_one(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "driver.py", ESTOP_BLOCK, "")
        gs.regenerate(directory)
        done = gs.run_cli("check", str(directory), "--backend", "fake")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("FAIL: G3", done.stdout)
        report = json.loads((directory / REPORT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(report["failed"], ["G3"])


SCENE_UPSTREAM = (
    "class Box:\n"
    "    def __init__(self, low, high, shape):\n"
    "        self.low, self.high, self.shape = low, high, shape\n\n\n"
    "class Scene:\n"
    "    def __init__(self):\n"
    "        self.action_space = Box(low=-0.5, high=0.5, shape=(2,))\n"   # line 8
    "        self.observation_space = Box(low=-10.0, high=10.0, shape=(1,))\n\n"
    "    def reset(self, seed=None, options=None):\n"
    "        return [0.0], {}\n\n"
    "    def step(self, action):\n"
    "        return [0.0], 0.0, False, False, {}\n\n"
    "    def close(self):\n"
    "        pass\n")
SCENE_FAKE = (
    "class Box:\n"
    "    def __init__(self, low, high):\n"
    "        self.low, self.high, self.shape, self.dtype = list(low), list(high), (len(low),), 'float32'\n\n\n"
    "class FakeScene:\n"
    "    def __init__(self, **_options):\n"
    "        self.action_space = Box([-0.5, -0.5], [0.5, 0.5])\n"
    "        self.observation_space = Box([-10.0], [10.0])\n\n"
    "    def reset(self, seed=None, options=None):\n"
    "        return [0.0], {}\n\n"
    "    def step(self, action):\n"
    "        return [0.0], 0.0, False, False, {}\n\n"
    "    def close(self):\n"
    "        pass\n")
SCENE_DRIVER = (
    "from mhs.driver import Action, GymnasiumDriver, Limit\n\n\n"
    "class Scene(GymnasiumDriver):\n"
    "    device_id = 'scene'\n"
    "    env_id = 'Scene-v0'\n"
    "    native = 'thermo.scene:Scene'\n"
    "    backends = {'fake': '.fake:FakeScene'}\n"
    "    safe_state = 'the simulation stops advancing'\n")


class GymnasiumLimitProvenanceTests(unittest.TestCase):
    """Wave D: bounds derived from a fake's action space were published as upstream_code."""

    def scene(self, extra: str = "") -> object:
        directory = gs.copy_tutorial(self)
        (directory / "vendor" / "thermo" / "scene.py").write_text(SCENE_UPSTREAM, encoding="utf-8")
        (directory / "fake.py").write_text(SCENE_FAKE, encoding="utf-8")
        (directory / "driver.py").write_text(SCENE_DRIVER + extra, encoding="utf-8")
        gs.edit_json(directory, "task.json", family="gymnasium", helper="GymnasiumDriver", decision="family-config",
                     safety={"expected_mode": "simulated", "risk_floor": "R0", "limit_hints": []},
                     entry_symbols=[{"symbol": "thermo.scene:Scene", "file": "thermo/scene.py", "line": 6,
                                     "confidence": "override"}])
        gs.regenerate(directory)
        return directory

    @staticmethod
    def action_limit(directory) -> dict:
        reference = json.loads((directory / "reference.json").read_text(encoding="utf-8"))
        step = next(item for item in reference["actions"] if item["cap_id"] == "cap.world.step.v1")
        return next(item for item in step["inputs"] if item["name"] == "action.values")["limit"]

    def test_the_fake_backends_bounds_are_published_without_a_source(self) -> None:
        directory = self.scene()
        report = gs.check(directory, gates=["G3", "G4", "G5"])
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertEqual(gs.coded(report, "G4"), [])
        ref = "action_space of the fake backend .fake:FakeScene"
        self.assertEqual(self.action_limit(directory), {"min": [-0.5, -0.5], "max": [0.5, 0.5], "ref": ref})
        markdown = (directory / "REFERENCE.md").read_text(encoding="utf-8")
        self.assertIn(f"[-0.5, -0.5] .. [0.5, 0.5]; (no source: {ref})", markdown)
        self.assertNotIn("Scene-v0:action_space", markdown)

    def test_a_declared_limit_on_the_step_still_needs_a_source(self) -> None:
        directory = self.scene("    actions = {'cap.world.step.v1': Action(input={'ticks': Limit(max=100, "
                               "reason='a guess')})}\n")
        report = gs.check(directory, gates=["G3"])
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn(("G3.UNSOURCED_LIMIT", "ticks"), gs.coded(report, "G3"))
        self.assertNotIn(("G3.UNSOURCED_LIMIT", "action.values"), gs.coded(report, "G3"))

    def test_g4_preserves_assignment_lines_in_the_cited_span(self) -> None:
        directory = self.scene("    action_space_ref = 'thermo/scene.py:8-9'\n")
        upstream = SCENE_UPSTREAM.replace(
            "        self.action_space = Box(low=-0.5, high=0.5, shape=(2,))",
            "        high = np.ones(2) * 0.5\n"
            "        self.action_space = Box(low=-high, high=high, shape=(2,))")
        (directory / "vendor" / "thermo" / "scene.py").write_text(upstream, encoding="utf-8")
        # The real G4 reader must preserve the two statements. No upstream import is needed.
        report = gs.check(directory, gates=["G3", "G4", "G5"])
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertEqual(gs.coded(report, "G4"), [])

    def test_g4_does_not_reach_outside_the_cited_assignment_span(self) -> None:
        for ref, definition in (("thermo/scene.py:9", "np.ones(2) * 0.5"),
                                ("thermo/scene.py:8-9", "make_bounds(2)")):
            with self.subTest(ref=ref, definition=definition):
                directory = self.scene(f"    action_space_ref = {ref!r}\n")
                upstream = SCENE_UPSTREAM.replace(
                    "        self.action_space = Box(low=-0.5, high=0.5, shape=(2,))",
                    f"        high = {definition}\n"
                    "        self.action_space = Box(low=-high, high=high, shape=(2,))")
                (directory / "vendor" / "thermo" / "scene.py").write_text(upstream, encoding="utf-8")
                report = gs.check(directory, gates=["G4"])
                self.assertIn("G4.REF_VALUE", gs.findings(report, "G4", severity="warning"))

    def test_action_space_ref_is_published_and_checked_by_g4(self) -> None:
        directory = self.scene("    action_space_ref = 'thermo/scene.py:8'\n")
        report = gs.check(directory, gates=["G3", "G4", "G5"])
        self.assertEqual(report["failed"], [], gs.findings(report))
        self.assertEqual(gs.coded(report, "G4"), [])
        self.assertEqual(self.action_limit(directory), {"min": [-0.5, -0.5], "max": [0.5, 0.5],
                                                        "source": "upstream_code", "ref": "thermo/scene.py:8"})
        for ref, expected in (("thermo/scene.py:7", ("G4.REF_VALUE", "warning")),
                              ("thermo/scene.py:99", ("G4.REF_LINE", "error")),
                              ("thermo/missing.py:8", ("G4.REF_MISSING", "error"))):
            with self.subTest(ref=ref):
                directory = self.scene(f"    action_space_ref = {ref!r}\n")
                report = gs.check(directory, gates=["G4"])
                found = [(finding["code"], finding["severity"]) for gate in report["gates"] if gate["id"] == "G4"
                         for finding in gate["findings"]]
                self.assertEqual(found, [expected])


class OrderAndNullTests(unittest.TestCase):
    def test_reversing_the_capability_order_still_passes(self) -> None:
        original = gs.check(gs.copy_tutorial(self))
        directory = gs.copy_tutorial(self)
        gs.reverse_methods(directory)
        gs.regenerate(directory)
        reversed_report = gs.check(directory)
        self.assertEqual(reversed_report["failed"], [], reversed_report)
        self.assertEqual(gs.statuses(reversed_report), gs.statuses(original))
        for gate in ("G3", "G6", "G7", "G8"):
            self.assertEqual(sorted(gs.findings(reversed_report, gate, severity=None)),
                             sorted(gs.findings(original, gate, severity=None)), gate)

    def test_a_null_driver_fails(self) -> None:
        directory = gs.copy_tutorial(self)
        for old, new in (
                ("return self.native.read_temperature()", "return 21.0"),
                ("return self.native.get_setpoint()\n\n    @write", "return 20.0\n\n    @write"),
                ("        self.native.set_setpoint(value)\n", "        pass\n"),
                ("        self.native.set_zone_trim(value[0], value[1])", "        pass"),
                ("        self.native.set_fan_speed(value)", "        pass"),
                ("        self.native.set_setpoint(target_temperature)\n"
                 '        return {"setpoint": self.native.get_setpoint()}',
                 '        return {"setpoint": target_temperature}'),
                ("        self.native.heater_off()\n        return", "        return"),
                ("        self.native.emergency_off()", "        pass"),
                ("        return self.native.lid_is_closed()", "        return True")):
            gs.edit(directory, "driver.py", old, new)
        gs.regenerate(directory)
        report = gs.check(directory)
        self.assertFalse(report["passed"])
        self.assertIn("G6", report["failed"])
        self.assertIn("G8", report["failed"])
        self.assertIn("G6.NO_NATIVE_CALL", gs.findings(report, "G6"))


class LayoutAndLockTests(unittest.TestCase):
    def test_missing_files_fail_g1(self) -> None:
        directory = gs.copy_tutorial(self)
        (directory / "test_driver.py").unlink()
        (directory / "fake.py").rename(directory / "fake_backend.py")
        report = gs.check(directory)
        self.assertIn("G1", report["failed"])
        codes = gs.findings(report, "G1")
        self.assertIn("G1.MISSING_FILE", codes)
        self.assertIn("G1.MISSING_FAKE", codes)

    def test_a_card_for_another_directory_fails_g1(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit_json(directory, "task.json", driver_dir="MHS/drivers/labs/someone__else")
        report = gs.check(directory)
        self.assertEqual(report["failed"], ["G1"])
        self.assertIn("G1.CARD_MISMATCH", gs.findings(report, "G1"))

    def test_a_quarantined_card_fails_g1(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit_json(directory, "task.json", quarantine=True)
        self.assertIn("G1.QUARANTINE", gs.findings(gs.check(directory), "G1"))

    def test_a_real_package_passes_with_a_plain_clone(self) -> None:
        root, directory = gs.real_package(self)
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], report)
        self.assertEqual(report["upstream"]["commit"], "a" * 40)
        self.assertEqual(report["driver_dir"], "MHS/drivers/labs/acme__th1")
        # Not a git checkout: the pinned commit cannot be verified, which is said, not hidden.
        self.assertIn("G2.NOT_GIT", gs.findings(report, "G2", severity="warning"))

    def test_lock_commit_must_equal_the_card(self) -> None:
        root, directory = gs.real_package(self)
        lock = json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))
        lock["upstream"]["commit"] = "b" * 40
        (directory / "driver.lock.json").write_text(json.dumps(lock), encoding="utf-8")
        gs.regenerate(directory)
        report = gs.check(directory, root=root)
        self.assertIn("G2", report["failed"])
        self.assertIn("G2.COMMIT_MISMATCH", gs.findings(report, "G2"))

    def test_lock_backends_must_name_the_backends_of_the_class(self) -> None:
        """`mhs.driver new --like` writes the backends of its template kind; a stale lock fails and the message says what to write."""
        directory = gs.copy_tutorial(self)
        gs.edit_json(directory, "driver.lock.json", backends={"fake": ".fake:FakeExampleDevice"})
        report = gs.check(directory)
        self.assertIn("G2", report["failed"])
        self.assertIn("G2.BACKENDS_DIFFER", gs.findings(report, "G2"))
        message = next(f["message"] for g in report["gates"] if g["id"] == "G2" for f in g["findings"]
                       if f["code"] == "G2.BACKENDS_DIFFER")
        self.assertIn('{"fake": ".fake:FakeController", "hardware": ".native:connect"}', message)
        gs.edit_json(directory, "driver.lock.json", backends={"hardware": ".native:connect", "fake": ".fake:FakeController"})
        self.assertNotIn("G2", gs.check(directory)["failed"])

    def test_a_real_package_needs_an_upstream(self) -> None:
        root, directory = gs.real_package(self)
        gs.edit_json(directory, "task.json", upstream=None, local_path="vendor")
        report = gs.check(directory, root=root)
        self.assertIn("G2.NO_UPSTREAM", gs.findings(report, "G2"))

    def test_task_json_must_equal_the_registry_card(self) -> None:
        root, directory = gs.real_package(self)
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        registry = root / "MHS" / "registry" / "tasks" / "labs"
        registry.mkdir(parents=True)
        card["safety"]["risk_floor"] = "R3"
        (registry / "acme__th1.json").write_text(json.dumps(card), encoding="utf-8")
        report = gs.check(directory, root=root)
        self.assertIn("G1.CARD_EDITED", gs.findings(report, "G1"))

    def test_task_json_is_validated_by_the_registry_schema(self) -> None:
        root, directory = gs.real_package(self)
        schema_dir = root / "MHS" / "registry" / "schema"
        schema_dir.mkdir(parents=True)
        (schema_dir / "taskcard.schema.json").write_text(json.dumps({
            "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "required": ["package_id", "card_version"],
            "properties": {"card_version": {"const": "1.0"}}}), encoding="utf-8")
        report = gs.check(directory, root=root, gates=["G1"])
        self.assertIn("G1.CARD_INVALID", gs.findings(report, "G1"))

    def test_risk_below_the_card_floor_fails_g3(self) -> None:
        root, directory = gs.real_package(self)
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        card["safety"]["risk_floor"] = "R3"
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        report = gs.check(directory, root=root)
        self.assertIn("G3.RISK_FLOOR", gs.findings(report, "G3"))

    def test_a_hardware_card_needs_a_hardware_driver(self) -> None:
        # The round-1 verifier's case: a hardware card (expected_mode hardware, risk_floor R2) built as a simulated
        # driver without a hardware backend or safe state would skip every hardware rule of G3.
        root, directory = gs.real_package(self)
        gs.edit(directory, "driver.py", 'mode = "hardware"', 'mode = "simulated"\n    fidelity = {"engine": "fake", '
                '"fidelity_level": "F0", "determinism": {"kind": "seeded", "seed_control": "none"}, "timestep_ms": 0, '
                '"realtime_factor": 0, "reset": "full", "snapshot_restore": False, "gaps": ["tutorial"]}')
        gs.edit(directory, "driver.py", '"hardware": ".native:connect", ', "")
        gs.edit(directory, "driver.py", '    safe_state = "heater off, fan at idle"\n', "")
        gs.edit(directory, "driver.py", "safe_state=True, ", "")
        gs.regenerate(directory)
        report = gs.check(directory, root=root)
        self.assertIn("G3", report["failed"])
        self.assertIn("G3.MODE_MISMATCH", gs.findings(report, "G3"))
        self.assertEqual(report["evidence_state"], "none")
        for gate_id in ("G5", "G6", "G8"):
            self.assertEqual(gs.statuses(report)[gate_id], "skip", gate_id)

    def test_a_simulated_card_needs_a_simulated_driver(self) -> None:
        directory = gs.copy_tutorial(self)
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        card["safety"]["expected_mode"] = "simulated"
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        report = gs.check(directory, gates=["G3"])
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.MODE_MISMATCH", gs.findings(report, "G3"))
        del card["safety"]["expected_mode"]  # no expected mode on the card: nothing to compare
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        self.assertEqual(gs.check(directory, gates=["G3"])["failed"], [])

    def test_missing_clone_fails(self) -> None:
        root, directory = gs.real_package(self)
        report = gs.check(directory, root=root, clone=root / "nowhere")
        self.assertIn("G1.NO_CLONE", gs.findings(report, "G1"))
        self.assertIn("G4", report["failed"])


class RepoTestGateTests(unittest.TestCase):
    def test_removing_the_harness_call_fails_g9(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "test_driver.py", 'report = check_driver(HERE, backend="fake")', 'report = {"failed": []}')
        report = run_check(directory, write_report=False)
        self.assertEqual(report["failed"], ["G9"])
        self.assertIn("G9.NO_HARNESS", gs.findings(report, "G9"))

    def test_a_failing_package_test_fails_g9(self) -> None:
        directory = gs.copy_tutorial(self)
        gs.edit(directory, "test_driver.py", "\n\nif __name__",
                "\n\n    def test_extra(self) -> None:\n        self.fail('seeded failure')\n\n\nif __name__")
        report = run_check(directory, write_report=False)
        self.assertEqual(report["failed"], ["G9"])
        self.assertIn("G9.FAILED", gs.findings(report, "G9"))

    def test_partial_runs_never_claim_evidence(self) -> None:
        report = gs.check(gs.copy_tutorial(self), gates=["G1", "G2"])
        valid(self, report)
        self.assertTrue(report["passed"])
        self.assertEqual(report["evidence_state"], "none")
        skipped = [item for item in report["gates"] if item["id"] not in ("G1", "G2")]
        self.assertTrue(all(item["status"] == "skip" and not item["required"] for item in skipped))

    def test_usage_errors(self) -> None:
        directory = gs.copy_tutorial(self)
        with self.assertRaises(CheckUsageError):
            run_check(directory, backend="hardware")
        with self.assertRaises(CheckUsageError):
            run_check(directory / "missing")
        with self.assertRaises(CheckUsageError):
            run_check(directory, gates=["G10"])


if __name__ == "__main__":
    unittest.main()
