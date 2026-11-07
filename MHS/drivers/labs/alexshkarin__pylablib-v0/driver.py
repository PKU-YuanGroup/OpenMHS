"""OpenMHS driver for gh.alexshkarin/pylablib-v0: the Agilent AWG33220A arbitrary waveform generator.

This is a direct Driver over ``pylablib.aux_libs.devices.AgilentElectronics:AWG33220A``.  The card proposes a
ScpiDriver (``decision: family-config``), but the upstream class applies transforms that a command table cannot
express: the amplitude setter sends twice the requested value in Vpp and the getter halves the Vpp reply
(AgilentElectronics.py:100-107), the frequency getter parses a value and a unit (lines 145-148), and the getter for
the phase first selects degrees (lines 153-156).  The driver therefore calls the upstream methods directly and the
wire syntax stays exactly the upstream one.  This is the "DEVIATION FROM THE CARD" recorded in RESULT.json.

* reads: amplitude, frequency, offset, phase, function, duty cycle, burst enable and mode, and the output enable;
* writes: the same parameters; every numeric write carries ``Limit.operator_required`` because no text in the clone
  states a device range;
* actions: ``x-cap.alexshkarin.output_off.v1`` disables the output (the safe state);
* the e-stop calls ``set_output(False)``, the lowest-risk state of the one output this driver actuates.

Every Fact cites a line of the clone at the pinned commit (1c3c59d4bcbea4a16eee916033972ee13a7d1af6).  The package is
model-authored and unreviewed; its hardware backend has never been run.  It is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

AWG = "pylablib/aux_libs/devices/AgilentElectronics.py"

#: The function names the class maps the SCPI values to (AgilentElectronics.py:29).
FUNCTIONS = ["sine", "square", "ramp", "pulse", "noise", "prbs", "DC", "user", "arb"]


class Awg33220a(Driver):
    device_id = "awg33220a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pylablib.aux_libs.devices.AgilentElectronics:AWG33220A"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAwg33220A"}
    vendor, model = "Agilent", "33220A arbitrary waveform generator"
    display_name = "Agilent 33220A arbitrary waveform generator"
    tags = ["awg", "waveform generator", "signal generator", "agilent", "33220a", "scpi"]
    facts = [
        Fact("AWG33220A covers the Agilent 33220A and partially compatible generators such as the Agilent 33500 "
             "and the Rigol D1000", source="upstream_code", ref=f"{AWG}:14-18"),
        Fact("set_amplitude writes twice the requested value in Vpp and get_amplitude halves the Vpp reply",
             source="upstream_code", ref=f"{AWG}:100-107"),
        Fact("get_output and set_output use the boolean SCPI command :OUTPUT", source="upstream_code",
             ref=f"{AWG}:42-48"),
        Fact("The frequency is written and read in Hz with :FREQUENCY", source="upstream_code", ref=f"{AWG}:145-152"),
        Fact("get_phase selects degrees with :UNIT:ANGLE DEG before reading :PHASE?", source="upstream_code",
             ref=f"{AWG}:153-156"),
        Fact("The duty cycle is in percent and applies only to the square function", source="upstream_code",
             ref=f"{AWG}:163-176"),
        Fact("The function values are sine, square, ramp, pulse, noise, prbs, DC, user and arb", source="upstream_code",
             ref=f"{AWG}:29"),
        Fact("The burst mode is trig or gate", source="upstream_code", ref=f"{AWG}:34"),
        Fact("set_output(False) turns the generator output off", source="upstream_code", ref=f"{AWG}:45-48"),
    ]
    safe_state = "generator output disabled"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("amplitude", unit="V", description="Output amplitude (zero to peak; half the Vpp value the instrument sets)")
    def amplitude(self):
        return self.native.get_amplitude()

    @read("frequency", unit="Hz", description="Output frequency")
    def frequency(self):
        return self.native.get_frequency()

    @read("offset", unit="V", description="DC offset of the output")
    def offset(self):
        return self.native.get_offset()

    @read("phase", unit="deg", description="Output phase in degrees")
    def phase(self):
        return self.native.get_phase()

    @read("function", type="string", description="Output waveform function")
    def function(self):
        return self.native.get_function()

    @read("duty_cycle", unit="%", description="Duty cycle of the square function, in percent")
    def duty_cycle(self):
        return self.native.get_duty_cycle()

    @read("burst_enabled", type="boolean", description="True while burst mode is enabled")
    def burst_enabled(self):
        return self.native.is_burst_enabled()

    @read("burst_mode", type="string", description="Burst mode: trig or gate")
    def burst_mode(self):
        return self.native.get_burst_mode()

    @read("output", type="boolean", description="True while the generator output is enabled")
    def output(self):
        return self.native.get_output()

    # -- writes -----------------------------------------------------------------------------------------------
    @write("amplitude", unit="V", description="Output amplitude (zero to peak)",
           limit=Limit.operator_required(
               "the clone states no amplitude range for the 33220A or its compatible models; the site supplies "
               "the range of its generator output"))
    def set_amplitude(self, value):
        return self.native.set_amplitude(value)

    @write("frequency", unit="Hz", description="Output frequency",
           limit=Limit.operator_required(
               "the clone states no frequency range for the 33220A or its compatible models; the site supplies "
               "the range of its generator"))
    def set_frequency(self, value):
        return self.native.set_frequency(value)

    @write("offset", unit="V", description="DC offset of the output",
           limit=Limit.operator_required(
               "the clone states no offset range for the 33220A or its compatible models; the site supplies "
               "the range of its generator output"))
    def set_offset(self, value):
        return self.native.set_offset(value)

    @write("phase", unit="deg", description="Output phase in degrees",
           limit=Limit.operator_required(
               "the clone states no phase range for the 33220A or its compatible models; the site supplies "
               "the range of its generator"))
    def set_phase(self, value):
        return self.native.set_phase(value)

    @write("function", type="string", description="Output waveform function",
           limit=Limit(allowed=FUNCTIONS, source="upstream_code", ref=f"{AWG}:29",
                       reason="the function map of the class lists the accepted names"))
    def set_function(self, value):
        return self.native.set_function(value)

    @write("duty_cycle", unit="%", description="Duty cycle of the square function, in percent",
           limit=Limit.operator_required(
               "the clone states no duty-cycle range for the 33220A; the site supplies the range its square "
               "waveform may use"))
    def set_duty_cycle(self, value):
        return self.native.set_duty_cycle(value)

    @write("burst_enabled", type="boolean", description="Enable or disable burst mode")
    def set_burst_enabled(self, value):
        return self.native.enable_burst(value)

    @write("burst_mode", type="string", description="Burst mode: trig or gate",
           limit=Limit(allowed=["trig", "gate"], source="upstream_code", ref=f"{AWG}:34",
                       reason="the burst mode map of the class lists the accepted names"))
    def set_burst_mode(self, value):
        return self.native.set_burst_mode(value)

    @write("output", type="boolean", description="Enable or disable the generator output")
    def set_output(self, value):
        return self.native.set_output(value)

    # -- actions and safety ------------------------------------------------------------------------------------
    @action(name="x-cap.alexshkarin.output_off.v1", safe_state=True,
            description="Disable the generator output (the safe state); it takes no input",
            output={"output": Field("boolean", description="False once the output is disabled")})
    def output_off(self):
        self.native.set_output(False)
        return {"output": self.native.get_output()}

    @estop
    def stop(self):
        """The native stop: disable the output; the runtime latches before this runs."""
        self.native.set_output(False)
