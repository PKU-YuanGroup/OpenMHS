# Facts and tags for gh.baroobob/keithley2400

Every fact cites its source in the upstream clone at commit `6491ff740bbdeac2f5cceca43a8b9133fb615399`. The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The user API is ten module-level functions, not a class | upstream_code | `keithley2400.py:28-39` |
| The module imports prologixGPIBUSB as the GPIB transport and Error from errors | upstream_code | `keithley2400.py:44-46` |
| The module uses Python 2 print statements | upstream_code | `keithley2400.py:154` |
| open_connection sets the GPIB address to 24 and clears the selected device | upstream_code | `keithley2400.py:74-77` |
| open_connection checks the *IDN? reply for 'KEITHLEY INSTRUMENTS INC.,MODEL 2400' and writes OUTP ON | upstream_code | `keithley2400.py:78-81` |
| current_mode writes SOUR:FUNC VOLT, SOUR:VOLT 0, CONF:CURR and FORM:ELEM CURR | upstream_code | `keithley2400.py:64-68` |
| voltage_mode writes SOUR:FUNC CURR, SOUR:CURR 0, CONF:VOLT and FORM:ELEM VOLT | upstream_code | `keithley2400.py:160-164` |
| resistance_mode writes CONF:RES and FORM:ELEM RES | upstream_code | `keithley2400.py:146-148` |
| read writes ARM:COUN 1, TRIG:COUN samples, TRIG:DEL interval and READ? | upstream_code | `keithley2400.py:114-121` |
| For more than one sample the allowed intervals are 0, 1, 10, 60, 600 and 3600 s; for one sample the interval is 0 through 99 s; samples is 1 to 100 | upstream_code | `keithley2400.py:248-251` |
| set_voltage_source writes SOUR:VOLT followed by the value and warns that the source has a maximum resolution of 5 uV | upstream_code | `keithley2400.py:152-156` |
| disable_voltage_source writes SOUR:VOLT 0 | upstream_code | `keithley2400.py:102-103` |
| A read of one sample returns one value; with more than one sample it returns Time and Data lists | upstream_code | `keithley2400.py:139-142` |
| enable_live_readings writes ARM:COUN INF, TRIG:DEL 0 and INIT | upstream_code | `keithley2400.py:86-90` |
| The upstream README calls the project a Python module for controlling a Keithley 2400 source-measure unit and says it depends on prologixGPIBUSB | vendor_doc | `README.md:4-5` |

## Limits

| parameter or input | command | limit | ref |
|---|---|---|---|
| `voltage` (V) | SOUR:VOLT | `Limit.operator_required`: the clone states only the 5 uV resolution, not a minimum or maximum; the operator supplies the source-voltage envelope | `keithley2400.py:152-156` |
| measurement `interval` (s) | TRIG:DEL | 0 through 99 s for one sample | `keithley2400.py:248-250` |

The output is a boolean and carries no numeric bound. `site-limits.example.json` is an example operator overlay: it
fills the `operator_required` source-voltage envelope with a narrow example range. It is not a fact about the device.

## Safety

The source-measure unit can source a voltage and a current; no line of the clone states a maximum, and the
`voltage` write is `operator_required`. The device is declared R3 (MHS/spec/04-safety.md calls high voltage R3): the
upstream sets SOUR:VOLT to any value (lines 152-156), so the hazard is the source output, not a measured value. No
line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. The independent
stop is the `x-cap.baroobob.safe_state.v1` action (`safe_state=True`): it disables the output and zeroes both source
quantities. The e-stop writes the same commands. The safe-state action takes no input and is always callable during
an e-stop.

## Not covered

Multi-sample reads (`read(interval, samples)` with `samples > 1` returns `Time` and `Data` lists,
`keithley2400.py:139-142`), live readings (`enable_live_readings`, lines 86-90), and the Prologix adapter setup
(GPIB address 24 and clear, lines 74-77) are not covered. The hardware backend expects a preconfigured raw-SCPI
TCP endpoint or VISA resource; the driver does not open the Prologix adapter and never ran hardware.

Tags: keithley, 2400, source-measure unit, smu, scpi
