"""Analytic lab endpoint: pipette + plate reader + sample mover (an OpenMHS reference endpoint).

This module is a protocol fixture, not a driver template: its hand-written
bridges and manifests exercise multi-device sessions, the runtime safety rules
and the conformance suite.  Write a per-repository driver with
:mod:`mhs.driver` (``MHS/sdk/docs/driver-authoring.md``).  The bindings keep
their field names (``source_well``, ``volume_ul``, ``plate_id``,
``wavelengths_nm``, ``well_ids``, ``to``) and MCP tool names; that drift from
the catalogue classes, and ``cap.motion.stop.v1`` bound to a pipette and a
labware resource, are listed in ``MHS/sdk/docs/reference-endpoints.md`` and
realigned after the pilot.

One MHS endpoint owns three simulated devices that share one physical lab
bench, so a single session can orchestrate a real protocol:

1. ``cap.fluid.transfer.v1`` on the liquid handler draws sample from a source
   well and dispenses it into a destination well (integer microlitre
   bookkeeping, consumable tip state);
2. ``cap.sample.move.v1`` on the sample mover carries the plate from the liquid
   handler deck to the plate reader (and refuses to move a plate that is not
   where the command says it is);
3. ``cap.measure.spectrum.v1`` on the plate reader measures absorbance for a
   plate/wavelength set -- an integer analytic function of the well content, so
   the reading is deterministic and reproducible.

The shared :class:`LabBench` object is the single source of truth for plate
location and well volumes; devices expose their own resource documents, and the
manifest discloses that state is only restorable per device (the shared plate is
not independently snapshotted).

Run::

    python3 -m mhs.reference lab --port 7400
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from mhs.bridge.base import Bridge, BridgeContext, make_mhs_error
from mhs.signals import Cancelled
from mhs.reference._common import (
    INSTANCE_IDS,
    EndpointSpec,
    capability,
    device,
    exact_fidelity,
    resource,
)

__all__ = ["LabBench", "PipetteBridge", "PlateReaderBridge", "SampleMoverBridge", "build", "device_manifests"]

PIPETTE_SLUG = "lab/liquid-handler"
READER_SLUG = "lab/plate-reader"
MOVER_SLUG = "lab/sample-mover"

PIPETTE_RESOURCE = "pipette"
PLATE_RESOURCE = "plate"
READER_RESOURCE = "reader"
BENCH_RESOURCE = "bench"

TIP_CAPACITY_UL = 200
TIP_RACK_SIZE = 8
MAX_TRANSFERS = 64
DECK = "liquid_handler"
LOCATIONS = ("liquid_handler", "reader", "output")


class LabBench:
    """Shared physical bench: plate location and integer well volumes."""

    rows = "ABCDEFGH"
    columns = range(1, 9)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.plate_id = "plate-001"
        self.location = DECK
        self.door = "closed"
        self.wells: dict[str, dict[str, int]] = {}
        for row in self.rows:
            for column in self.columns:
                well = f"{row}{column}"
                volume = 150 if row == "A" and column <= 6 else 0
                self.wells[well] = {"volume_ul": volume, "max_volume_ul": TIP_CAPACITY_UL}
        self.transfers = 0

    # -- checks -----------------------------------------------------------
    def well(self, well_id: str) -> dict[str, int]:
        try:
            return self.wells[well_id]
        except KeyError as exc:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"well {well_id!r} does not exist on {self.plate_id!r}",
                {"retryable": False, "details": {"wells": sorted(self.wells)}},
            ) from exc

    def require_location(self, location: str, action: str) -> None:
        if self.location != location:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"{action} requires the plate at {location!r}; it is at {self.location!r}",
                {"retryable": True, "details": {"location": self.location, "required": location}},
            )

    # -- state ------------------------------------------------------------
    def plate_state(self) -> dict[str, Any]:
        return {
            "plate_id": self.plate_id,
            "wells": {well: dict(values) for well, values in self.wells.items()},
            "transfers": self.transfers,
        }

    def bench_state(self) -> dict[str, Any]:
        return {
            "plate_id": self.plate_id,
            "location": self.location,
            "door": self.door,
            "transfers": self.transfers,
        }

    def restore_plate(self, state: Mapping[str, Any]) -> None:
        if not isinstance(state, Mapping):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "plate state must be an object")
        self.plate_id = str(state.get("plate_id", self.plate_id))
        self.transfers = int(state.get("transfers", 0))
        wells = state.get("wells")
        if isinstance(wells, Mapping):
            for well, values in wells.items():
                if isinstance(values, Mapping) and well in self.wells:
                    self.wells[well]["volume_ul"] = int(values.get("volume_ul", 0))

    def restore_bench(self, state: Mapping[str, Any]) -> None:
        if not isinstance(state, Mapping):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "bench state must be an object")
        self.plate_id = str(state.get("plate_id", self.plate_id))
        self.location = str(state.get("location", self.location))
        self.transfers = int(state.get("transfers", 0))
        self.door = str(state.get("door", self.door))


class _LabBridge(Bridge):
    """Shared plumbing for the three lab-device bridges."""

    bridge_kind = "python-object"
    resource_id = "resource"
    manifest_caps: list[dict[str, Any]] = []
    device_risk_class = "R1"

    def __init__(self, bench: LabBench, *, device_id: str | None = None):
        super().__init__(device_id=device_id)
        self.bench = bench

    def capabilities(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.manifest_caps)

    def resources(self) -> list[dict[str, Any]]:
        return [{"resource_id": self.resource_id}]

    def safety_status(self) -> dict[str, Any]:
        return {
            "risk_class": self.device_risk_class,
            "estop": {"engaged": False, "latching": True},
            "interlocks": self.interlocks(),
            "permits": [],
            "safe_state": {"description": self.safe_state_description(), "achieved": True},
        }

    def interlocks(self) -> list[dict[str, str]]:
        # Hard, controllable interlocks only.  E-stop/latch state is server-owned
        # safety state (reported as estop.engaged), never an interlock: a latch
        # reported open here would make mhs.safety.reset impossible.
        return [
            {
                "id": "door_closed",
                "state": "closed" if self.bench.door == "closed" else "open",
                "description": "Bench safety door is closed",
            }
        ]

    def safe_state_description(self) -> str:
        return "No motion in progress; sample and consumables in a defined pose"

    def estop(self, reason: str = "", ctx: Any = None) -> dict[str, Any]:
        return {"estop": "engaged", "latched": True, "reason": reason}

    def reset(self, ctx: Any = None) -> dict[str, Any]:
        return {"reset": True, "estop": "released", "latched": False}

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        raise make_mhs_error(
            "MHS.DEVICE.UNSUPPORTED", f"{self.bridge_id} has no independent snapshot", {"retryable": False}
        )


class PipetteBridge(_LabBridge):
    """Analytic pipette with integer volume and consumable tip bookkeeping."""

    bridge_id = "mhs.bridge.reference.pipette"
    resource_id = PIPETTE_RESOURCE
    device_risk_class = "R2"

    def __init__(self, bench: LabBench, *, device_id: str | None = None):
        super().__init__(bench, device_id=device_id)
        self.tips_remaining = TIP_RACK_SIZE - 1
        self.tip_loaded = True
        self.tip_volume_ul = 0
        self.tips_used = 0
        self.cycles = 0
        self.mode = "idle"

    # -- state ------------------------------------------------------------
    def interlocks(self) -> list[dict[str, str]]:
        return super().interlocks() + [
            {
                "id": "plate_loaded",
                "state": "closed" if self.bench.location == DECK else "open",
                "description": "Plate is on the liquid handler deck",
            }
        ]

    def tip_state(self) -> dict[str, Any]:
        return {
            "tip_loaded": self.tip_loaded,
            "tip_volume_ul": self.tip_volume_ul,
            "tip_capacity_ul": TIP_CAPACITY_UL,
            "tips_remaining": self.tips_remaining,
            "tips_used": self.tips_used,
            "cycles": self.cycles,
            "mode": self.mode,
        }

    def pipette_state(self) -> dict[str, Any]:
        return self.tip_state()

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        if resource_id == PIPETTE_RESOURCE:
            state = self.tip_state()
        elif resource_id == PLATE_RESOURCE:
            state = self.bench.plate_state()
        else:
            raise make_mhs_error("MHS.DEVICE.UNSUPPORTED", f"unknown resource {resource_id!r}")
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    # -- helpers ----------------------------------------------------------
    def _check_tip(self) -> None:
        if self.tip_loaded and self.tip_volume_ul > TIP_CAPACITY_UL:
            raise make_mhs_error("MHS.SCHEMA.INVALID_STATE", "tip volume exceeds capacity", {"retryable": False})
        if not self.tip_loaded:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                "no pipette tip is loaded; the tip rack is empty",
                {"retryable": False, "remediation": "Load a new tip rack (not modelled by this reference endpoint)."},
            )

    def _check_volume(self, volume_ul: int) -> int:
        if not isinstance(volume_ul, int) or isinstance(volume_ul, bool):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "volume_ul must be an integer")
        if volume_ul < 1 or volume_ul > TIP_CAPACITY_UL:
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                f"volume_ul={volume_ul} is outside the declared envelope 1..{TIP_CAPACITY_UL}",
                {"retryable": False, "details": {"field": "volume_ul", "min": 1, "max": TIP_CAPACITY_UL}},
            )
        return int(volume_ul)

    def _consume_tip(self) -> None:
        self.tips_used += 1
        if self.tips_remaining > 0:
            self.tips_remaining -= 1
            self.tip_loaded = True
        else:
            self.tip_loaded = False
        self.tip_volume_ul = 0

    def aspirate(self, source_well: str, volume_ul: int) -> dict[str, Any]:
        self.bench.require_location(DECK, "aspirate")
        self._check_tip()
        volume = self._check_volume(volume_ul)
        well = self.bench.well(str(source_well))
        if well["volume_ul"] < volume:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"well {source_well!r} holds {well['volume_ul']} uL; cannot aspirate {volume} uL",
                {"retryable": False, "details": {"well": source_well, "available_ul": well["volume_ul"]}},
            )
        if self.tip_volume_ul + volume > TIP_CAPACITY_UL:
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                "aspiration would overfill the tip",
                {"retryable": False, "details": {"tip_volume_ul": self.tip_volume_ul, "volume_ul": volume}},
            )
        well["volume_ul"] -= volume
        self.tip_volume_ul += volume
        self.mode = "holding"
        return {"well": source_well, "aspirated_ul": volume, "tip_volume_ul": self.tip_volume_ul}

    def dispense(self, destination_well: str, volume_ul: int) -> dict[str, Any]:
        self.bench.require_location(DECK, "dispense")
        volume = self._check_volume(volume_ul)
        if volume > self.tip_volume_ul:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"tip holds {self.tip_volume_ul} uL; cannot dispense {volume} uL",
                {"retryable": False, "details": {"tip_volume_ul": self.tip_volume_ul}},
            )
        well = self.bench.well(str(destination_well))
        if well["volume_ul"] + volume > int(well.get("max_volume_ul", TIP_CAPACITY_UL)):
            raise make_mhs_error(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                f"well {destination_well!r} would overflow ({well['volume_ul']} + {volume} uL)",
                {"retryable": False, "details": {"well": destination_well, "volume_ul": well["volume_ul"]}},
            )
        well["volume_ul"] += volume
        self.tip_volume_ul -= volume
        self.mode = "dispensed"
        return {
            "well": destination_well,
            "dispensed_ul": volume,
            "well_volume_ul": well["volume_ul"],
            "tip_volume_ul": self.tip_volume_ul,
        }

    def transfer(self, source_well: str, destination_well: str, volume_ul: int) -> dict[str, Any]:
        if self.cycles >= MAX_TRANSFERS:
            raise make_mhs_error("MHS.SAFETY.ENVELOPE_VIOLATION", "transfer cycle limit reached")
        aspirated = self.aspirate(source_well, volume_ul)
        dispensed = self.dispense(destination_well, volume_ul)
        self._consume_tip()
        self.cycles += 1
        self.bench.transfers += 1
        return {
            "source_well": source_well,
            "destination_well": destination_well,
            "volume_ul": volume_ul,
            "tip_consumed": True,
            "tips_remaining": self.tips_remaining,
            "well_volume_ul": dispensed["well_volume_ul"],
            "aspirated": aspirated,
            "dispensed": dispensed,
        }

    def level(self, well_ids: Any = None) -> dict[str, Any]:
        ids = list(well_ids) if well_ids else sorted(self.bench.wells)
        levels = {}
        for well_id in ids:
            levels[str(well_id)] = dict(self.bench.well(str(well_id)))
        return {"plate_id": self.bench.plate_id, "wells": levels, "location": self.bench.location}

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self.ensure_open()
        return {
            PIPETTE_RESOURCE: self.tip_state(),
            PLATE_RESOURCE: self.bench.plate_state(),
        }

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.ensure_open()
        if not isinstance(snapshot, Mapping):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "snapshot must be an object")
        if isinstance(snapshot.get("snapshot"), Mapping):
            snapshot = snapshot["snapshot"]
        pipette = snapshot.get(PIPETTE_RESOURCE) or snapshot.get("state") or {}
        plate = snapshot.get(PLATE_RESOURCE)
        if isinstance(pipette, Mapping):
            self.tips_remaining = int(pipette.get("tips_remaining", self.tips_remaining))
            self.tip_loaded = bool(pipette.get("tip_loaded", self.tip_loaded))
            self.tip_volume_ul = int(pipette.get("tip_volume_ul", 0))
            self.tips_used = int(pipette.get("tips_used", 0))
            self.cycles = int(pipette.get("cycles", 0))
            self.mode = str(pipette.get("mode", "idle"))
        if isinstance(plate, Mapping):
            self.bench.restore_plate(plate)
        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        self.tip_volume_ul = 0
        self.mode = "idle"
        return {"mode": "idle", "safe_state_achieved": True, "tips_remaining": self.tips_remaining}

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        args = dict(args or {})
        context = BridgeContext.coerce(ctx)
        if context.cancelled():
            raise Cancelled(f"{capability_id} not started: cancellation was requested")
        if capability_id == "cap.fluid.aspirate.v1":
            return self.aspirate(str(args.get("source_well")), args.get("volume_ul"))
        if capability_id == "cap.fluid.dispense.v1":
            return self.dispense(str(args.get("destination_well")), args.get("volume_ul"))
        if capability_id == "cap.fluid.transfer.v1":
            return self.transfer(
                str(args.get("source_well")), str(args.get("destination_well")), args.get("volume_ul")
            )
        if capability_id == "cap.fluid.level.v1":
            return self.level(args.get("well_ids"))
        if capability_id == "cap.motion.stop.v1":
            return self.stop()
        raise make_mhs_error(
            "MHS.DEVICE.UNSUPPORTED", f"pipette bridge does not expose {capability_id!r}", {"retryable": False}
        )


class PlateReaderBridge(_LabBridge):
    """Analytic absorbance plate reader (deterministic integer photometry)."""

    bridge_id = "mhs.bridge.reference.plate-reader"
    resource_id = READER_RESOURCE
    device_risk_class = "R0"

    def __init__(self, bench: LabBench, *, device_id: str | None = None):
        super().__init__(bench, device_id=device_id)
        self.measurements = 0
        self.last_measurement: dict[str, Any] | None = None

    def interlocks(self) -> list[dict[str, str]]:
        return super().interlocks() + [
            {
                "id": "plate_loaded",
                "state": "closed" if self.bench.location == "reader" else "open",
                "description": "Plate is present on the reader",
            }
        ]

    def reader_state(self) -> dict[str, Any]:
        return {
            "plate_id": self.bench.plate_id,
            "measurements": self.measurements,
            "last_measurement": copy.deepcopy(self.last_measurement),
            "location": self.bench.location,
        }

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        if resource_id != READER_RESOURCE:
            raise make_mhs_error("MHS.DEVICE.UNSUPPORTED", f"unknown resource {resource_id!r}")
        state = self.reader_state()
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    @staticmethod
    def absorbance_mau(well_id: str, wavelength_nm: int, volume_ul: int) -> int:
        """Integer analytic absorbance in milli-absorbance units.

        deterministic, monotone in sample volume and path length; no RNG:
        ``((800 + 17*(hash(well) % 97)) + 2*(wavelength-400)) * volume // 200``.
        """

        if volume_ul <= 0:
            return 0
        well_code = sum(ord(char) for char in well_id) % 97
        base = 800 + 17 * well_code
        path = 2 * (int(wavelength_nm) - 400)
        return ((base + path) * int(volume_ul)) // 200

    def spectrum(self, plate_id: str, wavelengths_nm: Any, well_ids: Any = None) -> dict[str, Any]:
        self.bench.require_location("reader", "measure")
        if str(plate_id) != self.bench.plate_id:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"plate {plate_id!r} is not on the reader; found {self.bench.plate_id!r}",
                {"retryable": False, "details": {"plate_id": self.bench.plate_id}},
            )
        wavelengths = list(wavelengths_nm or [])
        if not wavelengths:
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "wavelengths_nm must not be empty")
        if len(wavelengths) > 16:
            raise make_mhs_error("MHS.SAFETY.ENVELOPE_VIOLATION", "at most 16 wavelengths per measurement")
        wells = list(well_ids) if well_ids else sorted(self.bench.wells)
        if len(wells) > 96:
            raise make_mhs_error("MHS.SAFETY.ENVELOPE_VIOLATION", "at most 96 wells per measurement")
        readings = []
        for well_id in wells:
            well = self.bench.well(str(well_id))
            volume = int(well["volume_ul"])
            for wavelength in wavelengths:
                wavelength_nm = int(wavelength)
                if wavelength_nm < 400 or wavelength_nm > 800:
                    raise make_mhs_error(
                        "MHS.SAFETY.ENVELOPE_VIOLATION",
                        f"wavelength {wavelength_nm} nm is outside the declared 400..800 nm",
                        {"retryable": False, "details": {"field": "wavelengths_nm"}},
                    )
                readings.append(
                    {
                        "well_id": str(well_id),
                        "wavelength_nm": wavelength_nm,
                        "absorbance_mAU": self.absorbance_mau(str(well_id), wavelength_nm, volume),
                        "volume_ul": volume,
                    }
                )
        self.measurements += 1
        self.last_measurement = {
            "plate_id": self.bench.plate_id,
            "readings": len(readings),
            "measurement_index": self.measurements,
        }
        return {
            "plate_id": self.bench.plate_id,
            "readings": readings,
            "measurement_index": self.measurements,
            "determinism": "exact",
        }

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self.ensure_open()
        return {READER_RESOURCE: self.reader_state()}

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.ensure_open()
        if not isinstance(snapshot, Mapping):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "snapshot must be an object")
        if isinstance(snapshot.get("snapshot"), Mapping):
            snapshot = snapshot["snapshot"]
        state = snapshot.get(READER_RESOURCE) if isinstance(snapshot, Mapping) else None
        if not isinstance(state, Mapping) and isinstance(snapshot.get("state"), Mapping):
            state = snapshot["state"]
        if isinstance(state, Mapping):
            self.measurements = int(state.get("measurements", 0))
            last = state.get("last_measurement")
            self.last_measurement = copy.deepcopy(last) if isinstance(last, Mapping) else None
        return self.snapshot()

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        args = dict(args or {})
        if BridgeContext.coerce(ctx).cancelled():
            raise Cancelled(f"{capability_id} not started: cancellation was requested")
        if capability_id == "cap.measure.spectrum.v1":
            return self.spectrum(
                str(args.get("plate_id")), args.get("wavelengths_nm"), args.get("well_ids")
            )
        raise make_mhs_error(
            "MHS.DEVICE.UNSUPPORTED", f"plate reader bridge does not expose {capability_id!r}", {"retryable": False}
        )


class SampleMoverBridge(_LabBridge):
    """Deterministic sample mover between the liquid handler, reader and output."""

    bridge_id = "mhs.bridge.reference.sample-mover"
    resource_id = BENCH_RESOURCE
    device_risk_class = "R1"

    def __init__(self, bench: LabBench, *, device_id: str | None = None):
        super().__init__(bench, device_id=device_id)
        self.moves = 0
        self.mode = "idle"

    def bench_state(self) -> dict[str, Any]:
        state = self.bench.bench_state()
        state.update({"moves": self.moves, "mode": self.mode})
        return state

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        self.ensure_open()
        if resource_id != BENCH_RESOURCE:
            raise make_mhs_error("MHS.DEVICE.UNSUPPORTED", f"unknown resource {resource_id!r}")
        state = self.bench_state()
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def move(self, plate_id: str, destination: str) -> dict[str, Any]:
        if self.bench.door != "closed":
            raise make_mhs_error(
                "MHS.SAFETY.INTERLOCK_OPEN",
                "bench safety door is open",
                {"retryable": False, "interlocks": [{"id": "door_closed", "state": "open"}]},
            )
        if destination not in LOCATIONS:
            raise make_mhs_error(
                "MHS.SCHEMA.INVALID_INPUT",
                f"unknown destination {destination!r}",
                {"retryable": False, "details": {"allowed": list(LOCATIONS)}},
            )
        if str(plate_id) != self.bench.plate_id:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"plate {plate_id!r} is not on the bench; found {self.bench.plate_id!r}",
                {"retryable": False, "details": {"plate_id": self.bench.plate_id}},
            )
        if destination == self.bench.location:
            raise make_mhs_error(
                "MHS.CONFLICT.PRECONDITION",
                f"plate is already at {destination!r}",
                {"retryable": True, "details": {"location": self.bench.location}},
            )
        previous = self.bench.location
        self.bench.location = destination
        self.moves += 1
        self.mode = "moved"
        return {"plate_id": self.bench.plate_id, "from": previous, "to": destination, "moves": self.moves}

    def stop(self) -> dict[str, Any]:
        self.mode = "idle"
        return {"mode": "idle", "safe_state_achieved": True, "plate_id": self.bench.plate_id}

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        self.ensure_open()
        return {BENCH_RESOURCE: self.bench_state()}

    def restore(self, snapshot: Any) -> dict[str, Any]:
        self.ensure_open()
        if not isinstance(snapshot, Mapping):
            raise make_mhs_error("MHS.SCHEMA.INVALID_INPUT", "snapshot must be an object")
        if isinstance(snapshot.get("snapshot"), Mapping):
            snapshot = snapshot["snapshot"]
        state = None
        if isinstance(snapshot, Mapping):
            state = snapshot.get(BENCH_RESOURCE)
            if not isinstance(state, Mapping) and isinstance(snapshot.get("state"), Mapping):
                state = snapshot["state"]
        if isinstance(state, Mapping):
            self.bench.restore_bench(state)
            self.moves = int(state.get("moves", 0))
            self.mode = str(state.get("mode", "idle"))
        return self.snapshot()

    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        args = dict(args or {})
        if BridgeContext.coerce(ctx).cancelled():
            raise Cancelled(f"{capability_id} not started: cancellation was requested")
        if capability_id == "cap.sample.move.v1":
            return self.move(str(args.get("plate_id")), str(args.get("to")))
        if capability_id == "cap.motion.stop.v1":
            return self.stop()
        raise make_mhs_error(
            "MHS.DEVICE.UNSUPPORTED", f"sample mover bridge does not expose {capability_id!r}", {"retryable": False}
        )


# ---------------------------------------------------------------------------
# manifests
# ---------------------------------------------------------------------------

_WELL_IDS = [f"{row}{column}" for row in LabBench.rows for column in LabBench.columns]


def _pipette_caps() -> list[dict[str, Any]]:
    return [
        capability(
            "cap.fluid.aspirate.v1",
            PIPETTE_RESOURCE,
            "Aspirate liquid from a well",
            "PipetteBridge::aspirate(source_well, volume_ul)",
            {
                "type": "object",
                "required": ["source_well", "volume_ul"],
                "properties": {
                    "source_well": {"type": "string", "default": "A1", "x-mhs-unit": "1"},
                    "volume_ul": {"type": "integer", "minimum": 1, "maximum": TIP_CAPACITY_UL, "default": 10, "x-mhs-unit": "uL"},
                },
            },
            {"type": "object"},
            summary="Draw a bounded volume of liquid from a plate well into the loaded pipette tip (integer uL bookkeeping).",
            tags=["liquid handling", "pipetting", "aspirate", "volume", "labware"],
            units={"volume_ul": "uL"},
            effects=["material.transfer"],
            hazards=["cross_contamination", "bubble_formation", "volume_error"],
            preconditions=["tip_loaded", "liquid_present", "plate on liquid handler deck"],
            constraints={"max_duration_ms": 5000},
            limits={"volume_ul": {"min": 1, "max": TIP_CAPACITY_UL, "unit": "uL", "reason": "tip capacity"}},
        ),
        capability(
            "cap.fluid.dispense.v1",
            PIPETTE_RESOURCE,
            "Dispense liquid into a well",
            "PipetteBridge::dispense(destination_well, volume_ul)",
            {
                "type": "object",
                "required": ["destination_well", "volume_ul"],
                "properties": {
                    "destination_well": {"type": "string", "default": "B1"},
                    "volume_ul": {"type": "integer", "minimum": 1, "maximum": TIP_CAPACITY_UL, "default": 10, "x-mhs-unit": "uL"},
                },
            },
            {"type": "object"},
            summary="Dispense a bounded volume from the pipette tip into a plate well, refusing well overflow.",
            tags=["liquid handling", "pipetting", "dispense", "volume", "labware"],
            units={"volume_ul": "uL"},
            effects=["material.transfer"],
            hazards=["spill", "well_overflow", "cross_contamination"],
            preconditions=["liquid in tip", "plate on liquid handler deck"],
            constraints={"max_duration_ms": 5000},
            limits={"volume_ul": {"min": 1, "max": TIP_CAPACITY_UL, "unit": "uL", "reason": "tip capacity"}},
        ),
        capability(
            "cap.fluid.transfer.v1",
            PIPETTE_RESOURCE,
            "Transfer liquid between wells",
            "PipetteBridge::transfer(source_well, destination_well, volume_ul)",
            {
                "type": "object",
                "required": ["source_well", "destination_well", "volume_ul"],
                "properties": {
                    "source_well": {"type": "string", "default": "A1"},
                    "destination_well": {"type": "string", "default": "B1"},
                    "volume_ul": {"type": "integer", "minimum": 1, "maximum": TIP_CAPACITY_UL, "default": 10, "x-mhs-unit": "uL"},
                },
            },
            {"type": "object"},
            summary="Atomically aspirate from a source well and dispense into a destination well, consuming one pipette tip.",
            tags=["liquid handling", "pipetting", "transfer", "volume", "consumable"],
            units={"volume_ul": "uL"},
            effects=["material.transfer", "consumable.tip_used"],
            hazards=["cross_contamination", "spill", "volume_error"],
            preconditions=["tip_loaded", "source volume sufficient", "destination capacity sufficient"],
            postconditions=["destination volume increased by volume_ul", "tip consumed"],
            constraints={"max_duration_ms": 10000},
            limits={"volume_ul": {"min": 1, "max": TIP_CAPACITY_UL, "unit": "uL", "reason": "tip capacity"}},
        ),
        capability(
            "cap.fluid.level.v1",
            PLATE_RESOURCE,
            "Read well volumes",
            "PipetteBridge::level(well_ids)",
            {
                "type": "object",
                "properties": {
                    "well_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": _WELL_IDS},
                        "minItems": 1,
                        "maxItems": 96,
                    }
                },
            },
            {"type": "object"},
            summary="Read the integer liquid volumes of plate wells (observational, no consumable use).",
            tags=["liquid handling", "plate", "volume", "observation"],
            determinism="exact",
            exclusive=False,
        ),
        capability(
            "cap.motion.stop.v1",
            PIPETTE_RESOURCE,
            "Abort pipetting and return to idle",
            "PipetteBridge::stop()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Stop the pipette in its declared safe state: tip stationary, no pending transfer.",
            tags=["liquid handling", "stop", "safe state"],
            effects=["motion.stop"],
            determinism="exact",
            exclusive=False,
        ),
    ]


def _reader_caps() -> list[dict[str, Any]]:
    return [
        capability(
            "cap.measure.spectrum.v1",
            READER_RESOURCE,
            "Measure absorbance spectra of a plate",
            "PlateReaderBridge::spectrum(plate_id, wavelengths_nm, well_ids)",
            {
                "type": "object",
                "required": ["plate_id", "wavelengths_nm"],
                "properties": {
                    "plate_id": {"type": "string", "default": "plate-001"},
                    "wavelengths_nm": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 400, "maximum": 800},
                        "minItems": 1,
                        "maxItems": 16,
                        "default": [600],
                        "x-mhs-unit": "nm",
                    },
                    "well_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": _WELL_IDS},
                        "minItems": 1,
                        "maxItems": 96,
                    },
                },
            },
            {"type": "object"},
            summary="Measure integer absorbance for the requested wells and wavelengths; deterministic analytic photometry.",
            tags=["plate reader", "absorbance", "spectrum", "measurement", "observation"],
            units={"wavelengths_nm": "nm"},
            effects=["measure.absorbance"],
            preconditions=["plate on reader", "plate location matches plate_id"],
            determinism="exact",
            exclusive=False,
        )
    ]


def _mover_caps() -> list[dict[str, Any]]:
    return [
        capability(
            "cap.sample.move.v1",
            BENCH_RESOURCE,
            "Move the sample plate between instruments",
            "SampleMoverBridge::move(plate_id, to)",
            {
                "type": "object",
                "required": ["plate_id", "to"],
                "properties": {
                    "plate_id": {"type": "string", "default": "plate-001"},
                    "to": {"type": "string", "enum": list(LOCATIONS)},
                },
            },
            {"type": "object"},
            summary="Carry the sample plate from its current instrument to another instrument or the output stacker.",
            tags=["sample mover", "plate transfer", "orchestration", "lab automation"],
            effects=["material.move"],
            hazards=["plate drop", "collision"],
            preconditions=["door closed", "plate present at current location"],
            constraints={"max_duration_ms": 10000},
            limits={"to": {"allowed": list(LOCATIONS), "reason": "declared bench locations"}},
        ),
        capability(
            "cap.motion.stop.v1",
            BENCH_RESOURCE,
            "Stop the sample mover",
            "SampleMoverBridge::stop()",
            {"type": "object", "properties": {}},
            {"type": "object"},
            summary="Stop the sample mover in its declared safe state: plate held still at its current location.",
            tags=["sample mover", "stop", "safe state"],
            effects=["motion.stop"],
            determinism="exact",
            exclusive=False,
        ),
    ]


def _bench_state_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["plate_id", "location", "door"],
        "properties": {
            "plate_id": {"type": "string"},
            "location": {"type": "string", "enum": list(LOCATIONS)},
            "door": {"type": "string", "enum": ["closed", "open"]},
            "transfers": {"type": "integer", "minimum": 0},
            "moves": {"type": "integer", "minimum": 0},
            "mode": {"type": "string"},
        },
    }


def _pipette_state_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tip_loaded", "tip_volume_ul", "tips_remaining"],
        "properties": {
            "tip_loaded": {"type": "boolean"},
            "tip_volume_ul": {"type": "integer", "minimum": 0, "maximum": TIP_CAPACITY_UL, "x-mhs-unit": "uL"},
            "tip_capacity_ul": {"type": "integer", "minimum": 1, "x-mhs-unit": "uL"},
            "tips_remaining": {"type": "integer", "minimum": 0},
            "tips_used": {"type": "integer", "minimum": 0},
            "cycles": {"type": "integer", "minimum": 0},
            "mode": {"type": "string"},
        },
    }


def _plate_state_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["plate_id", "wells"],
        "properties": {
            "plate_id": {"type": "string"},
            "wells": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "volume_ul": {"type": "integer", "minimum": 0, "x-mhs-unit": "uL"},
                        "max_volume_ul": {"type": "integer", "minimum": 1, "x-mhs-unit": "uL"},
                    },
                },
            },
            "transfers": {"type": "integer", "minimum": 0},
        },
    }


def _reader_state_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["plate_id", "measurements"],
        "properties": {
            "plate_id": {"type": "string"},
            "measurements": {"type": "integer", "minimum": 0},
            "last_measurement": {"type": ["object", "null"]},
            "location": {"type": "string", "enum": list(LOCATIONS)},
        },
    }


def _safety(
    risk_class: str,
    interlocks: list[dict[str, Any]],
    *,
    safe_state: str = "No motion in progress",
    achieved_by: tuple[str, ...] = ("cap.motion.stop.v1",),
) -> dict[str, Any]:
    """``achieved_by`` names only capabilities the device binds (an unbound one would make its e-stop fail)."""
    return {
        "risk_class": risk_class,
        "envelope": {},
        "interlocks": interlocks,
        "requires_permit": [],
        "estop": {"kind": "software", "latching": True, "latency_ms": 50, "reset": "mhs.safety.reset"},
        "safe_state": {"description": safe_state, "achieved_by": list(achieved_by)},
    }


def device_manifests(endpoint_id: str) -> list[dict[str, Any]]:
    """The three lab device manifests sharing one endpoint."""

    pipette_manifest = device(
        endpoint_id=endpoint_id,
        slug=PIPETTE_SLUG,
        display_name="Analytic pipette (simulated)",
        instance_id=INSTANCE_IDS["pipette"],
        mode="simulated",
        model="pipette-sim",
        resources=[
            resource(PIPETTE_RESOURCE, "lab.pipette", "Pipette tip state", _pipette_state_schema(), {
                "tip_loaded": True,
                "tip_volume_ul": 0,
                "tip_capacity_ul": TIP_CAPACITY_UL,
                "tips_remaining": TIP_RACK_SIZE - 1,
                "tips_used": 0,
                "cycles": 0,
                "mode": "idle",
            }),
            resource(PLATE_RESOURCE, "lab.labware", "Plate well volumes", _plate_state_schema(), {
                "plate_id": "plate-001",
                "wells": {
                    f"{row}{column}": {"volume_ul": 150 if row == "A" and column <= 6 else 0, "max_volume_ul": TIP_CAPACITY_UL}
                    for row in LabBench.rows
                    for column in LabBench.columns
                },
                "transfers": 0,
            }),
        ],
        capabilities=_pipette_caps(),
        safety=_safety(
            "R2",
            [
                {"id": "door_closed", "description": "Bench safety door is closed", "source": "simulated", "required_for": ["cap.fluid.*"]},
                {"id": "plate_loaded", "description": "Plate is on the liquid handler deck", "source": "simulated", "required_for": ["cap.fluid.*"]},
            ],
            safe_state="Tip stationary with no pending transfer",
        ),
        fidelity=exact_fidelity(
            "analytic",
            timestep_ms=0,
            gaps=[
                "Analytic fluid bookkeeping only: no viscosity, bubbles, droplet formation or evaporation",
                "No cross-contamination model",
                "Shared plate state is restored per device, not atomically across the endpoint",
            ],
        ),
        profile={
            "title": "Analytic pipette",
            "summary": "Integer microlitre pipette with consumable tip bookkeeping for deterministic liquid-handling protocol tests.",
            "tags": ["liquid handling", "pipetting", "volume bookkeeping", "deterministic simulation"],
            "operating_notes": [
                "Aspirate/dispense/transfer use integer microlitres; the tip capacity is 200 uL.",
                "Transfer consumes one tip and the reference rack has 8 tips.",
                "The plate must be on the liquid handler deck for pipetting.",
            ],
        },
        conformance_level="CL4",
        endpoint_name="lab",
        provenance_sources=["MHS/sdk/src/mhs/reference/lab.py"],
    )

    reader_manifest = device(
        endpoint_id=endpoint_id,
        slug=READER_SLUG,
        display_name="Absorbance plate reader (simulated)",
        instance_id=INSTANCE_IDS["reader"],
        mode="simulated",
        model="plate-reader-sim",
        resources=[
            resource(READER_RESOURCE, "instrument.spectrophotometer", "Plate reader state", _reader_state_schema(), {
                "plate_id": "plate-001",
                "measurements": 0,
                "last_measurement": None,
                "location": DECK,
            })
        ],
        capabilities=_reader_caps(),
        safety=_safety(
            "R0",
            [
                {"id": "door_closed", "description": "Bench safety door is closed", "source": "simulated", "required_for": ["cap.measure.*"]},
                {"id": "plate_loaded", "description": "Plate is present on the reader", "source": "simulated", "required_for": ["cap.measure.*"]},
            ],
            # The reader has no actuator: a measurement is instantaneous and
            # nothing has to be stopped, so no safe-state action is bound.
            safe_state="Reader idle: no measurement running, nothing moving",
            achieved_by=(),
        ),
        fidelity=exact_fidelity(
            "analytic",
            timestep_ms=0,
            gaps=["Analytic photometry only: no optical noise, stray light or path-length variation"],
        ),
        profile={
            "title": "Plate reader",
            "summary": "Deterministic integer absorbance reader; readings are a pure function of well content and wavelength.",
            "tags": ["plate reader", "absorbance", "spectrophotometry", "measurement"],
            "operating_notes": ["The plate must be moved to the reader before measuring."],
        },
        conformance_level="CL4",
        endpoint_name="lab",
        provenance_sources=["MHS/sdk/src/mhs/reference/lab.py"],
    )

    mover_manifest = device(
        endpoint_id=endpoint_id,
        slug=MOVER_SLUG,
        display_name="Sample mover (simulated)",
        instance_id=INSTANCE_IDS["mover"],
        mode="simulated",
        model="sample-mover-sim",
        resources=[
            resource(BENCH_RESOURCE, "lab.labware", "Shared bench state", _bench_state_schema(), {
                "plate_id": "plate-001",
                "location": DECK,
                "door": "closed",
                "transfers": 0,
                "moves": 0,
                "mode": "idle",
            })
        ],
        capabilities=_mover_caps(),
        safety=_safety(
            "R1",
            [
                {"id": "door_closed", "description": "Bench safety door is closed", "source": "simulated", "required_for": ["cap.sample.*"]},
            ],
            safe_state="Plate held still at a declared bench location",
        ),
        fidelity=exact_fidelity(
            "analytic",
            timestep_ms=0,
            gaps=["Point-to-point transfer only: no trajectory dynamics or collision geometry"],
        ),
        profile={
            "title": "Sample mover",
            "summary": "Moves the sample plate between the liquid handler, the plate reader and the output stacker.",
            "tags": ["sample mover", "plate transfer", "laboratory automation", "orchestration"],
            "operating_notes": ["Moves are instant and deterministic; the plate must be at the named location."],
        },
        conformance_level="CL4",
        endpoint_name="lab",
        provenance_sources=["MHS/sdk/src/mhs/reference/lab.py"],
    )

    return [pipette_manifest, reader_manifest, mover_manifest]


def build(endpoint_id: str) -> EndpointSpec:
    bench = LabBench()
    manifests = device_manifests(endpoint_id)
    bridges = {
        manifests[0]["device_id"]: PipetteBridge(bench, device_id=manifests[0]["device_id"]),
        manifests[1]["device_id"]: PlateReaderBridge(bench, device_id=manifests[1]["device_id"]),
        manifests[2]["device_id"]: SampleMoverBridge(bench, device_id=manifests[2]["device_id"]),
    }
    return EndpointSpec(
        name="lab",
        endpoint_id=endpoint_id,
        profile="MHS-Sim",
        devices=manifests,
        bridges=bridges,
        features=[
            "MHS.SAFETY.NOT_CERTIFIED",
            "deterministic-simulation",
            "multi-device",
            "orchestration",
            "mcp-projection-v1",
        ],
        notes="Analytic lab endpoint: pipette + plate reader + sample mover sharing one simulated bench.",
        conformance_level="CL4",
    )
