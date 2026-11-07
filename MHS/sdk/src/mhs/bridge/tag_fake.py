"""RecordingTagTransport: a deterministic in-memory point store for tag-bridge package fakes.

No I/O, no threads, no vendor library. A package fake subclasses it, seeds
placeholder values and adds the device's behaviour in :meth:`on_write` and
:meth:`on_invoke`. The gate wraps the object in :class:`mhs.testing.Recorder`,
so every request the bridge sends is recorded and checked by G7 against the
declared points. Unseeded addresses answer like a device that does not have
them (:class:`mhs.bridge.tags.TagRefused`, Modbus exception code 2), never
with an invented value.

Negative-path switches (test data, not device facts): ``refuse`` holds request
keys the fake refuses, ``fail`` request keys whose I/O raises, ``silent`` request
keys whose write is applied but not acknowledged.
"""
from __future__ import annotations

import copy
import json
import math
import threading
from typing import Any, Mapping

from .tags import TagRefused

__all__ = ["RecordingTagTransport", "request_key"]

_MODBUS_TABLES = ("holding", "input", "coil", "discrete")


def request_key(request: Mapping[str, Any]) -> str:
    """A stable text key of a request (the same for equal requests)."""
    return json.dumps(dict(request), sort_keys=True)


class RecordingTagTransport:
    """In-memory transport for one profile (``modbus``, ``epics-ca`` or ``alpaca``)."""

    def __init__(self, profile: str):
        if profile not in ("modbus", "epics-ca", "alpaca"):
            raise ValueError(f"unsupported tag profile {profile!r}")
        self.profile = profile
        #: modbus: {(table, register): word or bool}; epics-ca: {pv: value}; alpaca: {member: value}
        self.registers: dict[tuple[str, int], Any] = {}
        self.pvs: dict[str, Any] = {}
        self.properties: dict[str, Any] = {}
        self.refuse: set[str] = set()
        self.fail: set[str] = set()
        self.silent: set[str] = set()
        self.closed = False
        self._transactions = 0
        self._lock = threading.Lock()

    # -- device behaviour hooks (override in the package fake) ---------------------------
    def on_write(self, request: Mapping[str, Any], raw: Any) -> None:
        """Called after a write was stored (under the fake's lock)."""

    def on_invoke(self, request: Mapping[str, Any], args: Mapping[str, Any]) -> int:
        """Run an Alpaca method; return the Alpaca ErrorNumber (0: success)."""
        return 0x400

    # -- transport -------------------------------------------------------------------------
    def _check(self, request: Any, timeout_s: Any) -> str:
        if self.closed:
            raise ConnectionError("the fake transport is closed")
        if (isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s)
                or not 0 < timeout_s <= 10):
            raise ValueError("a tag request needs a finite timeout_s in (0, 10]")
        if type(request) is not dict or request.get("profile") != self.profile:
            raise ValueError("the request does not belong to this transport's profile")
        key = request_key(request)
        if key in self.fail:
            raise TimeoutError("placeholder transport failure")
        if key in self.refuse:
            raise TagRefused("placeholder refusal", code=2)
        return key

    def _alpaca(self, value: Any = None, error: int = 0) -> dict[str, Any]:
        self._transactions += 1
        out = {"ClientTransactionID": 0, "ServerTransactionID": self._transactions, "ErrorNumber": error,
               "ErrorMessage": "" if error == 0 else "placeholder error"}
        if value is not None:
            out["Value"] = copy.deepcopy(value)
        return out

    def read_point(self, request: Any, *, timeout_s: Any) -> Any:
        self._check(request, timeout_s)
        with self._lock:
            if self.profile == "modbus":
                table, start, words = request["table"], request["register"], request["words"]
                if table not in _MODBUS_TABLES:
                    raise TagRefused("illegal function", code=1)
                values = []
                for register in range(start, start + words):
                    if (table, register) not in self.registers:
                        raise TagRefused("illegal data address", code=2)
                    values.append(copy.deepcopy(self.registers[(table, register)]))
                return values
            if self.profile == "epics-ca":
                if request["pv"] not in self.pvs:
                    raise TagRefused("no such PV", code="disconnected")
                return copy.deepcopy(self.pvs[request["pv"]])
            if request.get("method") or request["member"] not in self.properties:
                return self._alpaca(error=0x400)
            return self._alpaca(self.properties[request["member"]])

    def write_point(self, request: Any, raw: Any, *, timeout_s: Any) -> Any:
        key = self._check(request, timeout_s)
        with self._lock:
            if self.profile == "modbus":
                table, register = request["table"], request["register"]
                if table not in ("holding", "coil") or (table, register) not in self.registers:
                    raise TagRefused("illegal data address", code=2)
                if table == "holding":
                    if type(raw) is not list or len(raw) != 1 or type(raw[0]) is not int or not 0 <= raw[0] <= 0xFFFF:
                        raise TagRefused("illegal data value", code=3)
                    self.registers[(table, register)] = raw[0]
                else:
                    if type(raw) is not bool:
                        raise TagRefused("illegal data value", code=3)
                    self.registers[(table, register)] = raw
            elif self.profile == "epics-ca":
                if request["pv"] not in self.pvs:
                    raise TagRefused("no such PV", code="disconnected")
                self.pvs[request["pv"]] = copy.deepcopy(raw)
            else:
                if request.get("method") or "field" not in request or request["member"] not in self.properties:
                    return self._alpaca(error=0x40B)
                self.properties[request["member"]] = copy.deepcopy(raw)
            self.on_write(request, raw)
            if key in self.silent:
                return None if self.profile != "alpaca" else {"unexpected": True}
            return True if self.profile != "alpaca" else self._alpaca()

    def invoke_point(self, request: Any, args: Any, *, timeout_s: Any) -> Any:
        key = self._check(request, timeout_s)
        if self.profile != "alpaca" or not request.get("method") or type(args) is not dict:
            raise ValueError("only Alpaca method requests can be invoked")
        with self._lock:
            error = self.on_invoke(request, copy.deepcopy(args))
            if key in self.silent:
                return {"unexpected": True}
            return self._alpaca(error=int(error))

    def close(self) -> None:
        self.closed = True
