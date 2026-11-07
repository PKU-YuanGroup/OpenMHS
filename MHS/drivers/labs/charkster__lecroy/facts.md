# Facts and tags for gh.charkster/lecroy

Every fact cites its source at commit `da08c5168d8c63809d60b4c8b4b3529cbaf3de18`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The class wraps a pyvisa instrument object passed to its constructor | upstream_code | lecroy.py:7-10 |
| get_screen_image writes a PNG screenshot to a file and returns its byte count | upstream_code | lecroy.py:15-27 |
| A screen image accepts the backcolor 'WHITE' or 'BLACK' | upstream_code | lecroy.py:16 |
| trigger_setup takes the trigger channel, level, horizontal offset, slope and mode | upstream_code | lecroy.py:29-36 |
| The trigger channel is a scope channel such as 'C1' or 'D1' | upstream_code | lecroy.py:32 |
| The trigger slope is 'Positive', 'Negative' or 'Either' | upstream_code | lecroy.py:35 |
| The trigger mode is 'Single', 'Normal', 'Auto' or 'Stopped' | upstream_code | lecroy.py:36 |
| trigger_setup writes the VBS trigger commands and sets Trigger.Type to Edge | upstream_code | lecroy.py:41-46 |
| get_trigger_setup returns the channel, level, horizontal offset, slope, mode and trigger type under keys 0 to 5 | upstream_code | lecroy.py:61-68 |
| get_analog_channel_setup returns the label, vertical scale, vertical offset, bandwidth limit and coupling of channels 1 to 8 | upstream_code | lecroy.py:170-182 |
| get_digital_channel_setup returns the label of each enabled digital channel 0 to 15 | upstream_code | lecroy.py:184-190 |
| get_measurement_setup reads measurement slots P1 to P12 and returns each source and parameter | upstream_code | lecroy.py:262-269 |
| getValueOnChannel reads value, mean, max, min, num and sdev as a float and status as text | upstream_code | lecroy.py:296-310 |
| setGrid accepts Single, Dual, Quad, Octal, Tandem, Quattro or Auto | upstream_code | lecroy.py:312-318 |
| setHorizontal_delay writes the horizontal offset in Horizontal.HorOffset | upstream_code | lecroy.py:320-321 |
| reset_scope sends *RST | upstream_code | lecroy.py:323-324 |
| trigger_force sends FORCE_TRIGGER | upstream_code | lecroy.py:192-194 |
| get_horizontal_scale reads Horizontal.HorScale | upstream_code | lecroy.py:200-202 |
| The README describes the class as configuration, measurement and screen capture for a LeCroy oscilloscope | vendor_doc | README.md:5 |

Limits:

| parameter or input | limit | source and ref |
|---|---|---|
| trigger_slope (write and the trigger action input) | one of Positive, Negative, Either | upstream_code, lecroy.py:35 |
| trigger_mode (write and the trigger action input) | one of Single, Normal, Auto, Stopped | upstream_code, lecroy.py:36 |
| assigned_channel (measure action input) | one of P1 to P12, the measurement slots the clone loops over | upstream_code, lecroy.py:262-269 |
| stat_type (measure action input) | one of value, mean, max, min, num, sdev, the numeric keys of the clone's measurement map | upstream_code, lecroy.py:296-302 |
| grid_mode (grid action input) | one of Single, Dual, Quad, Octal, Tandem, Quattro, Auto | upstream_code, lecroy.py:315 |
| horizontal_scale (write) | operator_required: the clone states only the method default 1E-3 s (lecroy.py:196), not the scale range of the instrument | operator, site-limits.example.json |
| trigger_level (write and the trigger action input) | operator_required: the clone states no trigger level range (lecroy.py:33) | operator, site-limits.example.json |
| trigger_horizontal_offset (write and the trigger action input) | operator_required: the clone states no horizontal offset range (lecroy.py:34) | operator, site-limits.example.json |

Safety: the e-stop calls `reset_scope`, which sends `*RST` (lecroy.py:323-324). The instrument returns to its
power-on defaults and any trigger or acquisition configuration is cleared. The clone has no other stop command and
no hardware stop input; at R1 no independent hardware stop is required. The display intensity, memory size,
date/time and channel-colour setters are not exposed: the clone has no getter for them, so a write could not be
read back.

NOT COVERED: the screen image (``get_screen_image`` writes a PNG file; lecroy.py:15-27). No catalogue class carries
an image array for an instrument, and the clone writes to a local path.

Tags: oscilloscope, lecroy, scpi, vbs, visa, instrument
