"""OpenMHS driver for gh.tiagocoutinho/gepace: a GE Druck Pace pressure controller.

A direct Driver (decorated methods) over the upstream device class ``gepace.pace:Pace``
(gepace/pace.py:293).  The upstream class talks to the instrument over a line-oriented connection;
on the asyncio connection the native factory builds (native.py, mirroring the upstream tango server at
gepace/tango/server/pace.py:54-68) every member is a coroutine, so every method here is ``async def``
and awaits ``self.native``.

The package serves module 1, the module the upstream tango server reads for its pressure, setpoint,
rate and control attributes (gepace/tango/server/pace.py:29-35):

* reads: identification, version, MAC, task, world area, self test, error, startup mode, serial
  numbers, pressure, barometric pressure, pressure control, pressure unit, pressure range and the
  in-limits flag;
* three extension actions enable or disable the pressure control output and stop it as the safe
  state.  They send the exact ``OUTP1:STAT`` setter+readback request that ``Module.start()`` /
  ``Module.stop()`` build (gepace/pace.py:138-184, 240, 258-262) through the upstream
  ``Pace.__call__`` (gepace/pace.py:376-377), so the wire syntax is the upstream's;
* the ``@estop`` method sends the same stop request.

No write is bound: the card lists none, and no text file of the clone states a pressure setpoint range
(the manuals under ``docs/`` are PDFs), so the pressure setpoint is left out rather than given an
invented bound.  Every Fact cites a line of the clone at the pinned commit
4caa5f8c404277281033bc7f10b280d42941dfeb.

Risk R2: enabling the pressure control output can pressurize an external system, a high-energy action
that can be destructive if wrong (MHS-004 R2).  No text file of the clone documents an independent
hardware e-stop, so ``estop_physical_ref`` is not set; the ``@estop`` method and the safe-state action
``stop_pressure_control`` both send ``OUTP1:STAT 0``, which satisfies SAFE-045 for this hardware R2
driver.  This package is model-authored and unreviewed: the loader refuses its hardware backend until
a human sets ``reviewed_by`` in driver.lock.json (R2 and R3 only), and the gate runs the fake backend
only.
"""

from mhs.driver import Driver, Fact, Field, action, estop, read

#: The upstream tango server reads module 1 for its pressure attributes (gepace/tango/server/pace.py:29-35).
MODULE = 1

#: The setter+readback request that Module.pressure_control builds (gepace/pace.py:138-184, 240).  The
#: semicolon-separated pair is the upstream wire syntax: set the output state, then query it back.
_CONTROL_REQUEST = ":OUTP{module}:STAT {state};:OUTP{module}:STAT?"


def _to_bool(reply):
    """Apply the upstream ``to_nop`` + ``to_bool`` reading (gepace/pace.py:18-20, 39-40) to a reply."""

    if isinstance(reply, bool):
        return reply
    text = str(reply).strip()
    if " " in text:
        text = text.split(" ", 1)[-1]
    return text.strip() == "1"


