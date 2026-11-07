"""OpenMHS driver for gh.ap/python-oceanoptics: the TEC controller of a QE65000/QE65Pro spectrometer.

A direct Driver over the upstream class ``oceanoptics.base:OceanOpticsTEC`` (base.py:312).  The upstream talks to the
spectrometer over USB with framed binary commands (a command byte plus little-endian fields, base.py:317-395), so
this is not a text-command SerialDriver/ScpiDriver and not a plain PythonObjectDriver: the hardware factory in
native.py opens the pyusb transport, and this class exposes only the TEC methods.

* reads: the TEC temperature, the PCB and heatsink temperatures, the TEC enable state, the fan enable state and the
  setpoint.  The setpoint and the enable states come from ``_tec_controller_get_status`` (base.py:430-439), the only
  status query of the class;
* one write: the TEC setpoint, through ``set_TEC_temperature`` (base.py:383-395);
* the same setpoint as the catalogue class ``cap.thermal.setpoint.v1``;
* the native safe state: the TEC controller is switched off (0x71, 0x00) and the fan is left on (0x70, 0x01), as
  the class always switches the fan on because switching it off might be unsafe (base.py:317-323).

No text of the clone states a TEC setpoint range.  ``initialize_TEC`` chooses -17 as a standard value and calls it
"should work for most cases" (base.py:398-404); that is a method default, not a device bound.  The setpoint is
therefore ``Limit.operator_required``: every setpoint call is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site
supplies the range of its unit (site-limits.example.json shows the overlay).

Every Fact cites a line of the clone at the pinned commit 3df0c263e47c374dcd569681780cf5fc5faa2029.  This package
is model-authored and unreviewed: the hardware backend is refused by the loader until a human signs reviewed_by.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_SETPOINT_LIMIT = Limit.operator_required(
    "no text of the clone states the TEC setpoint range: initialize_TEC() chooses -17 as a standard value that "
    "should work for most cases (oceanoptics/base.py:398-404), which is a method default, not a device bound; the "
    "site supplies the range of its unit")


class OceanOpticsTEC(Driver):
    device_id = "oceanoptics-tec"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "oceanoptics.base:OceanOpticsTEC"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOceanOpticsTEC"}
    vendor, model = "Ocean Optics", "QE65000/QE65Pro TEC controller"
    display_name = "Ocean Optics QE65000/QE65Pro TEC"
    tags = ["tec", "temperature-control", "spectrometer", "thermoelectric-cooler"]
    facts = [
        Fact("OceanOpticsTEC is the class for the TEC found in QE65000 and QE65Pro spectrometers",
             source="upstream_code", ref="oceanoptics/base.py:312-315"),
        Fact("get_temperatures() sends command 0x6C and returns the PCB and heatsink temperatures, each decoded as a "
             "signed 16-bit value scaled by 0.003906", source="upstream_code",
             ref="oceanoptics/base.py:357-370"),
        Fact("The TEC controller read is command 0x72", source="upstream_code",
             ref="oceanoptics/base.py:336-345"),
        Fact("get_TEC_temperature() decodes the TEC temperature as a signed 16-bit integer divided by 10",
             source="upstream_code", ref="oceanoptics/base.py:373-380"),
        Fact("The setpoint command 0x73 carries the temperature times 10 as a signed 16-bit integer",
             source="upstream_code", ref="oceanoptics/base.py:348-355"),
        Fact("set_TEC_temperature() reads the temperature, disables the TEC controller, writes the setpoint, enables "
             "the fan, re-enables the TEC controller and waits 2 s", source="upstream_code",
             ref="oceanoptics/base.py:383-395"),
        Fact("_set_tec_controller_state() switches the TEC controller off with state 0x00 and on with state 0x01 "
             "(command 0x71)", source="upstream_code", ref="oceanoptics/base.py:327-333"),
        Fact("_set_fan_state() sends command 0x70 with state 0x01, and its docstring says the fan is always switched "
             "on because switching the fan off might be unsafe", source="upstream_code",
             ref="oceanoptics/base.py:317-323"),
        Fact("_tec_controller_get_status() queries information address 17 and decodes the TEC enable state, the fan "
             "enable state and the setpoint as a signed 16-bit integer divided by 10", source="upstream_code",
             ref="oceanoptics/base.py:430-439"),
        Fact("initialize_TEC() describes a setpoint of -17 as the standard value that results in a TEC temperature "
             "of -15 degrees Celsius; it is a chosen standard value, not a stated device range",
             source="upstream_code", ref="oceanoptics/base.py:398-404"),
    ]
    safe_state = ("TEC controller off (command 0x71 state 0x00); the cooling fan is left on (command 0x70 state "
                  "0x01) because the class always switches it on")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("tec_temperature", unit="Cel", description="Measured temperature of the thermoelectric cooler")
    def tec_temperature(self):
        return self.native.get_TEC_temperature()

    @read("pcb_temperature", unit="Cel", description="PCB temperature reported by command 0x6C")
    def pcb_temperature(self):
        return self.native.get_temperatures()[0]

    @read("heatsink_temperature", unit="Cel", description="Heatsink temperature reported by command 0x6C")
    def heatsink_temperature(self):
        return self.native.get_temperatures()[1]

    @read("setpoint", unit="Cel", description="TEC temperature setpoint stored by the controller")
    def setpoint(self):
        return self.native._tec_controller_get_status()[2]

    @read("tec_enabled", type="boolean", description="True while the TEC controller is enabled")
    def tec_enabled(self):
        return bool(self.native._tec_controller_get_status()[0])

    @read("fan_enabled", type="boolean", description="True while the cooling fan is enabled")
    def fan_enabled(self):
        return bool(self.native._tec_controller_get_status()[1])

    # -- the setpoint write -------------------------------------------------------------------------------------
    @write("setpoint", unit="Cel", description="TEC temperature setpoint", limit=_SETPOINT_LIMIT)
    def set_setpoint(self, value):
        self.native.set_TEC_temperature(value)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1", description="Set the TEC temperature setpoint",
            input={"target_temperature": Field(description="Target TEC temperature",
                                               limit=_SETPOINT_LIMIT)})
    def set_temperature(self, target_temperature):
        self.native.set_TEC_temperature(target_temperature)
        status = self.native._tec_controller_get_status()
        return {"setpoint": status[2], "actual_temperature": self.native.get_TEC_temperature()}

    @action(name="x-cap.ap.tec_safe_off.v1", safe_state=True,
            description="Switch the TEC controller off and leave the cooling fan on (the safe state); no input",
            output={"tec_enabled": Field("boolean", description="False once the TEC controller is off"),
                    "fan_enabled": Field("boolean", description="True while the fan is on")})
    def tec_safe_off(self):
        self.native._set_fan_state(0x01)
        self.native._set_tec_controller_state(0x00)
        status = self.native._tec_controller_get_status()
        return {"tec_enabled": bool(status[0]), "fan_enabled": bool(status[1])}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop(native="_set_tec_controller_state")
    def stop(self):
        """The native stop: latch first, then switch the TEC controller off (0x71, 0x00) and leave the fan on."""
        self.native._set_fan_state(0x01)
        self.native._set_tec_controller_state(0x00)
