"""OpenMHS driver for gh.tiagocoutinho/vacuubrand: a Vacuubrand DCP 3000 vacuum controller.

A direct Driver (decorated methods) over the upstream device class
``vacuubrand.dcp3000.dcp3000:DCP3000``.  The upstream class builds every request from parts
(``IN_PV_S{channel}``, ``OUT_SP_{on_off}{channel} {value} mbar``, ``REMOTE 1``, ``OUT_VENT 0``) and sends it
through a connection object (vacuubrand/dcp3000/dcp3000.py:18-86, protocol.py:83-88).  A command table cannot
reproduce those assembled strings, so this package is a direct Driver with a ``.native`` factory, not the
``PythonObjectDriver`` named by the card's static scan (DEVIATION FROM THE CARD: helper python-object replaced by a
direct driver; the card's decision is already ``direct-driver``).

The upstream protocol chooses an asyncio protocol when the connection's ``write_readline`` is a coroutine function
(protocol.py:113-143, 179-182), which is how the Tango server opens it (tango/server/dcp3000.py:41-55).  Every method
here is therefore ``async def`` and awaits ``self.native``.

* reads: the system pressure, the transducer pressures, the decoded configuration, the error list, the version,
  the event and recording intervals and the eight on/off set points (channels 1 to 4);
* writes: the event interval and the eight set points.  No text file of the clone states their ranges, so each is
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range
  of its unit (``site-limits.example.json`` shows an example overlay);
* actions: a pressure measurement through ``cap.measure.pressure.v1``, the remote-control on/off commands, and the
  three venting-valve commands.  ``cap.actuation.valve.v1`` and ``cap.actuation.pump.v1`` do not bind the
  ``instrument.gauge`` resource kind of this controller, so the valve and remote commands use extension ids;
* the e-stop sends ``REMOTE -`` and ``OUT_VENT 0``; the two safe-state actions send the same two commands, so a
  latched e-stop leaves remote control released and the venting valve closed.

The recording interval is read-only: on an asyncio connection the upstream setter calls ``self.write(...)`` without
awaiting the coroutine (dcp3000.py:46-50), so its write never reaches the device.  The driver does not expose that
broken setter as a write.

Every Fact cites a line of the clone at the pinned commit 12b2e12aa43866ffa2ab986fc466c5548a7aba07.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class DCP3000(Driver):
    device_id = "vacuubrand-dcp3000"
    device_kind = "instrument.gauge"
    mode = "hardware"
    risk = "R1"
    native = "vacuubrand.dcp3000.dcp3000:DCP3000"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDCP3000"}
    vendor, model = "Vacuubrand", "DCP 3000"
    display_name = "Vacuubrand DCP 3000 vacuum controller"
    tags = ["vacuum", "pressure", "gauge", "controller", "setpoint", "venting-valve", "serial", "asyncio"]
    facts = [
        Fact("pressure() queries IN_PV_1 and returns the decoded pressure", source="upstream_code",
             ref="vacuubrand/dcp3000/dcp3000.py:28-30"),
        Fact("decode_pressure converts a Torr reply to mbar and leaves an mbar or hPa reply numerically unchanged",
             source="upstream_code", ref="vacuubrand/dcp3000/protocol.py:50-56"),
        Fact("transducer_pressure queries IN_PV_S<channel> and transducer_pressures queries IN_PV_X",
             source="upstream_code", ref="vacuubrand/dcp3000/dcp3000.py:32-38"),
        Fact("decode_pressures returns its values in millibar", source="upstream_code",
             ref="vacuubrand/dcp3000/protocol.py:59-66"),
        Fact("config() queries IN_CFG and decode_config returns the unit, the acoustic and connection flags and the "
             "transducer counts", source="upstream_code",
             ref="vacuubrand/dcp3000/dcp3000.py:24-26"),
        Fact("decode_config maps the unit digit through a table of mbar, Torr and hPa", source="upstream_code",
             ref="vacuubrand/dcp3000/protocol.py:11-11"),
        Fact("errors() queries IN_ERR and decode_errors returns the names of the error flags that are set",
             source="upstream_code", ref="vacuubrand/dcp3000/dcp3000.py:66-68"),
        Fact("version() queries IN_VER and returns the reply text", source="upstream_code",
             ref="vacuubrand/dcp3000/dcp3000.py:70-71"),
        Fact("event_time_interval writes OUT_SP_1 and reads IN_SP_1; recording_time_interval writes OUT_SP_2 and "
             "reads IN_SP_2", source="upstream_code", ref="vacuubrand/dcp3000/dcp3000.py:40-50"),
        Fact("decode_interval parses mm:ss and returns minutes*60+seconds", source="upstream_code",
             ref="vacuubrand/dcp3000/protocol.py:77-80"),
        Fact("on_setpoint and off_setpoint accept a channel in 1 to 4, write OUT_SP_<on|off><channel> with the "
             "value in mbar and read the matching IN_SP reply", source="upstream_code",
             ref="vacuubrand/dcp3000/dcp3000.py:52-64"),
        Fact("switch_on writes REMOTE 1 and switch_off writes REMOTE -", source="upstream_code",
             ref="vacuubrand/dcp3000/dcp3000.py:73-77"),
        Fact("close_venting_valve writes OUT_VENT 0, open_venting_value writes OUT_VENT 1 and vent writes "
             "OUT_VENT 2", source="upstream_code", ref="vacuubrand/dcp3000/dcp3000.py:79-87"),
        Fact("The protocol encodes every request as UTF-8 text plus a newline and strips the reply text",
             source="upstream_code", ref="vacuubrand/dcp3000/protocol.py:83-88"),
        Fact("The protocol leaves 60 ms between commands, described as max 20 commands/s according to the "
             "documentation", source="upstream_code", ref="vacuubrand/dcp3000/protocol.py:99-100"),
        Fact("An asyncio connection selects AIOProtocol, whose write_readline and write methods are coroutines",
             source="upstream_code", ref="vacuubrand/dcp3000/protocol.py:113-143"),
        Fact("The Tango server opens the connection with connection_for_url, passes concurrency=\"async\" and adds "
             "baudrate, bytesize and parity for serial schemes", source="upstream_code",
             ref="vacuubrand/tango/server/dcp3000.py:41-55"),
        Fact("The Tango server device properties default to baudrate 9600, bytesize 8 and parity N",
             source="upstream_code", ref="vacuubrand/tango/server/dcp3000.py:34-37"),
        Fact("The README connects through connection_for_url('serial:///dev/ttyS0') and wraps the connection in "
             "DCP3000", source="vendor_doc", ref="README.md:34-48"),
        Fact("The README documents a serial line baudrate of 19200", source="vendor_doc", ref="README.md:57-60"),
    ]
    safe_state = ("remote control released (REMOTE -) and the venting valve closed (OUT_VENT 0); the clone has no "
                  "pump-state query, so the pump state is not observable")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("pressure", unit="Pa", native_unit="mbar",
          description="Absolute pressure of the vacuum system, published in pascals")
    async def pressure(self):
        return await self.native.pressure()

    @read("transducer_pressures", type="array", items=Field("number"), unit="Pa", native_unit="mbar",
          description="Pressure of every pressure transducer, published in pascals")
    async def transducer_pressures(self):
        return await self.native.transducer_pressures()

    @read("configuration", type="object",
          properties={
              "unit": Field("string", enum=["mbar", "Torr", "hPa"],
                            description="Pressure unit configured on the controller"),
              "acoustic_signal": Field("boolean", description="True when the acoustic signal is enabled"),
              "venting_valve_connected": Field("boolean",
                                               description="True when a venting valve is connected"),
              "fault_indicator_connected": Field("boolean",
                                                 description="True when a fault indicator is connected"),
              "nb_active_pressure_transducers": Field("integer",
                                                      description="Number of active pressure transducers"),
              "nb_pressure_transducers": Field("integer",
                                               description="Number of pressure transducers configured"),
          },
          description="Decoded IN_CFG: pressure unit, acoustic and connection flags and transducer counts")
    async def configuration(self):
        return await self.native.config()

    @read("errors", type="array", items=Field("string"),
          description="Names of the error flags the controller reports")
    async def errors(self):
        return await self.native.errors()

    @read("version", type="string", description="Version string reported by the controller")
    async def version(self):
        return await self.native.version()

    @read("event_time_interval", type="integer", unit="s",
          description="Time interval between event messages, in seconds")
    async def event_time_interval(self):
        return await self.native.event_time_interval()

    @read("recording_time_interval", type="integer", unit="s",
          description="Recording time interval, in seconds; read-only because the upstream setter drops its write "
                      "coroutine on an asyncio connection")
    async def recording_time_interval(self):
        return await self.native.recording_time_interval()

    # -- the eight on/off set points ---------------------------------------------------------------------------
    @read("on_setpoint_1", unit="Pa", native_unit="mbar",
          description="Switch-on pressure of set point channel 1, published in pascals")
    async def on_setpoint_1(self):
        return await self.native.on_setpoint(1)

    @read("off_setpoint_1", unit="Pa", native_unit="mbar",
          description="Switch-off pressure of set point channel 1, published in pascals")
    async def off_setpoint_1(self):
        return await self.native.off_setpoint(1)

    @read("on_setpoint_2", unit="Pa", native_unit="mbar",
          description="Switch-on pressure of set point channel 2, published in pascals")
    async def on_setpoint_2(self):
        return await self.native.on_setpoint(2)

    @read("off_setpoint_2", unit="Pa", native_unit="mbar",
          description="Switch-off pressure of set point channel 2, published in pascals")
    async def off_setpoint_2(self):
        return await self.native.off_setpoint(2)

    @read("on_setpoint_3", unit="Pa", native_unit="mbar",
          description="Switch-on pressure of set point channel 3, published in pascals")
    async def on_setpoint_3(self):
        return await self.native.on_setpoint(3)

    @read("off_setpoint_3", unit="Pa", native_unit="mbar",
          description="Switch-off pressure of set point channel 3, published in pascals")
    async def off_setpoint_3(self):
        return await self.native.off_setpoint(3)

    @read("on_setpoint_4", unit="Pa", native_unit="mbar",
          description="Switch-on pressure of set point channel 4, published in pascals")
    async def on_setpoint_4(self):
        return await self.native.on_setpoint(4)

    @read("off_setpoint_4", unit="Pa", native_unit="mbar",
          description="Switch-off pressure of set point channel 4, published in pascals")
    async def off_setpoint_4(self):
        return await self.native.off_setpoint(4)

    # -- writes ------------------------------------------------------------------------------------------------
    @write("event_time_interval", type="integer", unit="s",
           description="Event message interval",
           limit=Limit.operator_required(
               "no clone text states the event interval range; the site supplies the range"))
    async def set_event_time_interval(self, value):
        await self.native.event_time_interval(value)
        return await self.native.event_time_interval()

    @write("on_setpoint_1", unit="Pa", native_unit="mbar",
           description="Channel 1 switch-on pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_on_setpoint_1(self, value):
        await self.native.on_setpoint(1, value)
        return await self.native.on_setpoint(1)

    @write("off_setpoint_1", unit="Pa", native_unit="mbar",
           description="Channel 1 switch-off pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_off_setpoint_1(self, value):
        await self.native.off_setpoint(1, value)
        return await self.native.off_setpoint(1)

    @write("on_setpoint_2", unit="Pa", native_unit="mbar",
           description="Channel 2 switch-on pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_on_setpoint_2(self, value):
        await self.native.on_setpoint(2, value)
        return await self.native.on_setpoint(2)

    @write("off_setpoint_2", unit="Pa", native_unit="mbar",
           description="Channel 2 switch-off pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_off_setpoint_2(self, value):
        await self.native.off_setpoint(2, value)
        return await self.native.off_setpoint(2)

    @write("on_setpoint_3", unit="Pa", native_unit="mbar",
           description="Channel 3 switch-on pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_on_setpoint_3(self, value):
        await self.native.on_setpoint(3, value)
        return await self.native.on_setpoint(3)

    @write("off_setpoint_3", unit="Pa", native_unit="mbar",
           description="Channel 3 switch-off pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_off_setpoint_3(self, value):
        await self.native.off_setpoint(3, value)
        return await self.native.off_setpoint(3)

    @write("on_setpoint_4", unit="Pa", native_unit="mbar",
           description="Channel 4 switch-on pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_on_setpoint_4(self, value):
        await self.native.on_setpoint(4, value)
        return await self.native.on_setpoint(4)

    @write("off_setpoint_4", unit="Pa", native_unit="mbar",
           description="Channel 4 switch-off pressure",
           limit=Limit.operator_required(
               "no clone text states a set point range; the site supplies the range"))
    async def set_off_setpoint_4(self, value):
        await self.native.off_setpoint(4, value)
        return await self.native.off_setpoint(4)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(cap="cap.measure.pressure.v1",
            description="Measure the absolute pressure of the vacuum system (native IN_PV_1)",
            input={"reference": Field("string", enum=["absolute"],
                                      description="Pressure reference; the DCP 3000 reports absolute pressure")})
    async def measure_pressure(self, reference):
        pressure_mbar = await self.native.pressure()
        return {"pressure": pressure_mbar * 100.0,     # 1 mbar = 100 Pa
                "reference": reference}

    @action(name="x-cap.tiagocoutinho.switch_on.v1",
            description="Enter remote control (native REMOTE 1)",
            output={"remote": Field("boolean", description="True once remote control was requested")})
    async def switch_on(self):
        await self.native.switch_on()
        return {"remote": True}

    @action(name="x-cap.tiagocoutinho.switch_off.v1", safe_state=True,
            description="Release remote control (native REMOTE -); it takes no input",
            output={"remote": Field("boolean", description="False once remote control was released")})
    async def switch_off(self):
        await self.native.switch_off()
        return {"remote": False}

    @action(name="x-cap.tiagocoutinho.open_venting_valve.v1",
            description="Open the venting valve (native OUT_VENT 1); it takes no input",
            output={"venting_valve": Field("string", enum=["open"],
                                           description="The command sent to the venting valve")})
    async def open_venting_valve(self):
        await self.native.open_venting_value()      # the upstream method name is open_venting_value
        return {"venting_valve": "open"}

    @action(name="x-cap.tiagocoutinho.close_venting_valve.v1", safe_state=True,
            description="Close the venting valve (native OUT_VENT 0); it takes no input and is the safe-state "
                        "valve command",
            output={"venting_valve": Field("string", enum=["closed"],
                                           description="The command sent to the venting valve")})
    async def close_venting_valve(self):
        await self.native.close_venting_valve()
        return {"venting_valve": "closed"}

    @action(name="x-cap.tiagocoutinho.vent.v1",
            description="Vent until atmospheric pressure (native OUT_VENT 2); it takes no input",
            output={"venting_valve": Field("string", enum=["venting"],
                                           description="The command sent to the venting valve")})
    async def vent(self):
        await self.native.vent()
        return {"venting_valve": "venting"}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="switch_off")
    async def stop(self):
        """The native stop path: REMOTE - then OUT_VENT 0 (dcp3000.py:73-87)."""
        await self.native.switch_off()
        await self.native.close_venting_valve()