class Gepace(Driver):
    device_id = "gepace"
    device_kind = "process.controller"
    mode = "hardware"
    risk = "R2"
    native = "gepace.pace:Pace"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGepace"}
    vendor, model = "GE Druck", "Pace 1000/5000/6000"
    display_name = "GE Druck Pace pressure controller (gepace.Pace)"
    tags = ["pressure", "pressure-controller", "calibration", "gepace", "pace", "scpi", "asyncio"]
    facts = [
        Fact("The library controls basic features of a GE Pressure Automated Calibration Equipment "
             "(Pace) controller of models 1000, 5000 and 6000", source="vendor_doc", ref="README.md:5-6"),
        Fact("The core of the library is the Pace object, created with a connection object that provides "
             "write_readline and write, in a sync or async version", source="vendor_doc", ref="README.md:22-34"),
        Fact("Module.pressure reads SENS<module>:PRES as a float", source="upstream_code",
             ref="gepace/pace.py:224"),
        Fact("The tango server maps pace[1].pressure() to its Pressure attribute with unit bar",
             source="upstream_code", ref="gepace/tango/server/pace.py:118-120"),
        Fact("Module.barometric_pressure reads SENS<module>:PRES:BAR as a float", source="upstream_code",
             ref="gepace/pace.py:227"),
        Fact("Module.pressure_control reads and writes OUTP<module>:STAT as a bool", source="upstream_code",
             ref="gepace/pace.py:240"),
        Fact("Module.start() sets the pressure control output of the module True and Module.stop() sets it "
             "False", source="upstream_code", ref="gepace/pace.py:258-262"),
        Fact("A member read appends '?' to the command; a member write sends '<CMD> <value>;<CMD>?' so the "
             "setter is confirmed by a read-back", source="upstream_code", ref="gepace/pace.py:144-161"),
        Fact("Pace.__call__(request) sends one request through Pace._query", source="upstream_code",
             ref="gepace/pace.py:376-377"),
        Fact("idn, hw_test, mac, task, error, version, world_area and startup_mode query *IDN, *TST, INST:MAC, "
             "INST:TASK, SYST:ERR, SYST:VERS, SYST:AREA and SYST:SET", source="upstream_code",
             ref="gepace/pace.py:401-408"),
        Fact("startup_mode returns a Mode and a float setpoint; Mode.Control is CONT and Mode.Measurement is MEAS",
             source="upstream_code", ref="gepace/pace.py:207-219"),
        Fact("serial_numbers queries :INST:SN1 through :INST:SN7 in one request", source="upstream_code",
             ref="gepace/pace.py:411-415"),
        Fact("The serial number reply maps to ui, ctrl1, ctrl2, ao1, ao2, vfc1 and vfc2 as integers",
             source="upstream_code", ref="gepace/pace.py:60-63"),
        Fact("Module.unit reads and writes UNIT<module>:PRES as a string", source="upstream_code",
             ref="gepace/pace.py:245"),
        Fact("Module.pressure_range reads SENS<module>:PRES:RANG through to_name, which strips the quotes",
             source="upstream_code", ref="gepace/pace.py:225"),
        Fact("Module.pressure_in_limits reads SENS<module>:PRES:INL", source="upstream_code",
             ref="gepace/pace.py:226"),
        Fact("The in-limits reply is parsed as a pressure and a boolean", source="upstream_code",
             ref="gepace/pace.py:55-57"),
        Fact("The tango server reads module 1 for its pressure, source pressure, setpoint, rate, rate mode, "
             "control and unit attributes", source="upstream_code", ref="gepace/tango/server/pace.py:29-36"),
        Fact("The tango server publishes pressure control as a bool attribute and writes it with "
             "pace[1].pressure_control(value)", source="upstream_code",
             ref="gepace/tango/server/pace.py:168-175"),
        Fact("The tango server creates the device with connection_for_url(url, concurrency='async') and passes "
             "that connection to Pace", source="upstream_code", ref="gepace/tango/server/pace.py:54-68"),
        Fact("Pace._ask appends one newline to the request bytes and uses write_readline for a request that "
             "contains '?'", source="upstream_code", ref="gepace/pace.py:382-386"),
    ]
    safe_state = "pressure control output disabled for module 1 (OUTP1:STAT 0)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("idn", type="string", description="Identification string of the controller (*IDN?)")
    async def idn(self):
        return str(await self.native.idn())

    @read("version", type="string", description="Firmware version of the controller (SYST:VERS?)")
    async def version(self):
        return str(await self.native.version())

    @read("mac", type="string", description="MAC address reported by the controller (INST:MAC?)")
    async def mac(self):
        return str(await self.native.mac())

    @read("task", type="string", description="Task the controller reports (INST:TASK?)")
    async def task(self):
        return str(await self.native.task())

    @read("world_area", type="string", description="World area reported by the controller (SYST:AREA?)")
    async def world_area(self):
        return str(await self.native.world_area())

    @read("hw_test", type="boolean", description="Self-test result of the controller (*TST?)")
    async def hw_test(self):
        return bool(await self.native.hw_test())

    @read("error", type="string",
          description="Pending controller error as 'code: text', or an empty string when the code is zero "
                      "(SYST:ERR?)")
    async def error(self):
        code, text = await self.native.error()
        return "{}: {}".format(code, text) if code else ""

    @read("startup_mode", type="string",
          description="Startup mode stored by the controller (SYST:SET?): CONT for control, MEAS for measurement")
    async def startup_mode(self):
        mode, _setpoint = await self.native.startup_mode()
        return str(mode.name)

    @read("serial_numbers", type="object",
          description="Serial numbers reported by the controller in one :INST:SN1..7 query",
          properties={
              "ui": Field("integer", description="UI serial number"),
              "ctrl1": Field("integer", description="First controller serial number"),
              "ctrl2": Field("integer", description="Second controller serial number"),
              "ao1": Field("integer", description="First analogue output serial number"),
              "ao2": Field("integer", description="Second analogue output serial number"),
              "vfc1": Field("integer", description="First VFC serial number"),
              "vfc2": Field("integer", description="Second VFC serial number"),
          })
    async def serial_numbers(self):
        return dict(await self.native.serial_numbers())

    @read("pressure", unit="bar", description="Pressure measured by module 1 (SENS1:PRES), in bar")
    async def pressure(self):
        return float(await self.native.modules[MODULE].pressure())

    @read("barometric_pressure",
          description="Barometric pressure measured by module 1 (SENS1:PRES:BAR), in the module's pressure "
                      "unit reported by pressure_unit")
    async def barometric_pressure(self):
        return float(await self.native.modules[MODULE].barometric_pressure())

    @read("pressure_control", type="boolean",
          description="True while the pressure control output of module 1 is enabled (OUTP1:STAT)")
    async def pressure_control(self):
        return bool(await self.native.modules[MODULE].pressure_control())

    @read("pressure_unit", type="string",
          description="Pressure unit configured on module 1 (UNIT1:PRES), as the controller reports it")
    async def pressure_unit(self):
        return str(await self.native.modules[MODULE].unit())

    @read("pressure_range", type="string",
          description="Pressure range reported by module 1 (SENS1:PRES:RANG), with the quotes removed")
    async def pressure_range(self):
        return str(await self.native.modules[MODULE].pressure_range())

    @read("pressure_in_limits", type="boolean",
          description="True while module 1 reports the measured pressure inside its configured in-limit band "
                      "(SENS1:PRES:INL)")
    async def pressure_in_limits(self):
        _pressure, in_limits = await self.native.modules[MODULE].pressure_in_limits()
        return bool(in_limits)

    # -- control ----------------------------------------------------------------------------------------------
    async def _control(self, enabled):
        """Send the upstream pressure-control setter+readback for module 1 and return the applied state."""

        request = _CONTROL_REQUEST.format(module=MODULE, state="1" if enabled else "0")
        return _to_bool(await self.native(request))

    @action(name="x-cap.tiagocoutinho.set_pressure_control.v1",
            description="Enable or disable the pressure control output of module 1 (OUTP1:STAT)",
            input={"enabled": Field("boolean",
                                    description="True enables the pressure control output; False disables it")},
            output={"enabled": Field("boolean",
                                     description="Pressure control state read back from the controller")})
    async def set_pressure_control(self, enabled):
        return {"enabled": await self._control(bool(enabled))}

    @action(name="x-cap.tiagocoutinho.start_pressure_control.v1",
            description="Enable the pressure control output of module 1 (the native start, OUTP1:STAT 1)",
            output={"enabled": Field("boolean",
                                     description="Pressure control state read back from the controller")})
    async def start_pressure_control(self):
        return {"enabled": await self._control(True)}

    @action(name="x-cap.tiagocoutinho.stop_pressure_control.v1", safe_state=True,
            description="Disable the pressure control output of module 1 (the native stop, the safe state); it "
                        "takes no input",
            output={"enabled": Field("boolean",
                                     description="Pressure control state read back from the controller")})
    async def stop_pressure_control(self):
        return {"enabled": await self._control(False)}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="stop")
    async def stop(self):
        """The native stop: disable the pressure control output with OUTP1:STAT 0."""

        await self._control(False)

    async def teardown(self):
        await self.native.close()
