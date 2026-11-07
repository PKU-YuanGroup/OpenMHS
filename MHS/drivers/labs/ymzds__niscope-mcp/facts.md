# Facts and tags for gh.ymzds/niscope-mcp

Every fact cites its source at commit `75a3a09bb6eab9b1b0dd9e48ecdb30e93bbac6ed`. `vendor_doc` is a text file of
the clone (README.md); `upstream_code` is a code or help-text line of the clone.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package supports the NI PXIe-5160, 5164 and 5110 and states that it requires Windows and NI hardware | vendor_doc | README.md:5 |
| Adaptive sampling raises the sample rate towards 30 times the signal frequency and is capped at 1.25 GS/s | vendor_doc | README.md:9 |
| The hardware backend imports the niscope package | upstream_code | niscope_mcp/backends/direct.py:9 |
| DirectBackend drives real NI oscilloscopes through the niscope API | upstream_code | niscope_mcp/backends/direct.py:20-21 |
| scan_devices opens niscope.Session(name, reset_device=False) for each candidate PXI slot and reads the model, channel count and maximum rates | upstream_code | niscope_mcp/backends/direct.py:31-55 |
| open_device opens niscope.Session(resource_name, reset_device=False) for the selected scope | upstream_code | niscope_mcp/backends/direct.py:57-64 |
| configure_channel writes channel_enabled, vertical_range, vertical_offset, vertical_coupling, probe_attenuation and input_impedance | upstream_code | niscope_mcp/backends/direct.py:88-97 |
| configure_trigger writes the trigger source, level and slope, and configure_horizontal writes min_sample_rate, horz_min_num_pts, horz_num_records, horz_record_ref_position and horz_enforce_realtime | upstream_code | niscope_mcp/backends/direct.py:101-127 |
| read_waveform fetches num_samples and downsamples the time and voltage arrays to at most 2000 points | upstream_code | niscope_mcp/backends/direct.py:137-164 |
| measure_waveform fetches num_samples and returns rounded frequency, period, amplitude, RMS, minimum, maximum, mean, rise time, fall time, duty cycle, sample count and sample rate | upstream_code | niscope_mcp/backends/direct.py:166-191 |
| get_current_config reports the model, the horizontal sample rate, record length and actual sample rate, the trigger source, level and slope, and per-channel enabled, vertical range, offset, coupling, probe attenuation and input impedance | upstream_code | niscope_mcp/backends/direct.py:258-283 |
| ChannelConfig carries vertical_range in Vpp, vertical_offset in V, vertical_coupling AC/DC/GND, probe_attenuation, input_impedance in ohms and bandwidth_filter | upstream_code | niscope_mcp/backends/base.py:20-29 |
| TriggerConfig carries source, level, slope, coupling, holdoff and type | upstream_code | niscope_mcp/backends/base.py:32-49 |
| HorizontalConfig carries min_sample_rate, min_num_pts, num_records, ref_position, enforce_realtime and acquisition_type | upstream_code | niscope_mcp/backends/base.py:52-61 |
| The configure_scope help text names the channel, horizontal and trigger settings and their units | upstream_code | niscope_mcp/__main__.py:381-386 |
| The help text lists vertical_range common values 0.1-50 Vpp, input impedance 50 or 1000000 ohm, and min_sample_rate common values 1e6-1.25e9 S/s | upstream_code | niscope_mcp/__main__.py:1208-1214 |
| main() serves the MCP server over get_backend('direct') | upstream_code | niscope_mcp/__main__.py:1280 |

## Limits

| parameter | rule | source | ref |
|---|---|---|---|
| vertical_range | min 0.1 V, max 50 V | upstream_code | niscope_mcp/__main__.py:1211 |
| probe_attenuation | allowed 1, 10, 100 | upstream_code | niscope_mcp/__main__.py:382 |
| input_impedance | allowed 50, 1000000 Ohm | upstream_code | niscope_mcp/__main__.py:1212 |
| sample_rate | min 1e6 Hz, max 1.25e9 Hz | upstream_code | niscope_mcp/__main__.py:1213 |
| vertical_offset | `Limit.operator_required` | - | no text of the clone states a range |
| trigger_level | `Limit.operator_required` | - | no text of the clone states a range |
| record_length | `Limit.operator_required` | - | no text of the clone states a range |

The operator bounds live only in the site overlay. `site-limits.example.json` is an example of that overlay for
one bench; it is not a statement about any scope.  The vertical range, input impedance and sample-rate values are
the clone's own "common values" cheat-sheet entries, not a laboratory envelope; an operator may narrow them
further.

## Safety

The instrument is a measuring device at R1: it has no laser, motion, pump, heater or centrifuge.  The native stop
`DirectBackend.close_all` closes every acquisition session, and the same method is the e-stop and the teardown.
The clone documents no independent hardware e-stop, so `estop_physical_ref` is not set and no hardware protection
is claimed.  This package is model-authored and unreviewed; the gate exercises the fake backend only.

## Not covered

The waveform sample arrays (`read_waveform` and `auto_measure`) are not exposed: the 0.9 catalogue has no
oscilloscope waveform class.  The scalar `measure_waveform` result and every setting are exposed.  The fake's
waveform methods return a small placeholder array; the real `fetch` defaults to 100000 samples
(direct.py:166-191).

Tags: oscilloscope, ni-scope, pxie, waveform, instrument.
