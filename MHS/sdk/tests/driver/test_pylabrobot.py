"""PyLabRobot LiquidHandler helper (profile plr-liquid-handler-v1): definition, runtime, fake model and gate."""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
import time
import unittest
from pathlib import Path
from typing import Any

from mhs import canonical
from mhs.driver import (DriverDefinitionError, Field, Limit, PlrLabware, PlrOperation, PlrProfile, PlrStop,
                        PyLabRobotDriver, build_server, close_server)
from mhs.errors import MHSError
from mhs.testing import client_for
from mhs.testing.pylabrobot import (FakeDeck, FakeLiquidHandler, FakePlate, FakeTipRack, HasTipError, NoTipError,
                                    TooLittleLiquidError, TooLittleVolumeError, well_names)

from . import gate_support as gs

TRANSFER, MIX, VOLUMES = "x-cap.acme.transfer.v1", "x-cap.acme.mix.v1", "x-cap.acme.tracked_volumes.v1"
FIDELITY = {"engine": "custom:plr-test", "fidelity_level": "F0",
            "determinism": {"kind": "none", "seed_control": "none", "notes": "test"},
            "timestep_ms": 0.0, "realtime_factor": 0, "clock": "lockstep", "reset": "none",
            "snapshot_restore": False, "gaps": ["test fake"]}


def profile(**changes: Any) -> PlrProfile:
    values: dict[str, Any] = dict(
        handler="lh", handler_ref="twin/env.py:8", setup="setup", setup_ref="twin/env.py:7",
        close="teardown", close_ref="twin/env.py:11", channels=8, channels_ref="twin/env.py:4",
        tip_tracking_ref="twin/lab.py:5", volume_tracking_ref="twin/lab.py:6",
        labware=(PlrLabware("tips", "tip_rack", "twin/deck.py:2"), PlrLabware("plate", "plate", "twin/deck.py:3"),
                 PlrLabware("dest", "plate", "twin/deck.py:4")),
        operations={TRANSFER: PlrOperation("transfer", "twin/ops.py:2-5"),
                    MIX: PlrOperation("mix", "twin/ops.py:2-5"),
                    VOLUMES: PlrOperation("tracked_volumes", "twin/env.py:15")},
        volume_limit=Limit(min=1, max=500, source="upstream_code", ref="tools.py:1"),
        cycles_limit=Limit(min=1, max=5, source="upstream_code", ref="tools.py:2"),
        well_pattern="^[A-H](?:[1-9]|1[0-2])$")
    values.update(changes)
    return PlrProfile(**values)


class FakeEnv:
    """An upstream twin holding a fake LiquidHandler at ``lh`` (class attributes let a test swap parts)."""

    instances: list["FakeEnv"] = []
    handler_class: type = FakeLiquidHandler
    rack_class: type = FakeTipRack

    def __init__(self, **options: Any) -> None:
        self.options = options
        self.lh: Any = None
        FakeEnv.instances.append(self)

    async def setup(self) -> None:
        deck = FakeDeck([self.rack_class("tips", rows=8, columns=12, tip_volume=300),
                         FakePlate("plate", rows=8, columns=12, max_volume=900,
                                   volumes={well: 600.0 for well in well_names(8, 12)}),
                         FakePlate("dest", rows=8, columns=12, max_volume=900)])
        self.lh = self.handler_class(deck, num_channels=8)
        await self.lh.setup()

    async def teardown(self) -> None:
        await self.lh.stop()


def driver_class(*, mode: str = "simulated", plr: PlrProfile | None = None, **attrs: Any) -> type:
    body: dict[str, Any] = dict(device_id="plr-demo", device_kind="lab.liquid_handler", mode=mode, risk="R2",
                                native="twin.env:Env", backends={"fake": FakeEnv}, safe_state="test twin",
                                plr_profile=plr if plr is not None else profile())
    if mode == "simulated":
        body["fidelity"] = FIDELITY
    body.update(attrs)
    return type("Demo", (PyLabRobotDriver,), body)


def problems_of(cls: type) -> str:
    try:
        cls.driver_model()
    except DriverDefinitionError as exc:
        return str(exc)
    return ""


