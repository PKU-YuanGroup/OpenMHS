"""OpenMHS driver for gh.scaxlibur/wavebench: the RIGOL DG4202 signal source of the WaveBench toolkit.

A direct Driver over the upstream device class ``wavebench.drivers.dg4202:DG4202Source``, which speaks SCPI through
a WaveBench transport.  The card proposes a ``ScpiDriver`` (family ``scpi``, decision ``family-config``); a static
command table cannot express this interface, because the clone builds every command from parts (the channel index is
interpolated into the string: ``f":SOUR{channel}:FREQ?"``, src/wavebench/drivers/dg4202.py:481-527) and every setter
first reads a snapshot back before it writes.  So this package is a direct Driver over the upstream class
(DEVIATION FROM THE CARD, recorded in RESULT.json).

* the served resource is output channel 1 of the generator; the class validates the channel as 1 or 2
  (dg4202.py:52-54), and the e-stop switches both channels off;
* reads: identity, output state, function, frequency, amplitude (in Vpp), the amplitude unit, and the square-wave
  duty cycle;
* writes: output on/off, function, frequency, amplitude and duty cycle; the duty-cycle bound and the function set
  are stated in the clone and cited, while the frequency and amplitude ranges are not stated anywhere in the clone,
  so those two writes are ``Limit.operator_required``;
* the e-stop switches both output channels OFF: the class forces the channel of a failed output transaction OFF
  (dg4202.py:240-243), which is the safe state of this generator.

Every Limit and Fact cites a line of the clone at the pinned commit (44506c4975d8615ace0d2dbababe880b89567709).  This
package is model-authored and unreviewed: it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, estop, read, write

SOURCE = "src/wavebench/drivers/dg4202.py"
#: The channels the class accepts (dg4202.py:52-54); the driver serves channel 1.
CHANNEL = 1
CHANNELS = (1, 2)
#: The canonical functions set_function accepts (dg4202.py:632-638); USER and HARM are excluded by the clone.
BASIC_FUNCTIONS = ["SIN", "SQU", "RAMP", "PULS", "NOIS", "DC"]


class DG4202(Driver):
    device_id = "dg4202"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "wavebench.drivers.dg4202:DG4202Source"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDG4202Source"}
    vendor = "RIGOL Technologies"
    model = "DG4202 (DG4000 series function/arbitrary waveform generator)"
    display_name = "RIGOL DG4202 signal source (WaveBench dg4202 driver)"
    tags = ["signal generator", "function generator", "waveform generator", "dg4202", "dg4000", "scpi", "wavebench"]
    facts = [
        Fact("The DG4000 driver accepts the models DG4062, DG4102, DG4162 and DG4202, and it accepts configuration "
             "writes only on a DG4202", source="upstream_code", ref=f"{SOURCE}:30-31"),
        Fact("The generator has two output channels, 1 and 2",
             source="upstream_code", ref=f"{SOURCE}:52-54"),
        Fact("The identity query *IDN? is parsed into four comma-separated fields (manufacturer, model, serial "
             "number, firmware) and the manufacturer must be RIGOL TECHNOLOGIES",
             source="upstream_code", ref=f"{SOURCE}:80-90"),
        Fact("A status snapshot reads the output state, the function, the frequency, the amplitude, the amplitude "
             "unit, the offset, the phase, the frequency mode, the sweep state, the APPLy response and the "
             "square-wave duty cycle", source="upstream_code", ref=f"{SOURCE}:481-527"),
        Fact("An output is switched with ':OUTP<channel> ON' or ':OUTP<channel> OFF' and read back with ':OUTP"
             "<channel>?'", source="upstream_code", ref=f"{SOURCE}:594-595"),
        Fact("A frequency is written as ':SOUR<channel>:FREQ <value>' after the frequency mode is switched to FIX "
             "when it is not FIX", source="upstream_code", ref=f"{SOURCE}:550-556"),
        Fact("A function is written as ':SOUR<channel>:FUNC <FUNCTION>' with the canonical names SIN, SQU, RAMP, "
             "PULS, NOIS and DC (aliases such as SINE, SQUARE or TRI are accepted and normalized)",
             source="upstream_code", ref=f"{SOURCE}:632-645"),
        Fact("An amplitude is written in Vpp: the driver first writes ':SOUR<channel>:VOLT:UNIT VPP', then ':SOUR"
             "<channel>:VOLT <value>'", source="upstream_code", ref=f"{SOURCE}:675-682"),
        Fact("A square-wave duty cycle is written as ':SOUR<channel>:FUNC:SQU:DCYC <percent>' and read back with "
             "the same command followed by '?'", source="upstream_code", ref=f"{SOURCE}:717-721"),
        Fact("The class refuses a frequency that is not > 0 Hz", source="upstream_code", ref=f"{SOURCE}:538-539"),
        Fact("The class refuses an amplitude that is not > 0 V", source="upstream_code", ref=f"{SOURCE}:669-670"),
        Fact("The class refuses a square-wave duty cycle that is not strictly between 0 and 100 percent",
             source="upstream_code", ref=f"{SOURCE}:709-711"),
        Fact("A failed output transaction is recovered by forcing that channel OFF before the error is raised",
             source="upstream_code", ref=f"{SOURCE}:240-243"),
        Fact("The clone leaves the source amplitude ceiling to the operator: SafetyLimitsConfig.max_source_vpp "
             "defaults to None", source="upstream_code", ref="src/wavebench/config.py:167-168"),
        Fact("Setting a voltage, an amplitude or a frequency never switches an output on by itself",
             source="vendor_doc", ref="README.md:102"),
    ]
    safe_state = "both output channels off (the generator holds no actuation this driver sets)"

    def setup(self):
        """Check the identity: the clone accepts configuration writes only on a DG4202 (dg4202.py:30-31, 160-164)."""
        identity = self.native.idn()
        fields = [item.strip() for item in identity.split(",")]
        if len(fields) != 4 or fields[1].upper() != "DG4202":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"expected a RIGOL DG4202 (four *IDN? fields with model DG4202), got {identity!r}")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Identity string of the generator (the *IDN? reply)")
    def identity(self):
        return self.native.idn()

    @read("output", type="boolean", description="True while the output of channel 1 is switched on")
    def output(self):
        return self.native.get_status(CHANNEL).output == "ON"

    @read("function", type="string",
          description="Waveform function of channel 1: SIN, SQU, RAMP, PULS, NOIS or DC")
    def function(self):
        return self.native.get_status(CHANNEL).function

    @read("frequency", unit="Hz", description="Frequency of channel 1")
    def frequency(self):
        return self.native.get_status(CHANNEL).frequency_hz

    @read("amplitude", unit="V",
          description="Amplitude of channel 1 in volts peak-to-peak; the unit the generator reports is the "
                      "amplitude_unit field (Vpp after this driver writes an amplitude)")
    def amplitude(self):
        return self.native.get_status(CHANNEL).amplitude

    @read("amplitude_unit", type="string",
          description="Unit the generator reports for the amplitude: VPP, VRMS or DBM")
    def amplitude_unit(self):
        return self.native.get_status(CHANNEL).amplitude_unit

    @read("duty_cycle", unit="%", description="Duty cycle of the square wave of channel 1 in percent")
    def duty_cycle(self):
        return self.native.get_status(CHANNEL).square_duty_cycle_percent

    # -- writes -----------------------------------------------------------------------------------------------
    @write("output", type="boolean", description="Switch the output of channel 1 on (true) or off (false)")
    def set_output(self, value):
        status = self.native.set_output(CHANNEL, bool(value))
        return status.output == "ON"

    @write("function", type="string", description="Waveform function of channel 1",
           limit=Limit(allowed=BASIC_FUNCTIONS, source="upstream_code", ref=f"{SOURCE}:635-638",
                       reason="set_function accepts the canonical functions SIN, SQU, RAMP, PULS, NOIS and DC and "
                              "normalizes aliases of them; USER and HARM are excluded"))
    def set_function(self, value):
        status = self.native.set_function(CHANNEL, value)
        return status.function

    @write("frequency", unit="Hz", description="Frequency of channel 1",
           limit=Limit.operator_required(
               "no text file of the clone states the frequency range of the DG4202: the upstream code only refuses "
               "a frequency that is not > 0 (dg4202.py:538-539) and the range follows the model and the bench, so "
               "the site states the range of its generator"))
    def set_frequency(self, value):
        status = self.native.set_frequency(CHANNEL, value)
        return status.frequency_hz

    @write("amplitude", unit="V", description="Amplitude of channel 1, written in volts peak-to-peak",
           limit=Limit.operator_required(
               "no text file of the clone states the amplitude range of the DG4202: the upstream code only refuses "
               "an amplitude that is not > 0 (dg4202.py:669-670) and the clone leaves the ceiling to the operator "
               "(config.py:168), so the site states the range of its bench"))
    def set_amplitude(self, value):
        status = self.native.set_amplitude_vpp(CHANNEL, value)
        return status.amplitude

    @write("duty_cycle", unit="%", description="Duty cycle of the square wave of channel 1 in percent",
           limit=Limit(min=0, max=100, source="upstream_code", ref=f"{SOURCE}:709-711",
                       reason="the class refuses a duty cycle that is not > 0 and < 100 percent (dg4202.py:709-711); "
                              "the accepted range is that open interval, declared here as 0 to 100 percent"))
    def set_duty_cycle(self, value):
        status = self.native.set_square_duty_cycle(CHANNEL, value)
        return status.square_duty_cycle_percent

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="set_output")
    def stop(self):
        """The native stop: both output channels are switched OFF, the safe state of the generator."""
        for channel in CHANNELS:
            self.native.set_output(channel, False)
