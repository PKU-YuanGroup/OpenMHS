"""OpenMHS driver for gh.aicell-lab/hamilton-control: the PyLabRobot Incubator front end (hardware mode).

The upstream repository's own entry point is ``try.py``, which builds a PyLabRobot ``LiquidHandler`` over the Hamilton
Vantage backend (try.py:1-5, README.md:3).  The card's entry symbols do not include the Vantage class, but they do
include the concrete ``pylabrobot.incubators.incubator:Incubator`` front end, and the card's hints name its
temperature, shaking and plate-transfer methods.  This package therefore drives that Incubator front end through
a direct ``Driver`` rather than the card's ``PyLabRobotDriver`` helper: the helper serves only a ``LiquidHandler``
(README of the exemplar and MHS/sdk/docs/pylabrobot-helper.md), and an Incubator is not one.

The Incubator API used here is source-backed: ``setup`` (incubator.py:62-64), ``get_num_free_sites`` (66-67),
``fetch_plate_to_loading_tray`` (76-85), ``take_in_plate`` (115-133), ``set_temperature`` (135-136),
``get_temperature`` (139-140), ``start_shaking`` (148-149) and ``stop_shaking`` (151-152).  The front end also
exposes ``open_door``/``close_door`` (142-146), but this package does not expose them as actions.  The hardware
factory in ``native.py`` builds the front end over a deployment-supplied ``IncubatorBackend`` (or the clone's
Cytomat serial backend) and requires an independent power-cut relay callable.

SAFETY.  The native API has no heater-off command and ``Cytomat.set_temperature`` is not implemented
(cytomat.py:370-371); ``Machine.stop`` is the lifecycle teardown, not a motion stop (machine.py:67-70).

MODEL REVIEW (2026-11-05).  The author's ``@estop`` and ``safe_state=True`` action stopped the shaker and then called
``options['safe_stop']``, a "deployment-supplied independent power-cut relay" callable that no line of the clone
shows; the fake made it a no-op, so the SDK reported an achieved safe state for an invented stop.  The reviewer
removed the relay: the e-stop still sends ``stop_shaking`` (the only stop-like call of the front end), then raises
``MHS.SAFETY.SAFE_STATE_UNREACHED``, and the shaker-stop action is no longer a safe-state action.  The package is
blocked: the repository's device is the Hamilton Vantage liquid handler (README.md:3, try.py:4-5), whose vendored
backend has no stop command (``HamiltonLiquidHandler.stop`` only fails waiting tasks, base.py:98-102); the Incubator
front end served here is vendored PyLabRobot library code that no file of the repository uses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read


class HamiltonControlIncubator(Driver):
    device_id = "hamilton-control-incubator"
    device_kind = "instrument.incubator"
    mode = "hardware"
    risk = "R2"
    native = "pylabrobot.incubators.incubator:Incubator"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeIncubator"}
    vendor, model = "aicell-lab / PyLabRobot", "PyLabRobot Incubator (Cytomat backend)"
    display_name = "PyLabRobot Incubator front end (Cytomat backend)"
    tags = ["incubator", "cytomat", "pylabrobot", "temperature", "shaking", "plate-transfer", "hamilton-control"]
    safe_state = ("No acknowledged stop: the e-stop sends Incubator.stop_shaking, which stops only the shaker, and "
                  "then reports SAFE_STATE_UNREACHED; a plate transfer in progress, the door and temperature control "
                  "are not stopped, since the front end has no stop or heater-off command and Machine.stop is "
                  "teardown")
    facts = [
        Fact("The project controls the Hamilton Vantage liquid handler using PyLabRobot on a Raspberry Pi 5",
             source="vendor_doc", ref="README.md:3"),
        Fact("try.py builds a PyLabRobot LiquidHandler over the Vantage backend and a VantageDeck",
             source="upstream_code", ref="try.py:4-5"),
        Fact("The clone contains a concrete PyLabRobot Incubator front end", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:23"),
        Fact("Incubator.setup awaits the backend setup and then registers the racks", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:62-64"),
        Fact("Incubator.get_num_free_sites sums the free sites of every rack", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:66-67"),
        Fact("Incubator.fetch_plate_to_loading_tray fetches the named plate and moves it to the loading tray",
             source="upstream_code", ref="pylabrobot/incubators/incubator.py:76-85"),
        Fact("Incubator.take_in_plate moves the loading-tray plate into a chosen site", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:115-133"),
        Fact("Incubator.set_temperature delegates to the backend set_temperature", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:135-136"),
        Fact("Incubator.get_temperature delegates to the backend get_temperature", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:139-140"),
        Fact("Incubator.open_door and close_door delegate to the backend", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:142-146"),
        Fact("Incubator.start_shaking takes a frequency and delegates to the backend", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:148-149"),
        Fact("Incubator.stop_shaking delegates to the backend stop_shaking", source="upstream_code",
             ref="pylabrobot/incubators/incubator.py:151-152"),
        Fact("The Cytomat backend's set_temperature raises NotImplementedError", source="upstream_code",
             ref="pylabrobot/incubators/cytomat/cytomat.py:370-371"),
        Fact("Cytomat.get_temperature returns the incubation query's actual value", source="upstream_code",
             ref="pylabrobot/incubators/cytomat/cytomat.py:359-360"),
        Fact("Machine.stop calls backend.stop and is the lifecycle teardown, not a motion stop",
             source="upstream_code", ref="pylabrobot/machines/machine.py:67-70"),
        Fact("HamiltonLiquidHandler.stop fails every waiting task and clears the queue; it writes no stop command",
             source="upstream_code",
             ref="pylabrobot/liquid_handling/backends/hamilton/base.py:98-102"),
        Fact("Vantage subclasses HamiltonLiquidHandler", source="upstream_code",
             ref="pylabrobot/liquid_handling/backends/hamilton/vantage.py:342"),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._shaking = False

    async def setup(self) -> None:
        self._shaking = False
        await self.native.setup()

    async def teardown(self) -> None:
        await self.native.stop()

    @read("temperature", unit="Cel", description="Incubator temperature from the backend")
    async def read_temperature(self) -> float:
        return await self.native.get_temperature()

    @read("num_free_sites", type="integer", description="Free plate sites across the incubator racks")
    def read_num_free_sites(self) -> int:
        return self.native.get_num_free_sites()

    @action(
        cap="cap.measure.temperature.v1",
        description="Measure the incubator temperature",
        input={
            "location": Field("string", description="Optional location label; the Incubator has one probe",
                              required=False),
            "probe": Field("string", description="Optional probe label; the Incubator has one probe", required=False),
        },
    )
    async def measure_temperature(self, location: str | None = None, probe: str | None = None) -> dict[str, Any]:
        value = await self.native.get_temperature()
        return {"temperature": value, "sampled_at": datetime.now(timezone.utc).isoformat()}

    @action(
        cap="cap.thermal.setpoint.v1",
        description="Set the incubator temperature setpoint",
        input={
            "target_temperature": Field(
                "number",
                unit="Cel",
                description="Target temperature",
                limit=Limit.operator_required(
                    "the clone states no temperature range for the deployed incubator; the operator supplies the "
                    "safe setpoint range"
                ),
            )
        },
    )
    async def set_temperature(self, target_temperature: float) -> dict[str, Any]:
        await self.native.set_temperature(target_temperature)
        actual = await self.native.get_temperature()
        return {"setpoint": target_temperature, "actual_temperature": actual}

    @action(
        name="x-cap.aicell-lab.start_shaking.v1",
        description="Start the incubator shaker at a frequency",
        input={
            "frequency": Field(
                "number",
                unit="Hz",
                description="Shaking frequency",
                limit=Limit.operator_required(
                    "the clone states no shaking frequency range for the deployed incubator; the operator supplies "
                    "the safe range"
                ),
            )
        },
        output={"frequency": Field("number", unit="Hz", description="Frequency sent to the backend")},
        risk="R2",
    )
    async def start_shaking(self, frequency: float) -> dict[str, Any]:
        await self.native.start_shaking(frequency)
        self._shaking = True
        return {"frequency": frequency}

    @action(
        name="x-cap.aicell-lab.stop_shaking.v1",
        description="Stop the shaker (Incubator.stop_shaking); it stops no plate transfer and no temperature control",
        input={},
        output={"stopped": Field("boolean", description="stop_shaking returned without raising")},
        risk="R0",
    )
    async def stop_shaking(self) -> dict[str, Any]:
        await self.native.stop_shaking()
        self._shaking = False
        return {"stopped": True}

    @action(
        name="x-cap.aicell-lab.fetch_plate.v1",
        description="Fetch a named plate from its incubator site to the loading tray",
        input={"plate_name": Field("string", description="Name of a plate registered on an incubator rack")},
        output={"plate": Field("string", description="Plate requested")},
        risk="R2",
    )
    async def fetch_plate(self, plate_name: str) -> dict[str, Any]:
        await self.native.fetch_plate_to_loading_tray(plate_name)
        return {"plate": plate_name}

    @action(
        name="x-cap.aicell-lab.take_in_plate.v1",
        description="Take the loading-tray plate into a random or smallest free incubator site",
        input={"site": Field("string", enum=("random", "smallest"), description="Site selection mode")},
        output={"site": Field("string", description="Site selection mode used")},
        risk="R2",
    )
    async def take_in_plate(self, site: str) -> dict[str, Any]:
        await self.native.take_in_plate(site)
        return {"site": site}

    @estop(native="stop_shaking")
    async def stop(self) -> None:
        # Model review: stop_shaking is the only stop-like call of the front end and stops only the shaker; no line
        # of the clone stops a plate transfer or temperature control, so the stop is never reported as reached.
        await self.native.stop_shaking()
        self._shaking = False
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "the Incubator front end has no source-backed stop: only the shaker was commanded off")
