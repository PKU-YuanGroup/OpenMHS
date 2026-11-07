"""OpenMHS driver for gh.asvela/tektronix-func-gen: Tektronix AFG1000/AFG3000 arbitrary function generators.

A direct Driver over the upstream ``tektronix_func_gen:FuncGen``.  The card proposes a ScpiDriver
(``decision: family-config``), but every channel command is assembled from a channel number and a command word
(``SOURce{channel}:...``, ``OUTPut{channel}:...``, tektronix_func_gen.py:810-813 and 1044-1047), so a fixed command
table cannot reproduce the lines the device receives.  This is the "DEVIATION FROM THE CARD" recorded in
RESULT.json.

The driver uses the upstream object's high-level methods for reads and writes (``get_settings``/``set_settings``
and the channel getters), so the amplitude/offset combination checks of the clone still run before a write.  The
e-stop sends the two output-off commands through the upstream ``write`` method (tektronix_func_gen.py:1044-1047).

* reads: output state, function, amplitude, offset and frequency of both channels, the frequency lock, the error
  queue and the waveform catalogue;
* writes: the same channel settings and the frequency lock; every numeric write carries
  ``Limit.operator_required`` because the clone selects the range from the connected model and the impedance
  setting, and the impedance cannot be read remotely (README.md:197-200);
* the e-stop turns both channel outputs off.

NOT COVERED: the arbitrary-waveform arrays.  ``get_custom_waveform``/``set_custom_waveform`` transfer 2 to 8192
points (or a larger model-specific maximum) of 14-bit data through binary VISA calls (tektronix_func_gen.py:505-541
and 543-636); this package serves the scalar settings and the small waveform catalogue instead.

Every Fact and Limit cites a line of the clone at the pinned commit (30f7406e89bd9f344487b84913f5111e8bb110a7).
This package is model-authored and unreviewed, and its hardware backend was never run.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

UPSTREAM = "tektronix_func_gen.py"

#: The function names the upstream docstring documents (tektronix_func_gen.py:1071-1079); the README uses SIN
#: (README.md:53).  Custom USER waveforms are not covered by this package.
FUNCTIONS = ["SIN", "SINusoid", "SQUare", "PULSe", "RAMP", "PRNoise", "DC"]

#: The output states the upstream setter documents (tektronix_func_gen.py:1033-1036).
OUTPUT_STATES = ["ON", "OFF"]

#: The reasons of the three operator-required numeric bounds.  The model and the impedance select the range in the
#: clone, and the impedance cannot be read remotely, so no single bound of the clone is a bound of the installation.
AMPLITUDE_BOUND = (
    "the clone selects the amplitude range from the connected model and the impedance setting "
    "(tektronix_func_gen.py:214-267), and the impedance cannot be read remotely (README.md:197-200); the site "
    "supplies the amplitude range of its generator output")
FREQUENCY_BOUND = (
    "the clone selects the frequency range from the connected model (tektronix_func_gen.py:214-267), and its limits "
    "are those of a sine, not every function (README.md:29-31); the site supplies the range of its generator and "
    "waveform")
OFFSET_BOUND = (
    "the clone checks the offset against the voltage limits of the connected model and the impedance setting "
    "(tektronix_func_gen.py:1188-1201), and the impedance cannot be read remotely (README.md:197-200); the site "
    "supplies the offset range of its installation")


def _output_text(value):
    """The output state as ON/OFF: the query returns 0 or 1 (tektronix_func_gen.py:939-941)."""
    text = str(value).strip().upper()
    if text in ("1", "ON"):
        return "ON"
    if text in ("0", "OFF"):
        return "OFF"
    raise ValueError(f"unexpected output state {value!r}")


class TektronixFuncGen(Driver):
    device_id = "tektronix-afg"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "tektronix_func_gen:FuncGen"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFuncGen"}
    vendor = "Tektronix"
    model = "AFG1000/AFG3000 series arbitrary function generator"
    display_name = "Tektronix AFG1000/AFG3000 arbitrary function generator"
    tags = ["function generator", "arbitrary waveform generator", "afg1000", "afg3000", "tektronix", "visa"]
    facts = [
        Fact("The module provides basic control of AFG1000 and AFG3000 series Tektronix arbitrary function "
             "generators", source="vendor_doc", ref="README.md:6-9"),
        Fact("FuncGen exposes two channels, ch1 and ch2, as FuncGenChannel objects", source="upstream_code",
             ref=f"{UPSTREAM}:145-153"),
        Fact("The channel command prefix is SOURceN:", source="upstream_code", ref=f"{UPSTREAM}:810-813"),
        Fact("The frequency limits are selected from the connected model: AFG1022 and AFG3022 allow 1e-6 to 25e6 "
             "Hz, AFG1062 allows 1e-6 to 60e6 Hz", source="upstream_code", ref=f"{UPSTREAM}:214-267"),
        Fact("The amplitude limits also depend on the impedance: AFG1022 50 ohm 0.001 to 10 Vpp and highZ 0.002 to "
             "20 Vpp; AFG3022 50 ohm 0.01 to 10 Vpp and highZ 0.02 to 20 Vpp", source="upstream_code",
             ref=f"{UPSTREAM}:221-262"),
        Fact("The output impedance (50 ohm or high Z) cannot be controlled or read remotely", source="vendor_doc",
             ref="README.md:197-200"),
        Fact("The frequency limits are those of a sine; other functions may have a lower limit", source="vendor_doc",
             ref="README.md:29-31"),
        Fact("The output state query returns 0 for OFF and 1 for ON", source="upstream_code",
             ref=f"{UPSTREAM}:939-941"),
        Fact("The channel settings map converts the output state 0 or 1 to OFF or ON", source="upstream_code",
             ref=f"{UPSTREAM}:807-808"),
        Fact("The output is set with OUTPutN:STATe", source="upstream_code", ref=f"{UPSTREAM}:1044-1047"),
        Fact("The function is read with SOURceN:FUNCtion:SHAPe?", source="upstream_code",
             ref=f"{UPSTREAM}:943-945"),
        Fact("The function is set with SOURceN:FUNCtion:SHAPe <shape>", source="upstream_code",
             ref=f"{UPSTREAM}:1088-1089"),
        Fact("The function setter documents SINusoid, SQUare, PULSe, RAMP, PRNoise, built-in shapes and DC",
             source="upstream_code", ref=f"{UPSTREAM}:1071-1079"),
        Fact("The README sets the channel function to SIN", source="vendor_doc", ref="README.md:53"),
        Fact("The amplitude is read with SOURceN:VOLTage:AMPLitude?", source="upstream_code",
             ref=f"{UPSTREAM}:947-949"),
        Fact("The amplitude is set with SOURceN:VOLTage:LEVel <amplitude>Vpp", source="upstream_code",
             ref=f"{UPSTREAM}:1149-1152"),
        Fact("The offset is read with SOURceN:VOLTage:OFFSet?", source="upstream_code",
             ref=f"{UPSTREAM}:951-953"),
        Fact("The offset is set with SOURceN:VOLTage:LEVel:OFFSet <offset>V", source="upstream_code",
             ref=f"{UPSTREAM}:1202-1205"),
        Fact("The frequency is read with SOURceN:FREQuency?", source="upstream_code", ref=f"{UPSTREAM}:955-957"),
        Fact("The frequency is set with SOURceN:FREQuency:FIXed <freq>Hz", source="upstream_code",
             ref=f"{UPSTREAM}:1251-1255"),
        Fact("A channel set_settings turns the channel off, applies function, amplitude, offset and frequency, then "
             "restores the output state", source="upstream_code", ref=f"{UPSTREAM}:1007-1026"),
        Fact("Frequency lock is read with SOURCE1:FREQuency:CONCurrent?", source="upstream_code",
             ref=f"{UPSTREAM}:451-452"),
        Fact("Frequency lock is set with SOURCE{use_channel}:FREQuency:CONCurrent <state>", source="upstream_code",
             ref=f"{UPSTREAM}:482-484"),
        Fact("The waveform catalogue is read with DATA:CATalog?", source="upstream_code",
             ref=f"{UPSTREAM}:501-503"),
        Fact("The error queue is read with SYSTEM:ERROR:NEXT?", source="upstream_code", ref=f"{UPSTREAM}:369-377"),
    ]
    safe_state = "both channel outputs off"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("output_ch1", type="string", description="Ch1 output state")
    def output_ch1(self):
        return _output_text(self.native.ch1.get_output_state())

    @read("output_ch2", type="string", description="Ch2 output state")
    def output_ch2(self):
        return _output_text(self.native.ch2.get_output_state())

    @read("function_ch1", type="string", description="Ch1 function")
    def function_ch1(self):
        return str(self.native.ch1.get_function())

    @read("function_ch2", type="string", description="Ch2 function")
    def function_ch2(self):
        return str(self.native.ch2.get_function())

    @read("amplitude_ch1", unit="V", description="Ch1 amplitude")
    def amplitude_ch1(self):
        return float(self.native.ch1.get_amplitude())

    @read("amplitude_ch2", unit="V", description="Ch2 amplitude")
    def amplitude_ch2(self):
        return float(self.native.ch2.get_amplitude())

    @read("offset_ch1", unit="V", description="Ch1 offset")
    def offset_ch1(self):
        return float(self.native.ch1.get_offset())

    @read("offset_ch2", unit="V", description="Ch2 offset")
    def offset_ch2(self):
        return float(self.native.ch2.get_offset())

    @read("frequency_ch1", unit="Hz", description="Ch1 frequency")
    def frequency_ch1(self):
        return float(self.native.ch1.get_frequency())

    @read("frequency_ch2", unit="Hz", description="Ch2 frequency")
    def frequency_ch2(self):
        return float(self.native.ch2.get_frequency())

    @read("frequency_lock", type="boolean",
          description="True while the two channels share one frequency and phase")
    def frequency_lock(self):
        return bool(self.native.get_frequency_lock())

    @read("error_queue", type="string",
          description="Next error/event queue entry of the instrument, as the instrument reports it")
    def error_queue(self):
        return str(self.native.get_error())

    @read("waveform_catalogue", type="array", items="string",
          description="Names of the user waveform functions that are not empty")
    def waveform_catalogue(self):
        return [str(item) for item in self.native.get_waveform_catalogue()]

    # -- writes ---------------------------------------------------------------------------------------------------
    def _apply(self, channel, key, value, unit):
        """Change one field of one channel through the upstream settings methods.

        ``FuncGen.set_settings`` turns the channel off before applying the settings and restores its output state
        afterwards (tektronix_func_gen.py:1007-1026); using it keeps the upstream model, impedance and
        amplitude/offset checks in front of every write.
        """
        settings = self.native.get_settings()
        settings[channel - 1][key] = (value, unit)
        self.native.set_settings(settings)

    @write("output_ch1", type="string", limit=Limit(allowed=OUTPUT_STATES, source="upstream_code",
                                                    ref=f"{UPSTREAM}:1033-1036",
                                                    reason="ON/OFF as documented"),
           description="Ch1 output state")
    def set_output_ch1(self, value):
        self._apply(1, "output", str(value), "")

    @write("output_ch2", type="string", limit=Limit(allowed=OUTPUT_STATES, source="upstream_code",
                                                    ref=f"{UPSTREAM}:1033-1036",
                                                    reason="ON/OFF as documented"),
           description="Ch2 output state")
    def set_output_ch2(self, value):
        self._apply(2, "output", str(value), "")

    @write("function_ch1", type="string",
           limit=Limit(allowed=FUNCTIONS, source="upstream_code", ref=f"{UPSTREAM}:1071-1079",
                       reason="documented names"),
           description="Ch1 function")
    def set_function_ch1(self, value):
        self._apply(1, "function", str(value), "")

    @write("function_ch2", type="string",
           limit=Limit(allowed=FUNCTIONS, source="upstream_code", ref=f"{UPSTREAM}:1071-1079",
                       reason="documented names"),
           description="Ch2 function")
    def set_function_ch2(self, value):
        self._apply(2, "function", str(value), "")

    @write("amplitude_ch1", unit="V", description="Ch1 amplitude",
           limit=Limit.operator_required(AMPLITUDE_BOUND))
    def set_amplitude_ch1(self, value):
        self._apply(1, "amplitude", float(value), "Vpp")

    @write("amplitude_ch2", unit="V", description="Ch2 amplitude",
           limit=Limit.operator_required(AMPLITUDE_BOUND))
    def set_amplitude_ch2(self, value):
        self._apply(2, "amplitude", float(value), "Vpp")

    @write("offset_ch1", unit="V", description="Ch1 offset",
           limit=Limit.operator_required(OFFSET_BOUND))
    def set_offset_ch1(self, value):
        self._apply(1, "offset", float(value), "V")

    @write("offset_ch2", unit="V", description="Ch2 offset",
           limit=Limit.operator_required(OFFSET_BOUND))
    def set_offset_ch2(self, value):
        self._apply(2, "offset", float(value), "V")

    @write("frequency_ch1", unit="Hz", description="Ch1 frequency",
           limit=Limit.operator_required(FREQUENCY_BOUND))
    def set_frequency_ch1(self, value):
        self._apply(1, "frequency", float(value), "Hz")

    @write("frequency_ch2", unit="Hz", description="Ch2 frequency",
           limit=Limit.operator_required(FREQUENCY_BOUND))
    def set_frequency_ch2(self, value):
        self._apply(2, "frequency", float(value), "Hz")

    @write("frequency_lock", type="boolean",
           description="Lock to channel 1")
    def set_frequency_lock(self, value):
        self.native.set_frequency_lock("ON" if value else "OFF", use_channel=1)

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Turn both outputs off through the upstream transport; the runtime latches before this runs."""
        self.native.write("OUTPut1:STATe OFF")
        self.native.write("OUTPut2:STATe OFF")

    def teardown(self):
        self.native.close()
