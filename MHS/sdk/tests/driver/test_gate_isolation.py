"""The gate fails closed: package code cannot exit it with status 0, switch it off, or reach hardware (WP-06 06b fix).

* ``SystemExit`` from package code is a finding of the running gate; ``os._exit``
  or a hang in the gate's child process is ``<gate>.ABORTED`` / ``<gate>.TIMEOUT``
  and the command line exits 1 with a written report.
* G9 requires the test runner's own result, so a ``test_driver.py`` that exits
  early never passes.
* Patching ``mhs`` from package code is ``G3.GATE_TAMPERED``; the static scan
  (``G3.FORBIDDEN``) refuses the obvious ways in, and the parent repeats it.
* A hardware driver's fake backend is never the upstream ``native`` class.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Iterable
from unittest import mock

from mhs import canonical
from mhs.driver.check import (REPORT_FILE, CheckUsageError, _enforce, _identity, _read_progress, _report, _verified,
                              run_check, run_check_isolated, static_findings)
from mhs.driver.package import find_root
from mhs.schema import default_store

from tests.driver import gate_support as gs

#: Module names built at run time (not from constants), so only the runtime integrity check can see these patches.
PATCH_GATE = ("import importlib as _il\n_c = _il.import_module('.'.join(('mhs', 'driver', 'check')))\n"
              "setattr(_c, '_g' + '3', lambda ctx, gate: setattr(ctx, 'g3_ok', True))\n"
              "setattr(_c, '_g' + '6', lambda ctx, gate: None)\nsetattr(_c, '_g' + '8', lambda ctx, gate: None)\n")
PATCH_BEHAVIOUR = ("import importlib as _il\n_b = _il.import_module('.'.join(('mhs', 'driver', 'behaviour')))\n"
                   "setattr(getattr(_b, 'BehaviourRun'), 'run', lambda self: [])\n")
FAKE_END = "        return self.lid\n"
HEATER_OFF = "    def heater_off(self):\n        self.heating = False"


def valid(test: unittest.TestCase, report: dict) -> None:
    test.assertEqual(default_store().validate(report, "check-report.schema.json"), [])


def gate_of(report: dict, gate_id: str) -> dict:
    return next(item for item in report["gates"] if item["id"] == gate_id)


class StaticScanTests(unittest.TestCase):
    """G3 FORBIDDEN: what package code may not do, read from the sources with ast (nothing is imported)."""

    def scan(self, code: str, file: str = "driver.py") -> list[str]:
        directory = gs.temp_root(self)
        (directory / file).write_text(code, encoding="utf-8")
        return [message for _code, message, _path in static_findings(directory, {})]

    def test_the_tutorial_is_clean(self) -> None:
        self.assertEqual(static_findings(gs.TUTORIAL), [])

    def test_forbidden_constructs(self) -> None:
        forbidden = {
            "import mhs.driver.check": "mhs.driver.check",
            "from mhs.driver import check": "mhs.driver.check",
            "from mhs.driver.behaviour import BehaviourRun": "mhs.driver.behaviour",
            "from mhs.conformance.inprocess import Harness": "mhs.conformance",
            "from mhs import server": "mhs.server",
            "import mhs._server.strict": "mhs._server",
            "from mhs.testing import recorder": "mhs.testing.recorder",
            "import builtins": "builtins",
            "import gc": "gc",
            "import ctypes": "ctypes",
            "import sys\nsys.exit(0)": "sys.exit",
            "from sys import exit": "sys.exit",
            "import os\nos._exit(0)": "os._exit",
            "raise SystemExit(0)": "SystemExit",
            "exit()": "exit()",
            "import sys\nx = sys.modules": "sys.modules",
            "import sys\nf = sys._getframe(1)": "sys._getframe",
            "def f(frame):\n    return frame.f_globals": "f_globals",
            "def f(g):\n    g.__code__ = None": "__code__",
            "import mhs.driver.base\nmhs.driver.base.Driver.read = None": "assigns into the SDK",
            "from mhs.driver import Driver\nsetattr(Driver, 'read', None)": "setattr",
            "from unittest import mock\nmock.patch('mhs.driver.check._g3').start()": "mock.patch",
            "from mhs.driver import Driver\nDriver.backends['fake'] = None": "assigns into the SDK",
            # The forged-report probe: argv (the gate child's --result path), reflected exits, __import__ and
            # imports of the gate spelled in constants.
            "import sys\nresult = sys.argv[-1]": "sys.argv",
            "from sys import argv": "sys.argv",
            "import os as _o\ngetattr(_o, '_ex' + 'it')(0)": "os._exit (through getattr())",
            "import sys\ngetattr(sys, f'ex{\"it\"}')(0)": "sys.exit (through getattr())",
            "import os\nname = 'x'\ngetattr(os, name)": "computed attribute name",
            "import builtins as b": "builtins",
            "__import__('builtins')": "__import__",
            "import importlib\nimportlib.import_module('mhs.driver.check')": "mhs.driver.check",
            "import importlib as _il\n_il.import_module('mhs.driver.' + 'behaviour')": "mhs.driver.behaviour",
            "from importlib import import_module as im\nim('mhs.' + 'server')": "mhs.server",
        }
        for code, expected in forbidden.items():
            with self.subTest(code=code):
                messages = self.scan(code)
                self.assertTrue(messages, code)
                self.assertTrue(any(expected in message for message in messages), messages)

    def test_ordinary_driver_code_is_allowed(self) -> None:
        allowed = [
            "from mhs.driver import Driver, Field, Limit, action, estop, read, write\n"
            "class D(Driver):\n    native = 'a.b:C'\n    def x(self):\n        self.native.exit()\n",
            "from mhs.testing import Recorder, check_driver, log_of\n",
            "from mhs.bridge.serial import FakeSerial\nclass F(FakeSerial):\n    pass\n",
            "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent))\n",
            "import unittest\nif __name__ == '__main__':\n    import sys\n    sys.exit(unittest.main())\n",
            "from unittest import mock\nfrom .fake import Fake\nmock.patch.object(Fake, 'x', 1)\n",
            "import sys\nfrozen = getattr(sys, 'frozen', False)\n",
            "import importlib\nserial = importlib.import_module('serial')\n",
            "def f(native, name):\n    return getattr(native, name)\n",
        ]
        for code in allowed:
            with self.subTest(code=code):
                self.assertEqual(self.scan(code), [])

    def test_the_synthetic_clone_is_not_scanned(self) -> None:
        directory = gs.copy_tutorial(self)
        (directory / "vendor" / "thermo" / "tool.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        self.assertEqual(static_findings(directory), [])
        (directory / "helper.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        self.assertEqual([path for _code, _message, path in static_findings(directory)], ["helper.py"])

    def test_unparsable_package_code_fails(self) -> None:
        self.assertTrue(any("cannot be parsed" in message for message in self.scan("def (:\n", "helper.py")))


class SystemExitTests(unittest.TestCase):
    """In-process: SystemExit raised by package code is a finding of the running gate, never an exit."""

    def test_plain_systemexit_in_driver_fails_g3(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", gs.ESTOP_BLOCK, ""),
                                          ("driver.py", gs.DRIVER_IMPORT, "raise SystemExit(0)\n" + gs.DRIVER_IMPORT)],
                                   regen=False)
        report = gs.check(directory)
        valid(self, report)
        self.assertEqual(report["failed"], ["G3"])
        codes = gs.findings(report, "G3")
        self.assertIn("G3.FORBIDDEN", codes)
        self.assertIn("G3.IMPORT", codes)

    def test_hidden_exit_in_driver_fails_g3(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", gs.DRIVER_IMPORT, gs.EVADE_EXIT + gs.DRIVER_IMPORT)],
                                   regen=False)
        report = gs.check(directory)
        self.assertEqual(report["failed"], ["G3"])
        self.assertEqual(gs.findings(report, "G3"), ["G3.IMPORT"])
        self.assertIn("SystemExit", gate_of(report, "G3")["findings"][0]["message"])

    def test_hidden_exit_at_the_end_of_fake_fails_g3(self) -> None:
        directory = gs.broken_copy(self, [("fake.py", FAKE_END, FAKE_END + "\n\n" + gs.EVADE_EXIT)], regen=False)
        report = gs.check(directory)
        self.assertIn("G3", report["failed"])
        self.assertIn("G3.BACKEND_IMPORT", gs.findings(report, "G3"))
        self.assertEqual(report["evidence_state"], "none")

    def test_hidden_exit_in_a_fake_method_fails(self) -> None:
        directory = gs.broken_copy(self, [("fake.py", HEATER_OFF,
                                           "    def heater_off(self):\n" + gs.indent(gs.EVADE_EXIT))], regen=False)
        report = gs.check(directory)
        self.assertIn("G6", report["failed"])
        self.assertFalse(report["passed"])


    def test_a_gate_that_exits_is_a_crash_of_that_gate(self) -> None:
        import mhs.driver.check as check

        with mock.patch.object(check, "_g4", side_effect=SystemExit(0)):
            report = gs.check(gs.copy_tutorial(self), gates=["G1", "G3", "G4"])
        self.assertEqual(report["failed"], ["G4"])
        self.assertIn("SystemExit", json.dumps(gate_of(report, "G4")))


class ChildProcessTests(unittest.TestCase):
    """The command line runs the gates in a child process and exits 0 only on a verified passing report."""

    def test_os_exit_at_import_fails_g3_with_a_report(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", gs.DRIVER_IMPORT, gs.EVADE_OS_EXIT + gs.DRIVER_IMPORT)],
                                   regen=False)
        done = gs.run_cli("check", str(directory), "--backend", "fake")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("FAIL: G3", done.stdout)
        report = json.loads((directory / REPORT_FILE).read_text(encoding="utf-8"))
        valid(self, report)
        self.assertEqual(report["failed"], ["G3"])
        self.assertEqual(gs.findings(report, "G3"), ["G3.ABORTED"])
        self.assertEqual(report["evidence_state"], "none")

    def test_os_exit_in_a_gate_keeps_the_finished_gates(self) -> None:
        directory = gs.broken_copy(self, [("fake.py", HEATER_OFF,
                                           "    def heater_off(self):\n" + gs.indent(gs.EVADE_OS_EXIT))], regen=False)
        report, _output = run_check_isolated(directory, write_report=False)
        valid(self, report)
        self.assertEqual(report["failed"], ["G6"])
        self.assertIn("G6.ABORTED", gs.findings(report, "G6"))
        statuses = gs.statuses(report)
        for gate_id in ("G1", "G3", "G4", "G5"):
            self.assertIn(statuses[gate_id], ("pass", "warn"), gate_id)
        for gate_id in ("G7", "G8", "G9"):
            self.assertEqual(statuses[gate_id], "skip", gate_id)

    def test_a_hanging_package_times_out(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", gs.DRIVER_IMPORT,
                                           "import time\ntime.sleep(60)\n" + gs.DRIVER_IMPORT)], regen=False)
        report, _output = run_check_isolated(directory, write_report=False, timeout_s=3)
        valid(self, report)
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.TIMEOUT", gs.findings(report, "G3"))

    def test_the_parent_repeats_the_static_scan(self) -> None:
        report = run_check(gs.copy_tutorial(self), gates=["G1", "G3"], write_report=False)
        self.assertTrue(report["passed"])
        merged = _enforce(report, None, gs.TUTORIAL, None,
                               [("G3.FORBIDDEN", "driver.py:1: imports gc, an interpreter internal", "driver.py")])
        valid(self, merged)
        self.assertEqual(merged["failed"], ["G3"])
        self.assertEqual(merged["evidence_state"], "none")
        self.assertIs(_enforce(report, None, gs.TUTORIAL, None, []), report)
        # A tamper event the child reported is enforced even when the child's own report lacks it, once.
        tamper = ("G3.GATE_TAMPERED", "the SDK changed while package code ran: mhs.driver.check._g6", "driver.py")
        merged = _enforce(report, None, gs.TUTORIAL, None, [tamper])
        self.assertEqual(merged["failed"], ["G3"])
        again = _enforce(merged, None, gs.TUTORIAL, None, [tamper[:1] + ("another wording",) + tamper[2:]])
        self.assertIs(again, merged)
        # A gate the child left "pass" although it has an error finding fails in the parent's report.
        lying = json.loads(json.dumps(report))
        lying["gates"][0]["findings"].append({"code": "G1.CLONE_WRITTEN", "message": "x", "severity": "error"})
        enforced = _enforce(lying, None, gs.TUTORIAL, None, [])
        self.assertEqual(enforced["failed"], ["G1"])
        valid(self, enforced)

    def test_the_parent_restores_a_static_scan_the_child_lost(self) -> None:
        # driver.py imports gc (forbidden) and switches the child's scan off: the parent's own scan still reports it.
        patch = ("import gc\nimport importlib as _il\n_c = _il.import_module('mhs.driver.' + 'check')\n"
                 "setattr(_c, 'static_' + 'findings', lambda *a, **k: [])\n")
        directory = gs.broken_copy(self, [("driver.py", gs.DRIVER_IMPORT, patch + gs.DRIVER_IMPORT)], regen=False)
        report, _output = run_check_isolated(directory, write_report=False)
        self.assertIn("G3", report["failed"])
        codes = gs.findings(report, "G3")
        self.assertIn("G3.FORBIDDEN", codes)
        self.assertIn("G3.GATE_TAMPERED", codes)

    def test_only_a_verified_report_is_accepted(self) -> None:
        report = run_check(gs.copy_tutorial(self), gates=["G1"], write_report=False)
        self.assertIsNotNone(_verified({"report": report})[0])
        forged = dict(report, failed=[], passed=True, evidence_state="contract_checked")
        self.assertIsNone(_verified({"report": forged})[0])            # the digest no longer matches
        forged = signed(forged)
        self.assertIsNotNone(_verified({"report": forged})[0])         # bare: a re-signed forgery is well-formed
        self.assertIsNone(_verified({"report": dict(report, gates=report["gates"][:8])})[0])
        # Gates out of order are refused even when the report is re-signed.
        reordered = signed(dict(report, gates=[report["gates"][1], report["gates"][0]] + report["gates"][2:]))
        self.assertIsNone(valid_or_none(self, reordered))
        self.assertIn("in order", _verified({"report": reordered})[1])
        self.assertIsNone(_verified(None)[0])


def signed(report: dict) -> dict:
    """``report`` with a fresh ``report_digest`` (what a forger who knows the digest rule would write)."""
    unsigned = {key: value for key, value in report.items() if key != "report_digest"}
    return dict(unsigned, report_digest=canonical.digest(unsigned))


def valid_or_none(test: unittest.TestCase, report: dict) -> dict | None:
    valid(test, report)
    return _verified({"report": report})[0]


def gate_child(report: dict | None = None, events: Iterable[dict] = (), returncode: int = 0,
               document: dict | None = None):
    """A ``subprocess.run`` stand-in that plays the gate child: it writes ``--result`` and ``--progress`` and exits."""
    real_run = subprocess.run

    def run(command, **kwargs):
        if "mhs.driver._gate" not in command:
            return real_run(command, **kwargs)
        with open(command[command.index("--result") + 1], "w", encoding="utf-8") as handle:
            json.dump(document if document is not None else {"report": report}, handle)
        with open(command[command.index("--progress") + 1], "w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")
        return subprocess.CompletedProcess(command, returncode, b"", b"")

    return run


class VerifiedReportTests(unittest.TestCase):
    """The CLI parent accepts only the gate child's own report of a full run of this package (cheap hardening)."""

    @classmethod
    def setUpClass(cls) -> None:
        holder = tempfile.TemporaryDirectory(prefix="mhs-gate-test-")
        cls.addClassCleanup(holder.cleanup)
        cls.directory = gs.copy_tutorial(None, parent=Path(holder.name)).resolve()
        cls.events: list[dict] = []
        # What the gate child computes and streams for the tutorial (G9 included).
        cls.report = run_check(cls.directory, write_report=False, progress=cls.events.append)
        cls.progress_file = Path(holder.name) / "progress.jsonl"
        cls.progress_file.write_text("".join(json.dumps(event) + "\n" for event in cls.events), encoding="utf-8")
        card = json.loads((cls.directory / "task.json").read_text(encoding="utf-8"))
        cls.identity = _identity(card, cls.directory, find_root(cls.directory), "fake")

    def progress(self, events: Iterable[dict] | None = None) -> tuple:
        if events is None:
            stage, finished, _tampered = _read_progress(self.progress_file)
            return stage, finished
        path = gs.temp_root(self) / "progress.jsonl"
        path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        stage, finished, _tampered = _read_progress(path)
        return stage, finished

    def accepted(self, report: dict, progress: tuple | None = None) -> tuple:
        return _verified({"report": report}, identity=self.identity,
                         progress=self.progress() if progress is None else progress)

    def test_the_childs_own_report_is_accepted(self) -> None:
        self.assertTrue(self.report["passed"], self.report["failed"])
        self.assertEqual(self.accepted(self.report)[1], "")
        with mock.patch.object(check_module().subprocess, "run", side_effect=gate_child(self.report, self.events)):
            report, _output = run_check_isolated(self.directory, write_report=False)
        self.assertTrue(report["passed"], report["failed"])
        self.assertEqual(report["evidence_state"], "contract_checked")

    def test_a_report_counts_only_from_a_child_that_exited_cleanly(self) -> None:
        with mock.patch.object(check_module().subprocess, "run",
                               side_effect=gate_child(self.report, self.events, returncode=1)):
            report, _output = run_check_isolated(self.directory, write_report=False)
        valid(self, report)
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.ABORTED", gs.findings(report, "G3"))

    def test_a_report_of_another_package_or_run_is_refused(self) -> None:
        # The round-1 forged report: driver_dir "x", no package id, no upstream, re-signed.
        cases = {
            "driver_dir": signed(dict(self.report, driver_dir="x")),
            "package_id": signed({key: value for key, value in self.report.items() if key != "package_id"}),
            "backend": signed(dict(self.report, backend="sim")),
            "upstream": signed(dict(self.report, upstream={"commit": "a" * 40})),
            "required": signed(dict(self.report, gates=self.report["gates"][:8] + [
                dict(self.report["gates"][8], status="skip", required=False)])),
            "evidence": signed(dict(self.report, evidence_state="none")),
        }
        for label, forged in cases.items():
            with self.subTest(label):
                self.assertIsNotNone(valid_or_none(self, forged))  # well-formed and re-signed ...
                self.assertIsNone(self.accepted(forged)[0])        # ... but not this run's report
        with mock.patch.object(check_module().subprocess, "run",
                               side_effect=gate_child(cases["driver_dir"], self.events)):
            report, _output = run_check_isolated(self.directory, write_report=False)
        valid(self, report)
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("is not the gate's own", json.dumps(gate_of(report, "G3")))

    def test_the_progress_stream_must_back_the_report(self) -> None:
        g3 = next(event["gate"] for event in self.events if event.get("gate", {}).get("id") == "G3")
        failing_g3 = dict(g3, status="fail", findings=[{"code": "G3.NO_ESTOP", "message": "x", "severity": "error"}])
        cases = {
            "ended at the import": [{"stage": "load"}],
            "no report stage": [event for event in self.events if event.get("stage") != "report"],
            "a gate without a result": [event for event in self.events if event.get("gate", {}).get("id") != "G6"],
            "a gate that failed": [dict(event, gate=failing_g3) if event.get("gate", {}).get("id") == "G3" else event
                                   for event in self.events],
        }
        for label, events in cases.items():
            with self.subTest(label):
                report, why = self.accepted(self.report, self.progress(events))
                self.assertIsNone(report)
                self.assertTrue(why)
        # A gate that failed in the stream keeps its error codes in the report, even when it is reported failed,
        # and an error the report turned into a warning is lost too.
        failed = self.progress(cases["a gate that failed"])
        lying = signed(dict(self.report, passed=False, failed=["G3"], evidence_state="none", gates=[
            dict(item, status="fail") if item["id"] == "G3" else item for item in self.report["gates"]]))
        self.assertIn("lost the error findings", self.accepted(lying, failed)[1])
        downgraded = signed(dict(lying, gates=[
            dict(item, findings=[{"code": "G3.NO_ESTOP", "message": "x", "severity": "warning"}])
            if item["id"] == "G3" else item for item in lying["gates"]]))
        self.assertIsNotNone(valid_or_none(self, downgraded))
        self.assertIn("lost the error findings", self.accepted(downgraded, failed)[1])
        # A truncated finding list cannot be compared code by code; the gate's status still can.
        truncated = signed(dict(self.report, gates=[
            dict(item, status="warn", findings=[{"code": "G3.TRUNCATED", "message": "x", "severity": "warning"}])
            if item["id"] == "G3" else item for item in self.report["gates"]]))
        self.assertIsNotNone(valid_or_none(self, truncated))
        self.assertIn("failed in the progress stream", self.accepted(truncated, failed)[1])
        with mock.patch.object(check_module().subprocess, "run", side_effect=gate_child(self.report, [{"stage": "load"}])):
            report, _output = run_check_isolated(self.directory, write_report=False)
        self.assertIn("G3.ABORTED", gs.findings(report, "G3"))

    def test_tamper_events_of_the_progress_stream_are_enforced(self) -> None:
        events = self.events + [{"tampered": ["mhs.driver.check._g6"]}]
        with mock.patch.object(check_module().subprocess, "run", side_effect=gate_child(self.report, events)):
            report, _output = run_check_isolated(self.directory, write_report=False)
        valid(self, report)
        self.assertEqual(report["failed"], ["G3"])
        self.assertIn("G3.GATE_TAMPERED", gs.findings(report, "G3"))
        self.assertIn("mhs.driver.check._g6", json.dumps(gate_of(report, "G3")))
        self.assertEqual(report["evidence_state"], "none")

    def test_a_usage_error_of_the_child_is_a_usage_error(self) -> None:
        with mock.patch.object(check_module().subprocess, "run",
                               side_effect=gate_child(document={"usage_error": "unknown gate ids ['G10']"})):
            with self.assertRaises(CheckUsageError):
                run_check_isolated(self.directory, write_report=False)

    def test_the_report_fails_every_gate_with_an_error_finding(self) -> None:
        gates = [dict(item, findings=list(item["findings"])) for item in self.report["gates"]]
        gates[0]["findings"].append({"code": "G1.CLONE_WRITTEN", "message": "x", "severity": "error"})
        self.assertEqual(gates[0]["status"], "pass")
        report = _report(None, self.directory, None, "fake", gates, duration_ms=1.0, complete=True)
        valid(self, report)
        self.assertEqual(report["failed"], ["G1"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["evidence_state"], "none")
        self.assertEqual(gate_of(report, "G1")["status"], "fail")


def check_module():
    import mhs.driver.check as check

    return check


class RepoTestExitTests(unittest.TestCase):
    """G9: a test_driver.py that exits early never passes."""

    def test_systemexit_at_import_of_test_driver_fails_g9(self) -> None:
        directory = gs.broken_copy(self, [
            ("test_driver.py", "HERE = Path", "import os\nif os.environ.get('MHS_DRIVER_GATE_INNER'):\n"
                                              + gs.indent(gs.EVADE_EXIT, 4) + "HERE = Path"),
            ("test_driver.py", '        self.assertEqual(report["failed"], [], report)',
             '        self.assertEqual(report["failed"], [], report)\n        self.fail("never ran")')], regen=False)
        report = run_check(directory, write_report=False)
        self.assertEqual(report["failed"], ["G9"])
        self.assertIn("G9.FAILED", gs.findings(report, "G9"))

    def test_os_exit_inside_a_test_fails_g9(self) -> None:
        directory = gs.broken_copy(self, [("test_driver.py", '        report = check_driver(HERE, backend="fake")',
                                           gs.indent(gs.EVADE_OS_EXIT) + '        report = check_driver(HERE, '
                                                                         'backend="fake")')], regen=False)
        report = run_check(directory, write_report=False)
        self.assertEqual(report["failed"], ["G9"])
        self.assertIn("G9.NO_RESULT", gs.findings(report, "G9"))

    def test_g9_needs_a_passing_runner_result(self) -> None:
        import mhs.driver.check as check

        directory = gs.copy_tutorial(self)
        real_run = subprocess.run

        def child(result: object, returncode: int = 0):
            def run(command, **kwargs):
                if "mhs.driver._repotests" not in command:
                    return real_run(command, **kwargs)
                if result is not None:
                    path = command[command.index("--result") + 1]
                    with open(path, "w", encoding="utf-8") as handle:
                        json.dump(result, handle)
                return subprocess.CompletedProcess(command, returncode, b"", b"runner output")
            return run

        cases = [({"ok": True, "tests_run": 2}, 0, []), ({"ok": False, "tests_run": 2}, 0, ["G9.FAILED"]),
                 ({"ok": True, "tests_run": 0}, 0, ["G9.FAILED"]), (None, 0, ["G9.NO_RESULT"]),
                 ({"ok": True, "tests_run": 1}, 1, ["G9.FAILED"])]
        for result, returncode, expected in cases:
            with self.subTest(result=result, returncode=returncode):
                with mock.patch.object(check.subprocess, "run", side_effect=child(result, returncode)):
                    report = gs.check(directory, gates=["G3", "G9"])
                self.assertEqual(gs.findings(report, "G9"), expected)

    def test_the_runner_result_file(self) -> None:
        directory = gs.temp_root(self)
        result = directory / "result.json"
        cases = {
            "passing": ("import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n",
                        0, {"ok": True, "tests_run": 1}),
            "exit at import": ("import sys as _s\ngetattr(_s, 'ex' + 'it')(0)\n", 1, {"ok": False}),
            "no test": ("x = 1\n", 1, {"ok": False, "tests_run": 0}),
        }
        env = dict(os.environ, PYTHONPATH=str(gs.SRC), PYTHONDONTWRITEBYTECODE="1")
        for label, (code, status, expected) in cases.items():
            with self.subTest(label):
                (directory / "test_x.py").write_text(code, encoding="utf-8")
                result.unlink(missing_ok=True)
                done = subprocess.run([sys.executable, "-m", "mhs.driver._repotests", str(directory / "test_x.py"),
                                       "--result", str(result)], capture_output=True, text=True, timeout=120, env=env,
                                      cwd=str(directory), stdin=subprocess.DEVNULL)
                self.assertEqual(done.returncode, status, done.stderr)
                outcome = json.loads(result.read_text(encoding="utf-8"))
                for key, value in expected.items():
                    self.assertEqual(outcome.get(key), value, outcome)


class TamperTests(unittest.TestCase):
    """Patching the gate or the runtime from package code is G3.GATE_TAMPERED, and the real gates still run."""

    def setUp(self) -> None:
        # The seeded drivers patch this very process (the in-process gate imports them): undo it afterwards.
        import mhs.driver.behaviour as behaviour
        import mhs.driver.check as check

        saved = {name: getattr(check, name) for name in ("_g3", "_g6", "_g8")}
        run = behaviour.BehaviourRun.run

        def restore() -> None:
            for name, value in saved.items():
                setattr(check, name, value)
            behaviour.BehaviourRun.run = run

        self.addCleanup(restore)

    def test_patching_the_gate_functions_fails_g3(self) -> None:
        # The verifier's case: an R2 hardware driver without @estop switches G3/G6/G8 off at import.
        directory = gs.broken_copy(self, [("driver.py", gs.ESTOP_BLOCK, ""),
                                          ("driver.py", gs.DRIVER_IMPORT, PATCH_GATE + gs.DRIVER_IMPORT)],
                                   regen=False)
        report = gs.check(directory)
        valid(self, report)
        self.assertIn("G3", report["failed"])
        codes = gs.findings(report, "G3")
        self.assertIn("G3.GATE_TAMPERED", codes)
        self.assertIn("G3.NO_ESTOP", codes)       # the gate functions were bound before the import
        self.assertNotIn("G3.FORBIDDEN", codes)   # string-built names: only the runtime check sees it
        self.assertEqual(report["evidence_state"], "none")

    def test_patching_the_behaviour_checks_fails_g3(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", gs.DRIVER_IMPORT, PATCH_BEHAVIOUR + gs.DRIVER_IMPORT)],
                                   regen=False)
        report = gs.check(directory)
        self.assertIn("G3.GATE_TAMPERED", gs.findings(report, "G3"))
        self.assertIn("BehaviourRun", " ".join(item["message"] for item in gate_of(report, "G3")["findings"]))

    def test_the_cli_refuses_a_patched_gate(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", gs.ESTOP_BLOCK, ""),
                                          ("driver.py", gs.DRIVER_IMPORT,
                                           "import mhs.driver.check as _c\n"
                                           "_c._g3 = lambda ctx, gate: setattr(ctx, 'g3_ok', True)\n"
                                           + gs.DRIVER_IMPORT)], regen=False)
        done = gs.run_cli("check", str(directory), "--backend", "fake", "--json")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        self.assertIn("G3", report["failed"])
        codes = gs.findings(report, "G3")
        for code in ("G3.FORBIDDEN", "G3.GATE_TAMPERED", "G3.NO_ESTOP"):
            self.assertIn(code, codes)


    def test_the_cli_refuses_a_gate_whose_bookkeeping_is_patched(self) -> None:
        # Gate.error and Gate.settle no-ops would hide every finding in the child; the parent still sees the tamper
        # event and the error finding, and the report fails.
        patch = ("import importlib as _il\n_c = _il.import_module('mhs.driver.' + 'check')\n"
                 "setattr(_c.Gate, 'er' + 'ror', lambda self, *a, **k: None)\n"
                 "setattr(_c.Gate, 'set' + 'tle', lambda self: None)\n")
        directory = gs.broken_copy(self, [("driver.py", gs.ESTOP_BLOCK, ""),
                                          ("driver.py", gs.DRIVER_IMPORT, patch + gs.DRIVER_IMPORT)], regen=False)
        report, _output = run_check_isolated(directory, write_report=False)
        valid(self, report)
        self.assertFalse(report["passed"])
        self.assertIn("G3", report["failed"])
        self.assertIn("G3.GATE_TAMPERED", gs.findings(report, "G3"))


