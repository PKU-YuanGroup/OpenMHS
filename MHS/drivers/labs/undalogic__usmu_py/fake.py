"""Fake backend of the uSMU driver: an in-memory stand-in for usmu_py.smu:USMU.

Gate G7 checks every public method defined here against the upstream class (usmu_py/smu.py:8-180); the stand-in
implements exactly the upstream surface the driver can reach:

* ``read_idn`` (line 160), ``read_adc`` (line 130), ``enable_output`` / ``disable_output`` (lines 79 and 83),
  ``set_current_limit`` (line 87), ``set_voltage`` (line 94), ``set_voltage_and_measure`` (line 101),
  ``set_oversample_rate`` (line 117), ``set_dac`` (line 124), ``set_current_limit_dac`` (line 141),
  ``enable_voltage_calibration_mode`` (line 147), ``lock_current_range`` (line 151), ``measure_iv_point``
  (line 167) and ``close`` (line 47).

The stand-in keeps the last applied settings in private attributes; it models an ideal resistive load only so the
driver's conversion of the comma-separated reply is exercised.  Every number below is test data for this stand-in,
never a Fact, a Limit or a reference: each one is marked ``# placeholder``.  Nothing here talks to a device.
"""


class FakeUSMU:
    def __init__(self, **_options):
        self._idn = "uSMU fake"                     # placeholder test data: canned *IDN? reply
        self._voltage = 0.0                         # placeholder test data: last voltage setpoint in volts
        self._current_limit_ma = 0.0                # placeholder test data: last current limit in mA
        self._oversample = 1                        # placeholder test data: last oversample rate
        self._current_range = 1                     # placeholder test data: last locked current range
        self._dac = 0                               # placeholder test data: last voltage DAC level
        self._current_limit_dac = 0                 # placeholder test data: last current limit DAC level
        self._output = False                        # placeholder test data: the stand-in starts with output disabled
        self._calibration = False                   # placeholder test data: voltage calibration mode flag
        self._adc = {0: 0, 2: 0}                    # placeholder test data: signed 16-bit ADC replies
        self._load_ohms = 1000.0                    # placeholder test data: ideal load of the stand-in
        self._closed = False
        self._writes = []                           # placeholder test data: native writes observed by package tests

    # -- connection ----------------------------------------------------------------------------------------------
    def close(self):
        """Close the connection; the upstream method closes the pyserial handle (usmu_py/smu.py:47-50)."""
        self._closed = True

    # -- output --------------------------------------------------------------------------------------------------
    def enable_output(self):
        """Enable the output; the upstream method writes CH1:ENA (usmu_py/smu.py:79-81)."""
        self._output = True
        self._writes.append("enable_output")

    def disable_output(self):
        """Disable the output; the upstream method writes CH1:DIS (usmu_py/smu.py:83-85)."""
        self._output = False
        self._writes.append("disable_output")

    # -- settings ------------------------------------------------------------------------------------------------
    def set_current_limit(self, current_mA):
        """Set the current limit in mA; the upstream method writes CH1:CUR (usmu_py/smu.py:87-92)."""
        self._current_limit_ma = float(current_mA)
        self._writes.append("set_current_limit")

    def set_voltage(self, voltage_V):
        """Set the voltage in volts; the upstream method writes CH1:VOL (usmu_py/smu.py:94-99)."""
        self._voltage = float(voltage_V)
        self._writes.append("set_voltage")

    def set_oversample_rate(self, oversample):
        """Set the oversample rate; the upstream method writes CH1:OSR (usmu_py/smu.py:117-122)."""
        self._oversample = int(oversample)
        self._writes.append("set_oversample_rate")

    def set_dac(self, value):
        """Set the voltage DAC level; the upstream method writes DAC (usmu_py/smu.py:124-128)."""
        self._dac = int(value)
        self._writes.append("set_dac")

    def set_current_limit_dac(self, value):
        """Set the current limit DAC level; the upstream method writes ILIM (usmu_py/smu.py:141-145)."""
        self._current_limit_dac = int(value)
        self._writes.append("set_current_limit_dac")

    def enable_voltage_calibration_mode(self):
        """Enter voltage calibration mode; the upstream method writes CH1:VCAL (usmu_py/smu.py:147-149)."""
        self._calibration = True
        self._writes.append("enable_voltage_calibration_mode")

    def lock_current_range(self, range_val):
        """Lock the current range; the upstream method writes CH1:RANGE (usmu_py/smu.py:151-158)."""
        if range_val not in [1, 2, 3, 4]:
            raise ValueError("Current range must be 1, 2, 3, or 4.")
        self._current_range = int(range_val)
        self._writes.append("lock_current_range")

    # -- measurements ---------------------------------------------------------------------------------------------
    def set_voltage_and_measure(self, voltage_V):
        """Apply the voltage and return (voltage, current); the upstream query is CH1:MEA:VOL (usmu_py/smu.py:101)."""
        self._voltage = float(voltage_V)
        self._writes.append("set_voltage_and_measure")
        current = self._voltage / self._load_ohms if self._output else 0.0
        return self._voltage, current

    def read_adc(self, adc_channel):
        """Return the signed 16-bit differential ADC value; the upstream query is ADC (usmu_py/smu.py:130-139)."""
        return int(self._adc.get(int(adc_channel), 0))

    def read_idn(self):
        """Return the identification string; the upstream query is *IDN? (usmu_py/smu.py:160-162)."""
        return self._idn

    def measure_iv_point(self, voltage_V):
        """Delegate to set_voltage_and_measure, as the upstream helper does (usmu_py/smu.py:167-171)."""
        return self.set_voltage_and_measure(voltage_V)