class Served:
    def __init__(self, test: unittest.TestCase, cls: type, **driver_options: Any) -> None:
        self.driver = cls(backend="fake", **driver_options)
        self.server = build_server(self.driver)
        test.addCleanup(close_server, self.server)
        self.client = client_for(self.server)
        self.device_id = self.client.hello()["devices"][0]["device_id"]
        self.session = self.client.open_session(device_ids=[self.device_id])["session_id"]

    def invoke(self, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.invoke(capability, payload, device_id=self.device_id, session_id=self.session)

    def transfer(self, volume: float = 50, source: list[str] | None = None, target: list[str] | None = None,
                 **changes: Any) -> dict[str, Any]:
        payload = {"tip_rack": "tips", "source": "plate", "source_wells": source or ["A1"], "target": "dest",
                   "target_wells": target or ["A1"], "volume": volume}
        payload.update(changes)
        return self.invoke(TRANSFER, payload)

    def volumes(self, labware: str, wells: list[str]) -> list[float]:
        receipt = self.invoke(VOLUMES, {"labware": labware, "wells": wells})
        assert receipt["status"] == "completed", receipt
        return receipt["output"]["volumes"]

    @property
    def lh(self) -> Any:
        return self.driver.native.lh


# ---------------------------------------------------------------------------------------------------------------
# definition
# ---------------------------------------------------------------------------------------------------------------


class PlrDefinitionTests(unittest.TestCase):
    def test_a_profile_generates_three_extensions_with_sourced_limits(self) -> None:
        model = driver_class().driver_model()
        self.assertEqual([binding.capability_id for binding in model.bindings], [TRANSFER, MIX, VOLUMES])
        self.assertEqual(model.risk, "R2")
        self.assertIsNone(model.estop)
        transfer, mix, volumes = model.bindings
        self.assertEqual(transfer.limits["volume"], {"min": 1, "max": 500, "source": "upstream_code",
                                                     "ref": "tools.py:1"})
        self.assertEqual(mix.limits["cycles"]["max"], 5)
        self.assertEqual(volumes.verb, "read")
        self.assertEqual(volumes.risk, "R0")
        properties = transfer.input_schema["properties"]
        self.assertEqual(properties["source"]["enum"], ["dest", "plate"])
        self.assertEqual(properties["tip_rack"]["enum"], ["tips"])
        self.assertEqual(properties["source_wells"]["maxItems"], 8)
        self.assertEqual(properties["source_wells"]["items"]["pattern"], "^[A-H](?:[1-9]|1[0-2])$")

    def test_an_operator_required_volume_is_accepted(self) -> None:
        cls = driver_class(plr=profile(volume_limit=Limit.operator_required("the site sets its tip volumes")))
        transfer = cls.driver_model().bindings[0]
        self.assertEqual(transfer.limits["volume"], "operator_required")
        self.assertIn("volume", transfer.operator_reasons)

    def test_a_bound_without_a_pinned_source_is_refused(self) -> None:
        self.assertIn("volume_limit needs source", problems_of(driver_class(plr=profile(
            volume_limit=Limit(min=1, max=500)))))
        self.assertIn("cycles_limit must be a Limit", problems_of(driver_class(plr=profile(cycles_limit=None))))

    def test_a_teardown_is_never_the_stop(self) -> None:
        for native in ("lh.stop", "teardown", "lh.backend.close"):
            stop = PlrStop(native, "twin/env.py:11", "a stop that is really a teardown")
            self.assertIn("names a teardown", problems_of(driver_class(plr=profile(stop=stop))), native)

    def test_each_operation_may_cite_its_own_volume_bound(self) -> None:
        own = {TRANSFER: PlrOperation("transfer", "twin/ops.py:2-5",
                                      volume_limit=Limit(min=1, max=500, source="upstream_code", ref="tools.py:1")),
               MIX: PlrOperation("mix", "twin/ops.py:2-5",
                                 volume_limit=Limit(min=1, max=200, source="upstream_code", ref="tools.py:3"))}
        model = driver_class(plr=profile(volume_limit=None, operations=own)).driver_model()
        self.assertEqual(model.binding(TRANSFER).limits["volume"]["ref"], "tools.py:1")
        self.assertEqual((model.binding(MIX).limits["volume"]["max"], model.binding(MIX).limits["volume"]["ref"]),
                         (200, "tools.py:3"))
        self.assertIn("volume_limit is unused", problems_of(driver_class(plr=profile(operations=own))))
        self.assertIn("plr_profile.volume_limit must be a Limit", problems_of(driver_class(plr=profile(
            volume_limit=None, operations={TRANSFER: PlrOperation("transfer", "twin/ops.py:2-5")}))))
        reads = {VOLUMES: PlrOperation("tracked_volumes", "twin/env.py:15",
                                       volume_limit=Limit(min=1, max=5, source="upstream_code", ref="tools.py:1"))}
        self.assertIn("only transfer and mix take a volume_limit", problems_of(driver_class(plr=profile(
            operations=reads, volume_limit=None, cycles_limit=None))))

    def test_tracking_references_are_required(self) -> None:
        self.assertIn("tip_tracking_ref", problems_of(driver_class(plr=profile(tip_tracking_ref=None))))
        self.assertIn("volume_tracking_ref", problems_of(driver_class(plr=profile(volume_tracking_ref=None))))
        only_transfer = profile(operations={TRANSFER: PlrOperation("transfer", "twin/ops.py:2-5")},
                                cycles_limit=None, volume_tracking_ref=None)
        self.assertEqual(problems_of(driver_class(plr=only_transfer)), "")

    def test_ids_kinds_labware_channels_and_patterns_are_checked(self) -> None:
        cases = {
            "the id must be x-cap": profile(operations={"cap.fluid.transfer.v1": PlrOperation("transfer", "a.py:1")}),
            "PlrOperation(kind, ref)": profile(operations={TRANSFER: PlrOperation("aspirate", "a.py:1")}),
            "declared twice": profile(labware=(PlrLabware("tips", "tip_rack", "a.py:1"),
                                               PlrLabware("tips", "plate", "a.py:2"))),
            "kind must be one of": profile(labware=(PlrLabware("tips", "trough", "a.py:1"),)),
            "channels must be an integer": profile(channels=0),
            "anchored": profile(well_pattern="[A-H][0-9]+"),
            "needs at least one declared tip rack": profile(labware=(PlrLabware("plate", "plate", "a.py:1"),)),
            "handler_ref must be": profile(handler_ref="twin/env.py"),
            "close must name the PyLabRobot teardown": profile(close="reset"),
        }
        for expected, plr in cases.items():
            self.assertIn(expected, problems_of(driver_class(plr=plr)), expected)

    def test_packages_are_data_only(self) -> None:
        with_method = driver_class(extra=lambda self: None)
        self.assertIn("data only", problems_of(with_method))
        self.assertIn("generated from plr_profile", problems_of(driver_class(commands={"x": {"native": "y"}})))
        self.assertIn("generated from plr_profile", problems_of(driver_class(safety_bindings={"estop": "lh.stop"})))
        writable = driver_class(parameters={"speed": Field("number", unit="1", writable=True,
                                                           limit=Limit.operator_required("site"))},
                                reads={"speed": {"native": "speed", "invoke": "get"}})
        self.assertIn("read-only parameters only", problems_of(writable))
        self.assertIn("exact PlrProfile", problems_of(driver_class(plr_profile={"handler": "lh"})))

    def test_generated_tools_fit_the_mcp_limit(self) -> None:
        from mhs.mcp import MCPProjection

        labware = tuple(PlrLabware(f"plate_carrier_site_{index}_96", "plate", f"twin/deck.py:{index + 1}")
                        for index in range(8)) + tuple(
            PlrLabware(f"tip_rack_1000ul_{index}", "tip_rack", f"twin/deck.py:{index + 20}") for index in range(4))
        served = Served(self, driver_class(plr=profile(labware=labware)))
        projection = MCPProjection(served.client)
        projection.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
        listed = projection.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = [tool for tool in listed["result"]["tools"] if "x-mhs" in tool]
        self.assertEqual(len(tools), 3)
        for tool in tools:   # measured as gate G8 does: the projection's own call options are not counted
            schema = json.loads(json.dumps(tool["inputSchema"]))
            for key in ("session_id", "command_id", "expected_revision", "permit_id", "deadline_ms"):
                schema["properties"].pop(key, None)
            owned = {"name": tool["name"], "description": tool.get("description") or "", "inputSchema": schema}
            self.assertLess(len(canonical.jcs(owned)), 2048, tool["name"])


# ---------------------------------------------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------------------------------------------


class _GatedHandler(FakeLiquidHandler):
    """A handler whose ``gate_at``-th aspirate waits for ``release`` (optionally ignoring cancellation, as a step that
    cannot be interrupted), then raises ``fail_with`` if set; ``halt`` stands for a source-backed native stop."""

    entered = threading.Event()
    release = threading.Event()
    gate_at, fail_with, shield, aspirations = 1, None, False, 0

    @classmethod
    def arm(cls, *, gate_at: int = 1, fail_with: BaseException | None = None, shield: bool = False) -> None:
        cls.entered, cls.release = threading.Event(), threading.Event()
        cls.gate_at, cls.fail_with, cls.shield, cls.aspirations = gate_at, fail_with, shield, 0

    async def aspirate(self, *args: Any, **kwargs: Any) -> None:
        cls = type(self)
        cls.aspirations += 1
        if cls.aspirations == cls.gate_at:
            cls.entered.set()
            while not cls.release.is_set():
                try:
                    await asyncio.sleep(0.005)
                except asyncio.CancelledError:
                    if not cls.shield:
                        raise
            if cls.fail_with is not None:
                raise cls.fail_with
        await super().aspirate(*args, **kwargs)

    async def halt(self) -> None:
        self.calls.append(("halt", None))


class _FailingHandler(FakeLiquidHandler):
    """Raises ``error`` from the step named ``step`` (the front end raised it; nothing says whether it moved)."""

    step, error = "dispense", OSError("bus fault")

    async def pick_up_tips(self, *args: Any, **kwargs: Any) -> None:
        if type(self).step == "pick_up_tips":
            raise type(self).error
        await super().pick_up_tips(*args, **kwargs)

    async def dispense(self, *args: Any, **kwargs: Any) -> None:
        if type(self).step == "dispense":
            raise type(self).error
        await super().dispense(*args, **kwargs)


class _UntrackedHandler(FakeLiquidHandler):
    """A pick-up that leaves the tip spots' trackers unchanged (PyLabRobot tip tracking switched off)."""

    async def pick_up_tips(self, tip_spots: Any, use_channels: Any = None, **kwargs: Any) -> None:
        await super().pick_up_tips(tip_spots, use_channels=use_channels, **kwargs)
        for spot in tip_spots:
            spot.tracker.has_tip = True


HALT = PlrStop("lh.halt", "twin/env.py:13", "discards queued commands; the running one completes")


class PlrRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeEnv.handler_class, FakeEnv.rack_class = FakeLiquidHandler, FakeTipRack
        FakeEnv.instances = []

    def tearDown(self) -> None:
        _GatedHandler.release.set()
        FakeEnv.handler_class, FakeEnv.rack_class = FakeLiquidHandler, FakeTipRack

    # -- helpers ----------------------------------------------------------------------------------------------------
    def estop(self, served: Served) -> dict[str, Any]:
        return served.client.estop("test", device_id=served.device_id, session_id=served.session)

    def reset(self, served: Served) -> dict[str, Any]:
        response = served.client.reset(device_id=served.device_id, session_id=served.session)
        return response.get("result", response) if isinstance(response, dict) else response

    def in_background(self, served: Served, *args: Any, **kwargs: Any) -> tuple[threading.Thread, dict[str, Any]]:
        outcome: dict[str, Any] = {}
        worker = threading.Thread(target=lambda: outcome.setdefault("receipt", served.transfer(*args, **kwargs)),
                                  daemon=True)
        worker.start()
        self.assertTrue(_GatedHandler.entered.wait(5))
        return worker, outcome

    def names(self, served: Served) -> list[str]:
        return [name for name, _ in served.lh.calls]

    # -- normal operation -------------------------------------------------------------------------------------------
    def test_a_transfer_runs_the_four_steps_with_fresh_tips(self) -> None:
        served = Served(self, driver_class())
        first = served.transfer(100, ["A1", "B1"], ["C1", "D1"])
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(first["output"], {"transferred_volume": 100.0, "channels": 2, "tips": ["A1", "B1"]})
        self.assertEqual(self.names(served)[1:], ["pick_up_tips", "aspirate", "dispense", "discard_tips"])
        self.assertEqual(served.volumes("dest", ["C1", "D1"]), [100.0, 100.0])
        self.assertEqual(served.volumes("plate", ["A1", "B1"]), [500.0, 500.0])
        second = served.transfer(10)
        self.assertEqual(second["output"]["tips"], ["C1"])                       # the next adjacent tip, same column
        self.assertFalse(any(tracker.has_tip for tracker in served.lh.head.values()))

    def test_an_eight_channel_transfer_takes_a_full_column(self) -> None:
        served = Served(self, driver_class())
        served.transfer(10)                                                     # uses A1
        column = [f"{row}1" for row in "ABCDEFGH"]
        receipt = served.transfer(10, column, column)
        self.assertEqual(receipt["output"]["tips"], [f"{row}2" for row in "ABCDEFGH"])

    def test_mix_returns_liquid_and_reports_its_cycles(self) -> None:
        served = Served(self, driver_class())
        receipt = served.invoke(MIX, {"tip_rack": "tips", "labware": "plate", "wells": ["E3"], "volume": 200,
                                      "cycles": 3})
        self.assertEqual(receipt["output"], {"mixed_volume": 200.0, "cycles": 3, "channels": 1, "tips": ["A1"]})
        self.assertEqual(served.volumes("plate", ["E3"]), [600.0])
        self.assertEqual(self.names(served)[1:], ["pick_up_tips"] + ["aspirate", "dispense"] * 3 + ["discard_tips"])

    # -- input boundary ---------------------------------------------------------------------------------------------
    def test_limits_and_cross_field_rules_refuse_before_any_native_call(self) -> None:
        served = Served(self, driver_class())
        calls = len(served.lh.calls)
        for volume in (0.5, 500.5):
            self.assertEqual(served.transfer(volume)["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        mix = served.invoke(MIX, {"tip_rack": "tips", "labware": "plate", "wells": ["A1"], "volume": 5, "cycles": 6})
        self.assertEqual(mix["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        for receipt in (served.transfer(10, tip_rack="plate"), served.transfer(10, source="tips"),
                        served.transfer(10, source=["I1"])):                    # the schema refuses these
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", receipt)
        unpaired = served.transfer(10, ["A1", "B1"], ["A1"])                    # the bridge refuses this one
        self.assertEqual(unpaired["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", unpaired)
        self.assertEqual(len(served.lh.calls), calls)

    def test_the_wells_of_one_call_form_one_column_without_repeats(self) -> None:
        served = Served(self, driver_class())
        calls = len(served.lh.calls)
        refused = {
            "a repeated source well": served.transfer(10, ["A2", "A2"], ["A2", "B2"]),
            "a repeated target well": served.transfer(10, ["A2", "B2"], ["C2", "C2"]),
            "two source columns": served.transfer(10, ["A1", "B2"], ["A3", "B3"]),
            "rows out of channel order": served.transfer(10, ["B1", "A1"], ["A3", "B3"]),
            "a repeated mix well": served.invoke(MIX, {"tip_rack": "tips", "labware": "plate", "wells": ["D4", "D4"],
                                                       "volume": 5, "cycles": 1}),
        }
        for what, receipt in refused.items():
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", what)
        self.assertEqual(len(served.lh.calls), calls)
        gaps = served.transfer(10, ["A5", "C5"], ["B6", "H6"])                  # rows may skip, one column each
        self.assertEqual(gaps["status"], "completed", gaps)
        self.assertEqual(served.volumes("plate", ["A5", "B5", "C5"]), [590.0, 600.0, 590.0])

    def test_an_unmappable_input_is_refused_as_invalid(self) -> None:
        driver = driver_class()(backend="fake")
        self.addCleanup(driver.close)
        driver.open()
        payload = {"tip_rack": "tips", "source": "plate", "source_wells": ["A1"], "target": "dest",
                   "target_wells": ["A1"], "volume": float("nan")}
        with self.assertRaises(MHSError) as caught:
            driver.inner.call(TRANSFER, payload)
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual([name for name, _ in driver.native.lh.calls], ["setup"])

    # -- failures ---------------------------------------------------------------------------------------------------
    def test_a_bookkeeping_failure_names_the_completed_steps(self) -> None:
        served = Served(self, driver_class())
        self.assertEqual(served.transfer(300, ["A5"], ["A5"])["status"], "completed")
        self.assertEqual(served.transfer(300, ["A5"], ["B5"])["status"], "completed")
        receipt = served.transfer(300, ["A5"], ["C5"])                          # the well is empty now
        self.assertEqual(receipt["status"], "failed")
        error = receipt["error"]
        self.assertEqual(error["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(error["details"]["completed_steps"], ["pick_up_tips"])
        self.assertEqual(error["details"]["precondition"], "liquid_present")
        self.assertTrue(served.lh.head[0].has_tip)                              # no cleanup motion after a failure
        blocked = served.transfer(10, ["A6"], ["A6"])                           # the documented dead end
        self.assertEqual(blocked["error"]["details"]["precondition"], "channel_free")

    def test_an_error_that_may_have_reached_the_device_is_unknown_and_fences(self) -> None:
        for step, error, done in (("dispense", OSError("bus fault"), ["pick_up_tips", "aspirate"]),
                                  ("pick_up_tips", TimeoutError("no reply"), [])):
            with self.subTest(step=step):
                _FailingHandler.step, _FailingHandler.error = step, error
                FakeEnv.handler_class = _FailingHandler
                served = Served(self, driver_class())
                receipt = served.transfer(10)
                self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("unknown", "MHS.OUTCOME.UNKNOWN"))
                details = receipt["error"]["details"]
                self.assertEqual((details["step"], details["completed_steps"]), (step, done))
                self.assertNotIn("native_message", details)
                calls = len(served.lh.calls)
                fenced = served.transfer(10, ["B2"], ["B2"])
                self.assertEqual((fenced["status"], fenced["error"]["mhs_code"]), ("failed", "MHS.DEVICE.NOT_READY"))
                self.assertEqual(len(served.lh.calls), calls)

    def test_a_mid_step_timeout_needs_a_confirmed_stop_before_reset(self) -> None:
        for stop in (None, HALT):
            with self.subTest(stop=bool(stop)):
                _GatedHandler.arm(fail_with=TimeoutError("no reply"))
                FakeEnv.handler_class = _GatedHandler
                served = Served(self, driver_class(plr=profile(stop=stop)))
                worker, outcome = self.in_background(served, 10)
                _GatedHandler.release.set()
                worker.join(5)
                receipt = outcome["receipt"]
                self.assertEqual((receipt["status"], receipt["error"]["details"]["completed_steps"]),
                                 ("unknown", ["pick_up_tips"]))
                self.assertEqual(served.transfer(10, ["B2"], ["B2"])["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
                estop = self.estop(served)
                reset = self.reset(served)
                if stop is None:                                                # nothing can confirm a stop
                    self.assertEqual(estop["error"]["details"]["reason"], "bridge_reports_unsafe")
                    self.assertEqual(reset["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED")
                else:                                                           # the bound stop confirms
                    self.assertEqual((estop["status"], estop["output"]["estop"]), ("completed", "engaged"))
                    self.assertEqual(reset["status"], "completed", reset)
                    self.assertEqual(served.volumes("plate", ["B2"]), [600.0])
                    self.assertEqual(self.names(served).count("halt"), 1)

    def test_a_deadline_expiry_mid_step_is_unknown_and_fences(self) -> None:
        _GatedHandler.arm()
        FakeEnv.handler_class = _GatedHandler
        served = Served(self, driver_class())
        payload = {"tip_rack": "tips", "source": "plate", "source_wells": ["A1"], "target": "dest",
                   "target_wells": ["A1"], "volume": 10}
        receipt = served.client.invoke(TRANSFER, payload, device_id=served.device_id, session_id=served.session,
                                       deadline_ms=300)
        # Whichever bound expires first (the request deadline or the bridge's), the outcome is unknown.
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertIn(receipt["error"]["mhs_code"], ("MHS.OUTCOME.TIMEOUT", "MHS.OUTCOME.UNKNOWN"))
        _GatedHandler.release.set()
        time.sleep(0.1)
        self.assertEqual(served.transfer(10, ["B2"], ["B2"])["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
        self.assertNotIn("dispense", self.names(served))

    def test_a_first_call_failure_keeps_the_redacted_bridge_mapping(self) -> None:
        served = Served(self, driver_class())
        served.lh.deck.get_resource = lambda name: (_ for _ in ()).throw(RuntimeError("secret detail"))
        receipt = served.transfer(10)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")
        self.assertNotIn("secret", json.dumps(receipt["error"]))

    def test_tip_selection_needs_tip_tracking(self) -> None:
        FakeEnv.handler_class = _UntrackedHandler
        served = Served(self, driver_class())
        receipt = served.transfer(10)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED")
        self.assertEqual(receipt["error"]["details"]["completed_steps"], ["pick_up_tips"])
        self.assertEqual(self.names(served)[1:], ["pick_up_tips"])

    # -- e-stop and reset -------------------------------------------------------------------------------------------
    def test_an_estop_sends_no_further_step_of_a_running_transfer(self) -> None:
        _GatedHandler.arm()
        FakeEnv.handler_class = _GatedHandler
        served = Served(self, driver_class())
        worker, outcome = self.in_background(served, 10)
        estop = self.estop(served)
        # No native stop: the latch holds, and the in-flight step is honestly not confirmed stopped.
        self.assertEqual((estop["status"], estop["output"]["estop"]), ("failed", "software_only"))
        self.assertEqual(estop["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(estop["error"]["details"]["reason"], "bridge_reports_unsafe")
        worker.join(5)
        self.assertEqual(outcome["receipt"]["status"], "cancelled", outcome)
        _GatedHandler.release.set()
        time.sleep(0.2)  # let a late, uncancelled step show up if the fence failed
        self.assertNotIn("dispense", self.names(served))
        self.assertNotIn("discard_tips", self.names(served))
        self.assertEqual(served.transfer(10, ["B2"], ["B2"])["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        # The caller saw the cancellation while the step was in flight: that execution stays uncertain, and with no
        # bound stop nothing can confirm a safe state, so the reset is refused (an endpoint restart recovers).
        self.assertEqual(self.reset(served)["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED")

    def test_the_fence_also_stops_the_mix_cycles(self) -> None:
        _GatedHandler.arm(gate_at=2)
        FakeEnv.handler_class = _GatedHandler
        served = Served(self, driver_class())
        outcome: dict[str, Any] = {}
        payload = {"tip_rack": "tips", "labware": "plate", "wells": ["E3"], "volume": 50, "cycles": 3}
        worker = threading.Thread(target=lambda: outcome.setdefault("receipt", served.invoke(MIX, payload)),
                                  daemon=True)
        worker.start()
        self.assertTrue(_GatedHandler.entered.wait(5))
        self.estop(served)
        worker.join(5)
        _GatedHandler.release.set()
        time.sleep(0.2)
        self.assertEqual(outcome["receipt"]["status"], "cancelled", outcome)
        names = self.names(served)
        self.assertEqual(names.count("dispense"), 1)                            # cycle 1 only
        self.assertNotIn("discard_tips", names)

    def test_a_reset_is_refused_while_a_step_is_in_flight(self) -> None:
        _GatedHandler.arm(shield=True)                                          # the step ignores cancellation
        FakeEnv.handler_class = _GatedHandler
        served = Served(self, driver_class())
        worker, outcome = self.in_background(served, 10)
        self.estop(served)
        worker.join(5)
        self.assertEqual(self.reset(served)["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED")
        _GatedHandler.release.set()                                             # the step ends; no later step is sent
        time.sleep(0.3)
        self.assertEqual(self.names(served)[1:], ["pick_up_tips", "aspirate"])
        self.assertEqual(self.reset(served)["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED")

    def test_a_bound_stop_runs_at_the_estop_and_once_more_from_the_background_retry(self) -> None:
        """The first attempt cannot confirm while a step is in flight; the server's retry (SAFE-040) calls the stop
        again once the step has ended and then confirms. No PyLabRobot step follows the first stop call."""
        _GatedHandler.arm(shield=True)
        FakeEnv.handler_class = _GatedHandler
        served = Served(self, driver_class(plr=profile(stop=HALT)))
        self.assertEqual(served.driver.estop_native, "lh.halt")
        worker, outcome = self.in_background(served, 10)
        estop = self.estop(served)
        self.assertEqual((estop["status"], estop["error"]["mhs_code"]), ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"))
        self.assertTrue(estop["error"]["details"]["retrying"])
        worker.join(5)
        self.assertEqual(outcome["receipt"]["status"], "cancelled", outcome)
        _GatedHandler.release.set()                                             # the in-flight aspirate completes
        deadline = time.monotonic() + 5
        while self.reset(served).get("status") != "completed":
            self.assertLess(time.monotonic(), deadline, "the background retry never confirmed the stop")
            time.sleep(0.1)
        names = self.names(served)
        first = names.index("halt")
        self.assertEqual(names[:first], ["setup", "pick_up_tips"])
        self.assertEqual([name for name in names[first:] if name != "halt"], ["aspirate"])   # the in-flight step only
        self.assertEqual(names.count("halt"), 2)
        time.sleep(0.8)
        self.assertEqual(self.names(served).count("halt"), 2)                    # confirmed: no further retry

    def test_a_bound_stop_is_the_native_estop(self) -> None:
        FakeEnv.handler_class = _GatedHandler
        served = Served(self, driver_class(plr=profile(stop=HALT)))
        estop = self.estop(served)
        self.assertEqual((estop["status"], estop["output"]["estop"]), ("completed", "engaged"))
        self.assertEqual(self.names(served).count("halt"), 1)

    def test_a_hardware_backend_without_a_stop_is_refused_before_its_factory(self) -> None:
        created: list[Any] = []

        def factory(**options: Any) -> Any:
            created.append(options)
            return FakeEnv()

        cls = driver_class(mode="hardware", backends={"hardware": factory, "fake": FakeEnv})
        with self.assertRaises(MHSError) as caught:
            cls(backend="hardware").open()
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")
        self.assertIn("plr_profile.stop", caught.exception.message)
        self.assertEqual(created, [])
        FakeEnv.handler_class = _GatedHandler
        stopped = driver_class(mode="hardware", backends={"hardware": factory, "fake": FakeEnv}, plr=profile(stop=HALT),
                               estop_physical_ref="twin/env.py:13")
        driver = stopped(backend="hardware")
        self.addCleanup(driver.close)
        driver.open()
        self.assertEqual(created, [{}])

    def test_close_runs_the_teardown_once(self) -> None:
        driver = driver_class()(backend="fake")
        server = build_server(driver)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        client.invoke(VOLUMES, {"labware": "plate", "wells": ["A1"]}, device_id=device_id, session_id=session)
        lh = driver.native.lh
        close_server(server)
        self.assertEqual([name for name, _ in lh.calls].count("stop"), 1)
        self.assertFalse(lh.setup_finished)

    def test_configuration_edits_after_construction_are_refused(self) -> None:
        cls = driver_class()
        driver = cls(backend="fake")
        self.addCleanup(driver.close)
        driver._plr_config["capabilities"][TRANSFER]["timeout_ms"] = 1
        with self.assertRaises(DriverDefinitionError):
            driver.open()


# ---------------------------------------------------------------------------------------------------------------
# deterministic PyLabRobot model
# ---------------------------------------------------------------------------------------------------------------


class PlrFakeModelTests(unittest.TestCase):
    def handler(self) -> FakeLiquidHandler:
        deck = FakeDeck([FakeTipRack("tips", rows=2, columns=2, tip_volume=100, empty=["B1"]),
                         FakePlate("plate", rows=2, columns=2, max_volume=150, volumes={"A1": 120.0})])
        return FakeLiquidHandler(deck, num_channels=2)

    def run_async(self, coroutine: Any) -> Any:
        return asyncio.run(coroutine)

    def test_well_names_are_column_major(self) -> None:
        self.assertEqual(well_names(2, 2), ["A1", "B1", "A2", "B2"])

    def test_setup_is_required_once(self) -> None:
        handler = self.handler()
        rack = handler.deck.get_resource("tips")
        with self.assertRaisesRegex(RuntimeError, "setup has not finished"):
            self.run_async(handler.pick_up_tips([rack.get_item("A1")]))
        self.run_async(handler.setup())
        with self.assertRaisesRegex(RuntimeError, "already finished"):
            self.run_async(handler.setup())

    def test_tip_and_volume_bookkeeping(self) -> None:
        handler = self.handler()
        rack, plate = handler.deck.get_resource("tips"), handler.deck.get_resource("plate")
        self.run_async(handler.setup())
        with self.assertRaises(NoTipError):
            self.run_async(handler.pick_up_tips([rack.get_item("B1")]))
        with self.assertRaises(NoTipError):
            self.run_async(handler.aspirate([plate.get_item("A1")], vols=[10]))
        self.run_async(handler.pick_up_tips([rack.get_item("A1")]))
        with self.assertRaises(HasTipError):
            self.run_async(handler.pick_up_tips([rack.get_item("A2")]))
        with self.assertRaises(TooLittleLiquidError):
            self.run_async(handler.aspirate([plate.get_item("B1")], vols=[10]))
        with self.assertRaises(TooLittleVolumeError):
            self.run_async(handler.aspirate([plate.get_item("A1")], vols=[110]))
        self.run_async(handler.aspirate([plate.get_item("A1")], vols=[90]))
        with self.assertRaises(TooLittleLiquidError):
            self.run_async(handler.dispense([plate.get_item("A2")], vols=[95]))
        self.run_async(handler.dispense([plate.get_item("A2")], vols=[90]))
        self.assertEqual(plate.get_item("A2").tracker.get_used_volume(), 90.0)
        self.run_async(handler.discard_tips())
        with self.assertRaisesRegex(RuntimeError, "No tips have been picked up"):
            self.run_async(handler.discard_tips())
        with self.assertRaises(ValueError):
            self.run_async(handler.pick_up_tips([rack.get_item("A2")], use_channels=[5]))


# ---------------------------------------------------------------------------------------------------------------
# the acceptance gate on a synthetic package with a plain-directory clone
# ---------------------------------------------------------------------------------------------------------------

_CLONE = {
    "twin/__init__.py": "",
    "twin/lab.py": ("from pylabrobot.resources import set_tip_tracking, set_volume_tracking\n\n\n"
                    "def make(num_channels):\n    set_tip_tracking(True)\n    set_volume_tracking(True)\n"
                    "    return num_channels\n"),
    "twin/env.py": ("from .lab import make\n\n\nclass Env:\n    def __init__(self, num_channels: int = 8):\n"
                    "        self.num_channels = num_channels\n\n    async def setup(self):\n"
                    "        self.lh = make(self.num_channels)\n        await self.lh.setup()\n\n"
                    "    async def teardown(self):\n        await self.lh.stop()\n\n"
                    "    def volume(self, plate, well):\n        return plate.get_item(well).tracker.get_used_volume()\n"),
    "twin/deck.py": ('def build(TipRack, Plate):\n    tips = TipRack(name="tips")\n    plate = Plate(name="plate")\n'
                     '    dest = Plate(name="dest")\n    return tips, plate, dest\n'),
    "twin/ops.py": ("async def transfer(env, tips, src, dst, vols):\n    await env.lh.pick_up_tips(tips)\n"
                    "    await env.lh.aspirate(src, vols=vols)\n    await env.lh.dispense(dst, vols=vols)\n"
                    "    await env.lh.discard_tips()\n"),
    "tools.py": 'VOLUME = {"minimum": 1, "maximum": 500}\nCYCLES = {"minimum": 1, "maximum": 5}\n',
    "twin/notes.py": ("# env.lh.pick_up_tips(tips); env.lh.aspirate(src); env.lh.dispense(dst); env.lh.discard_tips()\n"
                      "# lh.halt() would stop the head; plate.get_item(well).tracker.get_used_volume()\n"
                      + "".join(f"VALUE_{index} = {index}\n" for index in range(48))),
}

_DRIVER = '''"""Synthetic PyLabRobot package for the gate tests."""

from mhs.driver import Limit, PlrLabware, PlrOperation, PlrProfile, PlrStop, PyLabRobotDriver


class Twin(PyLabRobotDriver):
    device_id, device_kind, mode, risk = "plr-twin", "lab.liquid_handler", "simulated", "R2"
    native = "twin.env:Env"
    backends = {"fake": ".fake:FakeTwin"}
    safe_state = "simulated twin"
    fidelity = FIDELITY
    plr_profile = PlrProfile(
        handler="lh", handler_ref="twin/env.py:9", setup="setup", setup_ref="twin/env.py:8",
        close="teardown", close_ref="twin/env.py:12", channels=8, channels_ref="twin/env.py:5",
        tip_tracking_ref="twin/lab.py:5", volume_tracking_ref="twin/lab.py:6",
        labware=(PlrLabware("tips", "tip_rack", "twin/deck.py:2"), PlrLabware("plate", "plate", "twin/deck.py:3"),
                 PlrLabware("dest", "plate", "twin/deck.py:4")),
        operations={"x-cap.acme.transfer.v1": PlrOperation("transfer", "twin/ops.py:2-5"),
                    "x-cap.acme.tracked_volumes.v1": PlrOperation("tracked_volumes", "twin/env.py:16")},
        volume_limit=Limit(min=1, max=500, source="upstream_code", ref="tools.py:1"),
        well_pattern="^[A-H](?:[1-9]|1[0-2])$")
'''

_FAKE = '''"""Fake of twin.env:Env."""

from mhs.testing.pylabrobot import FakeDeck, FakeLiquidHandler, FakePlate, FakeTipRack, well_names


class FakeTwin:
    def __init__(self, num_channels=8):
        self.num_channels = num_channels

    async def setup(self):
        deck = FakeDeck([FakeTipRack("tips", rows=8, columns=12, tip_volume=300),  # placeholder
                         FakePlate("plate", rows=8, columns=12, max_volume=900,  # placeholder
                                   volumes={well: 600.0 for well in well_names(8, 12)}),  # placeholder
                         FakePlate("dest", rows=8, columns=12, max_volume=900)])  # placeholder
        self.lh = FakeLiquidHandler(deck, num_channels=self.num_channels)
        await self.lh.setup()

    async def teardown(self):
        await self.lh.stop()
'''

_FIXTURES = {"capabilities": {
    "x-cap.acme.transfer.v1": {
        "valid": {"tip_rack": "tips", "source": "plate", "source_wells": ["A1"], "target": "dest",
                  "target_wells": ["A1"], "volume": 50},
        "alternate": {"tip_rack": "tips", "source": "plate", "source_wells": ["B1"], "target": "dest",
                      "target_wells": ["B1"], "volume": 60}},
    "x-cap.acme.tracked_volumes.v1": {"valid": {"labware": "plate", "wells": ["A1"]},
                                      "alternate": {"labware": "dest", "wells": ["B1"]}}}}


def plr_package(test: unittest.TestCase) -> tuple[Path, Path]:
    """``(root, driver dir)``: a simulated PyLabRobot package over a plain-directory clone ``labs/acme/plr``."""
    root, tutorial = gs.real_package(test)
    directory = root / "MHS" / "drivers" / "labs" / "acme__plr"
    shutil.copytree(tutorial, directory)
    shutil.rmtree(tutorial)
    for name in ("driver.py", "fake.py", "native.py", "site-limits.example.json", "test_driver.py", "facts.md"):
        (directory / name).unlink(missing_ok=True)
    clone = root / "labs" / "acme" / "plr"
    for relative, text in _CLONE.items():
        (clone / relative).parent.mkdir(parents=True, exist_ok=True)
        (clone / relative).write_text(text, encoding="utf-8")
    (directory / "driver.py").write_text(_DRIVER.replace("fidelity = FIDELITY", f"fidelity = {FIDELITY!r}"),
                                         encoding="utf-8")
    (directory / "fake.py").write_text(_FAKE, encoding="utf-8")
    (directory / "facts.md").write_text("# Facts and tags for gh.acme/plr\n\nNo facts: a synthetic test package.\n",
                                        encoding="utf-8")
    (directory / "test_driver.py").write_text(
        "import unittest\nfrom pathlib import Path\n\nfrom mhs.testing import check_driver\n\n"
        "HERE = Path(__file__).resolve().parent\n\n\nclass DriverGate(unittest.TestCase):\n"
        "    def test_gate(self) -> None:\n        self.assertEqual(check_driver(HERE)['failed'], [])\n",
        encoding="utf-8")
    (directory / "fixtures").mkdir(exist_ok=True)
    (directory / "fixtures" / "conformance.json").write_text(json.dumps(_FIXTURES), encoding="utf-8")
    upstream = {"repo_url": "https://github.com/acme/plr", "commit": "a" * 40, "license_spdx": "MIT",
                "license_class": "permissive"}
    card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    card.update({"package_id": "gh.acme/plr", "upstream": upstream, "local_path": "labs/acme/plr",
                 "driver_dir": "MHS/drivers/labs/acme__plr", "family": "pylabrobot", "decision": "family-config",
                 "entry_symbols": [{"symbol": "twin.env:Env", "file": "twin/env.py", "line": 4,
                                    "confidence": "ast"}],
                 "acceptance": "python3 -m mhs.driver check MHS/drivers/labs/acme__plr --backend fake"})
    card["safety"] = {"expected_mode": "simulated", "risk_floor": "R1", "limit_hints": []}
    (directory / "task.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    gs.edit_json(directory, "driver.lock.json", package_id="gh.acme/plr", backends={"fake": ".fake:FakeTwin"},
                 upstream={key: upstream[key] for key in ("repo_url", "commit", "license_spdx")})
    gs.regenerate(directory)
    return root, directory


class PlrGateTests(unittest.TestCase):
    def test_a_synthetic_package_passes_g1_to_g8(self) -> None:
        root, directory = plr_package(self)
        report = gs.check(directory, root=root)
        self.assertEqual(report["failed"], [], report)
        self.assertEqual(gs.findings(report, "G7", severity=None), [])

    def test_g7_reads_every_profile_reference_in_the_clone(self) -> None:
        root, directory = plr_package(self)
        gs.edit(directory, "driver.py", 'PlrLabware("dest", "plate", "twin/deck.py:4")',
                'PlrLabware("dest", "plate", "twin/deck.py:3")')
        gs.edit(directory, "driver.py", 'PlrOperation("transfer", "twin/ops.py:2-5")',
                'PlrOperation("transfer", "twin/ops.py:2-3")')
        gs.edit(directory, "driver.py", 'tip_tracking_ref="twin/lab.py:5"', 'tip_tracking_ref="twin/lab.py:6"')
        gs.edit(directory, "driver.py", 'channels_ref="twin/env.py:5"', 'channels_ref="twin/env.py:99"')
        gs.regenerate(directory)
        report = gs.check(directory, root=root)
        self.assertIn("G7", report["failed"])
        found = gs.coded(report, "G7")
        self.assertIn(("G7.PLR_SOURCE", "labware 'dest'"), found)
        self.assertIn(("G7.PLR_SOURCE", "x-cap.acme.transfer.v1"), found)
        self.assertIn(("G7.PLR_SOURCE", "plr_profile.tip_tracking_ref"), found)
        self.assertIn(("G7.PLR_REF", "plr_profile.channels_ref"), found)
        messages = [finding["message"] for gate in report["gates"] if gate["id"] == "G7"
                    for finding in gate["findings"]]
        self.assertTrue(any(".dispense(" in message for message in messages), messages)

    def test_g7_needs_code_not_comments_and_bounded_spans(self) -> None:
        root, directory = plr_package(self)
        gs.edit(directory, "driver.py", 'PlrOperation("transfer", "twin/ops.py:2-5")',
                'PlrOperation("transfer", "twin/notes.py:1-2")')                # the calls only in comments
        gs.edit(directory, "driver.py", 'PlrOperation("tracked_volumes", "twin/env.py:16")',
                'PlrOperation("tracked_volumes", "twin/notes.py:1-45")')        # a span wider than 40 lines
        gs.edit(directory, "driver.py", 'PlrLabware("plate", "plate", "twin/deck.py:3")',
                'PlrLabware("plate", "plate", "twin/deck.py:3-4")')             # a span for a one-line reference
        gs.edit(directory, "driver.py", 'well_pattern=',
                'stop=PlrStop("lh.halt", "twin/notes.py:2", "a stop that is only mentioned in a comment"),\n        '
                'well_pattern=')                                                # a comment is not a stop
        gs.regenerate(directory)
        found = gs.coded(gs.check(directory, root=root), "G7")
        self.assertIn(("G7.PLR_SOURCE", "x-cap.acme.transfer.v1"), found)
        self.assertIn(("G7.PLR_REF", "x-cap.acme.tracked_volumes.v1"), found)
        self.assertIn(("G7.PLR_REF", "labware 'plate'"), found)
        self.assertIn(("G7.PLR_SOURCE", "plr_profile.stop.ref"), found)


if __name__ == "__main__":
    unittest.main()
