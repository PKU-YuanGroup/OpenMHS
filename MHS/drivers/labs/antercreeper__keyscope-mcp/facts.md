# Facts and tags for gh.antercreeper/keyscope-mcp

Every fact and limit cites its source at commit `344dc93cf9f151672d0b07dc4b29f780ae38bd08`: `vendor_doc` (a text
file of the clone) or `upstream_code` (`path/in/clone.py:LINE`).  The same entries are in `driver.py`
(`facts = [...]` and the decorators); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The supported hardware table lists the EDUX1052G and DSOX1102G as verified and other InfiniiVision models as likely compatible | vendor_doc | README.md:284-288 |
| The constructor creates pyvisa's pure-Python ResourceManager '@py' | upstream_code | keyscope_mcp/scope.py:28-30 |
| connect() opens the VISA resource, sets the timeout and uses newline read and write terminators | upstream_code | keyscope_mcp/scope.py:59-63 |
| The connection sets :WAVeform:UNSigned OFF and :WAVeform:BYTeorder LSBFirst for waveform transfers | upstream_code | keyscope_mcp/scope.py:72-74 |
| idn() queries *IDN? | upstream_code | keyscope_mcp/scope.py:242-243 |
| reset() writes *RST | upstream_code | keyscope_mcp/scope.py:245-246 |
| opc() queries *OPC? and returns True only when the reply is '1' | upstream_code | keyscope_mcp/scope.py:248-249 |
| run(), stop() and single() write :RUN, :STOP and :SINGle | upstream_code | keyscope_mcp/scope.py:251-258 |
| autoscale() writes :AUToscale | upstream_code | keyscope_mcp/scope.py:263-264 |
| get_error() reads one entry of the error FIFO with :SYSTem:ERRor? and returns a code and message | upstream_code | keyscope_mcp/scope.py:222-228 |
| The upstream close() attempts :RUN before closing the VISA session and suppresses both errors | upstream_code | keyscope_mcp/scope.py:76-86 |
| measure() selects :MEASure:SOURce CHANnel<n> and then queries :MEASure:<item>? CHANnel<n>, returning a float | upstream_code | keyscope_mcp/scope.py:353-356 |
| The DSL lists the measurement names vpp, vmax, vmin, vamp, vtop, vbase, vavg, vrms, freq, per, rise, fall, pwid, nwid, duty, over and preshoot | upstream_code | keyscope_mcp/dsl.py:436-439 |
| The DSL accepts only channel 1 or 2 for channel configuration | upstream_code | keyscope_mcp/dsl.py:214 |
| The DSL calls parse_voltage for channel scale and offset | upstream_code | keyscope_mcp/dsl.py:233-247 |
| The DSL calls parse_time for timebase scale and position | upstream_code | keyscope_mcp/dsl.py:281-292 |
| The DSL calls parse_voltage for the trigger level | upstream_code | keyscope_mcp/dsl.py:338-341 |
| parse_voltage converts voltage strings to volts | upstream_code | keyscope_mcp/units.py:30-45 |
| parse_time converts time strings to seconds | upstream_code | keyscope_mcp/units.py:48-56 |
| The DSL acquisition modes are NORMal, AVERage, HRESolution and PEAK | upstream_code | keyscope_mcp/dsl.py:402-403 |
| query_binary reads an IEEE 488.2 #n<length><data> binary block | upstream_code | keyscope_mcp/scope.py:181-212 |
| get_waveform sets :WAVeform:SOURce, :WAVeform:FORMat, :WAVeform:POINts and reads :WAVeform:PREamble? before :WAVeform:DATA? | upstream_code | keyscope_mcp/scope.py:274-290 |

Limits:

| parameter | limit | source | ref |
|---|---|---|---|
| measure.channel | 1 to 2 | upstream_code | keyscope_mcp/dsl.py:214 |
| measure.measurement | one of vpp, vmax, vmin, vamp, vtop, vbase, vavg, vrms, freq, per, rise, fall, pwid, nwid, duty, over, preshoot | upstream_code | keyscope_mcp/dsl.py:436-439 |
| channel1_coupling | one of AC, DC | upstream_code | keyscope_mcp/dsl.py:251-254 |
| acquire_type | one of NORMal, AVERage, HRESolution, PEAK | upstream_code | keyscope_mcp/dsl.py:402-403 |

The settings without a stated range use `Limit.operator_required`: `channel1_scale_v_per_div`,
`channel1_offset_v`, `timebase_scale_s_per_div`, `timebase_position_s` and `trigger_level_v`.  Their bounds depend
on the model, the probe ratio, the vertical scale and the timebase or trigger mode; the clone states only the
parsing units.  `site-limits.example.json` is an example overlay for one bench; it is not a source of device
bounds, and the operator must supply the real limits before any of those writes is accepted.

Only channel 1 is exposed as writable analog-channel state. The trigger-source read returns the instrument's source
unchanged and may name another input. The measurement action accepts channel
1 or 2 because the DSL validates a configured channel against 1 and 2.  The waveform array is not exposed: the
upstream `get_waveform` returns time and voltage arrays from a binary block, and no catalogue class carries an
oscilloscope trace.  The screenshot, setup block, *LRN? and the raw-command path are not exposed either.

Safety: the stop sends `:STOP`, requires `opc()` to return True (`*OPC?` must be `1`) and checks a zero error-FIFO
code. False completion, an error code or a query failure raises; an e-stop then stays failed and latched. This is an
acknowledged acquisition command, not an independent sensed acquisition-state measurement. Reset only clears the latch.

The upstream `close()` sends `:RUN` before releasing the VISA handle (`keyscope_mcp/scope.py:76-86`). `native.py`
therefore overrides that lifecycle step: it closes the handle without any instrument command and propagates a close
failure. The fake's close follows this deliberate package override. The upstream import occurs only in connect();
local lifecycle tests exercise this override with a stub VISA handle, without importing the upstream package.

The card floor is R0 and this package is R1 because it exposes settings under `cap.device.configure.v1`. It serves
no waveform-generator output. The upstream VISA timeout defaults to 15000 ms (`keyscope_mcp/scope.py:28`); real
stop/query latency and concurrent access to that session are not validated by the synchronous fake. External clients
or a front-panel command can resume acquisition outside this endpoint's latch.

Tags: oscilloscope, keysight, infiniivision, edux1052g, dsox1102g, scpi, visa

Authoring: model-authored (`driver.lock.json` `authored_by` kind `model`, model `deepseek-v4.1-flash:1017`, run
`retriage-drivers-1-015`); `reviewed_by` is null.  The package is checked on the fake backend only; nothing here
ran on hardware, and no traffic was captured for the fake.
