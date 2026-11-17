# Facts, limits and tags for gh.krystalmonolith/skippy-mcp

The clone is an MCP server that drives a Rigol MSO/DSO oscilloscope over SCPI/PyVISA (`README.md:3-4`). This
package serves one device through its high-level `skippy_mcp.driver.scope:Scope` class: analog channel 1, the shared
edge-trigger configuration and the acquisition commands. Waveform arrays are not served.

Every fact cites its source at commit `0f35e7dca264dc7956d7a083bcc4a652c7aac6a5`: `upstream_code` is a code line of
the clone, `vendor_doc` a text file of it. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The repository is an MCP server that drives a Rigol MSO/DSO oscilloscope over SCPI/PyVISA | vendor_doc | README.md:3-4 |
| The package declares pyvisa and pyvisa-py as runtime dependencies and no vendor scope SDK | upstream_code | packages/skippy-mcp/pyproject.toml:14-18 |
| Scope is the high-level control of one connected instrument | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:53-54 |
| establish queries *IDN?, selects the dialect and returns a Scope | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/session.py:30-35 |
| PyVisaTransport.open opens a VISA resource and sets newline read and write terminators | upstream_code | packages/skippy-mcp/src/skippy_mcp/transport/pyvisa_transport.py:36-53 |
| Scope.identify returns the parsed identity | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:86-87 |
| Scope.reset writes the dialect reset command and then the clear-status command | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:93-95 |
| Scope.configure_channel writes display, scale, offset, coupling, bandwidth limit and probe ratio of one channel, then checks :SYSTem:ERRor? | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:102-119 |
| Scope.configure_logic requires at least one digital channel, validates it against the model's count and writes enable and threshold for each channel | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:122-135 |
| Scope.configure_trigger writes the trigger mode and, only in EDGE mode, the source, slope and level | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:138-147 |
| Scope.capture writes RUN, STOP or SINGle and then checks :SYSTem:ERRor? | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:150-157 |
| Scope.measure queries one measurement item, parses a float, rejects the 9.9e37 sentinel and returns the value with a unit | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:160-175 |
| Scope.screenshot returns the native screenshot bytes | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:178-181 |
| The MSO5000 screenshot is always a 24-bit BMP | upstream_code | packages/skippy-mcp/src/skippy_mcp/dialect/mso5000.py:28-32 |
| Scope.read_waveform transfers a byte waveform, converts it with the preamble and downsamples it to max_points | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:184-213 |
| Scope.raw_scpi queries when the command ends in '?' and writes otherwise | upstream_code | packages/skippy-mcp/src/skippy_mcp/driver/scope.py:257-265 |
| The MSO5000 dialect declares 4 analog channels, 16 digital channels and a vertical scale from 5.0e-4 to 10.0 V/div | upstream_code | packages/skippy-mcp/src/skippy_mcp/dialect/mso5000.py:20-26 |
| The API coupling tokens are dc, ac and gnd, with the SCPI spellings DC, AC and GND | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/enums.py:31-36 |
| The API bandwidth-limit tokens are off and 20m, with the SCPI spellings OFF and 20M | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/enums.py:39-43 |
| The trigger modes are edge, pulse and pattern, with the SCPI spellings EDGE, PULSe and PATTern | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/enums.py:46-51 |
| The edge-trigger slopes are rising, falling and either, with the SCPI spellings POSitive, NEGative and RFALl | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/enums.py:54-59 |
| The measurement items are vpp, vrms, freq, period, duty, rise, fall, delay and phase | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/enums.py:62-73 |
| The capture actions are run, stop and single | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/enums.py:118-123 |
| DeviceLimits carries the per-model channel counts and vertical-scale bounds used for pre-validation | upstream_code | packages/skippy-mcp/src/skippy_mcp/core/models.py:46-53 |
| The dialect translates CH1 to CHANnel1 for a source token | upstream_code | packages/skippy-mcp/src/skippy_mcp/dialect/base.py:62-69 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| channel1_scale_v_per_div | V | 0.0005 .. 10.0 (the value is V/div) | upstream_code: packages/skippy-mcp/src/skippy_mcp/dialect/mso5000.py:24-25 |
| channel1_offset_v | V | operator_required: the clone writes :CHANnel<n>:OFFSet without a numeric range | operator |
| channel1_coupling | | one of dc, ac, gnd | upstream_code: packages/skippy-mcp/src/skippy_mcp/core/enums.py:34-36 |
| channel1_probe_ratio | 1 | operator_required: the clone writes :CHANnel<n>:PROBe without a numeric range or allowed set | operator |
| channel1_bandwidth_limit | | one of off, 20m | upstream_code: packages/skippy-mcp/src/skippy_mcp/core/enums.py:42-43 |
| trigger mode | | one of edge, pulse, pattern | upstream_code: packages/skippy-mcp/src/skippy_mcp/core/enums.py:49-51 |
| trigger edge slope | | one of rising, falling, either | upstream_code: packages/skippy-mcp/src/skippy_mcp/core/enums.py:57-59 |
| trigger_level_v (action input) | V | operator_required: the clone writes :TRIGger:EDGE:LEVel without a numeric range | operator |

The three operator-required ranges are supplied by the site in `site-limits.json`; `site-limits.example.json`
shows one overlay that narrows them for a bench. Without an overlay every write of those fields is refused with
`MHS.SAFETY.LIMITS_UNSET`. The example overlay also narrows the channel-1 scale to a subset of the upstream range.

## Safety

* The e-stop calls the native `Scope.capture("stop")`, which writes `:STOP` and then checks `:SYSTem:ERRor?`
  (`scope.py:150-157`): the acquisition is halted and the display is frozen. The oscilloscope emits no energy and
  this package sets no output.
* The capture, trigger and channel writes go through the upstream `Scope` methods, which check `:SYSTem:ERRor?`
  after the write (`scope.py:119`, `147`, `157`); a driver never reports a silent clamp as success.
* This is an R1 hardware package. It is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null),
  checked on the fake backend only, and never ran on hardware. The loader's unreviewed-hardware guard applies at R2
  and R3 only, so this package does not claim it.

## Not covered

* Waveform arrays: `Scope.read_waveform` returns a time/voltage trace from `:WAVeform:DATA?` (`scope.py:184-213`);
  no catalogue class carries a trace array. Only the scalar automatic measurements and the settings are served.
* The screenshot bytes (native BMP, `scope.py:178-181`, `dialect/mso5000.py:28-32`), the logic channels
  (`configure_logic`, `scope.py:122-135`), bus decode (`scope.py:216-254`), the raw SCPI tool and the vertical
  settings of channels 2 to 4 are not exposed.
* The measurement action can name any analog channel as its source, but only channel 1 is configured or read.

## Tags

oscilloscope, scpi, visa, rigol, mso5000, mso5204, skippy-mcp
