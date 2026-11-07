"""OpenMHS driver for gh.slietar/nikon: a Nikon Ti2-E microscope over its reverse-engineered USB protocol.

A direct Driver (decorated methods) over ``nikon.microscope:MicroscopeDevice``.  The upstream class owns a PyUSB
``usb.core.Device`` and every device command is an ``async def`` sharing one asyncio lock (nikon/microscope.py:94-155),
so every method here is ``async def`` and awaits ``self.native``.  The SDK runs those coroutines on its one persistent
event loop.

* reads: the live state snapshot from ``get_stable_status`` (stage x, y, z; condenser, diaphragm, filter, objective,
  optical path, light, shutter, zoom) and the firmware CPU version.  One snapshot is shared by the getters of a state
  read for a short moment; every setter drops it first, so a read after a write is fresh;
* writes: stage x, y and z in um, the condenser/filter/objective/optical-path indices, the diaphragm opening in
  0 to 1, and the light and shutter booleans;
* the native e-stop is ``set_light(False)`` followed by ``set_shutter(False)``.  The clone has no stop command and
  does not brake the stage, so an e-stop cannot stop a stage motion that was already sent.

Units.  ``StatusEvent`` documents x and y in 0.1 um and z in 0.01 um (nikon/microscope.py:51-58), so this driver
publishes the stage positions in um and converts at the native call.  The indices, the diaphragm opening and the zoom
code are dimensionless.

Limits.  The condenser, filter, objective, optical-path and diaphragm setters assert their ranges in the clone
(nikon/microscope.py:366-435).  The stage travel is not a constant: the clone queries it from the device
(``get_x_bounds``/``get_y_bounds``/``get_z_bound``, nikon/microscope.py:241-275), so x, y and z are
``Limit.operator_required`` and the site supplies the um range of its stage.  ``site-limits.example.json`` shows the
overlay with example values, not a statement about a particular stage.

Safety.  R1: illumination off and the shutter disabled is the native safe state.  The package is model-authored and
unreviewed, and nothing here ran on a microscope.  The upstream README reports a firmware delay of at least 4.096 s
for status calls on macOS and Linux (readme.md:16); ``read_timeout_ms`` leaves room for the initial snapshot.

Every Fact cites a line of the clone at the pinned commit d53b4e261ae487f237a65048cf1931a40e39794b.
"""

import time

from mhs.driver import Driver, Fact, Limit, estop, read, write

PY = "nikon/microscope.py"
README = "readme.md"

#: Why the stage positions cannot carry a fixed limit (the clone only queries the bounds from the device).
STAGE_REASON = ("the clone states no fixed stage travel: the bounds are queried from the device "
                "(get_x_bounds/get_y_bounds/get_z_bound, nikon/microscope.py:241-275), so the site declares the um "
                "range of its stage")

#: How long the getters of one state read share a StatusEvent snapshot (an implementation cache, not device data).
_SNAPSHOT_TTL_S = 0.25


