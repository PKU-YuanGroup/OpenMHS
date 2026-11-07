"""OpenMHS driver for gh.nominal-io/instro: a Siglent SPD3303 series programmable power supply.

A direct Driver (decorated methods) over the upstream device class
``instro.psu.drivers.siglent_spd3303:SiglentSPD3303``.  The upstream class composes a VISA transport
(``instro/psu/drivers/siglent_spd3303.py:11-18``) and exposes one synchronous method per SCPI action, so
each method here is a plain ``def`` that calls ``self.native``.

* reads, for each of the two programmable channels: the measured output voltage, the measured output
  current, the configured voltage and current set points, the output-enable state and the regulation mode;
  the PSU tracking mode is read once;
* writes, for each channel: the voltage set point, the current limit and the output-enable state.  The
  clone states no numeric output range for this model family, so the four numeric set points are
  ``Limit.operator_required``: every one of those writes is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  site supplies the range of its installed unit (``site-limits.example.json`` shows an example overlay);
* one safe-state action, ``x-cap.nominal-io.output_off.v1``, which disables both channel outputs;
* the native stop, ``output_enable(False, channel)`` on both channels, is the e-stop and the safe state.

Only channels 1 and 2 are addressed: the upstream SCPI driver marks channel 3 as front-panel selectable
without a programming interface (``instro/psu/drivers/siglent_spd3303.py:189-197``).

Every Fact cites a line of the clone at the pinned commit
311aee4ae227205b773e6cc9c523df9ea7e7ce03.  This package is model-authored and unreviewed.  It is R1, so the
loader does not refuse its hardware backend; nothing mechanical prevents a hardware run, and a human must
review the package before anyone passes ``--allow-hardware``.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


_NO_VOLTAGE_RANGE = (
    "the clone states no output voltage range for the Siglent SPD3303 series: the upstream class only "
    "writes the value with three decimals and checks the instrument error queue, and the clone names no "
    "rating for the installed model; the site supplies the range of its unit")
_NO_CURRENT_RANGE = (
    "the clone states no output current range for the Siglent SPD3303 series: the upstream class only "
    "writes the value with three decimals and checks the instrument error queue, and the clone names no "
    "rating for the installed model; the site supplies the range of its unit")


class SiglentSPD3303(Driver):
    device_id = "siglent-spd3303"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "instro.psu.drivers.siglent_spd3303:SiglentSPD3303"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSiglentSPD3303"}
    vendor, model = "Siglent", "SPD3303 series programmable DC power supply"
    display_name = "Siglent SPD3303 series power supply (instro.psu.drivers.siglent_spd3303.SiglentSPD3303)"
    tags = ["power-supply", "dc-source", "scpi", "visa", "two-channel"]
    facts = [
        Fact("set_voltage writes CH{channel}:VOLT with three decimals and get_voltage queries "
             "MEAS:VOLT? for that channel", source="upstream_code",
             ref="instro/psu/drivers/siglent_spd3303.py:20-26"),
        Fact("set_current_limit writes CH{channel}:CURR with three decimals and get_current queries "
             "MEAS:CURR? for that channel", source="upstream_code",
             ref="instro/psu/drivers/siglent_spd3303.py:28-34"),
        Fact("get_voltage_setpoint and get_current_setpoint query CH{channel}:VOLT? and "
             "CH{channel}:CURR?", source="upstream_code",
             ref="instro/psu/drivers/siglent_spd3303.py:36-42"),
        Fact("output_enable writes OUTP CH{channel},ON or OUTP CH{channel},OFF",
             source="upstream_code", ref="instro/psu/drivers/siglent_spd3303.py:44-47"),
        Fact("get_output_status returns the ch{channel}_enable entry of the query_status() dictionary",
             source="upstream_code", ref="instro/psu/drivers/siglent_spd3303.py:49-51"),
        Fact("query_status decodes the SYST:STAT? status word with masks 1 and 2 for the channel CC/CV "
             "mode, bits 2-3 for the PSU tracking mode and masks 16 and 32 for the channel enables",
             source="upstream_code", ref="instro/psu/drivers/siglent_spd3303.py:151-158"),
        Fact("Only channels 1 and 2 are programmable; channel 3 is selectable via the front panel and "
             "does not expose a programming interface", source="upstream_code",
             ref="instro/psu/drivers/siglent_spd3303.py:189-197"),
        Fact("The PSU driver contract documents voltages in volts and currents in amperes",
             source="upstream_code", ref="instro/psu/psu.py:36-53"),
        Fact("SiglentSPD3303 composes a VisaDriver in __init__ and open()/close() open and close that "
             "transport", source="upstream_code",
             ref="instro/psu/drivers/siglent_spd3303.py:11-18"),
        Fact("Every checked write and query reads SYST:ERR? afterwards and raises RuntimeError on a "
             "non-zero error reply", source="upstream_code",
             ref="instro/psu/drivers/siglent_spd3303.py:160-174"),
    ]
    safe_state = "both channel outputs disabled (OUTP CHn,OFF); the voltage and current set points are unchanged"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("voltage_setpoint_ch1", unit="V", description="Channel 1 output voltage set point (CH1:VOLT?)")
    def voltage_setpoint_ch1(self):
        return self.native.get_voltage_setpoint(1)

    @read("current_setpoint_ch1", unit="A", description="Channel 1 current limit set point (CH1:CURR?)")
    def current_setpoint_ch1(self):
        return self.native.get_current_setpoint(1)

    @read("voltage_ch1", unit="V", description="Channel 1 measured output voltage (MEAS:VOLT? CH1)")
    def voltage_ch1(self):
        return self.native.get_voltage(1)

    @read("current_ch1", unit="A", description="Channel 1 measured output current (MEAS:CURR? CH1)")
    def current_ch1(self):
        return self.native.get_current(1)

    @read("output_enabled_ch1", type="boolean",
          description="True while channel 1 reports its output enabled (SYST:STAT? bit 4)")
    def output_enabled_ch1(self):
        return self.native.get_output_status(1)

    @read("regulation_mode_ch1", type="string",
          description="Channel 1 regulation mode from SYST:STAT?: CC (current regulated) or CV (voltage regulated)")
    def regulation_mode_ch1(self):
        return self.native.query_status()["ch1_mode"]

    @read("voltage_setpoint_ch2", unit="V", description="Channel 2 output voltage set point (CH2:VOLT?)")
    def voltage_setpoint_ch2(self):
        return self.native.get_voltage_setpoint(2)

    @read("current_setpoint_ch2", unit="A", description="Channel 2 current limit set point (CH2:CURR?)")
    def current_setpoint_ch2(self):
        return self.native.get_current_setpoint(2)

    @read("voltage_ch2", unit="V", description="Channel 2 measured output voltage (MEAS:VOLT? CH2)")
    def voltage_ch2(self):
        return self.native.get_voltage(2)

    @read("current_ch2", unit="A", description="Channel 2 measured output current (MEAS:CURR? CH2)")
    def current_ch2(self):
        return self.native.get_current(2)

    @read("output_enabled_ch2", type="boolean",
          description="True while channel 2 reports its output enabled (SYST:STAT? bit 5)")
    def output_enabled_ch2(self):
        return self.native.get_output_status(2)

    @read("regulation_mode_ch2", type="string",
          description="Channel 2 regulation mode from SYST:STAT?: CC (current regulated) or CV (voltage regulated)")
    def regulation_mode_ch2(self):
        return self.native.query_status()["ch2_mode"]

    @read("psu_mode", type="string",
          description="Tracking mode from SYST:STAT?: INDEPENDENT, PARALLEL, SERIES or UNDEFINED")
    def psu_mode(self):
        return self.native.query_status()["psu_mode"]

    # -- writes -------------------------------------------------------------------------------------------------
    @write("voltage_setpoint_ch1", unit="V",
           description="Channel 1 output voltage set point, written with three decimals",
           limit=Limit.operator_required(_NO_VOLTAGE_RANGE))
    def set_voltage_setpoint_ch1(self, value):
        self.native.set_voltage(value, 1)
        return self.native.get_voltage_setpoint(1)

    @write("current_setpoint_ch1", unit="A",
           description="Channel 1 current limit set point, written with three decimals",
           limit=Limit.operator_required(_NO_CURRENT_RANGE))
    def set_current_setpoint_ch1(self, value):
        self.native.set_current_limit(value, 1)
        return self.native.get_current_setpoint(1)

    @write("output_enabled_ch1", type="boolean", risk="R1",
           description="Enable or disable the channel 1 output (OUTP CH1,ON or OUTP CH1,OFF)")
    def set_output_enabled_ch1(self, value):
        self.native.output_enable(value, 1)
        return self.native.get_output_status(1)

    @write("voltage_setpoint_ch2", unit="V",
           description="Channel 2 output voltage set point, written with three decimals",
           limit=Limit.operator_required(_NO_VOLTAGE_RANGE))
    def set_voltage_setpoint_ch2(self, value):
        self.native.set_voltage(value, 2)
        return self.native.get_voltage_setpoint(2)

    @write("current_setpoint_ch2", unit="A",
           description="Channel 2 current limit set point, written with three decimals",
           limit=Limit.operator_required(_NO_CURRENT_RANGE))
    def set_current_setpoint_ch2(self, value):
        self.native.set_current_limit(value, 2)
        return self.native.get_current_setpoint(2)

    @write("output_enabled_ch2", type="boolean", risk="R1",
           description="Enable or disable the channel 2 output (OUTP CH2,ON or OUTP CH2,OFF)")
    def set_output_enabled_ch2(self, value):
        self.native.output_enable(value, 2)
        return self.native.get_output_status(2)

    # -- action -------------------------------------------------------------------------------------------------
    @action(name="x-cap.nominal-io.output_off.v1", safe_state=True, risk="R1",
            description="Disable both channel outputs (OUTP CH1,OFF and OUTP CH2,OFF); it takes no input "
                        "and is the declared safe state",
            output={"output_enabled_ch1": Field("boolean",
                                                description="False once the channel 1 output is disabled"),
                    "output_enabled_ch2": Field("boolean",
                                                description="False once the channel 2 output is disabled")})
    def output_off(self):
        self.native.output_enable(False, 1)
        self.native.output_enable(False, 2)
        return {"output_enabled_ch1": self.native.get_output_status(1),
                "output_enabled_ch2": self.native.get_output_status(2)}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="output_enable")
    def stop(self):
        """The native stop: the runtime latches first, then switches both outputs off."""
        self.native.output_enable(False, 1)
        self.native.output_enable(False, 2)

    def teardown(self):
        self.native.close()
