# Facts and tags for gh.autolab-project/autolab-drivers

Every fact cites its source at commit `4b44dfba7444d1e8e8b5fd895fa304fa550ce882` in
`anritsu_MS2830A/anritsu_MS2830A.py`. The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Driver_VISA is the pyvisa connection class: it opens the VISA resource named by address, stores it in self.controller and sets the controller timeout to 3000 ms | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:138-146 |
| The driver forces the SCPI language, selects spectrum mode and sets the ASCII trace format, then builds the Frequency module | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:19-24 |
| get_id queries *IDN? and returns the answer | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:31-32 |
| get_power_marker queries CALC:MARK<n>:Y? as a float; get_power_marker_1, _2 and _3 select marker 1, 2 and 3 | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:35-46 |
| The driver model publishes power1, power2 and power3 in dBm | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:102-112 |
| get_timeout and set_timeout read and write the pyvisa controller timeout | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:62-67 |
| The driver model publishes timeout in seconds | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:131-133 |
| get_frequency_start queries FREQ:STARt? and returns GHz (multiplied by 1e-9); set_frequency_start writes FREQ:STAR <value>GHZ | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:166-171 |
| get_frequency_stop queries FREQ:STOP? and returns GHz; set_frequency_stop writes FREQ:STOP <value>GHZ | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:174-179 |
| get_frequency_step queries FREQ:CENT:STEP? and set_frequency_step writes the bare value without a unit suffix or conversion | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:182-187 |
| The driver model declares step with unit Hz and its help text says GHz, so the raw query value is published as Hz | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:226-228 |
| get_frequency_span queries FREQ:SPAN? and returns GHz; set_frequency_span writes FREQ:SPAN <value>GHZ | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:190-195 |
| get_frequency_center queries FREQ:CENT? and returns GHz; set_frequency_center writes FREQ:CENT <value>GHZ and then waits for *OPC? | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:198-204 |
| get_points queries :SENS:SWEep:POINts? and set_points writes SENS:SWEep:POINts with a whole number | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:207-212 |
| The driver model declares points as an int | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:238-240 |
| repeat_sweep writes INIT:CONT ON; single_sweep writes INIT:CONT OFF, then INIT:MODE:SING and *OPC? | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:49-59 |
| The trace is built from frequency_array (start, stop and points) and power_array (TRAC? TRAC1) as a DataFrame with frequency(GHz) and power columns | upstream_code | anritsu_MS2830A/anritsu_MS2830A.py:74-92 |

Limits: every numeric write (the four sweep-window values, the center step, the point count and the timeout) is
`Limit.operator_required`. No text file of the clone states a range for them; the 3000 ms timeout in
`Driver_VISA.__init__` is the pyvisa constructor default, not a bound of the analyser. The site supplies its own
ranges in `site-limits.json`; `site-limits.example.json` shows the shape of that overlay and is only an example.

Safety: the e-stop sends `INIT:CONT OFF` through the upstream `write`, the first command of the upstream
`single_sweep`; it stops a repeating sweep. No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set. The analyser is a receive-only measuring instrument, so the risk is R1.

What this package does not expose: the trace array. The upstream `get_waveform` returns a DataFrame built from
`frequency_array` and `power_array` (`TRAC? TRAC1`); this package carries the scalar marker powers and the sweep
settings only. NOT COVERED: the trace arrays frequency(GHz) and power.

Tags: spectrum-analyzer, esa, scpi, visa, rf
