"""install() is idempotent and registers a complete, portable native surface."""

from __future__ import annotations

import os
import re
import unittest
from unittest import mock

from openai4s.tools import registry as registry_module
from openai4s import host_dispatch as dispatch_module

from openai4s_mhs import install
from openai4s_mhs import tools as mhs_tools
from openai4s_mhs.config import MHSConfig

TOOL_NAMES = (
    "mhs_devices",
    "mhs_inspect",
    "mhs_read",
    "mhs_command",
    "mhs_operations",
    "mhs_safety",
    "mhs_evidence",
    "mhs_connect",
)


class ExperimentalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        mhs_tools.uninstall()

    def tearDown(self) -> None:
        mhs_tools.uninstall()

    def test_default_is_disabled_and_registers_nothing(self) -> None:
        # No config, no env: the experimental skill is off.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MHS_ENABLED", None)
            os.environ.pop("MHS_CONFIG", None)
            self.assertFalse(MHSConfig().enabled)
            self.assertFalse(install())
        names = [tool.name for tool in registry_module.all_tools() if tool.name.startswith("mhs_")]
        self.assertEqual(names, [])

    def test_disabled_config_registers_nothing(self) -> None:
        self.assertFalse(install(MHSConfig(enabled=False, sync_openai4s=False)))
        names = [tool.name for tool in registry_module.all_tools() if tool.name.startswith("mhs_")]
        self.assertEqual(names, [])

    def test_enabled_config_installs_and_disable_removes(self) -> None:
        self.assertTrue(install(MHSConfig(enabled=True, sync_openai4s=False)))
        self.assertIsNotNone(registry_module.get_tool("mhs_command"))
        mhs_tools.uninstall()
        self.assertIsNone(registry_module.get_tool("mhs_command"))


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(install(MHSConfig(enabled=True, sync_openai4s=False)))
        self.tools = [registry_module.get_tool(name) for name in TOOL_NAMES]

    def test_idempotent_registration(self) -> None:
        enabled = MHSConfig(enabled=True, sync_openai4s=False)
        self.assertTrue(install(enabled))
        self.assertTrue(install(enabled))
        names = [tool.name for tool in registry_module.all_tools() if tool.name.startswith("mhs_")]
        self.assertEqual(sorted(names), sorted(TOOL_NAMES))
        self.assertEqual(len(names), len(set(names)))

    def test_every_tool_is_resolvable_by_host_method(self) -> None:
        for tool in self.tools:
            self.assertIsNotNone(tool)
            self.assertEqual(tool.host_method, tool.name)
            self.assertIs(registry_module.get_tool_by_host_method(tool.host_method), tool)

    def test_names_are_provider_portable(self) -> None:
        portable = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
        for tool in self.tools:
            self.assertRegex(tool.name, portable)

    def test_schemas_are_closed_objects_with_declared_required(self) -> None:
        for tool in self.tools:
            schema = tool.input_schema()
            self.assertEqual(schema["type"], "object")
            self.assertIs(schema["additionalProperties"], False)
            self.assertNotIn("$schema", tool.parameters)
            for name in tool.parameters.get("required", []):
                self.assertIn(name, tool.parameters["properties"])
            self.assertEqual(tool.validation_error({}) is None, not schema["required"])

    def test_descriptions_teach_mode_receipts_and_unknown_outcome(self) -> None:
        by_name = {tool.name: tool for tool in self.tools}
        devices = by_name["mhs_devices"].description.lower()
        self.assertIn("mode", devices)
        self.assertIn("fidelity", devices)
        command = by_name["mhs_command"].description.lower()
        self.assertIn("receipt", command)
        self.assertIn("unknown", command)
        self.assertIn("re-read", command)
        self.assertIn("permit", command)
        self.assertIn("estop", by_name["mhs_safety"].description.lower())
        self.assertIn("cancel", by_name["mhs_operations"].description.lower())
        self.assertIn("verify", by_name["mhs_evidence"].description.lower())
        self.assertIn("endpoint", by_name["mhs_connect"].description.lower())

    def test_permission_and_side_effect_flags(self) -> None:
        by_name = {tool.name: tool for tool in self.tools}
        for name in ("mhs_devices", "mhs_inspect", "mhs_read", "mhs_connect"):
            self.assertTrue(by_name[name].read_only, name)
            self.assertFalse(by_name[name].requires_approval, name)
            self.assertEqual(by_name[name].side_effect_class, "read_only")
        command = by_name["mhs_command"]
        self.assertFalse(command.read_only)
        self.assertTrue(command.requires_approval)
        self.assertTrue(command.dangerous)
        self.assertEqual(command.side_effect_class, "high_risk")
        # An e-stop must never sit behind an approval prompt.
        self.assertFalse(by_name["mhs_safety"].requires_approval)
        self.assertEqual(by_name["mhs_safety"].side_effect_class, "high_risk")
        self.assertFalse(by_name["mhs_evidence"].writes_files)

    def test_network_tools_screen_untrusted_output(self) -> None:
        for tool in self.tools:
            if tool.needs_network:
                self.assertTrue(tool.screen_untrusted_output, tool.name)

    def test_resource_keys_are_namespaced(self) -> None:
        for tool in self.tools:
            keys = tool.resource_keys({})
            self.assertTrue(keys)
            for key in keys:
                self.assertIn(":", key)
                self.assertTrue(key.startswith("mhs:"), key)
        command = registry_module.get_tool("mhs_command")
        self.assertEqual(
            command.resource_keys(
                {"device_id": "mhs://x/conveyor", "capability_id": "cap.world.step.v1"}
            ),
            ("mhs:mhs%3A//x/conveyor/cap.world.step.v1",),
        )

    def test_conflict_rule_builtin_sets_include_every_method(self) -> None:
        for method in mhs_tools.HOST_METHODS:
            self.assertIn(method, registry_module.BUILTIN_CONTROL_HOST_METHODS)
            self.assertIn(method, dispatch_module.BUILTIN_CONTROL_HOST_METHODS)
            self.assertTrue(hasattr(dispatch_module.HostDispatcher, f"_m_{method}"))

    def test_lazy_host_property_is_a_property(self) -> None:
        self.assertIsInstance(
            dispatch_module.HostDispatcher.__dict__.get("openai4s_mhs_host"), property
        )


if __name__ == "__main__":
    unittest.main()


class EvidenceFilesystemBoundaryTests(unittest.TestCase):
    def test_model_paths_are_refused_before_host_or_filesystem_access(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "access-token"
            target.write_text('{"private": "sentinel"}')
            for action in ("export", "verify", "ledger"):
                with self.subTest(action=action), mock.patch.object(mhs_tools, "_host", side_effect=AssertionError("host must not run")):
                    result = mhs_tools._m_mhs_evidence(object(), {"action": action, "path": str(target)})
                    self.assertIn("MHS.HOST.INVALID_ARGUMENT", str(result))
                    self.assertNotIn("sentinel", str(result))
                    self.assertEqual(target.read_text(), '{"private": "sentinel"}')
