"""OpenMHS driver for gh.anoryth/alim_seq: the Rohde & Schwarz HMP4040 SCPI power supply.

A direct Driver (decorated methods) over ``alim_seq.psu:HMP4040``, the upstream class that opens a VISA
resource with pyvisa and builds each SCPI line from the selected channel and the value (``INST OUT<n>``,
``VOLT {voltage:.4f}``, ``CURR {current:.4f}``, ``OUTP:SEL ON|OFF``, ``MEAS:VOLT?``, ``MEAS:CURR?``).
This package binds the upstream object's methods through a decorated direct Driver: a DEVIATION FROM THE CARD,
which names helper ScpiDriver and family scpi. The fake preserves that native method surface.

* reads: the measured output voltage and current of channels 1 to 4 and the ``*IDN?`` identity string;
* writes through cap.device.configure.v1: the voltage and current set points of channels 1 to 4, each
  requiring an operator envelope; the upstream model maxima are 32.0 V and 10.0 A;
* actions: ``x-cap.anoryth.set_output.v1`` switches one channel output and reports the measured voltage;
  ``x-cap.anoryth.all_outputs_off.v1`` requests every channel off without certifying that state;
* the native stop attempts ``all_outputs_off()``, then reports SAFE_STATE_UNREACHED: upstream discards
  *OPC? replies, allows those queries to be disabled, and shares an unprotected channel selector with commands.
  No verified safe-state action or independent physical-stop reference is supplied, so this R2 package is blocked.

The HMP4040 class offers no output-state query.  Its only measured quantities are MEAS:VOLT? and MEAS:CURR?,
so the ordinary off-request action reports measured voltages without claiming verified output-disable state.

Every Limit and Fact cites a line of the clone at the pinned commit
4264b54bdb8087636da640420735c0633fd1dcb9.  This package is model-authored and unreviewed
(driver.lock.json reviewed_by is null); the hardware backend was never opened.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: BasePSU declares four channels and HMP4040 inherits it (alim_seq/psu.py:119); the smaller HMP4030,
#: HMP2030 and HMP2020 variants override n_channels (alim_seq/psu.py:403-420).
CHANNEL_LIMIT = Limit(allowed=[1, 2, 3, 4], source="upstream_code", ref="alim_seq/psu.py:111-119",
                      reason="BasePSU declares four channels numbered from 1; this package serves HMP4040 only")

#: Per-channel SOA of the HMP4040: max_voltage = 32.0 V and max_current = 10.0 A (alim_seq/psu.py:158-159).
#: Those lines do not specify lower bounds or the attached load's envelope. No lower bound is inferred.
VOLTAGE_LIMIT = Limit.operator_required(
    "the site supplies both voltage bounds for its load; the model maximum is 32.0 V (alim_seq/psu.py:158), "
    "but that line states no lower bound; site-limits.example.json is test data only")
CURRENT_LIMIT = Limit.operator_required(
    "the site supplies both current bounds for its load; the model maximum is 10.0 A (alim_seq/psu.py:159), "
    "but that line states no lower bound; site-limits.example.json is test data only")


class HMP4040(Driver):
    device_id = "hmp4040"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "alim_seq.psu:HMP4040"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHMP4040"}
    vendor, model = "Rohde & Schwarz", "HMP4040"
    display_name = "Rohde & Schwarz HMP4040 four-channel power supply"
    tags = ["power-supply", "dc-source", "scpi", "visa", "hmp4040", "alim-seq"]
    facts = [
        Fact("The project sequences the power supply of an electronic board and controls R&S HMP40xx/20xx "
             "supplies over SCPI", source="vendor_doc", ref="README.md:3-6"),
        Fact("The upstream README warns that its software protections do not replace a hardware safety device "
             "nor the operator's judgement", source="vendor_doc", ref="README.md:11-15"),
        Fact("HMP4040 is the SCPI driver for the Rohde & Schwarz HMP4040 through pyvisa", source="upstream_code",
             ref="alim_seq/psu.py:148-154"),
        Fact("BasePSU declares n_channels = 4",
             source="upstream_code", ref="alim_seq/psu.py:119"),
        Fact("HMP4030 and HMP2030 declare three channels, and HMP2020 declares two channels",
             source="upstream_code", ref="alim_seq/psu.py:403-420"),
        Fact("connect() opens the VISA resource with pyvisa and probes *IDN?", source="upstream_code",
             ref="alim_seq/psu.py:199-231"),
        Fact("connect() sends *CLS, switches every channel output off with OUTP:SEL OFF and then enables the "
             "general output with OUTP:GEN ON", source="upstream_code", ref="alim_seq/psu.py:249-255"),
        Fact("A setting selects the channel with INST OUT<n> and then writes VOLT, CURR or OUTP:SEL",
             source="upstream_code", ref="alim_seq/psu.py:344-359"),
        Fact("A measurement selects the channel and queries MEAS:VOLT? or MEAS:CURR?", source="upstream_code",
             ref="alim_seq/psu.py:361-367"),
        Fact("When status reading is enabled, measure_status queries STAT:QUES:INST:ISUM<channel>:COND? and "
             "decodes CC/CV/OTP/OVP/FUSE bits; a disabled or failed status query returns mode=None and no faults",
             source="upstream_code", ref="alim_seq/psu.py:372-397"),
        Fact("all_outputs_off() calls set_output(ch, False) for every channel", source="upstream_code",
             ref="alim_seq/psu.py:143-145"),
        Fact("close() attempts all_outputs_off with a shortened timeout and use_opc=False, suppresses its failure, "
             "then closes the VISA session",
             source="upstream_code", ref="alim_seq/psu.py:289-317"),
        Fact("_write sends a command and optionally queries *OPC? without inspecting its reply",
             source="upstream_code", ref="alim_seq/psu.py:328-330"),
        Fact("_select caches a channel number, and setting voltage, current or output selects a channel before "
             "writing its command; those methods contain no lock",
             source="upstream_code", ref="alim_seq/psu.py:344-359"),
        Fact("The HMP4040 declares max_voltage = 32.0 V, max_current = 10.0 A and max_power = 160.0 W per "
             "channel", source="upstream_code", ref="alim_seq/psu.py:156-160"),
        Fact("The config validator rejects a channel max_voltage above the model's max_voltage and a max_current "
             "above max_current, but does not combine them into a power bound", source="upstream_code",
             ref="alim_seq/config.py:402-410"),
        Fact("The controller's emergency_stop() takes each instrument lock non-blocking and still calls "
             "all_outputs_off() when the lock is busy", source="upstream_code", ref="alim_seq/controller.py:1056-1078"),
        Fact("The upstream factory builds MockPSU when simulate is true and the model class otherwise",
             source="upstream_code", ref="alim_seq/psu.py:562-575"),
    ]
    safe_state = ("unconfirmed: OUTP:SEL OFF is attempted on each channel, but completion replies are unchecked "
                  "and concurrent I/O shares the channel selector; the latch alone does not prove outputs off")

    # -- reads --------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Reply of *IDN? recorded by connect()")
    def identity(self):
        return str(self.native.idn)

    @read("voltage_ch1", unit="V", description="Channel 1 measured output voltage (MEAS:VOLT?)")
    def voltage_ch1(self):
        return float(self.native.measure_voltage(1))

    @read("current_ch1", unit="A", description="Channel 1 measured output current (MEAS:CURR?)")
    def current_ch1(self):
        return float(self.native.measure_current(1))

    @read("voltage_ch2", unit="V", description="Channel 2 measured output voltage (MEAS:VOLT?)")
    def voltage_ch2(self):
        return float(self.native.measure_voltage(2))

    @read("current_ch2", unit="A", description="Channel 2 measured output current (MEAS:CURR?)")
    def current_ch2(self):
        return float(self.native.measure_current(2))

    @read("voltage_ch3", unit="V", description="Channel 3 measured output voltage (MEAS:VOLT?)")
    def voltage_ch3(self):
        return float(self.native.measure_voltage(3))

    @read("current_ch3", unit="A", description="Channel 3 measured output current (MEAS:CURR?)")
    def current_ch3(self):
        return float(self.native.measure_current(3))

    @read("voltage_ch4", unit="V", description="Channel 4 measured output voltage (MEAS:VOLT?)")
    def voltage_ch4(self):
        return float(self.native.measure_voltage(4))

    @read("current_ch4", unit="A", description="Channel 4 measured output current (MEAS:CURR?)")
    def current_ch4(self):
        return float(self.native.measure_current(4))

    # -- writes -------------------------------------------------------------------------------------------------
    @write("voltage_setpoint_ch1", unit="V", limit=VOLTAGE_LIMIT,
           description="CH1 voltage set point")
    def set_voltage_setpoint_ch1(self, value):
        self.native.set_voltage(1, value)
        return round(float(value), 4)

    @write("current_setpoint_ch1", unit="A", limit=CURRENT_LIMIT,
           description="CH1 current set point")
    def set_current_setpoint_ch1(self, value):
        self.native.set_current(1, value)
        return round(float(value), 4)

    @write("voltage_setpoint_ch2", unit="V", limit=VOLTAGE_LIMIT,
           description="CH2 voltage set point")
    def set_voltage_setpoint_ch2(self, value):
        self.native.set_voltage(2, value)
        return round(float(value), 4)

    @write("current_setpoint_ch2", unit="A", limit=CURRENT_LIMIT,
           description="CH2 current set point")
    def set_current_setpoint_ch2(self, value):
        self.native.set_current(2, value)
        return round(float(value), 4)

    @write("voltage_setpoint_ch3", unit="V", limit=VOLTAGE_LIMIT,
           description="CH3 voltage set point")
    def set_voltage_setpoint_ch3(self, value):
        self.native.set_voltage(3, value)
        return round(float(value), 4)

    @write("current_setpoint_ch3", unit="A", limit=CURRENT_LIMIT,
           description="CH3 current set point")
    def set_current_setpoint_ch3(self, value):
        self.native.set_current(3, value)
        return round(float(value), 4)

    @write("voltage_setpoint_ch4", unit="V", limit=VOLTAGE_LIMIT,
           description="CH4 voltage set point")
    def set_voltage_setpoint_ch4(self, value):
        self.native.set_voltage(4, value)
        return round(float(value), 4)

    @write("current_setpoint_ch4", unit="A", limit=CURRENT_LIMIT,
           description="CH4 current set point")
    def set_current_setpoint_ch4(self, value):
        self.native.set_current(4, value)
        return round(float(value), 4)

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.anoryth.set_output.v1", risk="R2",
            description="Switch one channel output on or off (OUTP:SEL ON/OFF) and report the measured voltage",
            input={"channel": Field("integer", unit="1", description="Channel number (1 to 4)", limit=CHANNEL_LIMIT),
                   "enabled": Field("boolean", description="True to switch the output on, False to switch it off")},
            output={"channel": Field("integer", description="Channel whose output was switched"),
                    "enabled": Field("boolean", description="State requested for the channel output"),
                    "voltage": Field("number", unit="V",
                                     description="Measured channel voltage after the command")})
    def set_output(self, channel, enabled):
        channel = int(channel)
        if channel not in (1, 2, 3, 4):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"channel {channel} is not 1, 2, 3 or 4")
        self.native.set_output(channel, bool(enabled))
        return {"channel": channel, "enabled": bool(enabled),
                "voltage": float(self.native.measure_voltage(channel))}

    @action(name="x-cap.anoryth.all_outputs_off.v1", risk="R2",
            description="Request every channel output off and report measured voltages; no confirmed stop is claimed",
            output={"off_requested": Field("boolean",
                                           description="True after all_outputs_off returned; no output-state acknowledgement"),
                    "voltages": Field("array", items="number", length=4, unit="V",
                                      description="Measured channel voltages after the cut-off, channels 1 to 4")})
    def all_outputs_off(self):
        self.native.all_outputs_off()
        return {"off_requested": True,
                "voltages": [float(self.native.measure_voltage(channel)) for channel in (1, 2, 3, 4)]}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="all_outputs_off")
    def stop(self):
        """Attempt the upstream cut-off, but never certify this unverified stop path."""
        self.native.all_outputs_off()
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "all_outputs_off has unchecked completion replies and an unprotected shared channel selector")

    def teardown(self):
        self.native.close()
