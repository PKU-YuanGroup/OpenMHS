# Facts and tags for gh.undalogic/usmu_py

Every fact cites its source at commit `345dc809f9711162a7cc60ca273a3fd13693735a`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| USMU is the Python interface for the USB SMU device over a virtual COM port (VCP) | upstream_code | usmu_py/smu.py:8-11 |
| The constructor opens a pyserial Serial connection on the given port and baud rate and resets its input and output buffers | upstream_code | usmu_py/smu.py:28-40 |
| enable_output writes 'CH1:ENA'; disable_output writes 'CH1:DIS' and documents the disabled state as high impedance | upstream_code | usmu_py/smu.py:79-85 |
| set_current_limit writes 'CH1:CUR <current_mA>', the sink/source current limit in mA | upstream_code | usmu_py/smu.py:87-92 |
| set_voltage writes 'CH1:VOL <voltage_V>', the output voltage in volts | upstream_code | usmu_py/smu.py:94-99 |
| set_voltage_and_measure queries 'CH1:MEA:VOL <voltage_V>' and parses a comma-separated voltage,current reply | upstream_code | usmu_py/smu.py:101-113 |
| set_oversample_rate writes 'CH1:OSR <oversample>'; the docstring states a default of 25, not a permitted range | upstream_code | usmu_py/smu.py:117-122 |
| read_adc queries 'ADC <adc_channel>', a differential conversion between adjacent ADC channels (0 = 0+1, 2 = 2+3), and returns a signed int16 value | upstream_code | usmu_py/smu.py:130-139 |
| lock_current_range accepts only 1, 2, 3 or 4 and writes 'CH1:RANGE <range_val>' | upstream_code | usmu_py/smu.py:151-158 |
| read_idn queries '*IDN?' | upstream_code | usmu_py/smu.py:160-162 |
| measure_iv_point delegates to set_voltage_and_measure | upstream_code | usmu_py/smu.py:167-171 |
| close closes the serial connection if it is open | upstream_code | usmu_py/smu.py:47-50 |
| The README says output voltage, current limit, oversampling rate, DAC values and other settings are settable and that voltage and current are measured in a single command | vendor_doc | README.md:6-7 |
| The README uses a 20 mA current limit and a 1 V setpoint as usage examples; it states no bound | vendor_doc | README.md:44-49 |

Limits: no text of the clone states an output voltage range, a current-limit range or an oversample range (the
README's 1 V and 20 mA are examples on lines 44-49, and the oversample docstring on lines 120-121 states only a
default of 25). Those action inputs are therefore `Limit.operator_required`; the operator supplies the bounds in
`site-limits.json`, and `site-limits.example.json` shows the shape with example values. Until that overlay is
written, a call that sets one of them is refused `MHS.SAFETY.LIMITS_UNSET`. The current range 1 to 4 is stated by
the upstream validation on line 156 and is a sourced limit.

Safety: the native stop is `USMU.disable_output`, which writes `CH1:DIS` (usmu_py/smu.py:83-85) and enters the
high-impedance state; the `safe_state` sentence says the output is disabled. The package is R1, so no independent
hardware e-stop reference is cited. OpenMHS is not a safety certification and not a safety-rated channel; the
physical stop stays authoritative.

Tags: smu, source measure unit, iv sweep, serial, vcp, voltage, current.
