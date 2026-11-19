"""G5 on a backend other than fake compares against the committed reference, which the default (fake) backend writes.

`python3 -m mhs.driver reference <dir>` renders the declared view over the default backend. Before this fix G5 rendered
the reference from the gate's own instance, so `--backend sim` of every simulator package whose surface comes from its
backend (action-space limits, their source labels) reported reference.json as stale although nothing had changed. A
surface the live backend derives differently is now a warning (BACKEND_SURFACE) that names the differing paths.
"""
from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import mhs.driver.check as check

FAKE_VIEW = {"actions": [{"limit": {"min": -1, "max": 1}}], "name": "x"}
SIM_VIEW = {"actions": [{"limit": {"min": 0, "max": 512}}], "name": "x"}
LIVE = object()


def _render(directory, *, cls=None, instance=None):  # the shape of package.reference_documents
    view = SIM_VIEW if instance is LIVE else FAKE_VIEW
    return json.dumps(view).encode() + b"\n", "# reference\n"


class G5BackendReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        data, markdown = _render(self.dir)
        (self.dir / check.REFERENCE_JSON).write_bytes(data)
        (self.dir / check.REFERENCE_MD).write_text(markdown)
        self.patch = mock.patch.object(check, "reference_documents", side_effect=_render)
        self.render = self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.tmp.cleanup()

    def _run(self, backend: str) -> check.Gate:
        ctx = types.SimpleNamespace(g3_ok=True, dir=self.dir, backend=backend, instance=LIVE,
                                    cls=type("Sim", (), {"_needs_instance": True}))
        gate = check.Gate("G5", "Reference")
        check._g5(ctx, gate)
        return gate

    def test_sim_backend_compares_against_the_default_backend_reference(self) -> None:
        gate = self._run("sim")
        self.assertEqual([f.code for f in gate.findings if f.severity == "error"], [])
        self.assertIsNone(self.render.call_args_list[0].kwargs["instance"])

    def test_sim_backend_reports_a_different_surface_as_a_warning(self) -> None:
        warnings = [f for f in self._run("sim").findings if f.severity == "warning"]
        self.assertEqual([f.code for f in warnings], ["G5.BACKEND_SURFACE"])
        self.assertIn("$.actions[0].limit.max", warnings[0].message)
        self.assertIn("$.actions[0].limit.min", warnings[0].message)

    def test_fake_backend_still_uses_its_own_instance(self) -> None:
        gate = self._run("fake")
        self.assertIs(self.render.call_args_list[0].kwargs["instance"], LIVE)
        # The fake instance renders the committed view in real use; here it renders SIM_VIEW, so the file is stale.
        self.assertEqual([f.code for f in gate.findings], ["G5.STALE"])

    def test_a_stale_file_is_still_an_error_on_sim(self) -> None:
        (self.dir / check.REFERENCE_JSON).write_bytes(b"{}\n")
        self.assertIn("G5.STALE", [f.code for f in self._run("sim").findings if f.severity == "error"])


if __name__ == "__main__":
    unittest.main()
