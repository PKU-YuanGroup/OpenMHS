"""OpenMHS driver for gh.bamresearch/mapz_at_bam: an IKA RCT digital 5 hotplate from the Minerva tree.

A direct Driver (decorated methods) over the upstream device class
``Minerva.Hardware.Hotplates.IkaHotplate:RCTDigital5``.  The upstream class owns the serial transport and builds every
NAMUR command from the constants at IkaHotplate.py:56-70, so this driver calls the upstream methods rather than
re-sending text.  It is a single-device package: the card lists five entry symbols of the clone, and this package binds
the RCTDigital5 hotplate.

* reads: the device name, the external thermocouple temperature, the hotplate temperature, the current stirring speed,
  the viscosity trend, the temperature setpoint, the safety temperature and the stirring speed setpoint;
* writes: the temperature setpoint and the stirring speed setpoint.  No text file of the clone states an absolute
  range for either, so both are ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  site supplies the range of its plate (``site-limits.example.json`` shows the overlay);
* actions: start heating to a target temperature (``cap.thermal.setpoint.v1``) and start stirring at a speed
  (``x-cap.bamresearch.start_stirring.v1``);
* safety: the upstream ``emergency_stop`` is the e-stop and ``x-cap.bamresearch.stop_hotplate.v1`` is the safe-state
  action; it calls the upstream ``stop_heating`` and ``stop_stirring``, which switch both actuators off and reset both
  setpoints to zero (IkaHotplate.py:438-457, 480-499).

Every Fact cites a line of the clone at the pinned commit (ad4cd71528aa7d9fa1b74379dcf02266318081cb).  This package
is model-authored and unreviewed: it is checked on the fake backend only.  The hardware path was not run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_NO_TEMPERATURE_RANGE = (
    "no text file of the clone states an absolute temperature setpoint range; the safety temperature and the sample "
    "set the usable range, so the site supplies it")
_NO_SPEED_RANGE = (
    "no text file of the clone states a stirring speed range; the vessel, the fill level and the stir bar set the "
    "usable range, so the site supplies it")


class IkaRctDigital5(Driver):
    device_id = "ika-rct-digital-5"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "Minerva.Hardware.Hotplates.IkaHotplate:RCTDigital5"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRCTDigital5"}
    vendor, model = "IKA", "RCT digital 5"
    display_name = "IKA RCT digital 5 hotplate and magnetic stirrer (Minerva RCTDigital5)"
    tags = ["hotplate", "magnetic stirrer", "temperature-control", "heating", "serial"]
    facts = [
        Fact("The class controls an IKA RCT digital 5 hotplate over a serial COM port", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:45-52"),
        Fact("The module names the NAMUR commands: IN_NAME for the device name, IN_PV_1 and IN_PV_2 for the external "
             "and hotplate temperatures, IN_PV_4 for the stirring speed, IN_PV_5 for the viscosity trend, and IN_SP_1, "
             "IN_SP_3 and IN_SP_4 for the setpoints", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:56-64"),
        Fact("The external thermocouple temperature is reported in degrees Celsius", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:238"),
        Fact("The hotplate temperature is reported in degrees Celsius", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:259"),
        Fact("The stirring speed is reported in rpm", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:280"),
        Fact("The temperature setpoint is reported in degrees Celsius", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:322"),
        Fact("The safety temperature is reported in degrees Celsius", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:341"),
        Fact("The stirring speed setpoint is reported in rpm", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:360"),
        Fact("The comment on READ_SAFETY_TEMPERATURE_VALUE says the target/set temperature may be 50 degrees beneath "
             "the safety temperature", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:63"),
        Fact("start_heating sets the temperature setpoint first when a value is given, then sends the start-heating "
             "command", source="upstream_code", ref="Minerva/Hardware/Hotplates/IkaHotplate.py:432-434"),
        Fact("stop_heating switches the heating off and, with its default reset_setpoint=True, sets the temperature "
             "setpoint to 0 degrees Celsius", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:445"),
        Fact("stop_stirring switches the stirring off and, with its default reset_setpoint=True, sets the stirring "
             "setpoint to 0 rpm", source="upstream_code", ref="Minerva/Hardware/Hotplates/IkaHotplate.py:487"),
        Fact("emergency_stop sets EMERGENCY_STOP_REQUEST and calls stop_heating and stop_stirring", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:760-763"),
        Fact("Commands and responses are terminated with CR LF", source="upstream_code",
             ref="Minerva/Hardware/Hotplates/IkaHotplate.py:85"),
        Fact("The constructor prefixes a port with COM when the argument does not already start with COM",
             source="upstream_code", ref="Minerva/Hardware/Hotplates/IkaHotplate.py:109-110"),
    ]
    safe_state = ("heating and stirring off, with both setpoints reset to zero by the native stop methods; the serial "
                  "line remains open until teardown")

    # -- reads --------------------------------------------------------------------------------------------------------
    @read("device_name", type="string", description="Name the plate reports for the device-name query")
    def device_name(self):
        return self.native.read_device_name()

    @read("external_temperature", unit="Cel", description="Temperature of the external thermocouple probe")
    def external_temperature(self):
        return self.native.read_current_external_sensor_value()

    @read("hotplate_temperature", unit="Cel", description="Temperature the plate reads at its own sensor")
    def hotplate_temperature(self):
        return self.native.read_current_hotplate_sensor_value()

    @read("stirring_speed", unit="/min", description="Current stirring speed")
    def stirring_speed(self):
        return self.native.read_current_stirring_speed_value()

    @read("viscosity_trend", description="Viscosity trend value reported by the plate; the clone states no unit")
    def viscosity_trend(self):
        return self.native.read_current_viscosity_trend_value()

    @read("temperature_setpoint", unit="Cel", description="Temperature setpoint the plate holds")
    def temperature_setpoint(self):
        return self.native.read_temperature_setpoint()

    @read("safety_temperature", unit="Cel", description="Safety temperature the plate reports")
    def safety_temperature(self):
        return self.native.read_safety_temperature_value()

    @read("stirring_speed_setpoint", unit="/min", description="Stirring speed setpoint the plate holds")
    def stirring_speed_setpoint(self):
        return self.native.read_stirring_speed_setpoint()

    # -- writes -------------------------------------------------------------------------------------------------------
    @write("temperature_setpoint", unit="Cel", risk="R2",
           description="Temperature setpoint, written with the upstream OUT_SP_1 command",
           limit=Limit.operator_required(_NO_TEMPERATURE_RANGE))
    def set_temperature_setpoint(self, value):
        self.native.set_temperature_setpoint(value)
        return self.native.read_temperature_setpoint()

    @write("stirring_speed_setpoint", unit="/min", risk="R2",
           description="Stirring speed setpoint, written with the upstream OUT_SP_4 command",
           limit=Limit.operator_required(_NO_SPEED_RANGE))
    def set_stirring_speed_setpoint(self, value):
        self.native.set_stirring_speed_setpoint(value)
        return self.native.read_stirring_speed_setpoint()

    # -- actions ------------------------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1",
            description="Set the temperature setpoint and start heating the plate",
            input={"target_temperature": Field(
                unit="Cel", description="Target temperature the plate heats to",
                limit=Limit.operator_required(_NO_TEMPERATURE_RANGE))})
    def heat_to(self, target_temperature):
        self.native.start_heating(target_temperature)
        return {"setpoint": self.native.read_temperature_setpoint()}

    @action(name="x-cap.bamresearch.start_stirring.v1", risk="R2",
            description="Start stirring at a speed; the speed is the setpoint used by the start command",
            input={"stirring_speed": Field(
                "number", unit="/min", description="Stirring speed to start at",
                limit=Limit.operator_required(_NO_SPEED_RANGE))},
            output={"stirring_speed_setpoint": Field(
                "number", unit="/min", description="Stirring speed setpoint the plate holds after the start")})
    def start_stirring(self, stirring_speed):
        self.native.start_stirring(stirring_speed)
        return {"stirring_speed_setpoint": self.native.read_stirring_speed_setpoint()}

    @action(name="x-cap.bamresearch.stop_hotplate.v1", safe_state=True,
            description="Stop heating and stirring and reset both setpoints to zero (the safe state); takes no input",
            output={
                "temperature_setpoint": Field(
                    "number", unit="Cel", description="Temperature setpoint after the stop (zero)"),
                "stirring_speed_setpoint": Field(
                    "number", unit="/min", description="Stirring speed setpoint after the stop (zero)"),
            })
    def stop_hotplate(self):
        self.native.stop_heating()
        self.native.stop_stirring()
        return {
            "temperature_setpoint": self.native.read_temperature_setpoint(),
            "stirring_speed_setpoint": self.native.read_stirring_speed_setpoint(),
        }

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native ``emergency_stop``: the runtime latches first, then the plate stops both actuators."""
        if not self.native.emergency_stop():
            raise DriverFailed("MHS.DEVICE.FAULTED", "emergency_stop returned False")

    def teardown(self):
        self.native.disconnect()
