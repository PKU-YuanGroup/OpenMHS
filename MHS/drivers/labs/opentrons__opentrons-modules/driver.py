"""OpenMHS driver for gh.opentrons/opentrons-modules: the Opentrons Temp Deck Gen 3 over USB serial.

A direct Driver over the upstream host-side class ``test_utils:Tempdeck`` (the class the
temperature-module test scripts of the clone use, at its pinned commit).  The upstream class opens the
module with pyserial at 115200 baud and speaks newline-terminated M-code lines
(``stm32-modules/tempdeck-gen3/scripts/test_utils.py:194-200, 212-225``); this driver keeps that wire
syntax and translates the reads and commands the module documents:

* reads: the two plate thermistors and the heatsink thermistor (``M105.D``) and the peltier current,
  fan speed, peltier PWM and fan PWM (``M103.D``);
* one writable parameter: the manual fan PWM (``M106 S``), bounded by the parser's 0 to 1 range
  (``gcodes.hpp:417-418``); the state reads back the fan PWM that ``M103.D`` reports;
* ``cap.thermal.setpoint.v1``: set the temperature target (``M104 S``).  No text file of the clone
  states the operating range of the module, so the input is ``Limit.operator_required`` and every call
  is refused until the site overlay supplies the range of its unit;
* ``x-cap.opentrons.deactivate.v1``: ``M18`` turns off the thermal system, the safe state and the
  native call of the e-stop.  The module documents no independent hardware e-stop, so
  ``estop_physical_ref`` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware
  driver.

Every Fact and Limit cites a line of the clone at the pinned commit
(bb98120ac93ccff0ae9224f95309604dd8b7d0aa).  This package is model-authored and unreviewed: it is
checked on the fake backend only, and the loader refuses the R2 hardware backend until a human sets
``reviewed_by`` in driver.lock.json.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

SCRIPTS = "stm32-modules/tempdeck-gen3/scripts/test_utils.py"
GCODES = "stm32-modules/include/tempdeck-gen3/tempdeck-gen3/gcodes.hpp"
THERMAL_TASK = "stm32-modules/include/tempdeck-gen3/tempdeck-gen3/thermal_task.hpp"
FIRMWARE_README = "stm32-modules/tempdeck-gen3/firmware/README.md"

_NO_TEMPERATURE_RANGE = (
    "no text file of the clone states the operating temperature range of the module: the M104 parser "
    "accepts any float (gcodes.hpp:317-343) and the Opentrons range is not written in this clone; the "
    "site supplies the range its labware and samples tolerate"
)


class Tempdeck(Driver):
    device_id = "tempdeck-gen3"
    device_kind = "lab.thermal_block"
    mode = "hardware"
    risk = "R2"
    native = "test_utils:Tempdeck"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTempdeck"}
    vendor, model = "Opentrons", "Temperature Deck Gen 3"
    display_name = "Opentrons Temp Deck Gen 3"
    tags = ["opentrons", "temperature module", "tempdeck", "thermal", "peltier", "serial"]
    facts = [
        Fact("The host-side Tempdeck class opens the module over pyserial at 115200 baud",
             source="upstream_code", ref=f"{SCRIPTS}:194-200"),
        Fact("get_temperatures sends M105.D and returns plate1, plate2 and the heatsink temperature",
             source="upstream_code", ref=f"{SCRIPTS}:227-239"),
        Fact("M105.D replies with PT1, PT2, HST, PA1, PA2 and HSA values and OK", source="upstream_code",
             ref=f"{GCODES}:244-253"),
        Fact("deactivate sends M18 and expects the reply M18 OK", source="upstream_code",
             ref=f"{SCRIPTS}:241-242"),
        Fact("M18 turns off the thermal system", source="upstream_code", ref=f"{GCODES}:206-215"),
        Fact("M18 clears the fan manual mode and sets fan power 0, then clears the peltier target and "
             "disables the peltier", source="upstream_code", ref=f"{THERMAL_TASK}:233-246"),
        Fact("set_temperature sends 'M104 S<temp>' and expects the reply M104 OK", source="upstream_code",
             ref=f"{SCRIPTS}:244-246"),
        Fact("M104 sets a temperature target for the peltiers; its one parameter is the target temperature",
             source="upstream_code", ref=f"{GCODES}:310-320"),
        Fact("set_fan_power sends 'M106 S<power>' and expects the reply M106 OK", source="upstream_code",
             ref=f"{SCRIPTS}:256-261"),
        Fact("M106 sets the fan PWM between 0 and 1; the parser refuses a value outside that range",
             source="upstream_code", ref=f"{GCODES}:401-418"),
        Fact("M103.D returns the peltier current in mA, the fan RPM, the peltier PWM and the fan PWM",
             source="upstream_code", ref=f"{SCRIPTS}:307-324"),
        Fact("M103.D replies with I, R, P and F values and OK", source="upstream_code",
             ref=f"{GCODES}:270-300"),
        Fact("The thermistor conversion yields a temperature in Celsius", source="upstream_code",
             ref=f"{FIRMWARE_README}:11"),
    ]
    safe_state = "peltier target cleared, peltier output disabled, fan power 0 (M18)"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("plate_temperature_1", unit="Cel", description="Plate thermistor 1 temperature (PT1 of M105.D)")
    def plate_temperature_1(self):
        return self.native.get_temperatures()[0]

    @read("plate_temperature_2", unit="Cel", description="Plate thermistor 2 temperature (PT2 of M105.D)")
    def plate_temperature_2(self):
        return self.native.get_temperatures()[1]

    @read("heatsink_temperature", unit="Cel", description="Heatsink thermistor temperature (HST of M105.D)")
    def heatsink_temperature(self):
        return self.native.get_temperatures()[2]

    @read("peltier_current", unit="mA", description="Peltier current in mA (I of M103.D)")
    def peltier_current(self):
        return self.native.get_thermal_power()[0]

    @read("fan_speed", unit="/min", description="Fan speed in RPM (R of M103.D)")
    def fan_speed(self):
        return self.native.get_thermal_power()[1]

    @read("peltier_power", unit="1",
          description="Peltier PWM reported by M103.D, where 1 is full heat and -1 full cool")
    def peltier_power(self):
        return self.native.get_thermal_power()[2]

    @read("fan_power", unit="1", description="Fan PWM reported by M103.D, from 0 to 1")
    def fan_power(self):
        return self.native.get_thermal_power()[3]

    # -- one writable parameter -----------------------------------------------------------------------------------
    @write("fan_power", unit="1", description="Manual fan PWM (M106 S), from 0 to 1",
           limit=Limit(min=0, max=1, source="upstream_code", ref=f"{GCODES}:417-418",
                       reason="SetFanManual declares min_power 0.0 and max_power 1.0 and refuses a value outside them"))
    def set_fan_power(self, value):
        self.native.set_fan_power(value)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1",
            description="Set the temperature target of the peltiers (M104 S); the firmware regulates to it",
            input={"target_temperature": Field(
                unit="Cel", description="Target plate temperature; the site supplies its allowed range",
                limit=Limit.operator_required(_NO_TEMPERATURE_RANGE))})
    def set_target_temperature(self, target_temperature):
        self.native.set_temperature(target_temperature)
        return {"setpoint": target_temperature}

    @action(name="x-cap.opentrons.deactivate.v1", safe_state=True,
            description="Deactivate the thermal system (M18): clear the target, disable the peltier and set fan power 0",
            output={"deactivated": Field("boolean", description="True once the module has acknowledged M18")})
    def deactivate(self):
        self.native.deactivate()
        return {"deactivated": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: M18 deactivates the thermal system."""
        self.native.deactivate()
