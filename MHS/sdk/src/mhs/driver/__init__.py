"""OpenMHS Driver API: one decorated class per device (plan 3.8).

::

    from mhs.driver import Driver, read, write, action, estop, Limit, Fact

    class Bath(Driver):
        device_id, device_kind = "bath", "thermal.zone"
        mode, risk = "hardware", "R2"         # a fake backend is served as mode "simulated"
        native = "pkg.module:Class"           # checked against the pinned clone, never imported
        backends = {"hardware": ".native:connect", "fake": ".fake:FakeBath"}
        tags = ["circulator"]
        facts = [Fact("...", source="vendor_doc", ref="README.md:41")]
        safe_state = "heater off, pump stopped"
        # R2+ hardware needs an independent hardware e-stop or an @action(..., safe_state=True) (SAFE-045)
        estop_physical_ref = "manual.pdf:12"

        @read("temperature", unit="Cel")
        async def temperature(self):
            return await self.native.get_temperature()

        @write("setpoint", unit="Cel",
               limit=Limit(min=-20, max=150, source="upstream_code", ref="pkg/module.py:88"))
        async def set_setpoint(self, value):
            await self.native.set_setpoint(value)

        @estop
        async def stop(self):
            await self.native.stop()

The server is unchanged: a :class:`Driver` is a :class:`mhs.bridge.base.Bridge`
and :func:`mhs.driver.build.build_device` turns it into the
``Device``/``Resource``/``Capability``/``SafetyEnvelope`` objects
:class:`mhs.server.MHSServer` serves in strict mode.  :func:`mhs.adapter.load`
loads a driver directory.  Family drivers (:mod:`mhs.driver.families`) are
config-only subclasses over the bundled bridges.  A driver package is done
when ``python3 -m mhs.driver check <dir> --backend fake`` exits 0 (the gates
G1-G9 of :mod:`mhs.driver.check`); ``python3 -m mhs.driver`` also generates
the reference file, scaffolds packages and looks up the catalogue
(:mod:`mhs.driver.__main__`); :mod:`mhs.testing` holds the test helpers.
See ``MHS/sdk/docs/driver-authoring.md`` and the tutorial package
``MHS/sdk/examples/thermostat``.
"""

from __future__ import annotations

from ..signals import Busy, Cancelled, DriverFailed, OutcomeUnknown
from .base import Driver, current_context
from .build import (
    DEFAULT_ENDPOINT_ID,
    FAKE_FIDELITY,
    build_device,
    build_manifest,
    build_reference,
    build_server,
    close_server,
    hardware_device_id,
    served_device_id,
)
from .decorators import action, estop, interlock, read, reset, write
from .families import Sila2Driver, GymnasiumDriver, HttpDriver, MujocoDriver, OphydDriver, PythonObjectDriver, QcodesDriver, RosDriver, ScpiDriver, SerialDriver
from .spec import Action, DriverDefinitionError, Fact, Field, Limit

from .mcp_client_driver import McpClientDriver
from .pymmcore import CameraFactory, CameraProfile, PymmcorePlusDriver
# --- PyLabRobot helper (plr-liquid-handler-v1) ---
from .pylabrobot import PlrLabware, PlrOperation, PlrProfile, PlrStop, PyLabRobotDriver
# --- end PyLabRobot helper ---
from .tag_driver import TagDriver  # tag-bridge helper (2026-11-04)

__all__ = [
    "Action",
    "CameraFactory",
    "CameraProfile",
    "Busy",
    "Cancelled",
    "DEFAULT_ENDPOINT_ID",
    "Driver",
    "DriverDefinitionError",
    "DriverFailed",
    "FAKE_FIDELITY",
    "Fact",
    "Field",
    "GymnasiumDriver",
    "HttpDriver",
    "Limit",
    "McpClientDriver",
    "MujocoDriver",
    "OutcomeUnknown",
    "OphydDriver",
    "PlrLabware", "PlrOperation", "PlrProfile", "PlrStop", "PyLabRobotDriver",  # PyLabRobot helper
    "PythonObjectDriver", "QcodesDriver",
    "PymmcorePlusDriver",
    "RosDriver",
    "ScpiDriver",
    "SerialDriver",
    "Sila2Driver",
    "TagDriver",
    "action",
    "build_device",
    "build_manifest",
    "build_reference",
    "build_server",
    "close_server",
    "current_context",
    "estop",
    "hardware_device_id",
    "interlock",
    "read",
    "reset",
    "served_device_id",
    "write",
]
