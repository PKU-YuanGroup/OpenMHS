"""OpenMHS driver for gh.tiagocoutinho/cryocon: a CryoCon temperature controller.

A direct Driver (decorated methods) over the upstream class ``cryocon.cryocon:CryoCon``.  The card's decision is
direct-driver; the package serves the documented reads and the catalogue temperature measurement as a direct Driver.
The upstream class owns a connection object and builds every request from a member descriptor
(``cryocon/cryocon.py:105-124``, ``cryocon/cryocon.py:187-206`` and ``cryocon/cryocon.py:340-348``); the hardware
factory opens the connection through connio in the same way as the upstream tango server
(``cryocon/tango/server/cryocon.py:113-125`` and ``cryocon/tango/server/cryocon.py:146-148``).

The package is deliberately read-only.  The same class can write channel names, loop set points, loop types and
ranges, and the manual output power (``cryocon/cryocon.py:115-122``, ``cryocon/cryocon.py:133-141`` and
``cryocon/cryocon.py:151-185``), and ``control``/``STOP`` switches the controller output
(``cryocon/cryocon.py:350-355``).  Those are heating actuations (R2 or above under ``MHS/spec/04-safety.md``).
This package binds none of them, so its only capability is ``cap.measure.temperature.v1`` (class floor R0) and it
never changes the controller's output.  ``facts.md`` records the write paths and why they are not bound.

Every Fact cites a line of the clone at the pinned commit a60636963d001e407c534494443b772742f6f545.  This package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null): the acceptance gate runs the fake
backend only, and nothing here ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

CRYOCON = "cryocon/cryocon.py"


def _to_celsius(value, unit, channel):
    """Convert a channel reading in K, C or F to degrees Celsius; sensor units (S) are not a temperature."""
    if value is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"input channel {channel} reports a sensor fault")
    unit = str(unit).upper()
    if unit == "C":
        return float(value)
    if unit == "K":
        return float(value) - 273.15
    if unit == "F":
        return (float(value) - 32.0) * 5.0 / 9.0
    raise DriverFailed(
        "MHS.DEVICE.PRECONDITION_UNMET",
        f"input channel {channel} reports unit {unit!r}, which is not a temperature (K, C or F)",
    )


class CryoCon(Driver):
    device_id = "cryocon"
    device_kind = "instrument.thermometer"
    mode = "hardware"
    risk = "R0"
    native = "cryocon.cryocon:CryoCon"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCryoCon"}
    vendor, model = "Cryo-con", "M24C/M32 temperature controller"
    display_name = "CryoCon temperature controller (cryocon.CryoCon)"
    tags = ["cryocon", "temperature", "thermometer", "controller", "read-only"]
    facts = [
        Fact("The README says the library has been tested with the M32 and M24C models and should work with other "
             "CryoCon models", source="vendor_doc", ref="README.md:9"),
        Fact("A CryoCon simulator is provided and is installed with the simulator extra",
             source="vendor_doc", ref="README.md:98-104"),
        Fact("The hardware accepts a query only every 100 ms, and queries can be grouped in a single request",
             source="vendor_doc", ref="README.md:72-78"),
        Fact("CryoCon binds the system properties to *IDN, SYSTEM:NAME, SYSTEM:HWR, SYSTEM:FWR, SYSTEM:LOCKOUT, "
             "SYSTEM:REMLED, SYSTEM:DISTC, SYSTEM:DATE and SYSTEM:TIME",
             source="upstream_code", ref=f"{CRYOCON}:340-348"),
        Fact("to_date and to_time parse the SYSTEM:DATE and SYSTEM:TIME replies into datetime.date and datetime.time",
             source="upstream_code", ref=f"{CRYOCON}:66-89"),
        Fact("channel_member builds the ':INPUT <id>:<name>' command, and Channel binds NAM, TEMP, UNIT, MIN, MAX, "
             "VARI, SLOP, OFFS and ALAR to it", source="upstream_code", ref=f"{CRYOCON}:105-141"),
        Fact("A channel's unit is one of K, C, F or S", source="upstream_code", ref=f"{CRYOCON}:18"),
        Fact("to_float returns None for the fault '-------', out-of-range '.......' and 'N/A' replies",
             source="upstream_code", ref=f"{CRYOCON}:9-39"),
        Fact("control() reads :CONTROL? and sets :CONTROL or :STOP", source="upstream_code",
             ref=f"{CRYOCON}:350-355"),
        Fact("to_float_unit drops the last character of a set point reply (its unit character)",
             source="upstream_code", ref=f"{CRYOCON}:42-43"),
        Fact("Loop.output_power reads OUTP and is a percentage", source="upstream_code", ref=f"{CRYOCON}:164"),
    ]

    # -- system reads ---------------------------------------------------------------------------------------------
    @read("idn", type="string", description="Instrument identification reported by *IDN?")
    async def idn(self):
        return str(await self.native.idn())

    @read("name", type="string", description="System name reported by SYSTEM:NAME?")
    async def name(self):
        return str(await self.native.name())

    @read("hw_revision", type="string", description="Hardware revision reported by SYSTEM:HWR?")
    async def hw_revision(self):
        return str(await self.native.hw_revision())

    @read("fw_revision", type="string", description="Firmware revision reported by SYSTEM:FWR?")
    async def fw_revision(self):
        return str(await self.native.fw_revision())

    @read("lockout", type="boolean", description="True while the front panel lockout reported by SYSTEM:LOCKOUT? is on")
    async def lockout(self):
        return bool(await self.native.lockout())

    @read("led", type="boolean", description="True while the remote LED reported by SYSTEM:REMLED? is on")
    async def led(self):
        return bool(await self.native.led())

    @read("display_filter_time", description="Display filter time reported by SYSTEM:DISTC?")
    async def display_filter_time(self):
        return float(await self.native.display_filter_time())

    @read("date", type="string", description="Controller date reported by SYSTEM:DATE?, as an ISO 8601 date")
    async def date(self):
        return (await self.native.date()).isoformat()

    @read("time", type="string", description="Controller time reported by SYSTEM:TIME?, as an ISO 8601 time")
    async def time(self):
        return (await self.native.time()).isoformat()

    @read("control", type="boolean", description="True while the controller reports that output control is on")
    async def control(self):
        return bool(await self.native.control())

    # -- input-channel reads --------------------------------------------------------------------------------------
    def _channel_entry(self, probe=None):
        """The configured (channel id, Channel) this driver reads: probe A-D, else the backend option, else first."""
        channels = self.native.channels
        if probe is not None:
            key = str(probe).upper()
            if key in channels:
                return key, channels[key]
        option = self.options.get("channel")
        if option is not None:
            key = str(option).upper()
            if key in channels:
                return key, channels[key]
        try:
            key = next(iter(channels))
        except StopIteration:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the controller reports no configured input channel")
        return key, channels[key]

    @read("channel", type="string",
          description="Configured input channel this driver reads (the first one unless the channel option selects "
                      "another)")
    def channel(self):
        key, _channel = self._channel_entry()
        return key

    @read("channel_name", type="string", description="Name of the selected input channel")
    async def channel_name(self):
        _key, channel = self._channel_entry()
        return str(await channel.name())

    @read("temperature", description="Temperature of the selected input channel in the unit reported by "
                                    "temperature_unit")
    async def temperature(self):
        _key, channel = self._channel_entry()
        value = await channel.temperature()
        return None if value is None else float(value)

    @read("temperature_unit", type="string",
          description="Unit of the selected input channel: K, C, F or S as the controller reports it")
    async def temperature_unit(self):
        _key, channel = self._channel_entry()
        return str(await channel.unit())

    @read("minimum", description="Lower sensor limit of the selected input channel, in temperature_unit")
    async def minimum(self):
        _key, channel = self._channel_entry()
        value = await channel.minimum()
        return None if value is None else float(value)

    @read("maximum", description="Upper sensor limit of the selected input channel, in temperature_unit")
    async def maximum(self):
        _key, channel = self._channel_entry()
        value = await channel.maximum()
        return None if value is None else float(value)

    @read("alarm", type="string", description="Alarm text reported for the selected input channel")
    async def alarm(self):
        _key, channel = self._channel_entry()
        return str(await channel.alarm())

    # -- control-loop reads ---------------------------------------------------------------------------------------
    def _loop_entry(self):
        """The configured (loop id, Loop) this driver reads: the backend option, else the first loop."""
        loops = self.native.loops
        option = self.options.get("loop")
        if option is not None:
            try:
                key = int(option)
            except (TypeError, ValueError):
                key = None
            if key in loops:
                return key, loops[key]
        try:
            key = next(iter(loops))
        except StopIteration:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the controller reports no configured control loop")
        return key, loops[key]

    @read("loop", type="integer",
          description="Configured control loop this driver reads (the first one unless the loop option selects "
                      "another)")
    def loop(self):
        key, _loop = self._loop_entry()
        return key

    @read("loop_setpoint", description="Set point of the selected loop in the unit of its source input channel")
    async def loop_setpoint(self):
        _key, loop = self._loop_entry()
        value = await loop.set_point()
        return None if value is None else float(value)

    @read("loop_source", type="string", description="Input channel id that is the source of the selected loop")
    async def loop_source(self):
        _key, loop = self._loop_entry()
        return str(await loop.source())

    @read("loop_type", type="string", description="Control type of the selected loop")
    async def loop_type(self):
        _key, loop = self._loop_entry()
        return str(await loop.type())

    @read("loop_output_power", unit="%", description="Output power of the selected loop in percent")
    async def loop_output_power(self):
        _key, loop = self._loop_entry()
        value = await loop.output_power()
        return None if value is None else float(value)

    @read("loop_range", type="string", description="Output range of the selected loop")
    async def loop_range(self):
        _key, loop = self._loop_entry()
        return str(await loop.range())

    # -- the measurement capability -------------------------------------------------------------------------------
    @action(cap="cap.measure.temperature.v1",
            description="Measure the selected input channel and return its temperature in degrees Celsius",
            input={
                "probe": Field("string", description="Optional input channel name (A to D); any other value "
                                                      "measures the selected channel"),
                "location": Field("string", description="Optional location label; it does not select a channel"),
            })
    async def measure_temperature(self, probe=None, location=None):
        key, channel = self._channel_entry(probe)
        value = await channel.temperature()
        unit = await channel.unit()
        return {"temperature": _to_celsius(value, unit, key)}
