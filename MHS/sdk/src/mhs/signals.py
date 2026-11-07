"""Driver control-flow signals (plan 3.7 and 3.8; stdlib only).

A driver or bridge reports the outcome of a native call in exactly one of five
ways: it returns an output, or it raises one of the four signals below.  The
runtime turns each into a receipt; drivers never build receipts or error
records themselves.

* :class:`Cancelled` -> receipt ``cancelled``, no error code;
* :class:`DriverFailed` -> ``failed`` with the registered code it names;
* :class:`Busy` -> ``rejected`` with ``MHS.DEVICE.BUSY`` (retryable; nothing
  was actuated);
* :class:`OutcomeUnknown` -> ``unknown`` with ``MHS.OUTCOME.UNKNOWN`` (not
  retryable: observe state first);
* any other exception -> ``failed`` with ``MHS.ADAPTER.SHIM_FAILED`` and a
  redacted message (the exception type only).

:func:`outcome` applies these rules to any exception, so the server and every
bridge classify failures the same way.  ``asyncio.CancelledError`` and
``concurrent.futures.CancelledError`` count as :class:`Cancelled`.

``DriverFailed`` accepts any registered normative code (legacy aliases are
normalised); :data:`mhs.errors.DRIVER_SUBSET` lists the codes a driver is
expected to use, and :attr:`DriverFailed.driver_subset` says whether the code
is one of them so a strict loader can refuse the others.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass, field
from typing import Any

from . import errors as _errors

__all__ = [
    "Busy",
    "Cancelled",
    "DriverFailed",
    "DriverSignal",
    "Outcome",
    "OutcomeUnknown",
    "outcome",
]

_MESSAGE_MAX = 1000


def _clip(message: Any) -> str:
    text = "" if message is None else str(message)
    return text if len(text) <= _MESSAGE_MAX else text[: _MESSAGE_MAX - 3] + "..."


class DriverSignal(Exception):
    """Base class of the signals; never raised directly."""

    #: Receipt status the runtime records for this signal.
    receipt_status: str = "failed"
    #: Normative error code, or ``None`` when the receipt carries no error.
    code: str | None = None
    retryable: bool = False

    def __init__(self, message: str = "", *, native_code: Any = None):
        self.message = _clip(message)
        self.native_code = native_code
        super().__init__(self.message or self.__class__.__name__)

    def details(self) -> dict[str, Any]:
        """JSON-able details for the receipt error (only what the driver stated)."""
        out: dict[str, Any] = {}
        if self.native_code is not None:
            out["native_code"] = (
                self.native_code
                if isinstance(self.native_code, (str, int, float, bool))
                else str(self.native_code)
            )
        return out


class Cancelled(DriverSignal):
    """The native call stopped because cancellation was requested (``ctx.cancel_event``)."""

    receipt_status = "cancelled"
    code = None
    retryable = False


class DriverFailed(DriverSignal):
    """The native call failed in a way the driver understands.

    ``code`` is a registered OpenMHS error code (for example
    ``MHS.DEVICE.FAULTED`` or ``MHS.DEVICE.PRECONDITION_UNMET``);
    ``native_code`` is the device's own return or error code, kept verbatim in
    the receipt details.  An unregistered code is a programming error and raises
    :class:`ValueError` at construction.
    """

    receipt_status = "failed"

    def __init__(self, code: str, message: str = "", native_code: Any = None):
        if not isinstance(code, str) or not code:
            raise ValueError("DriverFailed needs a registered MHS error code")
        normalized = _errors.normalize_code(code)
        if not _errors.is_normative_code(normalized):
            raise ValueError(f"DriverFailed code {code!r} is not a registered MHS error code")
        self.code = normalized
        self.retryable = _errors.retryable(normalized)
        super().__init__(message or normalized, native_code=native_code)

    @property
    def driver_subset(self) -> bool:
        """True when the code belongs to the driver subset of the error registry."""
        return _errors.is_driver_code(self.code)


class Busy(DriverSignal):
    """The device refused the call because it is busy; nothing was actuated."""

    receipt_status = "rejected"
    code = "MHS.DEVICE.BUSY"
    retryable = True

    def __init__(self, message: str = "", *, retry_after_ms: int | None = None, native_code: Any = None):
        self.retry_after_ms = retry_after_ms
        super().__init__(message or "device is busy", native_code=native_code)

    def details(self) -> dict[str, Any]:
        out = super().details()
        if self.retry_after_ms is not None:
            out["retry_after_ms"] = int(self.retry_after_ms)
        return out


class OutcomeUnknown(DriverSignal):
    """The effect may have happened but cannot be observed (for example a native timeout)."""

    receipt_status = "unknown"
    code = "MHS.OUTCOME.UNKNOWN"
    retryable = False

    def __init__(self, message: str = "", *, native_code: Any = None):
        super().__init__(message or "native outcome is unknown", native_code=native_code)


@dataclass(frozen=True)
class Outcome:
    """How the runtime records an exception raised by a driver or bridge."""

    status: str
    code: str | None
    message: str
    retryable: bool
    details: dict[str, Any] = field(default_factory=dict)


def outcome(exc: BaseException) -> Outcome:
    """Classify ``exc`` by the rules in the module docstring.

    Messages of exceptions other than the signals are never forwarded: they may
    carry paths, hostnames or credentials, so only the exception type is kept.
    """
    if isinstance(exc, DriverSignal):
        return Outcome(exc.receipt_status, exc.code, exc.message, exc.retryable, exc.details())
    if isinstance(exc, (asyncio.CancelledError, concurrent.futures.CancelledError)):
        return Outcome("cancelled", None, "native call was cancelled", False, {})
    return Outcome(
        "failed",
        "MHS.ADAPTER.SHIM_FAILED",
        f"driver raised {type(exc).__name__}",
        _errors.retryable("MHS.ADAPTER.SHIM_FAILED"),
        {"exception_type": type(exc).__name__},
    )
