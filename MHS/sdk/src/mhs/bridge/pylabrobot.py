"""PyLabRobot LiquidHandler bridge: finite, self-contained pipetting operations (``plr-liquid-handler-v1``).

The bridge is a :class:`mhs.bridge.python.PythonObjectBridge` whose target is the backend object: a PyLabRobot
``LiquidHandler`` front end, or an upstream object that holds one at a declared attribute path.  Every PyLabRobot
coroutine runs on the bridge's single event loop (PyLabRobot binds its transports to the loop that ran
``setup()``), inside the retained native execution of the python-object bridge, so deadlines, cancellation,
unknown outcomes and the e-stop lanes are those of that bridge.

A composite operation is one capability call that starts with no tips mounted on the channels it uses and, when
every step succeeds, ends with those tips discarded:

* ``transfer``: ``pick_up_tips`` -> ``aspirate`` -> ``dispense`` -> ``discard_tips``;
* ``mix``: ``pick_up_tips`` -> (``aspirate`` -> ``dispense``) x cycles -> ``discard_tips``;
* ``tracked_volumes``: reads ``get_item(well).tracker.get_used_volume()`` of declared plates (bookkeeping, never a
  measurement).

Tips are chosen like a cursor-based tip manager: the first run of adjacent rows that all hold a tip, within one
column of the named tip rack, in column order (``num_items_x``/``num_items_y``, ``get_item(...).tracker.has_tip``).
This needs PyLabRobot tip tracking switched on; the driver profile cites the upstream line that does so, and the
bridge checks after the pick-up that the chosen spots no longer report a tip.  The wells of one call lie in one
column with strictly increasing rows and no repeat (all channels of a gantry head share one X position).

Labware is resolved by name on the handler's deck (``deck.get_resource(name)``) and wells or tip spots with
``get_item(identifier)``, only for names the driver declared.  Before each PyLabRobot step the bridge checks that
no e-stop engaged (of the driver or of this bridge), the operation was not cancelled (its cancel event: the
server sets it under its lock on an e-stop, a session close or an accepted cancellation, also when the device has
no native stop) and the bridge is not closing; a step that would start after any of these is never sent.  A step
already in progress is not interrupted by the bridge.

Outcomes of a failing step.  PyLabRobot's front end checks tips and tracked volumes before it calls its backend
(``NoTipError``, ``HasTipError``, ``TooLittleLiquidError``, ``TooLittleVolumeError``, ``CrossContaminationError``):
such an error means the step sent nothing, and the call fails ``MHS.DEVICE.PRECONDITION_UNMET`` with the completed
steps.  Any other error raised by a step may come from the backend after the command reached the device (a
timeout, an I/O error, a firmware error reported as ``ChannelizedError``): the outcome is unknown
(``MHS.OUTCOME.UNKNOWN`` with the step and the completed steps, no native text), and the python-object bridge fences
new effects until a confirmed stop and an operator reset.  A failed or interrupted operation performs no cleanup
motion: tips and liquid stay where the last completed step left them.  This module imports no PyLabRobot code.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

import re

from mhs import signals
from mhs.bridge.base import (BridgeContext, MappingError, UnitError, driver_failed, make_mhs_error,
                             outcome_unknown)
from mhs.bridge.python import PythonObjectBridge
from mhs.errors import MHSError

__all__ = ["OP_PREFIX", "PlrBridge"]

#: Reserved native attribute path of a composite operation; the bridge resolves it itself, never on the target.
OP_PREFIX = "_mhs_plr_op."
#: Reserved keyword that carries the admission fence into the operation coroutine.
_FENCE = "_mhs_plr_fence"
#: PyLabRobot front-end bookkeeping errors, raised before the backend is called (matched by class name in the MRO;
#: never a wrapper such as ``ChannelizedError``) -> the precondition they report.
_PRECONDITIONS = {"NoTipError": "tip_mounted", "HasTipError": "channel_free", "TooLittleLiquidError": "liquid_present",
                  "TooLittleVolumeError": "room_available", "CrossContaminationError": "uncontaminated_tip"}
_WELL = re.compile(r"^([A-Z]+)([0-9]+)$")


def _input_invalid(message: str) -> Exception:
    return make_mhs_error("MHS.CAPABILITY.INPUT_INVALID", message, {"retryable": False})


class PlrBridge(PythonObjectBridge):
    """A python-object bridge with the finite PyLabRobot composite operations of one driver profile.

    ``plr`` is the compiled runtime profile of :func:`mhs.driver.pylabrobot.compile_profile`: ``handler`` (the
    attribute path from the target to the ``LiquidHandler``, ``""`` for the target itself), ``labware`` (name ->
    ``plate`` or ``tip_rack``), ``channels`` (the most channels one operation may use) and ``operations`` (native
    marker -> ``{"capability_id", "kind"}``).  ``outer_epoch`` returns the e-stop epoch of the driver that owns the
    bridge; with no native stop bound, the driver's software latch advances only that epoch.
    """

    def __init__(self, config: Mapping[str, Any], *, plr: Mapping[str, Any],
                 outer_epoch: Callable[[], int] | None = None, **kwargs: Any) -> None:
        operations = dict(plr.get("operations") or {})
        self._plr_handler = str(plr.get("handler") or "")
        self._plr_labware = {str(name): str(kind) for name, kind in dict(plr.get("labware") or {}).items()}
        self._plr_channels = int(plr.get("channels") or 0)
        self._plr_by_native = {str(native): dict(spec) for native, spec in operations.items()}
        self._plr_by_capability = {str(spec["capability_id"]): str(native) for native, spec in operations.items()}
        self._outer_epoch = outer_epoch if outer_epoch is not None else (lambda: 0)
        super().__init__(config, **kwargs)

    # -- admission -------------------------------------------------------------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        native = self._plr_by_capability.get(str(capability_id))
        if native is None:
            return super().call(capability_id, args, ctx)
        # The fence is taken before the input is checked and before the device lock is awaited.
        epochs = (self._outer_epoch(), self.estop_epoch)
        self._ensure_loaded()
        binding = self._caps[str(capability_id)]
        context = BridgeContext.coerce(ctx)
        fence = (epochs, context.cancel_event)
        if context.cancelled():
            raise signals.Cancelled("operation cancelled before the PyLabRobot call")
        payload = dict(args or {})
        self._check_payload(self._plr_by_native[native]["kind"], payload)
        call = binding["call"]
        try:
            mapped = call.args.map(payload)
        except (MappingError, UnitError, TypeError, ValueError) as exc:
            raise make_mhs_error(
                "MHS.CAPABILITY.INPUT_INVALID", f"cannot map input for {capability_id!r}: {exc}",
                {"retryable": False, "details": {"capability_id": capability_id}}) from exc
        mapped[_FENCE] = fence
        epoch = self.estop_epoch
        if binding.get("concurrency") == "shared":
            raw = self._perform(call, mapped, context, epoch=epoch)
        else:
            with self._lock:
                self._refuse_if_estopped(epoch, f"call {capability_id!r}")
                if context.cancelled():
                    raise signals.Cancelled("operation cancelled while it waited for the device")
                raw = self._perform(call, mapped, context, epoch=epoch)
        return self._map_result(binding, raw)

    def _check_payload(self, kind: str, payload: Mapping[str, Any]) -> None:
        """Cross-field rules the input schema cannot state; refused before any native call."""
        if kind == "tracked_volumes":
            self._labware_kind(payload.get("labware"), "plate", "labware")
            return
        self._labware_kind(payload.get("tip_rack"), "tip_rack", "tip_rack")
        channels = payload.get("source_wells" if kind == "transfer" else "wells")
        if not isinstance(channels, list) or not channels:
            raise _input_invalid("at least one well (one channel) is needed")
        if len(channels) > self._plr_channels:
            raise _input_invalid(f"at most {self._plr_channels} channels can be used by one operation")
        if kind == "transfer":
            self._labware_kind(payload.get("source"), "plate", "source")
            self._labware_kind(payload.get("target"), "plate", "target")
            if len(payload.get("target_wells") or []) != len(channels):
                raise _input_invalid("source_wells and target_wells must have the same length (one per channel)")
            self._check_layout(channels, "source_wells")
            self._check_layout(payload.get("target_wells"), "target_wells")
        elif kind == "mix":
            self._labware_kind(payload.get("labware"), "plate", "labware")
            self._check_layout(channels, "wells")
        else:  # pragma: no cover - compile_profile admits only the kinds above
            raise _input_invalid(f"unknown PyLabRobot operation kind {kind!r}")

    @staticmethod
    def _check_layout(wells: Any, field: str) -> None:
        """One call addresses one column, rows strictly increasing with the channel number, no well twice.

        The channels of a gantry pipetting head share one X position, and channel order runs from the back row
        to the front row; two channels in one well, or wells in two columns, cannot be served by one command.
        """
        parsed = [_WELL.match(item) if isinstance(item, str) else None for item in wells or []]
        if not parsed or any(match is None for match in parsed):
            raise _input_invalid(f"{field}: every well must be a row letter and a column number, e.g. A1")
        columns = {int(match.group(2)) for match in parsed}
        if len(columns) != 1:
            raise _input_invalid(f"{field}: the wells of one call must lie in one column (the channels share one X "
                                 "position)")
        rows = [match.group(1) for match in parsed]
        keys = [(len(row), row) for row in rows]
        if any(after <= before for before, after in zip(keys, keys[1:])):
            raise _input_invalid(f"{field}: rows must strictly increase with the channel number (no well twice)")

    def _labware_kind(self, name: Any, kind: str, field: str) -> str:
        declared = self._plr_labware.get(name) if isinstance(name, str) else None
        if declared != kind:
            raise _input_invalid(f"{field} must name a declared {kind.replace('_', ' ')}")
        return name

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> Any:
        """A resource without declared reads has an empty state (the operations carry their own outputs)."""
        if str(resource_id) not in self._reads and any(binding["resource"] == str(resource_id)
                                                         for binding in self._caps.values()):
            self._ensure_loaded()
            return {}
        return super().read(resource_id, fields, ctx)

    # -- resolution ------------------------------------------------------------------------------------------
    def _resolve(self, dotted: str) -> Callable[..., Any]:
        if dotted.startswith(OP_PREFIX):
            spec = self._plr_by_native.get(dotted)
            if spec is None:
                raise make_mhs_error("MHS.CAPABILITY.NOT_BOUND", f"no PyLabRobot operation {dotted!r}",
                                     {"retryable": False})
            kind = spec["kind"]
            return lambda **keyword: self._operation(kind, keyword)
        return super()._resolve(dotted)

    async def _operation(self, kind: str, keyword: dict[str, Any]) -> dict[str, Any]:
        fence = keyword.pop(_FENCE, None)
        self._fence(fence)
        handler = self._handler()
        if kind == "transfer":
            return await self._transfer(handler, fence, **keyword)
        if kind == "mix":
            return await self._mix(handler, fence, **keyword)
        if kind == "tracked_volumes":
            return self._tracked_volumes(handler, **keyword)
        raise make_mhs_error("MHS.CAPABILITY.NOT_BOUND", f"unknown PyLabRobot operation {kind!r}",
                             {"retryable": False})

    def _fence(self, fence: Any) -> None:
        """Refuse a step after an e-stop, a cancellation or a close since the operation was admitted."""
        epochs, event = fence if isinstance(fence, tuple) and len(fence) == 2 else (None, None)
        if epochs is None or (self._outer_epoch(), self.estop_epoch) != epochs or self._closing:
            raise make_mhs_error(
                "MHS.SAFETY.ESTOP_ENGAGED",
                "a PyLabRobot step was not sent: an e-stop or close happened after the operation was admitted",
                {"retryable": False, "details": {"preempted_by_estop": True}})
        if event is not None and event.is_set():
            raise signals.Cancelled("the operation was cancelled (e-stop, session close or cancellation); the next "
                                    "PyLabRobot step was not sent")

    def _handler(self) -> Any:
        current = self._target
        for part in self._plr_handler.split("."):
            if part:
                current = getattr(current, part)
        return current

    @staticmethod
    def _items(resource: Any, identifiers: list[str]) -> list[Any]:
        return [resource.get_item(identifier) for identifier in identifiers]

    @staticmethod
    def _next_tips(rack: Any, count: int) -> tuple[list[str], list[Any]]:
        """The first ``count`` adjacent rows of one column that all hold a tip, scanning columns in order."""
        rows, columns = int(rack.num_items_y), int(rack.num_items_x)
        letters = [chr(ord("A") + row) for row in range(rows)]
        for column in range(1, columns + 1):
            for start in range(0, rows - count + 1):
                names = [f"{letters[start + offset]}{column}" for offset in range(count)]
                spots = [rack.get_item(name) for name in names]
                if all(spot.tracker.has_tip for spot in spots):
                    return names, spots
        raise driver_failed("MHS.DEVICE.PRECONDITION_UNMET",
                            f"the tip rack has no {count} adjacent tip(s) left in one column",
                            details={"precondition": "tips_available", "completed_steps": []}, retryable=False)

    async def _pick_up(self, fence: Any, done: list[str], handler: Any, rack: Any, count: int) -> list[str]:
        names, spots = self._next_tips(rack, count)
        await self._step(fence, done, "pick_up_tips", handler.pick_up_tips, spots, use_channels=list(range(count)))
        if any(spot.tracker.has_tip for spot in spots):
            raise driver_failed("MHS.DEVICE.FAULTED", "tip tracking did not record the pick-up; automatic tip "
                                "selection cannot be trusted", details={"step": "pick_up_tips", "completed_steps":
                                                                         list(done)}, retryable=False)
        return names

    async def _step(self, fence: Any, done: list[str], name: str, method: Callable[..., Any], *args: Any,
                    **keyword: Any) -> None:
        """Run one front-end coroutine after the fence; a failure names the steps that already completed.

        A front-end bookkeeping error means this step sent nothing: ``PRECONDITION_UNMET`` (a known failure).
        Any other error may have reached the device: an unknown outcome, which fences the bridge.
        """
        self._fence(fence)
        try:
            await method(*args, **keyword)
        except (signals.DriverSignal, MHSError):
            raise
        except Exception as exc:  # noqa: BLE001 - translated below, never swallowed
            names = {base.__name__ for base in type(exc).__mro__}
            precondition = next((value for key, value in _PRECONDITIONS.items() if key in names), None)
            details: dict[str, Any] = {"step": name, "completed_steps": list(done),
                                       "native_error_type": type(exc).__name__}
            steps = ", ".join(done) or "none"
            if precondition is not None:
                details["precondition"] = precondition
                details["native_message"] = str(exc)[:300]
                raise driver_failed("MHS.DEVICE.PRECONDITION_UNMET",
                                    f"PyLabRobot {name} refused before the backend ({type(exc).__name__}); completed "
                                    f"steps: {steps}", details=details, retryable=False) from exc
            raise outcome_unknown(f"PyLabRobot {name} raised {type(exc).__name__} after it may have reached the "
                                  f"device; completed steps: {steps}", details=details) from exc
        done.append(name)

    async def _transfer(self, handler: Any, fence: Any, *, tip_rack: str, source: str, target: str,
                        source_wells: list[str], target_wells: list[str], volume: float) -> dict[str, Any]:
        deck = handler.deck
        rack = deck.get_resource(tip_rack)
        source_plate = deck.get_resource(source)
        target_plate = deck.get_resource(target)
        count = len(source_wells)
        use = list(range(count))
        wells_from = self._items(source_plate, list(source_wells))
        wells_to = self._items(target_plate, list(target_wells))
        vols = [float(volume)] * count
        done: list[str] = []
        self._fence(fence)
        tips = await self._pick_up(fence, done, handler, rack, count)
        await self._step(fence, done, "aspirate", handler.aspirate, wells_from, vols=vols, use_channels=use)
        await self._step(fence, done, "dispense", handler.dispense, wells_to, vols=vols, use_channels=use)
        await self._step(fence, done, "discard_tips", handler.discard_tips, use_channels=use)
        return {"transferred_volume": float(volume), "channels": count, "tips": tips}

    async def _mix(self, handler: Any, fence: Any, *, tip_rack: str, labware: str, wells: list[str],
                   volume: float, cycles: int) -> dict[str, Any]:
        deck = handler.deck
        rack = deck.get_resource(tip_rack)
        plate = deck.get_resource(labware)
        count = len(wells)
        use = list(range(count))
        items = self._items(plate, list(wells))
        vols = [float(volume)] * count
        done: list[str] = []
        self._fence(fence)
        tips = await self._pick_up(fence, done, handler, rack, count)
        for cycle in range(1, int(cycles) + 1):
            await self._step(fence, done, f"aspirate[{cycle}]", handler.aspirate, items, vols=vols, use_channels=use)
            await self._step(fence, done, f"dispense[{cycle}]", handler.dispense, items, vols=vols, use_channels=use)
        await self._step(fence, done, "discard_tips", handler.discard_tips, use_channels=use)
        return {"mixed_volume": float(volume), "cycles": int(cycles), "channels": count, "tips": tips}

    @staticmethod
    def _tracked_volumes(handler: Any, *, labware: str, wells: list[str]) -> dict[str, Any]:
        plate = handler.deck.get_resource(labware)
        volumes = [float(item.tracker.get_used_volume()) for item in PlrBridge._items(plate, list(wells))]
        return {"volumes": volumes}

    def describe(self) -> dict[str, Any]:
        out = super().describe()
        out["pylabrobot"] = {"profile": "plr-liquid-handler-v1", "handler": self._plr_handler,
                             "labware": dict(sorted(self._plr_labware.items())), "channels": self._plr_channels,
                             "operations": sorted(self._plr_by_capability)}
        return out