class NikonTi2E(Driver):
    device_id = "nikon-ti2-e"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "nikon.microscope:MicroscopeDevice"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMicroscopeDevice"}
    vendor, model = "Nikon", "Ti2-E microscope"
    display_name = "Nikon Ti2-E microscope (nikon.microscope:MicroscopeDevice)"
    tags = ["microscope", "nikon", "ti2-e", "stage", "optics", "asyncio"]
    facts = [
        Fact("The package controls the Nikon Ti2-E microscope over the reverse-engineered USB protocol through "
             "PyUSB, without the Nikon SDK", source="vendor_doc", ref=f"{README}:3"),
        Fact("MicroscopeDevice is constructed from a usb.core.Device and owns the asyncio lock its commands share",
             source="upstream_code", ref=f"{PY}:94-102"),
        Fact("StatusEvent reports the condenser (0-6), filter (0-5), objective (0-5), optical path (0-3), diaphragm "
             "opening (0-1), light, shutter, x and y [0.1 um], z [0.01 um] and the zoom code",
             source="upstream_code", ref=f"{PY}:28-61"),
        Fact("set_condenser accepts an index from 0 to 6", source="upstream_code", ref=f"{PY}:366-374"),
        Fact("set_dia accepts a diaphragm opening from 0.0 to 1.0", source="upstream_code", ref=f"{PY}:380-387"),
        Fact("set_filter accepts an index from 0 to 5", source="upstream_code", ref=f"{PY}:392-400"),
        Fact("set_objective accepts an index from 0 to 5", source="upstream_code", ref=f"{PY}:415-422"),
        Fact("set_optical_path accepts an index from 0 to 3", source="upstream_code", ref=f"{PY}:427-435"),
        Fact("set_x and set_y send a signed 32-bit position in 0.1 um and set_z sends one in 0.01 um",
             source="upstream_code", ref=f"{PY}:327-355"),
        Fact("The x and y stage bounds and the z stage bound are queried from the device at run time; the clone "
             "states no fixed travel", source="upstream_code", ref=f"{PY}:241-275"),
        Fact("get_status returns the next StatusEvent and get_stable_status returns the last one once no newer "
             "event arrives within idle_duration (0.5 s by default)", source="upstream_code", ref=f"{PY}:299-313"),
        Fact("get_firmware_cpu_version returns five ASCII bytes as the CPU version", source="upstream_code",
             ref=f"{PY}:163-168"),
        Fact("set_light and set_shutter take a boolean that enables or disables the light and the shutter",
             source="upstream_code", ref=f"{PY}:405-449"),
        Fact("On macOS and Linux a firmware bug makes get_event and other status calls return with a minimum delay "
             "of 4.096 s, and queued events may not be up to date", source="vendor_doc", ref=f"{README}:16"),
    ]
    safe_state = ("illumination off and shutter disabled (set_light(False), set_shutter(False)); the stage keeps its "
                  "position")
    #: The initial snapshot waits for one status event; the README reports a 4.096 s firmware delay for these calls.
    read_timeout_ms = 30000

    def __init__(self, **options):
        super().__init__(**options)
        self._snapshot = None
        self._snapshot_at = 0.0
        self._firmware = None

    # -- helpers -------------------------------------------------------------------------------------------------
    def _drop_snapshot(self):
        """Forget the cached StatusEvent before a command, so the following state read cannot be stale."""
        self._snapshot = None

    async def _status(self):
        now = time.monotonic()
        if self._snapshot is not None and now - self._snapshot_at < _SNAPSHOT_TTL_S:
            return self._snapshot
        self._snapshot = await self.native.get_stable_status()
        self._snapshot_at = time.monotonic()
        return self._snapshot

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("firmware_version", type="string", description="CPU firmware version the microscope reports")
    async def firmware_version(self):
        if self._firmware is None:
            self._firmware = await self.native.get_firmware_cpu_version()
        return self._firmware

    @read("x", unit="um", description="Stage x position in um (the device reports 0.1 um counts)")
    async def x(self):
        return (await self._status()).x / 10.0

    @read("y", unit="um", description="Stage y position in um (the device reports 0.1 um counts)")
    async def y(self):
        return (await self._status()).y / 10.0

    @read("z", unit="um", description="Stage z position in um (the device reports 0.01 um counts)")
    async def z(self):
        return (await self._status()).z / 100.0

    @read("condenser", type="integer", unit="1", description="Condenser index (0 to 6)")
    async def condenser(self):
        return int((await self._status()).condenser)

    @read("dia", unit="1", description="Diaphragm opening: 0.0 is 0% and 1.0 is 100%")
    async def dia(self):
        return float((await self._status()).dia)

    @read("filter", type="integer", unit="1", description="Filter index (0 to 5)")
    async def filter(self):
        return int((await self._status()).filter)

    @read("light", type="boolean", description="True while the light is enabled")
    async def light(self):
        return bool((await self._status()).light)

    @read("objective", type="integer", unit="1", description="Objective index (0 to 5)")
    async def objective(self):
        return int((await self._status()).objective)

    @read("optical_path", type="integer", unit="1", description="Optical path index (0 to 3)")
    async def optical_path(self):
        return int((await self._status()).optical_path)

    @read("shutter", type="boolean", description="True while the shutter is enabled")
    async def shutter(self):
        return bool((await self._status()).shutter)

    @read("zoom", type="integer", unit="1",
          description="Internal zoom code: 1 = 1X, 2 = 1.5X, 0 = indeterminate while the user changes it")
    async def zoom(self):
        return int((await self._status()).zoom)

    # -- writes --------------------------------------------------------------------------------------------------
    @write("x", unit="um", description="Stage x position in um; the native setter takes 0.1 um counts",
           limit=Limit.operator_required(STAGE_REASON))
    async def set_x(self, value):
        self._drop_snapshot()
        await self.native.set_x(round(value * 10.0))

    @write("y", unit="um", description="Stage y position in um; the native setter takes 0.1 um counts",
           limit=Limit.operator_required(STAGE_REASON))
    async def set_y(self, value):
        self._drop_snapshot()
        await self.native.set_y(round(value * 10.0))

    @write("z", unit="um", description="Stage z position in um; the native setter takes 0.01 um counts",
           limit=Limit.operator_required(STAGE_REASON))
    async def set_z(self, value):
        self._drop_snapshot()
        await self.native.set_z(round(value * 100.0))

    @write("condenser", type="integer", unit="1", description="Condenser index (0 to 6)",
           limit=Limit(min=0, max=6, unit="1", source="upstream_code", ref=f"{PY}:366-374"))
    async def set_condenser(self, value):
        self._drop_snapshot()
        await self.native.set_condenser(int(value))

    @write("dia", type="number", unit="1", description="Diaphragm opening: 0.0 is 0% and 1.0 is 100%",
           limit=Limit(min=0.0, max=1.0, unit="1", source="upstream_code", ref=f"{PY}:380-387"))
    async def set_dia(self, value):
        self._drop_snapshot()
        await self.native.set_dia(float(value))

    @write("filter", type="integer", unit="1", description="Filter index (0 to 5)",
           limit=Limit(min=0, max=5, unit="1", source="upstream_code", ref=f"{PY}:392-400"))
    async def set_filter(self, value):
        self._drop_snapshot()
        await self.native.set_filter(int(value))

    @write("light", type="boolean", description="Enable or disable the light")
    async def set_light(self, value):
        self._drop_snapshot()
        await self.native.set_light(bool(value))

    @write("objective", type="integer", unit="1", description="Objective index (0 to 5)",
           limit=Limit(min=0, max=5, unit="1", source="upstream_code", ref=f"{PY}:415-422"))
    async def set_objective(self, value):
        self._drop_snapshot()
        await self.native.set_objective(int(value))

    @write("optical_path", type="integer", unit="1", description="Optical path index (0 to 3)",
           limit=Limit(min=0, max=3, unit="1", source="upstream_code", ref=f"{PY}:427-435"))
    async def set_optical_path(self, value):
        self._drop_snapshot()
        await self.native.set_optical_path(int(value))

    @write("shutter", type="boolean", description="Enable or disable the shutter")
    async def set_shutter(self, value):
        self._drop_snapshot()
        await self.native.set_shutter(bool(value))

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="set_light(False), set_shutter(False)")
    async def emergency_stop(self):
        """The native safe state: disable the light and the shutter; the clone has no stage stop command."""
        self._drop_snapshot()
        await self.native.set_light(False)
        await self.native.set_shutter(False)
