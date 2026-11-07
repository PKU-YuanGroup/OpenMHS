"""TagBridge: finite tag, register and PV reads, acknowledged writes and confirmed stops (``tag-bridge`` family).

The bridge talks to an injected transport object, never to a network or a
vendor library itself. A transport offers::

    read_point(request, *, timeout_s)          -> the raw value (see mhs.driver.tag_config.decode)
    write_point(request, raw, *, timeout_s)    -> True only when the device acknowledged the write
                                                  (Alpaca: the response object, checked here)
    invoke_point(request, args, *, timeout_s)  -> Alpaca method response object (alpaca profile only)
    close()                                    -> optional

``request`` is the declared point address (a copy). A transport raises
:class:`TagRefused` when the device states that it did not perform a request
(a Modbus exception response, a refused Channel Access put); every other
exception, a missing acknowledgement or an expired budget after dispatch is an
unknown outcome. The transport must honour ``timeout_s``: the bridge does not
abandon a native call on a helper thread.

Safety rules (the server still owns limits, permits, the latch and receipts):

* Ordinary writes and commands hold one transaction lock, take the e-stop epoch
  first and are refused once a stop fired; a command pre-empted after an earlier
  step was written ends unknown, never failed.
* An unknown outcome (a lost or unacknowledged write, or an acknowledged
  write whose confirmation does not hold) marks the point uncertain (its
  cached value leaves the state) and the device owes a confirmation: ordinary
  writes and commands are refused ``MHS.DEVICE.PRECONDITION_UNMET`` until a
  confirmed stop succeeds. The stop resolves readable points (every read
  observes them), the methods it ends and the points it writes itself; a
  write-only point it does not write stays uncertain (no read can establish
  its value), and commands stay refused until that point is written again and
  acknowledged, by a parameter write or by a command that writes it before
  any other step.
* A stop (the e-stop binding or an input-free safe-state command) never takes the
  transaction lock. It is achieved only when every step was acknowledged, every
  confirmation predicate holds on a fresh read, no ordinary operation was in
  flight from its start to its last read, and the endpoint is open. An
  acknowledgement alone never proves a stop.
* ``reset`` writes nothing: it needs a confirmed stop of the current epoch, no
  owed confirmation and nothing in flight, and re-reads the confirmation
  points. A write-only point left uncertain does not block it (writes must
  stay possible to re-establish the value); commands stay refused until then.
"""
from __future__ import annotations

import copy
import threading
import time
from typing import Any, Mapping

from .. import signals
from ..driver.tag_config import alpaca_error, compare_key, decode, encode, stop_summary
from .base import Bridge, BridgeContext, busy, driver_failed, make_mhs_error, outcome_unknown, unsupported

__all__ = ["TagBridge", "TagRefused", "TRANSPORT_METHODS"]

#: Transport methods each profile needs.
TRANSPORT_METHODS = {"modbus": ("read_point", "write_point"), "epics-ca": ("read_point", "write_point"),
                     "alpaca": ("read_point", "write_point", "invoke_point")}
#: Upper bound of one stop (steps plus confirmation), whatever the caller's deadline.
STOP_BOUND_S = 5.0
#: Alpaca error numbers that state the request was not performed, as the ASCOM AlpycaDevice template defines them
#: (gh.holtzmanjon/apoalpyca device/exceptions.py): NotImplemented 0x400 (:250-264), InvalidValue 0x401 (:195-209),
#: NotConnected 0x407 (:223-237), Parked 0x408 (:304-318), Slaved 0x409 (:331-345), InvalidOperation 0x40B
#: (:167-181), ActionNotImplemented 0x40C (:76-90). Every other number is an unknown outcome: OperationCancelled
#: 0x40E (:277-291) reports an in-progress operation, driver errors 0x500..0xFFF (:104-147) can follow a partial
#: operation, and numbers such as 0x4FF are not defined there.
_ALPACA_REFUSALS = frozenset({0x400, 0x401, 0x407, 0x408, 0x409, 0x40B, 0x40C})


class TagRefused(Exception):
    """The device or server reported that it did not perform the request (no effect)."""

    def __init__(self, message: str = "", code: Any = None):
        super().__init__(message or "the device refused the request")
        self.code = code


class _Refused(Exception):
    def __init__(self, message: str, code: Any = None):
        super().__init__(message)
        self.code = code


