"""G3.GATE_TAMPERED and the interpreter's builtins.

pybind11 extensions add private names to ``builtins`` when they are imported (MuJoCo 3.8 adds four ``__MUJOCO_*``
lookups), so a sim-backend gate of any MuJoCo package reported the SDK as tampered. Adding a name changes no SDK
behaviour; replacing or removing an existing builtin, or rebinding a module's ``__builtins__``, still does.
"""
from __future__ import annotations

import builtins
import unittest

import mhs.bridge.mcp_stdio  # noqa: F401 - a core module, so its __builtins__ entry is part of the snapshot
import mhs.driver.check as check

ADDED = "__AI4S_TEST_EXTENSION_LOOKUP"


class BuiltinsIntegrityTests(unittest.TestCase):
    def tearDown(self) -> None:
        vars(builtins).pop(ADDED, None)

    def test_a_new_builtin_name_is_not_tampering(self) -> None:
        before = check._integrity_snapshot()
        setattr(builtins, ADDED, object())
        self.assertEqual(check._integrity_changes(before, check._integrity_snapshot()), [])

    def test_a_replaced_builtin_is_tampering(self) -> None:
        before = check._integrity_snapshot()
        original = builtins.open
        builtins.open = lambda *args, **kwargs: None  # type: ignore[assignment]
        try:
            changes = check._integrity_changes(before, check._integrity_snapshot())
        finally:
            builtins.open = original
        self.assertIn("builtins.open", changes)

    def test_a_removed_builtin_is_tampering(self) -> None:
        setattr(builtins, ADDED, object())
        before = check._integrity_snapshot()
        delattr(builtins, ADDED)
        self.assertIn(f"builtins.{ADDED}", check._integrity_changes(before, check._integrity_snapshot()))

    def test_a_rebound_module_builtins_is_tampering(self) -> None:
        module = mhs.bridge.mcp_stdio
        original = module.__dict__["__builtins__"]
        before = check._integrity_snapshot()
        module.__dict__["__builtins__"] = dict(vars(builtins))
        try:
            changes = check._integrity_changes(before, check._integrity_snapshot())
        finally:
            module.__dict__["__builtins__"] = original
        self.assertIn("mhs.bridge.mcp_stdio.__builtins__", changes)


if __name__ == "__main__":
    unittest.main()
