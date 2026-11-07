"""mhs.signals: the driver control-flow exceptions and how the runtime classifies them."""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
import unittest
from pathlib import Path

from mhs import errors, signals
from mhs.signals import Busy, Cancelled, DriverFailed, DriverSignal, OutcomeUnknown, outcome

PURE_MODULES = ("limits.py", "units.py", "catalog.py", "reference_file.py", "signals.py")


class SignalTests(unittest.TestCase):
    def test_cancelled(self):
        result = outcome(Cancelled("stop requested"))
        self.assertEqual((result.status, result.code, result.retryable), ("cancelled", None, False))
        self.assertEqual(result.message, "stop requested")
        for exc in (asyncio.CancelledError(), concurrent.futures.CancelledError()):
            self.assertEqual(outcome(exc).status, "cancelled")

    def test_driver_failed(self):
        exc = DriverFailed("MHS.DEVICE.FAULTED", "over-temperature", native_code=17)
        result = outcome(exc)
        self.assertEqual((result.status, result.code), ("failed", "MHS.DEVICE.FAULTED"))
        self.assertEqual(result.retryable, errors.retryable("MHS.DEVICE.FAULTED"))
        self.assertEqual(result.details, {"native_code": 17})
        self.assertTrue(exc.driver_subset)
        self.assertFalse(DriverFailed("MHS.SESSION.EXPIRED", "x").driver_subset)
        self.assertEqual(DriverFailed("MHS.DEVICE.FAULTED").message, "MHS.DEVICE.FAULTED")
        self.assertEqual(DriverFailed("MHS.DEVICE.FAULTED", native_code=object()).details()["native_code"][:8],
                         "<object ")

    def test_driver_failed_codes_are_registered(self):
        self.assertEqual(DriverFailed("MHS.UPSTREAM.BRIDGE_FAILURE", "legacy").code, "MHS.DEVICE.FAULTED")
        for code in ("MHS.DEVICE.ON_FIRE", "fault", "", None, 17):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    DriverFailed(code, "x")

    def test_busy_and_unknown(self):
        busy = outcome(Busy(retry_after_ms=250))
        self.assertEqual((busy.status, busy.code, busy.retryable), ("rejected", "MHS.DEVICE.BUSY", True))
        self.assertEqual(busy.details, {"retry_after_ms": 250})
        unknown = outcome(OutcomeUnknown("native call timed out"))
        self.assertEqual((unknown.status, unknown.code, unknown.retryable), ("unknown", "MHS.OUTCOME.UNKNOWN", False))
        self.assertTrue(errors.is_normative_code(Busy.code))
        self.assertTrue(errors.is_normative_code(OutcomeUnknown.code))

    def test_other_exceptions_are_redacted(self):
        result = outcome(RuntimeError("connect to 10.0.0.5 with password hunter2 failed"))
        self.assertEqual((result.status, result.code), ("failed", "MHS.ADAPTER.SHIM_FAILED"))
        self.assertNotIn("hunter2", result.message)
        self.assertNotIn("10.0.0.5", result.message)
        self.assertEqual(result.details, {"exception_type": "RuntimeError"})

    def test_hierarchy_and_message_length(self):
        for cls in (Cancelled, DriverFailed, Busy, OutcomeUnknown):
            self.assertTrue(issubclass(cls, DriverSignal))
            self.assertTrue(issubclass(cls, Exception))
        self.assertLessEqual(len(Cancelled("x" * 5000).message), 1000)


class PurityTests(unittest.TestCase):
    def test_safety_modules_never_import_the_server(self):
        package = Path(signals.__file__).resolve().parent
        pattern = re.compile(r"mhs\.server|from \.server|from \. import server|import server")
        for name in PURE_MODULES:
            with self.subTest(module=name):
                self.assertIsNone(pattern.search((package / name).read_text(encoding="utf-8")))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
