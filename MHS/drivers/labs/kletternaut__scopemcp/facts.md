# Facts and tags for gh.kletternaut/scopemcp

Every fact cites its source at commit `a932b777694d7bfc48c821c3afef7e3eb2da3f0e`: `vendor_doc` (a text file of the
clone such as README.md or doc/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The DS1102 connects over USB in PC mode with VID 0x5345 and PID 0x1234; USBTMC mode (PID 1235) is not supported | vendor_doc | doc/INSTALL.md:7-10 |
| The physical layer is USB bulk transfer with OUT endpoint 0x01 and IN endpoint 0x81 | vendor_doc | doc/ds1102_protocol.md:11-14 |
| Every command is prefixed with a 4-byte little-endian length header and ends with a line feed | upstream_code | ds1102_mcp.py:84-91 |
| Replies are read from the IN endpoint with dev.read | upstream_code | ds1102_mcp.py:117-121 |
| Metadata is fetched with :DATA:WAVE:SCREEN:HEAD? and parsed as the JSON between the first '{' and the last '}' | upstream_code | ds1102_mcp.py:144-148 |
| get_measurements reads FREQUENCE, SCALE, COUPLING, DISPLAY and OFFSET from each CHANNEL entry | upstream_code | ds1102_mcp.py:212-227 |
| The firmware OFFSET is an integer raw value from the metadata JSON, not volts | upstream_code | ds1102_logic.py:21-22 |
| The device transfers 1520 samples per channel (3040 bytes plus a 4-byte header) in SCREEN mode | vendor_doc | README.md:103 |
| The vertical scale command is :CH<channel>:SCALe <scale> | upstream_code | ds1102_mcp.py:365 |
| The horizontal scale command is :HORizontal:SCALe <scale> | upstream_code | ds1102_mcp.py:376 |
| The coupling command is :CH<channel>:COUPling <coupling> and the tool accepts AC, DC and GND | upstream_code | ds1102_mcp.py:381-390 |
| The offset command is :CH<channel>:OFFSet <offset> written with three decimals | upstream_code | ds1102_mcp.py:402 |
| The trigger mode is written with :TRIGger:SWEep and accepts AUTO, NORMAL and SINGLE | upstream_code | ds1102_mcp.py:407-417 |
| The trigger slope is written with :TRIGger:EDGE:SLOpe and accepts RISE and FALL | upstream_code | ds1102_mcp.py:421-431 |
| The trigger source is written with :TRIGger:EDGE:SOURce and accepts CH1 and CH2 | upstream_code | ds1102_mcp.py:435-445 |
| The trigger level is written with :TRIGger:EDGE:LEVel in mV with one decimal | upstream_code | ds1102_mcp.py:449-456 |
| Autoset sends :AUToset on | upstream_code | ds1102_mcp.py:335-342 |
| The run state is written with :run or :stop | upstream_code | ds1102_mcp.py:346-353 |
| The firmware always reports TRIG in the status field, even when stopped | vendor_doc | README.md:95 |
| The command throttle is 0.05 s | upstream_code | ds1102_mcp.py:35 |
| send_cmd sleeps 0.1 s after SCAL, HOR, TRIG or OFFS and 1.0 s after AUT | upstream_code | ds1102_mcp.py:110-115 |

Limits: the coupling, trigger mode, trigger slope and trigger source allowed sets are written in the clone
(`ds1102_mcp.py:382`, `409`, `423`, `437`). The vertical scale, horizontal scale, channel-1 offset and trigger level
have no complete bound in the clone: the README only gives examples (`README.md:30` and `33`), and no text file states
a numeric offset or trigger-level range. Those four writes are `Limit.operator_required`; every write is refused
`MHS.SAFETY.LIMITS_UNSET` until the site overlay supplies the scale spellings and the numeric windows of its unit.
`site-limits.example.json` is an example overlay, not a statement about any instrument.

Safety: the instrument observes and configures its observation; the package is R0. The native stop (`:stop` via
`send_cmd`, `ds1102_mcp.py:351-352`) is both the e-stop and the safe-state action `x-cap.kletternaut.stop_acquisition.v1`.
The clone documents no hardware emergency stop, so `estop_physical_ref` is not set. The upstream class has no close
method, so the driver has no teardown hook.

NOT COVERED: the waveform array from `:DATA:WAVE:SCREEN:CH1?`/`:CH2?` (1520 signed 16-bit samples per channel, 3040
bytes plus the 4-byte header), its voltage conversion, channel-2 settings, the screenshot/frame buffer and the USB
reconnect logic. The scalar metadata and the settings are served instead. The fake returns placeholder metadata, not a
recording of an instrument.

Tags: oscilloscope, ds1102, usb, pyusb, scpi
