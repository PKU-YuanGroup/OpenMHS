"""OpenMHS driver for gh.itdaniher/olin-smus: the Olin ModCon USB source-measure unit.

A direct Driver (decorated methods) over the upstream class modconsmu.modconsmu:smu, the Python pyusb driver for the
Olin SMU (README.mkd:7).  The upstream object owns one USB device and exposes two calls:

* set(volts=None, amps=None) stores a voltage or current target, switches the driving mode and calls update()
  (modconsmu/modconsmu.py:82-101);
* update(mod=1) writes the DAC target with the vendor UPDATE request, reads 12 bytes and returns the measured
  voltage, measured current and the third value the code calls modVolt (modconsmu/modconsmu.py:60-80;
  modconsmu/pic/ecs.c:526-563).

The upstream API measures only as part of an update, so every read of a measured value calls update(0), which repeats
the current target; the measured values and the two stored targets are exposed as read state.  No text of the clone
states a safe output envelope.  The only voltage numbers are the converter scale constants maxV and minV in the
constructor (modconsmu/modconsmu.py:30-32), and no current bound is stated at all; both numeric writes therefore use
Limit.operator_required until the site supplies the envelope of the installed unit and its load
(site-limits.example.json shows the overlay).

The safe state is the upstream's own exit action set(amps=0) (modconsmu/modconsmu.py:57-58): it switches to current
mode with a zero target.  The @estop and the no-input safe-state action x-cap.itdaniher.source_off.v1 both call it.
The clone documents no independent hardware e-stop, so the package does not claim one.  This package is model-authored
and unreviewed and it is R2: the loader refuses its hardware backend until a human signs driver.lock.json
reviewed_by (the loader does this at R2 and R3 only).

Not covered: the GET_NAME and SET_NAME vendor requests (modconsmu/pic/ecs.c:15-16) have no upstream method, the
calibration words are read by the upstream constructor and never changed, and no hardware backend was run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class OlinSMU(Driver):
    device_id = "olin-smu"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R2"
    native = "modconsmu.modconsmu:smu"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOlinSmus"}
    vendor, model = "Olin College", "ModCon source-measure unit"
    display_name = "Olin ModCon USB source-measure unit"
    tags = ["smu", "source-measure-unit", "usb", "pyusb", "electrical"]
    facts = [
        Fact("The user-facing driver object is the class smu", source="upstream_code",
             ref="modconsmu/modconsmu.py:7"),
        Fact("The README calls the modconsmu folder an importable pure-Python driver that uses pyusb",
             source="vendor_doc", ref="README.mkd:7"),
        Fact("The constructor finds the instrument by USB vendor id 0x6666 and product id 0x0005",
             source="upstream_code", ref="modconsmu/modconsmu.py:38"),
        Fact("The constructor reads the DAC, VADC, IADC and RES calibration words with four vendor control "
             "transfers and converts them into the gain and shunt values", source="upstream_code",
             ref="modconsmu/modconsmu.py:42-56"),
        Fact("The constructor registers set(amps=0) with atexit as its safety feature", source="upstream_code",
             ref="modconsmu/modconsmu.py:57-58"),
        Fact("update() writes the DAC target with the UPDATE vendor request, reads 12 bytes and returns the "
             "measured voltage, measured current and modVolt; its docstring says it returns actual V/I",
             source="upstream_code", ref="modconsmu/modconsmu.py:60-80"),
        Fact("update() maps a voltage target to the 12-bit code zeroV - v/scaleFactorV and a current target to "
             "zeroI + i*10000", source="upstream_code", ref="modconsmu/modconsmu.py:62-67"),
        Fact("set(volts, amps) stores one target, switches between voltage and current driving and calls update(); "
             "it raises NotImplementedError when both are given", source="upstream_code",
             ref="modconsmu/modconsmu.py:82-101"),
        Fact("The firmware UPDATE handler writes both DAC bytes and returns four ADC result pairs, the timer bytes "
             "and a 12-byte reply", source="upstream_code", ref="modconsmu/pic/ecs.c:526-563"),
        Fact("The firmware defines the vendor requests UPDATE 1, SET_DIGOUT 2, GET_DAC_VALS 3, SET_DAC_VALS 4, "
             "GET_VADC_VALS 5, GET_IADC_VALS 7, GET_RES_VAL 9, GET_NAME 11 and SET_NAME 12",
             source="upstream_code", ref="modconsmu/pic/ecs.c:5-16"),
        Fact("The example charger sets a constant current with set(amps=...), switches to a constant voltage with "
             "set(volts=...), and disables charging with set(amps=0)", source="upstream_code",
             ref="apps/charger.py:41-53"),
        Fact("The constructor's maxV=9.93 and minV=-10.45 are the ends of the voltage conversion scale and are used "
             "only to derive scaleFactorV", source="upstream_code", ref="modconsmu/modconsmu.py:30-32"),
    ]
    safe_state = "source current target zero in current mode (the upstream set(amps=0) safety call)"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("measured_voltage", unit="V", description="Voltage measured by the update() reply")
    def measured_voltage(self):
        return float(self.native.update(0)[0])

    @read("measured_current", unit="A", description="Current measured by the update() reply")
    def measured_current(self):
        return float(self.native.update(0)[1])

    @read("mod_voltage", unit="V",
          description="Third value of the update() reply, computed by the upstream code as (data[6] | data[7] << 8) "
                      "* 4.096 / 1023")
    def mod_voltage(self):
        return float(self.native.update()[2])

    @read("source_voltage", unit="V",
          description="Voltage target stored by set(volts=...); it drives the output while source_mode is voltage")
    def source_voltage(self):
        return float(self.native.v)

    @read("source_current", unit="A",
          description="Current target stored by set(amps=...); it drives the output while source_mode is current")
    def source_current(self):
        return float(self.native.i)

    @read("source_mode", type="string", description="Active driving mode: voltage or current")
    def source_mode(self):
        return self._mode()

    # -- writes ------------------------------------------------------------------------------------------------
    @write("source_voltage", unit="V", description="Output voltage target; the site supplies the safe envelope",
           limit=Limit.operator_required(
               "no text of the clone states a safe output-voltage envelope: maxV=9.93 and minV=-10.45 "
               "(modconsmu/modconsmu.py:30-32) are the ends of the driver's conversion scale, not a rating, and the "
               "site supplies the envelope of the installed unit and its load"))
    def set_source_voltage(self, value):
        self.native.set(volts=value)
        return float(self.native.v)

    @write("source_current", unit="A", description="Output current target; the site supplies the safe envelope",
           limit=Limit.operator_required(
               "no text of the clone states a current bound for the source: the constructor reads a shunt "
               "calibration word but names no current range (modconsmu/modconsmu.py:42-56), and the site supplies "
               "the envelope of the installed unit and its load"))
    def set_source_current(self, value):
        self.native.set(amps=value)
        return float(self.native.i)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.itdaniher.source_off.v1", safe_state=True,
            description="Set the source current target to zero with the upstream set(amps=0) safety call; it takes "
                        "no input and is the declared safe state",
            output={"source_current": Field("number", unit="A",
                                            description="Current target after the call; zero means no current is "
                                                        "sourced")})
    def source_off(self):
        self.native.set(amps=0)
        return {"source_current": float(self.native.i)}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="set")
    def stop(self):
        """The native stop: the runtime latches first, then calls the upstream set(amps=0)."""
        self.native.set(amps=0)

    # -- helpers ------------------------------------------------------------------------------------------------
    def _mode(self):
        driving = self.native.driving
        if driving == "v":
            return "voltage"
        if driving == "i":
            return "current"
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the upstream driver reports the unknown driving mode {driving!r}")