def _set_field(out: dict[str, Any], path: str, value: Any) -> None:
    head, _, tail = path.partition(".")
    if tail:
        out.setdefault(head, {})[tail] = value
    else:
        out[head] = value


class TagBridge(Bridge):
    bridge_kind = "tag"
    bridge_id = "mhs.bridge.tags"

    def __init__(self, config: Mapping[str, Any], *, transport: Any = None, device_id: str | None = None,
                 resource_id: str = "main", validation: bool = False):
        super().__init__(device_id=device_id)
        self._config = copy.deepcopy(dict(config))
        self._profile = self._config["profile"]
        self._points = self._config["points"]
        if transport is None and not validation:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", "a tag bridge needs a transport object; the fake backend "
                                 "supplies one and the hardware factory builds one in the package's native.py",
                                 {"retryable": False})
        if transport is not None:
            missing = [name for name in TRANSPORT_METHODS[self._profile] if not callable(getattr(transport, name, None))]
            if missing:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", f"the tag transport has no {', '.join(missing)}",
                                     {"retryable": False})
        self._transport = transport
        self._resource_id = resource_id
        self._txn = threading.RLock()
        self._state = threading.Lock()
        self._stop_lane = threading.Lock()
        self._latched = False
        self._debt = False
        self._uncertain: set[str] = set()
        self._written: dict[str, Any] = {}
        self._inflight = 0
        self._generation = 0
        self._safe = False
        self._safe_epoch = -1
        self._close_error: str | None = None
        self._params_of: dict[str, list[str]] = {}
        for name, spec in self._config["writes"].items():
            self._params_of.setdefault(spec["point"], []).append(name)
        #: write-only points: after an unknown outcome no read can establish their value, and a stop that does not
        #: write them leaves it unknown
        self._write_only = frozenset(name for name, point in self._points.items() if point["access"] == "write")

    # -- description -----------------------------------------------------------
    @property
    def estop_native(self) -> str | None:
        return stop_summary(self._config["estop"])

    def describe(self) -> dict[str, Any]:
        out = super().describe()
        out.update({"profile": self._profile, "points": sorted(self._points)})
        return out

    @property
    def _effectful(self) -> bool:
        return bool(self._config["writes"]) or any(spec["kind"] == "effect"
                                                   for spec in self._config["commands"].values())

    # -- low-level point I/O -------------------------------------------------------
    @staticmethod
    def _deadline(context: BridgeContext, bound_s: float | None = None) -> float:
        remaining = context.remaining_ms() / 1000.0
        if bound_s is not None:
            remaining = min(remaining, bound_s)
        return time.monotonic() + max(0.0, remaining)

    def _timeout(self, deadline: float) -> float:
        return min(self._config["timeout_ms"] / 1000.0, deadline - time.monotonic())

    def _read_param(self, name: str, deadline: float) -> Any:
        """Read and decode one point (the recorder files these native calls under the read phase)."""
        point = self._points[name]
        timeout = self._timeout(deadline)
        if timeout <= 0:
            raise driver_failed("MHS.OUTCOME.TIMEOUT", f"no time budget remains to read {name}")
        try:
            raw = self._transport.read_point(copy.deepcopy(point["request"]), timeout_s=timeout)
        except TagRefused as exc:
            raise driver_failed("MHS.DEVICE.FAULTED", f"the device refused the read of {name}",
                                native_code=exc.code) from exc
        except Exception as exc:  # noqa: BLE001 - any read failure is a failed observation, never a value
            raise driver_failed("MHS.DEVICE.FAULTED", f"reading {name} failed ({type(exc).__name__})") from exc
        try:
            return decode(point, raw)
        except ValueError as exc:
            raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", str(exc)[:300]) from exc

    def _alpaca_ack(self, response: Any, point: Mapping[str, Any]) -> None:
        try:
            number, message = alpaca_error(response, point["name"])
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        if number in _ALPACA_REFUSALS:
            raise _Refused(f"Alpaca refused {point['name']} with error 0x{number:X}: {message}", number)
        if number != 0:
            raise RuntimeError(f"Alpaca error 0x{number:X} after {point['name']}: {message}")

    def _dispatch(self, kind: str, point: Mapping[str, Any], raw: Any, timeout: float) -> None:
        request = copy.deepcopy(point["request"])
        try:
            if kind == "write":
                ack = self._transport.write_point(request, copy.deepcopy(raw), timeout_s=timeout)
                if self._profile == "alpaca":
                    self._alpaca_ack(ack, point)
                elif ack is not True:
                    raise RuntimeError(f"the transport did not acknowledge the write of {point['name']}")
            else:
                ack = self._transport.invoke_point(request, copy.deepcopy(raw), timeout_s=timeout)
                self._alpaca_ack(ack, point)
        except TagRefused as exc:
            raise _Refused(f"the device refused the {kind} of {point['name']}", exc.code) from exc

    def _prepare(self, steps: list[Mapping[str, Any]], inputs: Mapping[str, Any]) -> list[tuple]:
        plan = []
        for step in steps:
            try:
                if "write" in step:
                    point = self._points[step["write"]]
                    if "input" in step and step["input"] not in inputs:
                        raise ValueError(f"input {step['input']!r} is required")
                    value = inputs[step["input"]] if "input" in step else step["value"]
                    plan.append(("write", point, encode(point, value), value))
                else:
                    point = self._points[step["invoke"]]
                    args = {}
                    for form, source in step["args"].items():
                        if "input" in source and source["input"] not in inputs:
                            raise ValueError(f"input {source['input']!r} is required")
                        value = inputs[source["input"]] if "input" in source else source["value"]
                        shape = {"name": f"{point['name']}.{form}", "type": point["params"][form],
                                 "request": {"profile": "alpaca"}}
                        args[form] = encode(shape, value)
                    plan.append(("invoke", point, args, None))
            except (ValueError, OverflowError) as exc:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", str(exc)[:300], {"retryable": False}) from exc
        return plan

    def _holds(self, predicates: list[Mapping[str, Any]], deadline: float) -> tuple[bool, dict[str, Any]]:
        observed: dict[str, Any] = {}
        held = True
        for predicate in predicates:
            point = self._points[predicate["point"]]
            if predicate["point"] not in observed:
                observed[predicate["point"]] = self._read_param(predicate["point"], deadline)
            try:
                key = compare_key(point, observed[predicate["point"]])
            except (ValueError, OverflowError):
                held = False
                continue
            if key not in {compare_key(point, value) for value in predicate["in"]}:
                held = False
        return held, observed

    def _confirm(self, predicates: list[Mapping[str, Any]], deadline: float) -> tuple[bool, dict[str, Any]]:
        """Read the predicates once, then poll within ``confirm_ms`` (bounded by the deadline) until they hold."""
        if not predicates:
            return True, {}
        window = min(deadline, time.monotonic() + self._config["confirm_ms"] / 1000.0)
        while True:
            held, observed = self._holds(predicates, deadline)
            if held or time.monotonic() >= window:
                return held, observed
            time.sleep(max(0.0, min(self._config["poll_ms"] / 1000.0, window - time.monotonic())))

    def _acknowledged(self, kind: str, point: Mapping[str, Any], value: Any) -> None:
        """Caller holds ``self._state``: the device acknowledged this write (write-only state shows it)."""
        if kind != "write":
            return
        self._uncertain.discard(point["name"])
        for param in self._params_of.get(point["name"], ()):
            self._written[param] = copy.deepcopy(value)

    def _forget(self, point_name: str) -> None:
        """Caller holds ``self._state``: the point's outcome is unknown."""
        self._debt = True
        self._uncertain.add(point_name)
        for param in self._params_of.get(point_name, ()):
            self._written.pop(param, None)

    def _rewrites_first(self, plan: list[tuple]) -> bool:
        """Caller holds ``self._state``: the plan writes every uncertain point before any other step."""
        pending = set(self._uncertain)
        for kind, point, _raw, _value in plan:
            if not pending:
                return True
            if kind != "write" or point["name"] not in pending:
                return False
            pending.discard(point["name"])
        return not pending

    # -- ordinary lane ------------------------------------------------------------------
    def _ordinary(self, plan: list[tuple], confirm: list[Mapping[str, Any]], context: BridgeContext,
                  label: str, *, purpose: str = "command") -> tuple[list[tuple], dict[str, Any]]:
        epoch = self.estop_epoch
        deadline = self._deadline(context)
        if not self._txn.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise busy(f"{label}: another tag operation holds the device")
        try:
            self.ensure_open()
            self._refuse_if_estopped(epoch, label)
            with self._state:
                if self._latched:
                    raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED", f"{label} refused: the tag bridge is latched",
                                         {"retryable": False})
                if self._debt:
                    raise make_mhs_error(
                        "MHS.DEVICE.PRECONDITION_UNMET",
                        f"{label} refused: an earlier write has an unknown outcome ({sorted(self._uncertain)}); "
                        "a confirmed stop (the e-stop or the safe-state action) must succeed first",
                        {"retryable": False, "details": {"uncertain_points": sorted(self._uncertain)}})
                if purpose == "command" and self._uncertain and not self._rewrites_first(plan):
                    raise make_mhs_error(
                        "MHS.DEVICE.PRECONDITION_UNMET",
                        f"{label} refused: the value of {sorted(self._uncertain)} is unknown after an unconfirmed "
                        "write; write it again (a parameter write, or a command that writes it before any other "
                        "step) first",
                        {"retryable": False, "details": {"uncertain_points": sorted(self._uncertain)}})
                self._inflight += 1
                self._generation += 1
                self._safe = False
            done: list[tuple] = []
            try:
                for kind, point, raw, value in plan:
                    with self._state:
                        preempted = self._latched or epoch != self.estop_epoch or self._closed
                    timeout = self._timeout(deadline)
                    if preempted or context.cancelled() or timeout <= 0:
                        if done:
                            with self._state:
                                for item in done:
                                    self._forget(item[1]["name"])
                            raise outcome_unknown(f"{label}: stopped after {len(done)} of {len(plan)} step(s); "
                                                  "the earlier writes stand and the device state is unconfirmed")
                        if preempted:
                            raise make_mhs_error("MHS.SAFETY.ESTOP_ENGAGED", f"{label} was not executed: a stop "
                                                 "fired while it waited", {"retryable": False,
                                                                           "details": {"preempted_by_estop": True}})
                        if context.cancelled():
                            raise signals.Cancelled(f"{label} was cancelled before its first write")
                        raise driver_failed("MHS.OUTCOME.TIMEOUT", f"{label}: no time budget remains before dispatch")
                    try:
                        self._dispatch(kind, point, raw, timeout)
                    except _Refused as exc:
                        if done:
                            with self._state:
                                for item in done:
                                    self._forget(item[1]["name"])
                            raise outcome_unknown(f"{label}: a later step was refused after earlier writes") from exc
                        raise driver_failed("MHS.DEVICE.FAULTED", str(exc)[:300], native_code=exc.code) from exc
                    except Exception as exc:  # noqa: BLE001 - the request may have reached the device
                        with self._state:
                            self._forget(point["name"])
                            for item in done:
                                self._forget(item[1]["name"])
                        raise outcome_unknown(f"{label}: the {kind} of {point['name']} has no confirmed outcome "
                                              f"({type(exc).__name__})") from exc
                    done.append((kind, point, raw, value))
                    with self._state:
                        self._acknowledged(kind, point, value)
                try:
                    held, observed = self._confirm(confirm, deadline)
                except Exception as exc:  # noqa: BLE001 - an unreadable confirmation leaves the writes unconfirmed
                    with self._state:
                        for item in done:
                            self._forget(item[1]["name"])
                    raise outcome_unknown(f"{label}: the writes were acknowledged but the confirmation could not be "
                                          "read") from exc
                if not held:
                    # The device acknowledged the write; a confirmation that does not hold within the window
                    # cannot tell a refused effect from a slow one. The device owes a confirmed stop.
                    with self._state:
                        for item in done:
                            self._forget(item[1]["name"])
                    raise outcome_unknown(f"{label}: the device acknowledged the write but its confirmation reads "
                                          f"{observed}; the effect is unconfirmed", details={"observed": observed})
                return done, observed
            finally:
                with self._state:
                    self._inflight -= 1
                    self._generation += 1
        finally:
            self._txn.release()

    # -- protective lane ----------------------------------------------------------------------
    def _protect(self, steps: list[Mapping[str, Any]], confirm: list[Mapping[str, Any]], context: BridgeContext,
                 *, engage: bool) -> dict[str, Any]:
        if engage:
            self._engage_estop()
            with self._state:
                self._latched = True
                self._safe = False
        epoch = self.estop_epoch
        deadline = self._deadline(context, STOP_BOUND_S)
        if not self._stop_lane.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return {"performed": False, "achieved": False, "failed": ["another stop holds the stop lane"]}
        try:
            with self._state:
                if self._closed:
                    return {"performed": False, "achieved": False, "failed": ["the bridge is closed"]}
                generation, idle = self._generation, self._inflight == 0
            failed: list[str] = []
            for kind, point, raw, _value in self._prepare(steps, {}):
                timeout = self._timeout(deadline)
                if timeout <= 0:
                    failed.append(f"{point['name']}: no time budget")
                    continue
                try:
                    self._dispatch(kind, point, raw, timeout)
                except _Refused as exc:
                    failed.append(f"{point['name']}: refused ({exc.code})")
                    continue
                except Exception as exc:  # noqa: BLE001 - try every stop step, then report
                    with self._state:
                        self._forget(point["name"])         # the stop write may or may not have landed
                    failed.append(f"{point['name']}: {type(exc).__name__}")
                    continue
                with self._state:
                    self._acknowledged(kind, point, _value)
            observed: dict[str, Any] = {}
            held = False
            if not failed:
                try:
                    held, observed = self._confirm(confirm, deadline)
                except Exception as exc:  # noqa: BLE001 - an unreadable confirmation is not a stop
                    failed.append(f"confirmation: {type(exc).__name__}")
            with self._state:
                achieved = (not failed and held and idle and self._inflight == 0 and generation == self._generation
                            and epoch == self.estop_epoch and not self._closed)
                if achieved:
                    self._safe = True
                    self._safe_epoch = epoch
                    self._debt = False
                    # Readable points are observed by every state read, the stop ends the methods' effect and its
                    # own acknowledged writes left the set above; a write-only point it did not write stays unknown.
                    self._uncertain &= self._write_only
                else:
                    self._safe = False
            return {"performed": True, "achieved": achieved, "failed": failed, "observed": observed,
                    "in_flight": not idle}
        finally:
            self._stop_lane.release()

    # -- Bridge contract ---------------------------------------------------------------------------
    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> Any:
        self.ensure_open()
        if resource_id != self._resource_id:
            raise unsupported(resource_id, kind="resource")
        reads, writes = self._config["reads"], self._config["writes"]
        declared = list(reads) + [name for name in writes if name not in reads]
        selected = declared if fields is None else list(fields)
        if any(name not in declared for name in selected):
            raise unsupported(resource_id, kind="field")
        deadline = self._deadline(BridgeContext.coerce(ctx))
        state: dict[str, Any] = {}
        cache: dict[str, Any] = {}
        for name in selected:
            if name in reads:
                point = reads[name]["point"]
                if point not in cache:
                    cache[point] = self._read_param(point, deadline)
                state[name] = cache[point]
            else:
                with self._state:
                    if name in self._written:
                        state[name] = self._written[name]
        return state

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        self.ensure_open()
        if resource_id != self._resource_id:
            raise unsupported(resource_id, kind="resource")
        patch = dict(patch or {})
        unknown = sorted(name for name in patch if name not in self._config["writes"])
        if unknown or not patch:
            raise make_mhs_error("MHS.RESOURCE.FIELD_UNKNOWN", f"not a declared tag write: {unknown}",
                                 {"retryable": False})
        names = sorted(patch)
        steps = [{"write": self._config["writes"][name]["point"], "value": patch[name]} for name in names]
        plan = self._prepare(steps, {})
        context = BridgeContext.coerce(ctx)
        verify = [(name, self._config["writes"][name]["verify"]) for name in names
                  if self._config["writes"][name]["verify"] is not None]
        predicates = [{"point": point, "in": [patch[name]]} for name, point in verify]
        self._ordinary(plan, predicates, context, "tag write", purpose="write")
        return {"applied": {name: copy.deepcopy(patch[name]) for name in names}}

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        spec = self._config["commands"].get(capability_id)
        if spec is None:
            raise unsupported(capability_id)
        args = dict(args or {})
        context = BridgeContext.coerce(ctx)
        if spec["kind"] == "read":
            if args:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"{capability_id} is an observation without inputs",
                                     {"retryable": False})
            deadline = self._deadline(context)
            out: dict[str, Any] = {}
            cache: dict[str, Any] = {}
            for field, point in spec["read"].items():
                if point not in cache:
                    cache[point] = self._read_param(point, deadline)
                _set_field(out, field, cache[point])
            return out
        if spec.get("safe_state"):
            if args:
                raise make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", f"{capability_id} is an input-free safe-state "
                                     "action", {"retryable": False})
            result = self._protect(spec["steps"], spec["confirm"], context, engage=False)
            if not result["achieved"]:
                raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                    f"{capability_id}: the stop was not confirmed ({'; '.join(result['failed'][:3])})",
                                    details={"in_flight": result.get("in_flight", False)})
            return self._result(spec, {}, result["observed"], context)
        plan = self._prepare(spec["steps"], args)
        _done, observed = self._ordinary(plan, spec["confirm"], context, capability_id)
        return self._result(spec, args, observed, context)

    def _result(self, spec: Mapping[str, Any], args: Mapping[str, Any], observed: Mapping[str, Any],
                context: BridgeContext) -> dict[str, Any]:
        out: dict[str, Any] = {}
        deadline = self._deadline(context)
        for field, source in spec["result"].items():
            if "point" in source:
                point = source["point"]
                out[field] = observed[point] if point in observed else self._read_param(point, deadline)
            elif "input" in source:
                out[field] = copy.deepcopy(args.get(source["input"]))
            else:
                out[field] = copy.deepcopy(source["value"])
        return out

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        estop = self._config["estop"]
        if estop is None:
            self._engage_estop()
            with self._state:
                self._latched = True
                self._safe = False
            return {}
        result = self._protect(estop["steps"], estop["confirm"], BridgeContext.coerce(ctx), engage=True)
        if result["failed"]:
            raise driver_failed("MHS.SAFETY.SAFE_STATE_UNREACHED", "the tag stop failed: " + "; ".join(result["failed"][:3]),
                                details={"failed": result["failed"][:8]})
        return {"estop": "engaged", "native": self.estop_native, "performed": result["performed"],
                "safe_state_achieved": result["achieved"]}

    def safe_state(self, ctx: Any = None) -> Any:
        estop = self._config["estop"]
        if estop is None:
            return {}
        result = self._protect(estop["steps"], estop["confirm"], BridgeContext.coerce(ctx), engage=False)
        return {"achieved": result["achieved"], "native": self.estop_native}

    def reset(self, ctx: Any = None) -> Any:
        estop = self._config["estop"]
        if estop is None:
            with self._state:
                self._latched = False
            return {}
        refusal = make_mhs_error("MHS.SAFETY.SAFE_STATE_UNREACHED", "reset needs a confirmed stop of the current e-stop "
                                 "epoch, no owed confirmation and no operation in flight", {"retryable": False})
        with self._state:
            if (self._closed or self._debt or self._inflight or not self._safe
                    or self._safe_epoch != self.estop_epoch):
                raise refusal
            epoch = self.estop_epoch
        try:
            held, _observed = self._holds(estop["confirm"], self._deadline(BridgeContext.coerce(ctx), STOP_BOUND_S))
        except Exception as exc:  # noqa: BLE001 - an unreadable confirmation never releases the latch
            raise refusal from exc
        with self._state:
            if (not held or epoch != self.estop_epoch or self._closed or self._debt or self._inflight
                    or not self._safe):
                self._safe = self._safe and held
                raise refusal
            self._latched = False
        return {"reset": True}

    def safety_status(self) -> dict[str, Any]:
        with self._state:
            if self._config["estop"] is None:
                if not self._effectful:
                    return {}
                return {"estop": {"native": None}, "safe_state": {"achieved": False}}
            achieved = (self._safe and not self._debt and self._inflight == 0 and not self._closed
                        and self._safe_epoch == self.estop_epoch)
            return {"estop": {"native": self.estop_native}, "safe_state": {"achieved": achieved},
                    "outcome_uncertain": self._debt or bool(self._uncertain),
                    "uncertain_points": sorted(self._uncertain)}

    def close(self) -> None:
        with self._state:
            already = self._closed
            self._closed = True
            self._latched = True
            self._safe = False
        if not already and self._transport is not None:
            close = getattr(self._transport, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:  # noqa: BLE001 - closing is best effort and never a stop
                    self._close_error = type(exc).__name__
        super().close()
