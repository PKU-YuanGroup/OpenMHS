# Facts and tags for gh.gridinwork/ai-oscilloscope-isds205b

Every fact cites its source at commit `cb1bdda97869e5c897d742d6008a8a359128a61a`. `upstream_code` is a line of the
clone's Python code; `vendor_doc` is a text file of the clone (README or docs). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Scope is the high-level handle to one ISDS205B; the class docstring says it is not thread-safe | upstream_code | instrustar/device.py:154-155 |
| CaptureResult carries ch1 and ch2 sample arrays, the sample rate, requested and actual lengths in KB, elapsed time, out-of-range flags and a timestamp | upstream_code | instrustar/device.py:75-84 |
| capture() raises ScopeError when Capture() returns zero or less or when IsDataReady times out, and the returned CaptureResult reports the actual capture length in KB | upstream_code | instrustar/device.py:293-329 |
| set_channel_range takes channel 0 for CH1 and 1 for CH2 and a min/max range in mV | vendor_doc | docs/ISDS205B_PROTOCOL.md:55 |
| The module docstring says SetOscChannelRange silently clamps to the widest internal gain step and get_voltage_resolution should be read after a range request | upstream_code | instrustar/device.py:15-17 |
| The live support list of this unit has five discrete sample rates: 1000000, 4000000, 8000000, 16000000 and 48000000 Hz | vendor_doc | docs/ISDS205B_PROTOCOL.md:59 |
| set_sample_rate returns the applied rate and raises ScopeError when the device returns 0 | upstream_code | instrustar/device.py:248-253 |
| get_sample_rate reads the rate the device reports | upstream_code | instrustar/device.py:255-257 |
| This unit has no hardware trigger: IsSupportHardTrigger returned 0 in the live test | vendor_doc | docs/ISDS205B_PROTOCOL.md:67 |
| The trigger modes are AUTO=0 and CONTINUOUS=1 | upstream_code | instrustar/device.py:41-43 |
| Trigger styles are the bitmask values NONE=0x0000, RISE_EDGE=0x0001, FALL_EDGE=0x0002, EDGE=0x0004, POS_PULSE_MORE=0x0008, POS_PULSE_LESS=0x0010, POS_PULSE=0x0020, NEG_PULSE_MORE=0x0040, NEG_PULSE_LESS=0x0080 and NEG_PULSE=0x0100 | upstream_code | instrustar/device.py:46-56 |
| Trigger source 0 selects CH1 and 1 selects CH2; the trigger level is in mV | vendor_doc | docs/ISDS205B_PROTOCOL.md:70-71 |
| The pre-trigger percent range is 5 to 95 percent | vendor_doc | docs/ISDS205B_PROTOCOL.md:74 |
| AC coupling is a documented no-op on this unit; GetAcDc always reads back DC | upstream_code | instrustar/device.py:13-14 |
| The DDS waveform styles are SINE=0x00, SQUARE=0x01, TRIANGULAR=0x02, UP_SAWTOOTH=0x03 and DOWN_SAWTOOTH=0x04 | upstream_code | instrustar/device.py:59-65 |
| DDS style-select and output-enable were confirmed on this unit; frequency and duty-cycle accuracy is unverified and the DLL has no Get counterpart | upstream_code | instrustar/device.py:331-334 |
| generator_enable writes DDSOutputEnable and is_generator_enabled reads IsDDSOutputEnable | upstream_code | instrustar/device.py:357-363 |
| set_generator applies the waveform style, frequency and duty cycle to the DDS | upstream_code | instrustar/device.py:343-355 |
| has_hard_trigger, has_dds, has_io, has_roll_mode and has_pretrigger_percent return the device support flags | upstream_code | instrustar/device.py:204-217 |
| memory_length_kb returns the capture memory depth in KB | vendor_doc | docs/ISDS205B_PROTOCOL.md:60 |
| The clone says grounding between CH1, CH2 and USB is not confirmed isolated and the GUI defaults to a conservative +/-5 V range | vendor_doc | README.md:192-196 |
| DDS amplitude and offset software trim is not supported on this unit | upstream_code | instrustar/device.py:22-23 |

Limits: the sample rate is the five-rate live list (`docs/ISDS205B_PROTOCOL.md:59`); the DDS waveform styles and the
trigger mode/style/source values cite the upstream enums; the pre-trigger percentage is 5 to 95
(`docs/ISDS205B_PROTOCOL.md:74`). The trigger level and the channel input range are `Limit.operator_required`: no line
of the clone states a bound for them, the range silently clamps, and the grounding is not confirmed isolated, so
`site-limits.example.json` supplies example operator bounds and every write that sets them waits for the site overlay.

Safety: the e-stop disables the DDS output (`Scope.generator_enable(False)`, `instrustar/device.py:357-359`). No
independent hardware e-stop is documented in the clone, and the package is R1 (the task card's floor); SAFE-045's
physical-stop requirement applies at R2 and R3.

Tags: oscilloscope, usb, isds205b, instrustar, waveform, dds, voltage measurement
