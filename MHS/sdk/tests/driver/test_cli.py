"""``python -m mhs.driver``: reference, new, export, catalog, --print-interface and usage errors."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from mhs.adapter import load
from mhs.driver import close_server
from mhs.driver.__main__ import main as _main
from mhs.driver.interface import interface_text
from mhs.driver.package import export_adapter, scaffold, stale_references, ScaffoldError
from mhs.schema import default_store

from tests.driver import gate_support as gs


def main(argv: list[str]) -> int:
    """The CLI entry point with its output captured (the tests read exit codes and files)."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return _main(argv)


def card_for(test: unittest.TestCase, directory: Path) -> Path:
    """A non-synthetic task card (written next to ``directory``)."""
    document = json.loads((gs.TUTORIAL / "task.json").read_text(encoding="utf-8"))
    for key in ("synthetic", "notes"):
        document.pop(key, None)
    document.update({"package_id": "gh.acme-labs/heater-sdk", "local_path": "labs/acme-labs/heater-sdk",
                     "driver_dir": f"MHS/drivers/labs/{directory.name}",
                     "upstream": {"repo_url": "https://github.com/acme-labs/heater-sdk", "commit": "c" * 40,
                                  "license_spdx": "MIT", "license_class": "permissive"},
                     "entry_symbols": [{"symbol": "heater.sdk:Heater", "file": "heater/sdk.py", "line": 3,
                                        "confidence": "ast"}]})
    path = directory.parent / "card.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


class ReferenceCommandTests(unittest.TestCase):
    def test_reference_writes_and_checks(self) -> None:
        directory = gs.copy_tutorial(self)
        self.assertEqual(stale_references(directory), [])
        self.assertEqual(main(["reference", str(directory), "--check"]), 0)
        gs.edit(directory, "driver.py", 'tags = ["thermostat", "tutorial"]', 'tags = ["thermostat"]')
        self.assertEqual(main(["reference", str(directory), "--check"]), 1)
        self.assertEqual(sorted(stale_references(directory)), ["REFERENCE.md", "reference.json"])
        self.assertEqual(main(["reference", str(directory)]), 0)
        self.assertEqual(stale_references(directory), [])
        data = (directory / "reference.json").read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(default_store().validate(json.loads(data), "reference.schema.json"), [])

    def test_reference_is_deterministic(self) -> None:
        directory = gs.copy_tutorial(self)
        before = (directory / "reference.json").read_bytes(), (directory / "REFERENCE.md").read_bytes()
        gs.regenerate(directory)
        self.assertEqual(((directory / "reference.json").read_bytes(), (directory / "REFERENCE.md").read_bytes()),
                         before)

    def test_reference_of_a_non_driver_directory_is_a_usage_error(self) -> None:
        self.assertEqual(main(["reference", str(gs.temp_root(self))]), 2)


class NewCommandTests(unittest.TestCase):
    def test_new_from_a_card_renders_the_templates(self) -> None:
        directory = gs.temp_root(self) / "acme-labs__heater-sdk"
        card = card_for(self, directory)
        self.assertEqual(main(["new", str(directory), "--card", str(card), "--model-id", "m-1", "--run-id", "r-1"]), 0)
        for name in ("task.json", "driver.py", "fake.py", "native.py", "facts.md", "test_driver.py",
                     "driver.lock.json"):
            self.assertTrue((directory / name).is_file(), name)
        lock = json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(default_store().validate(lock, "driver-lock.schema.json"), [])
        self.assertEqual(lock["upstream"]["commit"], "c" * 40)
        self.assertEqual(lock["authored_by"]["model_id"], "m-1")
        self.assertIsNone(lock["reviewed_by"])
        driver = (directory / "driver.py").read_text(encoding="utf-8")
        self.assertIn('native = "heater.sdk:Heater"', driver)
        self.assertIn('risk = "R2"', driver)
        self.assertIn("x-cap.acme-labs.identify.v1", driver)
        self.assertIn("estop_physical_ref", driver)  # the SAFE-045 hint
        self.assertEqual((directory / "task.json").read_bytes(), card.read_bytes())
        # Scaffolding never overwrites.
        self.assertEqual(main(["new", str(directory), "--card", str(card)]), 1)
        with self.assertRaises(ScaffoldError):
            scaffold(directory, card=card)

    def test_new_like_an_exemplar_copies_its_code_and_not_its_identity(self) -> None:
        directory = gs.temp_root(self) / "acme-labs__heater-sdk"
        card = card_for(self, directory)
        written = {path.relative_to(directory.resolve()).as_posix()
                   for path in scaffold(directory, card=card, like=gs.TUTORIAL)}
        self.assertEqual(written, {"driver.lock.json", "driver.py", "facts.md", "fake.py", "native.py",
                                   "site-limits.example.json", "task.json", "test_driver.py"})
        self.assertEqual((directory / "driver.py").read_bytes(), (gs.TUTORIAL / "driver.py").read_bytes())
        self.assertFalse((directory / "vendor").exists())
        self.assertFalse((directory / "reference.json").exists())
        lock = json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["package_id"], "gh.acme-labs/heater-sdk")
        self.assertIn("check_driver(HERE", (directory / "test_driver.py").read_text(encoding="utf-8"))

    def test_the_lock_carries_the_install_block_of_the_card(self) -> None:
        directory = gs.temp_root(self) / "acme-labs__heater-sdk"
        card = card_for(self, directory)
        document = json.loads(card.read_text(encoding="utf-8"))
        document["install"] = {"python": None, "commands": ["pip install ."], "system_deps": ["libusb-1.0"], "gpu": False,
                               "platform": "linux"}
        card.write_text(json.dumps(document), encoding="utf-8")
        scaffold(directory, card=card)
        lock = json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["install"], {"python": ">=3.10", "commands": ["pip install ."], "system_deps": ["libusb-1.0"],
                                           "gpu": False, "platform": "linux"})
        document["install"]["python"] = ">=3.9"
        card.write_text(json.dumps(document), encoding="utf-8")
        scaffold(directory, card=card, force=True)
        self.assertEqual(json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))["install"]["python"], ">=3.9")

    def test_a_card_without_install_gets_the_default_block(self) -> None:
        directory = gs.temp_root(self) / "acme-labs__heater-sdk"
        card = card_for(self, directory)
        document = json.loads(card.read_text(encoding="utf-8"))
        document.pop("install", None)
        card.write_text(json.dumps(document), encoding="utf-8")
        scaffold(directory, card=card)
        lock = json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["install"], {"python": ">=3.10", "commands": [], "system_deps": [], "gpu": False, "platform": "any"})

    def test_new_kind_from_the_card_helper(self) -> None:
        directory = gs.temp_root(self) / "acme-labs__heater-sdk"
        card = card_for(self, directory)
        document = json.loads(card.read_text(encoding="utf-8"))
        document["helper"] = "ScpiDriver"
        card.write_text(json.dumps(document), encoding="utf-8")
        scaffold(directory, card=card)
        self.assertIn("(ScpiDriver)", (directory / "driver.py").read_text(encoding="utf-8"))
        self.assertFalse((directory / "native.py").exists())


