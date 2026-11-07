"""OpenMHS driver for gh.undalogic/usmu_py: the uSMU source-measure unit over its serial VCP protocol.

A direct Driver (decorated methods) over the upstream class ``usmu_py.smu:USMU`` (usmu_py/smu.py:8).  The upstream
constructor opens a pyserial connection (usmu_py/smu.py:28-40) and every method sends one literal protocol line
(``CH1:ENA``, ``CH1:CUR <current_mA>``, ``CH1:MEA:VOL <voltage_V>``); the upstream formats the numeric argument into
the line itself, so a command table cannot reproduce the wire syntax and this package is a direct driver with a
``native.py`` factory.

* reads: the ``*IDN?`` identification string and one signed 16-bit differential ADC conversion (channels 0 and 1,
  ``ADC 0``);
* actions: configure the current range and oversample rate (``CH1:OSR`` and ``CH1:RANGE``), take one I-V point
  (``CH1:CUR`` then ``CH1:MEA:VOL``) and enable or disable the output (``CH1:ENA`` / ``CH1:DIS``);
* limits: no text of the clone states an output voltage range, a current-limit range or an oversample range, so
  those inputs are ``Limit.operator_required`` and a call that sets them is refused ``MHS.SAFETY.LIMITS_UNSET``
  until the site writes the overlay (``site-limits.example.json`` shows the shape).  The current range 1 to 4 is
  stated by the upstream code (usmu_py/smu.py:156);
* the native stop is ``USMU.disable_output``: ``CH1:DIS`` disables the output and documents the high-impedance
  state (usmu_py/smu.py:83-85).

Every Fact cites a line of the clone at the pinned commit 345dc809f9711162a7cc60ca273a3fd13693735a.  This package is
model-authored and unreviewed: the acceptance gate checks the fake backend only and the hardware backend was never
opened.  OpenMHS is not a safety certification and the physical stop stays authoritative.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


class Usmu(Driver):
    device_id = "usmu"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R1"
    native = "usmu_py.smu:USMU"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeUSMU"}
    vendor, model = "undalogic", "uSMU source-measure unit"
    display_name = "uSMU source-measure unit (usmu_py.USMU)"
    tags = ["smu", "source measure unit", "iv sweep", "serial", "vcp", "voltage", "current"]
    facts = [
        Fact("USMU is the Python interface for the USB SMU device over a virtual COM port (VCP)",
             source="upstream_code", ref="usmu_py/smu.py:8-11"),
        Fact("The constructor opens a pyserial Serial connection on the given port and baud rate and resets its "
             "input and output buffers", source="upstream_code", ref="usmu_py/smu.py:28-40"),
        Fact("enable_output writes 'CH1:ENA'; disable_output writes 'CH1:DIS' and documents the disabled state as "
             "high impedance", source="upstream_code", ref="usmu_py/smu.py:79-85"),
        Fact("set_current_limit writes 'CH1:CUR <current_mA>', the sink/source current limit in mA",
             source="upstream_code", ref="usmu_py/smu.py:87-92"),
        Fact("set_voltage writes 'CH1:VOL <voltage_V>', the output voltage in volts", source="upstream_code",
             ref="usmu_py/smu.py:94-99"),
        Fact("set_voltage_and_measure queries 'CH1:MEA:VOL <voltage_V>' and parses a comma-separated "
             "voltage,current reply", source="upstream_code", ref="usmu_py/smu.py:101-113"),
        Fact("set_oversample_rate writes 'CH1:OSR <oversample>'; the docstring states a default of 25, not a "
             "permitted range", source="upstream_code", ref="usmu_py/smu.py:117-122"),
        Fact("read_adc queries 'ADC <adc_channel>', a differential conversion between adjacent ADC channels "
             "(0 = 0+1, 2 = 2+3), and returns a signed int16 value", source="upstream_code",
             ref="usmu_py/smu.py:130-139"),
        Fact("lock_current_range accepts only 1, 2, 3 or 4 and writes 'CH1:RANGE <range_val>'",
             source="upstream_code", ref="usmu_py/smu.py:151-158"),
        Fact("read_idn queries '*IDN?'", source="upstream_code", ref="usmu_py/smu.py:160-162"),
        Fact("measure_iv_point delegates to set_voltage_and_measure", source="upstream_code",
             ref="usmu_py/smu.py:167-171"),
        Fact("close closes the serial connection if it is open", source="upstream_code",
             ref="usmu_py/smu.py:47-50"),
        Fact("The README says output voltage, current limit, oversampling rate, DAC values and other settings are "
             "settable and that voltage and current are measured in a single command", source="vendor_doc",
             ref="README.md:6-7"),
        Fact("The README uses a 20 mA current limit and a 1 V setpoint as usage examples; it states no bound",
             source="vendor_doc", ref="README.md:44-49"),
    ]
    safe_state = "output disabled (high impedance) by CH1:DIS"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("identification", type="string", description="Identification string returned by the *IDN? query")
    def identification(self):
        return self.native.read_idn()

    @read("adc_0_1", type="integer", unit="1",
          description="Signed 16-bit differential ADC conversion between channels 0 and 1 (the upstream 'ADC 0')")
    def adc_0_1(self):
        return int(self.native.read_adc(0))

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.undalogic.usmu.configure.v1",
            description="Set the oversample rate and lock the current range; the native class has no query for "
                        "either setting, so the applied values are returned",
            input={
                "oversample_rate": Field(
                    "integer", unit="1",
                    description="Number of samples averaged per measurement, written as CH1:OSR",
                    limit=Limit.operator_required(
                        "the docstring states only a default of 25 (usmu_py/smu.py:120-121), not a permitted "
                        "range; a default is not a device bound, so the site supplies the range of its unit")),
                "current_range": Field(
                    "integer", unit="1",
                    description="Current range to lock: 1, 2, 3 or 4, written as CH1:RANGE",
                    limit=Limit(min=1, max=4, source="upstream_code", ref="usmu_py/smu.py:156")),
            },
            output={
                "oversample_rate": Field("integer", unit="1",
                                         description="Oversample rate the driver applied"),
                "current_range": Field("integer", unit="1",
                                       description="Current range the driver locked"),
            })
    def configure(self, oversample_rate, current_range):
        self.native.set_oversample_rate(int(oversample_rate))
        self.native.lock_current_range(int(current_range))
        return {"oversample_rate": int(oversample_rate), "current_range": int(current_range)}

    @action(name="x-cap.undalogic.usmu.iv_point.v1",
            description="Set the current limit, source the voltage and return the voltage and current the device "
                        "measures for that point",
            input={
                "voltage": Field(
                    "number", unit="V",
                    description="Output voltage to source, written as CH1:MEA:VOL <voltage>",
                    limit=Limit.operator_required(
                        "no text of the clone states the output voltage range; README.md:44-49 uses 1 V only as "
                        "an example, so the site supplies the range of its unit")),
                "current_limit": Field(
                    "number", unit="mA",
                    description="Sink/source current limit in mA, written as CH1:CUR before the measurement",
                    limit=Limit.operator_required(
                        "no text of the clone states the current limit range; README.md:44-49 uses 20 mA only as "
                        "an example, so the site supplies the limit of its unit")),
            },
            output={
                "voltage": Field("number", unit="V",
                                 description="Voltage the device reports for this I-V point"),
                "current": Field("number", unit="A",
                                 description="Current the device reports for this I-V point"),
            })
    def iv_point(self, voltage, current_limit):
        self.native.set_current_limit(float(current_limit))
        measured_voltage, measured_current = self.native.measure_iv_point(float(voltage))
        return {"voltage": float(measured_voltage), "current": float(measured_current)}

    @action(name="x-cap.undalogic.usmu.output.v1",
            description="Enable or disable the output: CH1:ENA enables it, CH1:DIS disables it into the "
                        "high-impedance state",
            input={
                "enabled": Field("boolean",
                                 description="True to enable the output, False to disable it (high impedance)"),
            },
            output={
                "enabled": Field("boolean", description="Output state the driver applied"),
            })
    def output(self, enabled):
        if enabled:
            self.native.enable_output()
        else:
            self.native.disable_output()
        return {"enabled": bool(enabled)}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="disable_output")
    def stop(self):
        """The native stop: USMU.disable_output writes CH1:DIS, the high-impedance state (usmu_py/smu.py:83-85)."""
        self.native.disable_output()

    def teardown(self):
        self.native.close()
