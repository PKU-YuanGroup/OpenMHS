# Facts and limits for gh.schimmilab/pico-mcp

Every fact cites its source at commit `08fd81ee1c1e79b4d82e0997ca840b46adeef811`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The clone has no
text manual under `docs/`; every citation is a text file or a line of the clone.

| fact | source | ref |
|---|---|---|
| Scope is the stateful handle of one connected PicoScope 5000A device; it keeps the handle, the resolution, max_adc, the variant and serial strings and the configured channels | upstream_code | src/pico_mcp/scope.py:100-108 |
| The clone targets the PicoScope 5000A/B series and was verified on a 5442B | upstream_code | src/pico_mcp/scope.py:3-4 |
| The README describes a lean MCP server for PicoScope 5000A USB oscilloscopes developed and verified on a 5442B | vendor_doc | README.md:3-4 |
| connect opens the unit, reads max_adc with ps5000aMaximumValue and reads the variant and serial with ps5000aGetUnitInfo | upstream_code | src/pico_mcp/scope.py:115-143 |
| The resolution must be one of 8, 12, 14, 15 and 16 bits | upstream_code | src/pico_mcp/scope.py:41-42 |
| The channel names are A, B, C and D | upstream_code | src/pico_mcp/scope.py:44-45 |
| set_channel validates the channel, maps AC or DC to PS5000A_AC or PS5000A_DC, picks the smallest range in _RANGE_NAMES that covers the request and calls ps5000aSetChannel | upstream_code | src/pico_mcp/scope.py:174-187 |
| The full-scale voltage ranges run from 0.01 V to 20.0 V | upstream_code | src/pico_mcp/scope.py:24-30 |
| set_channel defaults to enabled=True, coupling='DC', range_volts=5.0 and analog_offset=0.0 | upstream_code | src/pico_mcp/scope.py:174-175 |
| The README states that set_channel covers channel A to D, enable, DC/AC and a range of 0.01 to 20 V | vendor_doc | README.md:90 |
| The signal-generator wave names are sine, square, triangle, ramp_up, ramp_down and dc | upstream_code | src/pico_mcp/scope.py:34-35 |
| set_signal_generator converts amplitude_v to peak-to-peak (amplitude * 2 * 1e6) and calls ps5000aSetSigGenBuiltInV2 with the frequency and wave | upstream_code | src/pico_mcp/scope.py:190-204 |
| stop_signal_generator sets the generator to DC at 0 V to turn the output off | upstream_code | src/pico_mcp/scope.py:206-213 |
| The README states that set_signal_generator and stop_signal_generator drive the built-in AWG with sine, square, triangle and ramp, frequency and amplitude | vendor_doc | README.md:91 |
| capture_block captures one block on all enabled channels and returns the sample count, sample interval, sample rate, duration, timebase and per-channel measurements | upstream_code | src/pico_mcp/scope.py:216-239 |
| The per-channel analysis returns vpp_mv, vmin_mv, vmax_mv, mean_mv, rms_mv, frequency_hz, over_range and a downsampled waveform_mv | upstream_code | src/pico_mcp/scope.py:367-392 |
| The README states that capture_block returns Vpp/min/max/mean/rms, an estimated frequency and a downsampled waveform | vendor_doc | README.md:92 |
| The capture waits up to 10 s for ps5000aIsReady and stops the unit when the deadline passes | upstream_code | src/pico_mcp/scope.py:274-281 |
| The pyproject declares numpy and picosdk as runtime dependencies | upstream_code | pyproject.toml:12-14 |

Limits:

| parameter | limit | source | ref |
|---|---|---|---|
| channel_a_range_v, channel_b_range_v, channel_c_range_v, channel_d_range_v | 0.01 to 20.0 V full scale | upstream_code | src/pico_mcp/scope.py:25-29 |
| channel_a_coupling, channel_b_coupling, channel_c_coupling, channel_d_coupling | one of DC, AC | upstream_code | src/pico_mcp/scope.py:180 |

The signal-generator frequency and amplitude, and the capture sample count, timebase and trigger level, are
`Limit.operator_required`: the clone passes them to the ps5000a calls without stating a range, and the README states
none. `site-limits.example.json` is an example overlay that fills them for a bench; it is not a source of device
bounds. Without an overlay those capabilities are refused `MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop and the safe-state action `x-cap.schimmilab.stop_signal_generator.v1` both call the native
`stop_signal_generator()` (DC at 0 V, scope.py:206-213), which turns the built-in generator output off. No line of
the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. The package is R1; the
safe-state action is provided anyway. The scope itself is a passive measuring instrument.

Channel state: the driver reads the channel objects the upstream `set_channel` stores in `Scope.channels`
(scope.py:185); a channel that has never been configured has no entry, so its enabled/coupling/range fields are
omitted from the state rather than invented. Every channel write calls `set_channel` with all arguments, including
`analog_offset=0.0` (the upstream default, scope.py:174-175); the driver does not expose the analog offset because
the upstream `ChannelState` does not store it (scope.py:91-96), so there is no read-back to serve as state.

The waveform array is NOT COVERED: `capture_block` returns a downsampled `waveform_mv` list per channel
(scope.py:380-392) and the README describes it (README.md:92); no catalogue class carries a trace array, so the
driver returns the scalar measurements and the settings. The array is not put into the extension output.

Tags: oscilloscope, picoscope, ps5000a, usb, signal-generator, block-capture
