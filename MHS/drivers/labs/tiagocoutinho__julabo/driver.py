"""OpenMHS driver for gh.tiagocoutinho/julabo: a JULABO circulator over its asyncio protocol.

A direct Driver (decorated methods) over the upstream device class julabo.device:JulaboCF.  The upstream class talks
to the instrument through a connection object; on an asyncio connection (the default of connection_for_url,
julabo/connection.py:45; the protocol class follows from it, julabo/protocol.py:116-119) every member is a coroutine
function, so every method here is ``async def`` and awaits ``self.native``.

* reads: bath temperature, external (Pt100) temperature, set point 1, the active set point channel, the start/stop
  state and the status line;
* one write: set point 1.  No text file of the clone states a temperature range, so the limit is
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of
  its unit (``site-limits.example.json`` shows the overlay);
* the native stop (``OUT_MODE_05 0``) is the e-stop and, as ``stop_circulation``, the safe-state action.

Every Fact cites a line of the clone at the pinned commit (650da2138459d93e3bfdb8db17ce0bd161c6a9a7).  This package
is model-authored and unreviewed: it is checked on the fake backend only (README.md).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class Julabo(Driver):
    device_id = "julabo"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "julabo.device:JulaboCF"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeJulaboCF"}
    vendor, model = "JULABO", "CF cryo-compact circulator"
    display_name = "JULABO circulator (julabo.JulaboCF)"
    tags = ["circulator", "temperature-control", "bath", "asyncio"]
    facts = [
        Fact("bath_temperature reads IN_PV_00, external_temperature IN_PV_02, and set_point_1 reads IN_SP_00 and "
             "writes OUT_SP_00", source="upstream_code", ref="julabo/device.py:128-132"),
        Fact("The tango server publishes the bath temperature and the external PT100 temperature in degC",
             source="upstream_code", ref="julabo/tango/server/device.py:85-98"),
        Fact("Set point 1 is the working temperature set point of channel 1, published in degC",
             source="upstream_code", ref="julabo/tango/server/device.py:105-108"),
        Fact("A set point is written with two decimals ('{:.2f}')", source="upstream_code",
             ref="julabo/device.py:48"),
        Fact("start() writes OUT_MODE_05 1 and stop() writes OUT_MODE_05 0", source="upstream_code",
             ref="julabo/device.py:118-122"),
        Fact("The protocol idles the line 250 ms after a command and 10 ms after a query", source="upstream_code",
             ref="julabo/protocol.py:30-33"),
        Fact("The tango server maps status codes 0 and 2 to STANDBY, 1 and 3 to RUNNING and a code below 0 to ALARM",
             source="upstream_code", ref="julabo/tango/server/device.py:42-47"),
        Fact("The active set point channel is 1 to 3", source="upstream_code",
             ref="julabo/tango/server/device.py:150"),
    ]
    safe_state = "circulator stopped (remote stop, OUT_MODE_05 0)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("bath_temperature", unit="Cel", description="Actual bath temperature")
    async def bath_temperature(self):
        return await self.native.bath_temperature()

    @read("external_temperature", unit="Cel", description="Temperature of the external PT100 sensor")
    async def external_temperature(self):
        return await self.native.external_temperature()

    @read("setpoint", unit="Cel", description="Working temperature set point 1")
    async def setpoint(self):
        return await self.native.set_point_1()

    @read("active_set_point_channel", type="integer",
          description="Active set point channel (1 to 3): the channel of the working set point in use")
    async def active_set_point_channel(self):
        return await self.native.active_set_point_channel()

    @read("running", type="boolean", description="True while the circulator is started")
    async def running(self):
        return await self.native.is_started()

    @read("status", type="string", description="Status line of the circulator: a status code and a text")
    async def status(self):
        return await self.native.status()

    # -- the one write ------------------------------------------------------------------------------------------
    @write("setpoint", unit="Cel", description="Working temperature set point 1, written with two decimals",
           limit=Limit.operator_required(
               "no text file of the clone states the set point range of the circulator (the manuals are PDFs under "
               "docs/ and cannot be cited by line); the site sets the range of its unit"))
    async def set_setpoint(self, value):
        await self.native.set_point_1(value)
        return await self.native.set_point_1()      # the value the circulator stored (two decimals)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.tiagocoutinho.start_circulation.v1",
            description="Start the circulator (the native start)",
            output={"running": Field("boolean", description="True once the circulator reports that it is started")})
    async def start_circulation(self):
        await self.native.start()
        return {"running": await self.native.is_started()}

    @action(name="x-cap.tiagocoutinho.stop_circulation.v1", safe_state=True,
            description="Stop the circulator (the native stop, the safe state); it takes no input",
            output={"running": Field("boolean", description="False once the circulator reports that it is stopped")})
    async def stop_circulation(self):
        await self.native.stop()
        return {"running": await self.native.is_started()}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop
    async def stop(self):
        """The native stop: the runtime latches first, then sends OUT_MODE_05 0."""
        await self.native.stop()

    async def teardown(self):
        await self.native.protocol.conn.close()     # julabo/device.py:105, julabo/protocol.py:36
