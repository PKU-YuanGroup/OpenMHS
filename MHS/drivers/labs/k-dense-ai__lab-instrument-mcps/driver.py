"""OpenMHS driver for gh.k-dense-ai/lab-instrument-mcps: a JULABO circulator.

The upstream package ``labmcp-julabo`` (servers/chemistry/julabo-circulator) speaks
JULABO interface commands over a ``labmcp`` transport.  The class
``labmcp_julabo.driver:JulaboCirculator`` is a plain synchronous object: reads query
``in_pv_00``/``in_pv_01``/``in_pv_03``/``in_pv_04``/``in_sp_00``/``in_mode_05``,
``set_setpoint`` writes ``out_sp_00``, ``start`` writes ``out_mode_05 1`` and
``stop`` writes ``out_mode_05 0`` and reports whether ``in_mode_05`` confirms it.

The driver is a direct ``Driver`` over that class (a deviation from the card's
``PythonObjectDriver``: the declarative family cannot turn the native ``stop()``
boolean into a failed safe-state receipt, and the device needs the read-back and
remote-control handling below).  The set point write is refused until an operator
supplies the envelope with ``Limit.operator_required``; the native stop is both the
e-stop and the input-free safe-state action.

This package is model-authored and unreviewed.  It is checked on the fake backend
only; the loader refuses its R2 hardware backend until a human sets
``reviewed_by`` in driver.lock.json.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class LabMcpJulabo(Driver):
    device_id = "julabo-circulator"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "labmcp_julabo.driver:JulaboCirculator"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeJulaboCirculator"}
    vendor = "JULABO"
    model = "CORIO CD/CP, MAGIO MS, DYNEO DD circulator"
    display_name = "JULABO heating or refrigerated circulator (labmcp-julabo)"
    tags = ["circulator", "temperature-control", "bath", "serial", "julabo"]
    facts = [
        Fact("bath_temperature_c reads in_pv_00, heating_power_pct reads in_pv_01, "
             "safety_sensor_temperature_c reads in_pv_03 and excess_temperature_protection_c reads in_pv_04",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:227-245"),
        Fact("setpoint_c reads in_sp_00 and set_setpoint writes out_sp_00 with two decimals and reads it back",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:247-271"),
        Fact("is_running reads in_mode_05; start writes out_mode_05 1 and verifies is_running",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:254-281"),
        Fact("The upstream start_circulation tool reads the current set point and checks it against its "
             "operator safety limits before starting, because the set point may have been changed on the "
             "front panel",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/server.py:227-237"),
        Fact("stop writes out_mode_05 0, retries once and returns True only if in_mode_05 confirms the stop",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:283-296"),
        Fact("require_remote refuses settings when status has kind state and remote is False",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:215-223"),
        Fact("Status codes 0 to 3 are manual stop, manual start, remote stop and remote start",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:44-50"),
        Fact("parse_status classifies known command-error codes as command_error and other negative codes as alarm",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:122-134"),
        Fact("A set point outside the temperature limits set on the circulator is rejected with -13",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:58"),
        Fact("RS-232 factory settings are 4800 baud, 7 data bits, even parity, 1 stop bit and RTS/CTS handshake",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:19-20"),
        Fact("CORIO CD has only in_pv_00/01/03/04, in_sp_00, in_mode_05, out_sp_00, out_mode_05, version and "
             "status; the external Pt100 sensor in_pv_02 needs MAGIO or DYNEO",
             source="upstream_code",
             ref="servers/chemistry/julabo-circulator/src/labmcp_julabo/driver.py:23-25"),
        Fact("The README describes stop_circulation as stopping temperature control and the pump, then "
             "confirming with in_mode_05",
             source="vendor_doc",
             ref="servers/chemistry/julabo-circulator/README.md:71"),
        Fact("The MCP server's set point safety limits default to 5 and 90 Cel and the README tells the operator "
             "to set them to the bath fluid's working range",
             source="vendor_doc",
             ref="servers/chemistry/julabo-circulator/README.md:79-83"),
    ]
    safe_state = ("temperature control and pump stopped (out_mode_05 0); the bath and its fluid stay hot or "
                  "cold and are not physically isolated")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("temperature", unit="Cel", description="Actual bath/internal temperature (in_pv_00)")
    def temperature(self):
        return self.native.bath_temperature_c()

    @read("heating_power", unit="%", description="Heating or cooling actuating variable in percent (in_pv_01)")
    def heating_power(self):
        return self.native.heating_power_pct()

    @read("safety_sensor_temperature", unit="Cel",
          description="Temperature of the high-temperature safety sensor (in_pv_03)")
    def safety_sensor_temperature(self):
        return self.native.safety_sensor_temperature_c()

    @read("excess_temperature_protection", unit="Cel",
          description="Setting of the high-temperature protection function (in_pv_04)")
    def excess_temperature_protection(self):
        return self.native.excess_temperature_protection_c()

    @read("setpoint", unit="Cel", description="Stored working temperature set point (in_sp_00)")
    def setpoint(self):
        return self.native.setpoint_c()

    @read("running", type="boolean", description="True while temperature control is started (in_mode_05)")
    def running(self):
        return self.native.is_running()

    @read("status", type="string", description="Raw status line of the circulator (00-03 or a negative code)")
    def status(self):
        return self.native.query("status")

    @read("version", type="string", description="Firmware version string reported by the circulator")
    def version(self):
        return self.native.version()

    # -- the one write -------------------------------------------------------------------------------------------
    @write("setpoint", unit="Cel", description="Working temperature set point, written with two decimals (out_sp_00)",
           limit=Limit.operator_required(
               "no text file of the clone states the working temperature range of the circulator; the server's "
               "5 to 90 Cel defaults are operator-configurable water-bath limits (README.md:79-83), not a device "
               "bound, so the operator supplies the range of the installed unit and bath fluid"))
    def set_setpoint(self, value):
        self.native.set_setpoint(value)
        self.check_cancelled()
        return self.native.setpoint_c()

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.k-dense-ai.start_circulation.v1",
            description="Start temperature control and the pump (out_mode_05 1) at the stored set point",
            output={"running": Field("boolean",
                                     description="True once in_mode_05 confirms that temperature control is started")})
    def start_circulation(self):
        self.native.start()
        self.check_cancelled()
        return {"running": self.native.is_running()}

    @action(name="x-cap.k-dense-ai.stop_circulation.v1", safe_state=True,
            description="Stop temperature control and the pump (out_mode_05 0), the native stop and safe state",
            output={"running": Field("boolean",
                                     description="False once in_mode_05 confirms that temperature control is stopped")})
    def stop_circulation(self):
        if not self.native.stop():
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the circulator did not confirm out_mode_05 0 within two attempts")
        return {"running": self.native.is_running()}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sets out_mode_05 0 and confirms in_mode_05."""
        if not self.native.stop():
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the e-stop did not confirm out_mode_05 0 within two attempts")

    def teardown(self):
        self.native.close()