class ExportAndCatalogTests(unittest.TestCase):
    def test_export_points_back_at_the_driver(self) -> None:
        directory = gs.copy_tutorial(self)
        out = directory.parent / "exported" / "mhs-adapter.json"
        out.parent.mkdir()
        document = export_adapter(directory, out=out)
        self.assertEqual(default_store().validate(document, "adapter.schema.json"), [])
        self.assertEqual(document["bridges"], [{"bridge_id": "mhs.driver", "kind": "driver",
                                                "config": {"path": "../thermostat"}}])
        self.assertEqual(document["devices"][0]["mode"], "hardware")
        self.assertEqual(main(["export", str(directory), "--out", str(out)]), 0)
        server = load(out)
        try:
            self.assertEqual([device.mode for device in server.devices.values()], ["simulated"])
        finally:
            close_server(server)

    def test_an_ophyd_package_exports_as_bluesky_ophyd(self) -> None:
        # adapter.schema.json lists bluesky-ophyd and not ophyd. OphydDriver stays ahead of
        # PythonObjectDriver, so the export family is the schema name and not python-object.
        directory = Path(__file__).resolve().parents[1] / "fixtures" / "ophyd_axis"
        document = export_adapter(directory)
        self.assertEqual(document["family"], "bluesky-ophyd")
        self.assertEqual(default_store().validate(document, "adapter.schema.json"), [])

    def test_a_tag_package_still_exports_as_other(self) -> None:
        directory = Path(__file__).resolve().parents[1] / "fixtures" / "tag_modbus"
        document = export_adapter(directory)
        self.assertEqual(document["family"], "other")
        self.assertEqual(default_store().validate(document, "adapter.schema.json"), [])

    def test_export_creates_the_output_directory(self) -> None:
        directory = gs.copy_tutorial(self)
        out = directory.parent / "not" / "yet" / "mhs-adapter.json"
        self.assertEqual(main(["export", str(directory), "--out", str(out)]), 0)
        self.assertEqual(default_store().validate(json.loads(out.read_text(encoding="utf-8")), "adapter.schema.json"),
                         [])
        blocker = directory.parent / "a-file"
        blocker.write_text("", encoding="utf-8")
        self.assertEqual(main(["export", str(directory), "--out", str(blocker / "mhs-adapter.json")]), 2)

    def test_catalog_lookups(self) -> None:
        self.assertEqual(main(["catalog", "show", "cap.thermal.setpoint.v1"]), 0)
        self.assertEqual(main(["catalog", "show", "cap.no.such.v1"]), 1)
        self.assertEqual(main(["catalog", "search", "thermal", "setpoint"]), 0)
        self.assertEqual(main(["catalog", "kinds"]), 0)
        self.assertEqual(main(["catalog"]), 2)

    def test_usage_errors_exit_2(self) -> None:
        self.assertEqual(main([]), 2)
        self.assertEqual(main(["check", str(gs.temp_root(self) / "missing")]), 2)
        self.assertEqual(main(["check", str(gs.TUTORIAL), "--backend", "hardware"]), 2)
        self.assertEqual(main(["check", str(gs.TUTORIAL), "--backend", "nope"]), 2)


class InterfaceTests(unittest.TestCase):
    def test_print_interface_matches_the_committed_file(self) -> None:
        committed = (gs.SDK / "INTERFACE.md").read_text(encoding="utf-8")
        self.assertEqual(interface_text(), committed,
                         "regenerate it: python3 -m mhs.driver --print-interface > MHS/sdk/INTERFACE.md")

    def test_interface_is_stable_and_names_the_gates(self) -> None:
        text = interface_text()
        self.assertEqual(text, interface_text())
        for gate in ("G1", "G5", "G9"):
            self.assertIn(f"| {gate} |", text)
        self.assertNotIn(" at 0x", text)
        self.assertTrue(text.startswith("# OpenMHS SDK interface contract"))


if __name__ == "__main__":
    unittest.main()
