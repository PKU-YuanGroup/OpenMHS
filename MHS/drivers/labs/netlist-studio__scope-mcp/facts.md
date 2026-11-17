# Facts and tags for gh.netlist-studio/scope-mcp

Every fact cites its source at commit `877a4f6324a581f3b7d4c8de57d719b258d9d9f0`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream is an MCP server for controlling a Keysight/Agilent oscilloscope over Ethernet | vendor_doc | README.md:5 |
| The tested oscilloscope is the Agilent MSOX2024A with firmware 02.43.2018020635 | vendor_doc | README.md:9 |
| The constructor opens a VISA resource TCPIP0::<ip>::inst0::INSTR through pyvisa's pure-Python ResourceManager '@py' | upstream_code | scope.py:15-16 |
| The VISA session uses a newline read terminator and a newline write terminator | upstream_code | scope.py:18-19 |
| query sends a SCPI query and strips the reply; write sends SCPI text and ignores a blank command | upstream_code | scope.py:23-28 |
| reset sends *RST and then *CLS | upstream_code | scope.py:33-35 |
| run, stop, single and autoscale write :RUN, :STOP, :SINGle and :AUToscale | upstream_code | scope.py:39-49 |
| set_timebase writes :TIMebase:SCALe in seconds per division and set_timebase_delay writes :TIMebase:DELay in seconds | upstream_code | scope.py:53-59 |
| get_timebase reads the scale in seconds per division, the delay in seconds and the timebase mode | upstream_code | scope.py:61-66 |
| set_channel configures the channel scale in V/div, offset in V, coupling AC\|DC\|GND, display and bandwidth limit | upstream_code | scope.py:70-90 |
| get_channel reads the channel scale, offset, coupling, display and bandwidth limit | upstream_code | scope.py:92-101 |
| set_trigger writes the trigger mode and, in edge mode, the edge source, slope and level in volts | upstream_code | scope.py:105-124 |
| get_trigger reads the trigger mode, edge source, level in volts, slope and sweep | upstream_code | scope.py:126-133 |
| The automatic measurement names are frequency, period, vpp, vrms, vmax, vmin, vaverage, duty, rise, fall, overshoot, preshoot and width | upstream_code | scope.py:137-151 |
| A measurement above the no-measurement threshold is reported as 'no_signal' | upstream_code | scope.py:168-174 |
| get_waveform requests an IEEE 488.2 binary block from :WAVeform:DATA? and returns time and voltage arrays | upstream_code | scope.py:188-232 |
| get_serial_data arms a single acquisition, polls :OPERegister:CONDition? up to 100 times, breaking when the RUN bit (bit 3) clears, then reads the lister as an IEEE 488.2 block | upstream_code | scope.py:283-294 |
| screenshot reads the display as a PNG binary block from :DISPlay:DATA? | upstream_code | scope.py:315-318 |
| get_state returns the identity, timebase, trigger and channels 1 to 4 | upstream_code | scope.py:330-337 |
| The MCP tool schema restricts the channel to 1, 2, 3 and 4 | upstream_code | scope_server.py:108 |
| The MCP trigger tool restricts the slope to positive, negative or either | upstream_code | scope_server.py:154 |

Limits:

| parameter | limit | source | ref |
|---|---|---|---|
| channel1_coupling | one of AC, DC, GND | upstream_code | scope.py:79 |
| trigger_source_channel | one of 1, 2, 3, 4 | upstream_code | scope_server.py:152 |
| trigger_slope | one of positive, negative, either | upstream_code | scope.py:112 |
| measure channel | one of 1, 2, 3, 4 | upstream_code | scope_server.py:108 |
| measure parameter | one of the 13 names of PARAMETERS | upstream_code | scope.py:137-151 |

The numeric writes without a stated range use `Limit.operator_required`: `channel1_scale_v_per_div`,
`channel1_offset_v`, `timebase_scale_s_per_div`, `timebase_delay_s` and `trigger_level_v`. The clone gives their
units but no numeric bounds; `site-limits.example.json` is an example overlay for a bench, not a source of device
bounds. Without that overlay those writes are refused with `MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop calls the native `stop()` (`:STOP`, scope.py:42-43) and confirms the RUN bit (bit 3) of
`:OPERegister:CONDition?` is clear (scope.py:287-290). A write that returns while RUN stays set fails the e-stop
with `SAFE_STATE_UNREACHED` and keeps the latch held. A reset only releases the endpoint latch; it does not run
the scope. This state concerns acquisition, not any external circuit. The shared VISA session has a 10 s default
timeout (scope.py:14,17), so a concurrent query can delay the stop beyond the endpoint's stop budget; a timeout
does not confirm stopping. The card's safety floor is R1. Teardown closes the VISA session with the native
`close()` (scope.py:339-340).

Coverage: the waveform array, the PNG screenshot and the UART serial decode are **NOT COVERED** by this package.
The clone returns a time array and a voltage array from `:WAVeform:DATA?` (scope.py:188-232), PNG bytes from
`:DISPlay:DATA?` (scope.py:315-318) and decoded text rows from the lister (scope.py:278-297); no catalogue class of
this package carries those arrays. The package serves the oscilloscope's scalar measurements and settings.

Tags: oscilloscope, keysight, agilent, msox2024a, scpi, visa, ethernet

Authoring: model-authored (`driver.lock.json` `authored_by` kind `model`, model `deepseek-v4.1-flash:1017`, run
`retriage-drivers-1-021`); `reviewed_by` is null. The package is checked on the fake backend only; nothing here ran
on hardware.
