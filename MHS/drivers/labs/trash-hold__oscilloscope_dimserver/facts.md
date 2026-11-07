# Facts and tags for gh.trash-hold/oscilloscope_dimserver

Every fact cites its source at commit `6a34db58756fc0ac7ef8d4021bc290973d5cb65f`: `vendor_doc` (a
text file of the clone such as readMe.md) or `upstream_code` (`path/in/clone.py:LINE`). The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository README describes a system for controlling an oscilloscope with a ready-to-use driver for the Tektronix TDS3054C | vendor_doc | readMe.md:19-23 |
| The TDS3054C class is the repository's oscilloscope driver; it connects to the scope's HTTP server over an AF_INET TCP socket | upstream_code | zmq_server/drivers/TDS3054C.py:35-39 |
| test_connection queries *IDN? and accepts the device only when the reply contains 'TDS 3054C' | upstream_code | zmq_server/drivers/TDS3054C.py:121-127 |
| Every command is an HTTP POST to /Comm.html whose body is COMMAND=<command>&gpibsend=Send | upstream_code | zmq_server/drivers/TDS3054C.py:419-429 |
| set_channel accepts only channels 1 to 4 and writes DATA:SOURCE CH<n> | upstream_code | zmq_server/drivers/TDS3054C.py:141-145 |
| set_channel_state writes SELECT:CH<n> ON or OFF | upstream_code | zmq_server/drivers/TDS3054C.py:223-227 |
| set_vertical_scale writes CH<n>:SCAle and set_vertical_position writes CH<n>:POSition | upstream_code | zmq_server/drivers/TDS3054C.py:233-245 |
| set_horizontal_scale writes HORizontal:MAIn:SCAle and set_horizontal_position writes HORizontal:MAIn:POSition | upstream_code | zmq_server/drivers/TDS3054C.py:251-263 |
| get_horizontal_increment queries WFMPre:XINcr? and returns the device reply | upstream_code | zmq_server/drivers/TDS3054C.py:269-275 |
| The Slope enum allows only the values RISE and FALL | upstream_code | zmq_server/drivers/TDS3054C.py:9-11 |
| set_trigger_slope writes TRIGger:A:EDGE:SLOpe only for the two Slope values | upstream_code | zmq_server/drivers/TDS3054C.py:287-291 |
| set_trigger_level writes TRIGger:A:LEVel | upstream_code | zmq_server/drivers/TDS3054C.py:279-282 |
| set_trigger_channel accepts only channels 1 to 4 and writes TRIGger:A:EDGE:SOUrce CH<n> | upstream_code | zmq_server/drivers/TDS3054C.py:300-302 |
| sample stops the current acquisition, arms a single sequence, starts ACQ:STATE ON and polls BUSY? until 0 | upstream_code | zmq_server/drivers/TDS3054C.py:367-405 |
| SELECT? may return the channel states followed by CONTROL CH<n>, which names the selected waveform | upstream_code | zmq_server/drivers/TDS3054C.py:193-198 |

Limits: the only bounded settings in the clone are the channel numbers (1 to 4, validated in
`set_channel` and `set_trigger_channel`) and the trigger slope values (`RISE`/`FALL`). Every other
numeric setting is `Limit.operator_required`: the clone writes the value without validating or
stating a range, and no text file of the clone supplies one. Those writes are refused
`MHS.SAFETY.LIMITS_UNSET` until the operator's `site-limits.json` supplies a range
(`site-limits.example.json` shows the overlay).

Safety: the e-stop and the safe-state action `x-cap.trash-hold.stop_acquisition.v1` both write
`ACQ:STATE STOP` through the native `write` method (TDS3054C.py:376). The clone documents no
independent hardware e-stop, so `estop_physical_ref` is not set. This package is R1: SAFE-045 (an
independent stop for R2+) does not apply, and the loader does not refuse the R1 hardware backend
of an unreviewed model-written package; no hardware run was performed.

Not covered: the waveform array from `get_waveform` (`CURVE?`, TDS3054C.py:310-365). No catalogue
class carries a scope trace and the clone states no record length, so this package covers the
scalar settings and readbacks only.

Tags: oscilloscope, scope, tektronix, tds3054c, instrument
