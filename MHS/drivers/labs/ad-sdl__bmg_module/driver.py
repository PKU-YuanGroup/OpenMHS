"""OpenMHS driver for gh.ad-sdl/bmg_module: the incubator and status of a BMG microplate reader over ActiveX COM.

A direct Driver (decorated methods) over the upstream class sidecar.bmg_interface:BmgCom.  The class owns a
``BMG_ActiveX.BMGRemoteControl`` COM object and sends its device commands through ``ExecuteAndWait``
(sidecar/bmg_interface.py:147-152).  The reader needs 32-bit Python on Windows (README.md:15); the hardware factory in
native.py is the only place that imports the clone, and it keeps the COM object on one thread, as the upstream's own
sidecar does (sidecar/bmg_sidecar_server.py:31-87).

Served:

* reads: the GetVersion string, the status and error strings, and the three internal temperature sensors (a sensor
  the reader gives no value for is left out of the state, never replaced by a number);
* one write: the incubator temperature set point.  The valid range depends on the installed model and on the
  upstream constructor flag ``extended_temperature_range_model`` (sidecar/bmg_interface.py:72-84), so the bound is
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range
  of its unit (``site-limits.example.json`` shows the overlay).  The state shows the last value written, which the
  heater-off action and the e-stop do not change; the clone has no read of the device's set point;
* one action, the safe-state action: switch the incubator off with the native ``set_temp(0.0)``.  The ``@estop``
  method sends the same call.  The upstream documents 0.0 as "off" (sidecar/bmg_interface.py:75) and raises unless
  ExecuteAndWait answers 0 (sidecar/bmg_interface.py:86-90), so a completed stop is the reader's acknowledgement of
  the off command; a refused or failed one leaves the e-stop unreached with the latch held.

NOT COVERED (model review, 2026-11-05): the plate tray (PlateIn, PlateOut), Init and the assay run (Run), the reader's
primary function.  They are actuators, and the clone has no stop, abort or pause for any of them (the BmgCom class body,
sidecar/bmg_interface.py:15-152; the sidecar's endpoint list, sidecar/README.md:16-28); plate_in and plate_out also
discard the ExecuteAndWait response (sidecar/bmg_interface.py:64-70).  Actuators without a source-backed stop stay
out of the package.  The fake backend is an in-memory stand-in that follows the upstream method bodies, not a
recording.  This package is model-authored and unreviewed, so its hardware backend is refused by the loader until a
human signs ``reviewed_by``; the acceptance gate never touches hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class BmgModule(Driver):
    device_id = "bmg-reader"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "sidecar.bmg_interface:BmgCom"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBmgCom"}
    vendor, model = "BMG LABTECH", "VANTAstar / CLARIOstar microplate reader"
    display_name = "BMG microplate reader incubator and status (sidecar.bmg_interface.BmgCom)"
    tags = ["microplate-reader", "plate-reader", "incubator", "activex", "windows"]

    facts = [
        Fact("BmgCom's constructor calls pythoncom.CoInitialize, creates the BMG_ActiveX.BMGRemoteControl COM object "
             "and opens the connection with the control name; open_connection raises when OpenConnection returns "
             "a non-zero result", source="upstream_code", ref="sidecar/bmg_interface.py:18-36"),
        Fact("get_version returns the result of the COM GetVersion call; its docstring calls it the BMG instrument "
             "version", source="upstream_code", ref="sidecar/bmg_interface.py:44-46"),
        Fact("The module's __main__ block connects with the control name CLARIOstar and prints get_version() as the "
             "BMG LABTECH Remote Control Version", source="upstream_code", ref="sidecar/bmg_interface.py:155-157"),
        Fact("get_status and get_error return the COM GetInfo items 'Status' and 'Error' stripped, or the string "
             "'unknown' when GetInfo returns something other than a string",
             source="upstream_code", ref="sidecar/bmg_interface.py:48-58"),
        Fact("plate_in sends PlateIn and plate_out sends PlateOut through _exec (docstrings: close and open the plate "
             "tray), and neither checks the response", source="upstream_code", ref="sidecar/bmg_interface.py:64-70"),
        Fact("set_temp documents 0.0 as off, 0.1 as monitor only, 25.0-45.0 for standard models and 10.0-60.0 for "
             "extended-temperature-range models; it raises ValueError unless the value is 0.0, 0.1 or inside the "
             "range the extended_temperature_range_model flag selects, sends the Temp command with str(temp) and "
             "raises when the ExecuteAndWait response is not 0",
             source="upstream_code", ref="sidecar/bmg_interface.py:72-90"),
        Fact("read_temps reads Temp1, Temp2 and Temp3 with GetInfo and divides each value by 10; its docstring gives "
             "the values in Celsius, or None per sensor when GetInfo returns no value (typical when the device has "
             "not been initialized in SMART Control or the sensor is not yet reporting), and a value float() cannot "
             "parse also gives None", source="upstream_code", ref="sidecar/bmg_interface.py:92-112"),
        Fact("run_assay sends Run with the assay name, the protocol database path, the output directory, the three "
             "plate ids, the output directory again and the output file name (str(int(time.time())) + '.txt' when "
             "none is given), raises when the response is not 0 and returns the output directory joined with the "
             "file name", source="upstream_code", ref="sidecar/bmg_interface.py:114-145"),
        Fact("The BmgCom class defines __init__, open_connection, close_connection, get_version, get_status, "
             "get_error, init, plate_in, plate_out, set_temp, read_temps, run_assay and _exec; init, plate_in, "
             "plate_out, set_temp and run_assay send their command through _exec, which calls ExecuteAndWait and "
             "returns its response, and the class has no stop, abort or pause method",
             source="upstream_code", ref="sidecar/bmg_interface.py:15-152"),
        Fact("The upstream sidecar keeps BmgCom on one worker thread: the thread calls pythoncom.CoInitialize, "
             "constructs BmgCom and runs every call it takes from a queue, and on shutdown it closes the connection "
             "and calls pythoncom.CoUninitialize", source="upstream_code", ref="sidecar/bmg_sidecar_server.py:31-87"),
        Fact("The sidecar README lists the endpoints /, /is_busy, /status, /error, /temps, /plate_out, /plate_in, "
             "/set_temp and /run_assay", source="vendor_doc", ref="sidecar/README.md:16-28"),
        Fact("The MADSci REST node labels Temp1, Temp2 and Temp3 as the bottom heating plate, the top heating plate "
             "and the optic slide heating plate", source="upstream_code", ref="src/bmg_rest_node.py:203-209"),
        Fact("The upstream README says the BMG driver can only connect to the device when run with 32-bit Python "
             "on a Windows machine", source="vendor_doc", ref="README.md:15"),
        Fact("The upstream README says the model name must be entered as 'CLARIOstar' when the device is "
             "instantiated, even for a BMG VANTAstar", source="vendor_doc", ref="README.md:50"),
    ]

    safe_state = ("incubator heating off: the native set_temp(0.0) (Temp 0.0, the upstream's documented off value) "
                  "acknowledged by an ExecuteAndWait response of 0; the temperatures are not driven down, and the plate "
                  "tray and any assay started outside this package are not stopped")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("version", type="string",
          description="Result of the COM GetVersion call (the upstream prints it as the BMG LABTECH Remote Control "
                      "version)")
    def version(self):
        return self.native.get_version()

    @read("status", type="string",
          description="GetInfo 'Status' string, stripped; the upstream returns 'unknown' when GetInfo gives no string")
    def status(self):
        return self.native.get_status()

    @read("error", type="string",
          description="GetInfo 'Error' string, stripped; the upstream returns 'unknown' when GetInfo gives no string")
    def error(self):
        return self.native.get_error()

    @read("temperature_1", unit="Cel",
          description="Sensor Temp1 (GetInfo value / 10; the MADSci node labels it the bottom heating plate); left out "
                      "of the state when the reader gives no value")
    def temperature_1(self):
        return self.native.read_temps()["Temp1"]

    @read("temperature_2", unit="Cel",
          description="Sensor Temp2 (GetInfo value / 10; the MADSci node labels it the top heating plate); left out of "
                      "the state when the reader gives no value")
    def temperature_2(self):
        return self.native.read_temps()["Temp2"]

    @read("temperature_3", unit="Cel",
          description="Sensor Temp3 (GetInfo value / 10; the MADSci node labels it the optic slide heating plate); left "
                      "out of the state when the reader gives no value")
    def temperature_3(self):
        return self.native.read_temps()["Temp3"]

    # -- the one write ------------------------------------------------------------------------------------------
    @write("setpoint", unit="Cel", risk="R2",
           description="Incubator temperature set point in Celsius (native Temp command).  The state shows the last "
                       "value written here, also after the heater-off action or an e-stop has sent Temp 0.0; the "
                       "upstream has no read of the device's set point",
           limit=Limit.operator_required(
               "the valid range depends on the installed model and the upstream constructor flag "
               "extended_temperature_range_model: 25.0 to 45.0 Cel standard, 10.0 to 60.0 Cel extended, plus "
               "0.0 off and 0.1 monitor only (sidecar/bmg_interface.py:72-84); the site states the range of its "
               "unit"))
    def set_setpoint(self, value):
        self.native.set_temp(value)

    # -- the safe-state action ----------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.bmg_heater_off.v1", safe_state=True, risk="R2",
            description="Switch the incubator off (native set_temp(0.0), Temp 0.0); takes no input and runs during an "
                        "e-stop",
            output={"heating_off": Field(
                "boolean", description="True once the reader acknowledged Temp 0.0 (ExecuteAndWait response 0)")})
    def heater_off(self):
        self.native.set_temp(0.0)
        return {"heating_off": True}

    # -- safety ----------------------------------------------------------------------------------------------
    @estop(native="set_temp")
    def stop(self):
        """The native heating-off command; the runtime latches before it calls this method."""
        self.native.set_temp(0.0)

    def teardown(self):
        self.native.close_connection()
