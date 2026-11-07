# Facts and tags for gh.yongxb/keithley-smu-controls

Every fact cites its source in the upstream clone at commit `6afb567c29125beb133facbbe62bb88c37d8529f`. The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The repository contains standalone scripts for the Keithley 2400, 2450 and 2657A source-measure units | vendor_doc | README.md:12-14 |
| The 2450 script opens the first USB VISA resource as the module-level object keithley | upstream_code | Keithley_control_2450.py:37-40 |
| The 2450 script queries *IDN? after opening the resource | upstream_code | Keithley_control_2450.py:41 |
| The 2450 script configures current source mode with smu.source.func = smu.FUNC_DC_CURRENT, smu.source.level and smu.source.vlimit.level | upstream_code | Keithley_control_2450.py:56-63 |
| The 2450 script configures voltage source mode with smu.source.func = smu.FUNC_DC_VOLTAGE, smu.source.level and smu.source.ilimit.level | upstream_code | Keithley_control_2450.py:67-74 |
| The 2450 script turns the source output on with smu.source.output = smu.ON | upstream_code | Keithley_control_2450.py:87 |
| The 2450 script sets the source level to zero and waits soak_time before writing smu.source.output = smu.OFF | upstream_code | Keithley_control_2450.py:173-184 |
| The 2450 script reads a voltage measurement by setting smu.measure.func to smu.FUNC_DC_VOLTAGE and calling smu.measure.read on a source buffer | upstream_code | Keithley_control_2450.py:123-126 |
| The 2450 script reads a current measurement by setting smu.measure.func to smu.FUNC_DC_CURRENT and calling smu.measure.read on a source buffer | upstream_code | Keithley_control_2450.py:128-131 |
| The 2450 script creates a source buffer with buffer.make(buffer_size) before measuring | upstream_code | Keithley_control_2450.py:80 |
| The README names PyVISA as the connection library for the 2450 and 2657A and PyMeasure for the 2400 | vendor_doc | README.md:20-21 |

## Limits

| parameter | TSP attribute | limit | ref |
|---|---|---|---|
| `source_current` (A) | `smu.source.level` | `Limit.operator_required`: the clone writes the value of its input parameter and states no current range | `Keithley_control_2450.py:56-63` |
| `compliance_voltage` (V) | `smu.source.vlimit.level` | `Limit.operator_required`: the clone sets it from `voltage_limit` and states no compliance range | `Keithley_control_2450.py:61-63` |

The script's input values (`source_current = -50e-6`, `voltage_limit = 210`, `source_voltage = 200`,
`current_limit = 1e-4`, lines 11-17) are one run's settings, not a device range, so they are not used as limits.
The output is a boolean and carries no numeric bound. `site-limits.example.json` fills the two
`operator_required` envelopes with narrow example ranges; it is an operator overlay, not a fact about the device.

## Safety

The source-measure unit sources current and voltage, and the clone states no maximum for either (lines 11-17,
56-74); the driver is declared R3 because a source output can present a high-voltage hazard
(MHS/spec/04-safety.md). The clone documents no independent hardware e-stop, so `estop_physical_ref` is not set;
the independent stop is the `x-cap.yongxb.safe_state.v1` action (`safe_state=True`), which disables the source
output and zeroes the source level. The e-stop writes the same command. The clone zeroes the source level, waits
`soak_time` (10 s, line 19) and only then disables the output (lines 173-184); an e-stop cannot wait, so this
driver disables the output first and does not reproduce the soak delay.

## Not covered

The voltage-source mode of the 2450 script (lines 67-74), its source buffer and buffer-based readback (lines 80
and 123-131), and its CSV logging (lines 139-166) are not part of this driver. The 2657A script (`smua.*`
commands, `keithley_control_2657A.py`) and the 2400 script (PyMeasure, `Keithley2400_source_current_v2.py`) are
separate device variants and are not covered by this package. The hardware backend connects to a raw-TCP or VISA
endpoint configured in the backend options; it does not discover a USB resource as the clone does (lines 37-40).

Tags: keithley, 2450, source-measure unit, smu, tsp, visa
