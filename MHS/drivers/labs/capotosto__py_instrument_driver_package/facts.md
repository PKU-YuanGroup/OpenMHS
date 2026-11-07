# Facts and tags for gh.capotosto/py_instrument_driver_package

Every fact cites its source at commit `1512bb3c1d76a16ada54cf042019a88710b7e12f`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The module controls Keysight E4980A series Precision LCR Meters with the class KeysightE4980A | upstream_code | instrument_module/keysight_E4980A.py:1-15 |
| The accepted impedance measurement functions are CPD, CPQ, CPG, CPRP, CSD, CSQ, CSRS, LPD, LPQ, LPG, LPRP, LPRD, LSD, LSQ, LSRS, LSRD, RX, ZTD, ZTR, GB, YTD, YTR and VDID | upstream_code | instrument_module/keysight_E4980A.py:18-24 |
| The measurement function is set with ':FUNCtion:IMPedance <function>' and queried with ':FUNCtion:IMPedance?' | upstream_code | instrument_module/keysight_E4980A.py:185-190 |
| A setting is sent as a fixed command word followed by the value, for example f':FREQuency {frequency}' | upstream_code | instrument_module/keysight_E4980A.py:198 |
| A query is sent as a fixed query word, for example ':FREQuency?' | upstream_code | instrument_module/keysight_E4980A.py:203 |
| Boolean states are written as ON or OFF and read back as 1/ON or 0/OFF | upstream_code | instrument_module/keysight_E4980A.py:73-86 |
| The aperture command is ':APERture <mode>,<averages>', with the instrument spellings SHORt, MEDium and LONG, and the averaging rate is checked to lie from 1 to 256 | upstream_code | instrument_module/keysight_E4980A.py:246-264 |
| The cable length is one of 0, 1, 2 or 4 metres | upstream_code | instrument_module/keysight_E4980A.py:534-535 |
| The exponent field accepts 2 or 3 digits | upstream_code | instrument_module/keysight_E4980A.py:673-674 |
| The correction method is written as SINGle or MULTiple | upstream_code | instrument_module/keysight_E4980A.py:548-560 |
| The data format command is ':FORMat:DATA ASCii' or ':FORMat:DATA REAL,64' | upstream_code | instrument_module/keysight_E4980A.py:639-642 |
| The trigger source is written as INternal, HOLD, EXternal or BUS | upstream_code | instrument_module/keysight_E4980A.py:367-383 |
| fetch_formatted queries ':FETCh:IMPedance:FORMatted?' and parses primary value, secondary value and a numeric status code | upstream_code | instrument_module/keysight_E4980A.py:416-430 |
| fetch_corrected_impedance queries ':FETCh:IMPedance:CORRected?' and parses resistance and reactance in ohms | upstream_code | instrument_module/keysight_E4980A.py:445-458 |
| The signal monitors fetch AC voltage, AC current, DC voltage and DC current from ':FETCh:SMONitor:VAC?', ':FETCh:SMONitor:IAC?', ':FETCh:SMONitor:VDC?' and ':FETCh:SMONitor:IDC?' | upstream_code | instrument_module/keysight_E4980A.py:506-528 |
| One error-queue entry is read from ':SYSTem:ERRor?' and get_all_system_errors stops when the code before the first comma is 0 | upstream_code | instrument_module/keysight_E4980A.py:153-171 |
| abort sends ':ABORt' and returns the trigger system to idle | upstream_code | instrument_module/keysight_E4980A.py:339-342 |
| The DC bias state is set with ':BIAS:STATe <state>' and queried with ':BIAS:STATe?' | upstream_code | instrument_module/keysight_E4980A.py:304-313 |
| The DC bias voltage is set with ':BIAS:VOLTage:LEVel <voltage>' and queried with ':BIAS:VOLTage:LEVel?' | upstream_code | instrument_module/keysight_E4980A.py:315-324 |
| The raw SCPI socket port is 5025 and a VISA resource is 'TCPIP0::<ip>::5025::SOCKET' or 'TCPIP0::<ip>::INSTR' | upstream_code | instrument_module/visa_utils.py:43-49 |

## Limits

| parameter | command | limit | ref |
|---|---|---|---|
| measurement_function | :FUNCtion:IMPedance | one of the 23 functions above | instrument_module/keysight_E4980A.py:18-24 |
| frequency (Hz) | :FREQuency | operator_required: the clone states no frequency range | - |
| voltage_level (V) | :VOLTage:LEVel | operator_required: the clone states no AC voltage range | - |
| current_level (A) | :CURRent:LEVel | operator_required: the clone states no AC current range | - |
| dc_bias_voltage (V) | :BIAS:VOLTage:LEVel | operator_required: the clone states no DC bias range | - |
| impedance_range (Ohm) | :FUNCtion:IMPedance:RANGe | operator_required: the clone states no impedance range | - |
| cable_length (m) | :CORRection:LENGth | 0, 1, 2 or 4 | instrument_module/keysight_E4980A.py:534 |
| aperture mode | :APERture | SHORT, MEDIUM or LONG | instrument_module/keysight_E4980A.py:246-252 |
| aperture averages | :APERture | 1 to 256 | instrument_module/keysight_E4980A.py:261 |

The five operator_required limits are filled by the operator in `site-limits.json`; `site-limits.example.json` shows
an example bench. Until the overlay is supplied, every write of those fields is refused with
`MHS.SAFETY.LIMITS_UNSET`.

The remaining settings are read-only in this package (the MCP projection bounds the single configure tool to 2048
bytes): DC bias autorange, correction method, data format, long ASCII formatting, exponent digits, trigger source,
trigger delay, continuous initiation and impedance autorange. Their values are read through the queries the clone
uses (for example `:CORRection:METHod?`, `:FORMat:DATA?`, `:TRIGger:SOURce?` and `:TRIGger:TDEL?`) and their
accepted spellings are the facts above; they are not written by this package.

## Coverage

The formatted measurement, corrected impedance and the four signal monitors are served as scalar values. The
status text of `fetch_formatted_with_status` is not exposed (the numeric code is returned and the caller maps it);
list sweep, bin sorting, correction execution and the correction states are not served. The clone's `README.md`
does not document the E4980A's numeric ranges, so no range is copied from it.

## Safety

The e-stop writes `:BIAS:STATe OFF` and the safe-state binding writes `:ABORt`: the DC bias is removed and the
current measurement is aborted. At R1 this is a software e-stop; the package cites no independent hardware stop and
claims no hardware run.

Tags: lcr meter, impedance, keysight, e4980a, scpi, visa
