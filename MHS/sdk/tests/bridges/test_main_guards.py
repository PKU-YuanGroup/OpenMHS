"""Bridge modules are not launchers: ``python -m mhs.bridge.<x>`` exits 2.

Ported reviewer repro (REGQ-02, SIM-02, TESTS-01, FIT-04): ``python3 -m
mhs.bridge.gymnasium --adapter x.json`` printed only a runpy warning and
exited 0, so 716 registry launch commands were silent no-ops.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

SDK_SRC = Path(__file__).resolve().parents[2] / "src"
MODULES = ("python", "gymnasium", "mujoco", "serial", "replay", "scpi", "transcript", "base", "bindings")


class MainGuardTests(unittest.TestCase):
    def test_every_bridge_module_refuses_to_run_and_exits_2(self) -> None:
        env = dict(os.environ, PYTHONPATH=str(SDK_SRC), PYTHONDONTWRITEBYTECODE="1")
        for name in MODULES:
            with self.subTest(module=name):
                completed = subprocess.run(
                    [sys.executable, "-m", f"mhs.bridge.{name}", "--adapter", "/nonexistent"],
                    capture_output=True, text=True, env=env, timeout=60,
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn("use: mhs serve <driver-dir|mhs-adapter.json>", completed.stderr)
                self.assertEqual(completed.stdout, "")

    def test_main_is_importable(self) -> None:
        import importlib

        for name in MODULES:
            module = importlib.import_module(f"mhs.bridge.{name}")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(module.main(["--adapter", "x"]), 2)
            self.assertIn("mhs serve", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