class FakeBackendTests(unittest.TestCase):
    """A hardware driver's fake/sim backend is the package's own fake, never the upstream hardware class."""

    def test_the_native_class_as_fake_fails_g3_and_is_never_run(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", '"fake": ".fake:FakeController"',
                                           '"fake": "thermo.controller:Controller"')])
        report = gs.check(directory)
        self.assertIn("G3.FAKE_IS_NATIVE", gs.findings(report, "G3"))
        for gate_id in ("G5", "G6", "G8"):  # nothing instantiates the backend
            self.assertEqual(gs.statuses(report)[gate_id], "skip", gate_id)

    def test_a_fake_derived_from_the_native_class_fails_g3(self) -> None:
        directory = gs.broken_copy(self, [("fake.py", "class FakeController:",
                                           "import pathlib, sys\n"
                                           "sys.path.insert(0, str(pathlib.Path(__file__).parent / 'vendor'))\n"
                                           "from thermo.controller import Controller\n\n\n"
                                           "class FakeController(Controller):")], regen=False)
        self.addCleanup(lambda: [sys.modules.pop(name, None) for name in ("thermo", "thermo.controller")])
        self.addCleanup(lambda: sys.path.remove(str(directory / "vendor")) if str(directory / "vendor") in sys.path
                        else None)
        report = gs.check(directory, gates=["G3"])
        self.assertIn("G3.FAKE_IS_NATIVE", gs.findings(report, "G3"))

    def test_native_named_through_a_re_export_is_still_seen(self) -> None:
        # native = "thermo:Controller" (thermo/__init__.py re-exports it); the fake's class comes from
        # thermo.controller, so the import paths differ but the class in the clone is the same.
        variants = {
            "derived": "from thermo import Controller\n\n\nclass FakeController(Controller):",
            "aliased": "from thermo import Controller as FakeController\n\n\nclass _Unused:",
        }
        for label, header in variants.items():
            with self.subTest(label):
                directory = gs.copy_tutorial(self)
                (directory / "vendor" / "thermo" / "__init__.py").write_text(
                    "from .controller import Controller  # noqa: F401\n", encoding="utf-8")
                gs.edit(directory, "driver.py", 'native = "thermo.controller:Controller"', 'native = "thermo:Controller"')
                gs.edit(directory, "task.json", '"symbol": "thermo.controller:Controller"', '"symbol": "thermo:Controller"')
                gs.edit(directory, "fake.py", "class FakeController:",
                        "import pathlib, sys\nsys.path.insert(0, str(pathlib.Path(__file__).parent / 'vendor'))\n"
                        + header)
                self.addCleanup(lambda path=str(directory / "vendor"): sys.path.remove(path) if path in sys.path
                                else None)
                try:
                    report = gs.check(directory, gates=["G3"])
                finally:
                    for name in ("thermo", "thermo.controller"):
                        sys.modules.pop(name, None)
                self.assertIn("G3.FAKE_IS_NATIVE", gs.findings(report, "G3"))

    def test_a_fake_outside_the_package_fails_g3(self) -> None:
        directory = gs.broken_copy(self, [("driver.py", '"fake": ".fake:FakeController"',
                                           '"fake": "types:SimpleNamespace"')])
        self.assertIn("G3.FAKE_OUTSIDE_PACKAGE", gs.findings(gs.check(directory, gates=["G3"]), "G3"))

    def test_a_package_entry_that_re_exports_foreign_code_fails_g3(self) -> None:
        # ".fake:Fake" looks like package code, but fake.py only re-exports a class of another library.
        directory = gs.broken_copy(self, [("fake.py", "class FakeController:",
                                           "from types import SimpleNamespace as Fake  # noqa: F401\n\n\n"
                                           "class FakeController:"),
                                          ("driver.py", '"fake": ".fake:FakeController"', '"fake": ".fake:Fake"')],
                                   regen=False)
        report = gs.check(directory, gates=["G3"])
        self.assertIn("G3.FAKE_OUTSIDE_PACKAGE", gs.findings(report, "G3"))
        self.assertIn("types:SimpleNamespace", json.dumps(gate_of(report, "G3")))

    def test_an_upstream_simulator_named_by_the_card(self) -> None:
        directory = gs.copy_tutorial(self)
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        card["mock_strategy"]["preferred"] = "upstream-sim"
        (directory / "task.json").write_text(json.dumps(card), encoding="utf-8")
        (directory / "vendor" / "thermo" / "sim.py").write_text(
            "from .controller import Controller\n\n\nclass SimController:\n    pass\n\n\n"
            "class Derived(Controller):\n    pass\n", encoding="utf-8")
        gs.edit(directory, "driver.py", '"fake": ".fake:FakeController"', '"fake": "thermo.sim:SimController"')
        self.assertEqual(gs.findings(gs.check(directory, gates=["G3"]), "G3"), [])
        # Never the native class, not even by derivation or a re-export (read from the clone's AST, not imported).
        for entry in ("thermo.sim:Derived", "thermo.sim:Controller"):
            gs.edit(directory, "driver.py", '"fake": "thermo.sim:SimController"', f'"fake": "{entry}"')
            self.assertIn("G3.FAKE_IS_NATIVE", gs.findings(gs.check(directory, gates=["G3"]), "G3"), entry)
            gs.edit(directory, "driver.py", f'"fake": "{entry}"', '"fake": "thermo.sim:SimController"')

    def test_the_gate_process_cannot_open_device_files(self) -> None:
        directory = gs.broken_copy(self, [("fake.py", "        self.lid = True\n",
                                           "        self.lid = True\n        open('/dev/ttyACM0', 'r+b')\n")],
                                   regen=False)
        report, _output = run_check_isolated(directory, write_report=False)
        self.assertIn("G6", report["failed"])
        self.assertIn("device files are not opened", json.dumps(gate_of(report, "G6")))


if __name__ == "__main__":
    unittest.main()
