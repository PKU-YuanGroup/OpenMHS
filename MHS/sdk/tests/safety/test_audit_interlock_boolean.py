"""A decorated ``@interlock`` closes only on boolean ``True`` (driver-profile.md).

Boolean ``False`` reads ``open``; any other return, including the string
``"closed"``, reads ``unknown``. Both block a gated command (CORE-073). An
in-memory driver is enough: no network and no device.
"""

from __future__ import annotations

import unittest
from typing import Any

from mhs.driver import Driver, Field, action, close_server, interlock

from tests.driver.support import code, serve

CAP = "x-cap.audit.gated.v1"


class _EqualsClosed:
    """Compares equal to the wire state ``"closed"`` without being that string."""

    def __eq__(self, other: object) -> bool:
        return other == "closed"


class _ClosedString(str):
    """A ``str`` subclass of ``"closed"``, so membership must not treat it as safe."""


def _gated(reading: Any) -> tuple[Driver, list[str]]:
    ran: list[str] = []

    class Gated(Driver):
        device_id, device_kind = "audit-interlock", "instrument"
        mode, risk = "hardware", "R0"
        backends = {"fake": dict}
        safe_state = "idle"

        @action(name=CAP, output={"done": Field("boolean", description="the gated action ran")})
        def go(self):
            ran.append("go")
            return {"done": True}

        @interlock("guard", description="guard is closed", blocks=[CAP])
        def guard(self):
            if isinstance(reading, BaseException):
                raise reading
            return reading

    return Gated(backend="fake"), ran


class DecoratedInterlockBooleanTests(unittest.TestCase):
    def _run(self, reading: Any) -> tuple[list[dict[str, str]], dict[str, Any], list[str]]:
        driver, ran = _gated(reading)
        server, client = serve(driver)
        self.addCleanup(close_server, server)
        return driver.interlocks(), client.command(CAP, {}), ran

    def test_boolean_true_is_closed_and_allows_the_gated_command(self) -> None:
        states, receipt, ran = self._run(True)
        self.assertEqual(states, [{"id": "guard", "state": "closed", "description": "guard is closed"}])
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(ran, ["go"])

    def test_string_closed_is_unknown_and_does_not_authorize(self) -> None:
        # The audit probe: the wire word "closed" is not boolean True, so the
        # server must refuse the gated command (server interlock check).
        states, receipt, ran = self._run("closed")
        self.assertEqual(states, [{"id": "guard", "state": "unknown", "description": "guard is closed"}])
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(code(receipt), "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertEqual(receipt["error"]["interlocks"], [{"id": "guard", "state": "unknown"}])
        self.assertEqual(ran, [])

    def test_boolean_false_is_open_and_blocks(self) -> None:
        states, receipt, ran = self._run(False)
        self.assertEqual(states[0]["state"], "open", states)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(code(receipt), "MHS.SAFETY.INTERLOCK_OPEN")
        self.assertEqual(receipt["error"]["interlocks"], [{"id": "guard", "state": "open"}])
        self.assertEqual(ran, [])

    def test_other_returns_are_unknown_and_block(self) -> None:
        readings: tuple[Any, ...] = (
            "open",
            "unknown",
            None,
            0,
            1,
            "true",
            "True",
            "",
            _EqualsClosed(),
            _ClosedString("closed"),
            RuntimeError("unreadable"),
        )
        for reading in readings:
            with self.subTest(reading=reading):
                states, receipt, ran = self._run(reading)
                self.assertEqual(states[0]["state"], "unknown", states)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(code(receipt), "MHS.SAFETY.INTERLOCK_OPEN")
                self.assertEqual(receipt["error"]["interlocks"], [{"id": "guard", "state": "unknown"}])
                self.assertEqual(ran, [])


if __name__ == "__main__":
    unittest.main()
