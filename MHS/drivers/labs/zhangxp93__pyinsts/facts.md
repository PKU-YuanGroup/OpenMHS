# Facts and tags for gh.zhangxp93/pyinsts

Every fact cites its source at commit `3bcaa2acbea14bb3ed30de140808e9d0de70c96a`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FSV3030Sp is the spectrum-mode class of the FSV3030 driver family and derives from FSV3030Base | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:239 |
| The FSV3030 constructor opens the instrument through BaseInstrument and sends SYST:DISP:UPD ON | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:13-23 |
| BaseInstrument writes *CLS and then queries *IDN? while it connects | upstream_code | src/pyinsts/instrument_drivers/baseinstrument.py:172-176 |
| The center frequency is written as 'SENSE:FREQ:CENT <value><unit>' | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:110 |
| The span is written as 'FREQ:SPAN <value><unit>' and the full span as 'SENS:FREQ:SPAN:FULL' | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:258-267 |
| set_mark_freq accepts marker numbers 1 to 7 and writes 'CALC:MARK<x>:X <Hz value>' after converting the caller's unit to Hz | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:118-134 |
| query_marker_x reads 'CALC:MARK<x>:X?' and divides the reply by the requested unit, so the reply is in Hz | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:138-155 |
| query_marker_y reads 'CALC:MARK<x>:Y?' and returns the reply as a float | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:157-165 |
| query_delta_mkr_x reads 'CALC:DELT<x>:X?' and query_delta_mkr_y reads 'CALC:DELT<x>:Y?' | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:364-384 |
| set_err_disp writes 'SYST:ERR:DISP ON' or 'SYST:ERR:DISP OFF' | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:94-101 |
| set_continuous_peak writes 'CALCulate1:MARKer1:MAXimum:AUTO ON' or '... OFF' | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:286-293 |
| set_abort_meas writes 'ABOR' to abort the current measurement | upstream_code | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:61-67 |
| The clone's FSV3030 simulator identifies the instrument as 'Rohde&Schwarz,FSV3030,100001,3.40' | upstream_code | src/pyinsts/instrument/sim/Fsv3030.yaml:12-13 |
| The clone's FSV3030 simulator answers FREQ:CENT? | upstream_code | src/pyinsts/instrument/sim/Fsv3030.yaml:60-62 |
| The clone's FSV3030 simulator answers CALC:MARK1:X?, CALC:MARK1:Y?, CALC:DELT1:X? and CALC:DELT1:Y? | upstream_code | src/pyinsts/instrument/sim/Fsv3030.yaml:113-143 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| center_frequency (Hz) | SENSE:FREQ:CENT | operator_required: the clone states no tuning range | - |
| span (Hz) | FREQ:SPAN | operator_required: the clone states no span range | - |
| marker_frequency (Hz) | CALC:MARK1:X | operator_required: the clone states no marker frequency range | - |
| error_display | SYST:ERR:DISP | ON or OFF | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:94-101 |
| continuous_peak | CALCulate1:MARKer1:MAXimum:AUTO | ON or OFF | src/pyinsts/instrument_drivers/rohde_schwarz/fsv3030.py:286-293 |

The three numeric writes are `Limit.operator_required`: no text file of the clone states a frequency range of the
analyzer, and the defaults in the simulator YAML are test data, not device bounds. `site-limits.example.json` shows
the operator overlay that fills them. The two ON/OFF writes are limited to the values their methods declare.

The marker level and the delta-marker level are published without a unit: the clone reads them as floats and states
no unit for them.

Safety: the e-stop writes `ABOR`, which aborts the current measurement. This driver sets no output and energizes no
source, so the measurement abort is the safe state; at R1 no independent hardware e-stop is claimed.

Coverage: marker 1 and delta marker 1 only. Trace arrays (`query_trace_x`, `query_trace_y`) and markers 2 to 7 are not
covered; the parameterless operations (all markers off, peak search, full span, auto search off, clear status) are
not exposed as capabilities.

Tags: spectrum analyzer, fsv3030, rohde schwarz, scpi
