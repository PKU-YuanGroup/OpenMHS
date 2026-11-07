# Facts and tags for gh.veerwang/octoaxes

Every fact cites the clone at commit `77cb47e0fdf83bde33c85d24be4d4b3723e74e15`.  The same facts and
limits are written into `driver.py`; `reference.json` and `REFERENCE.md` are generated from the driver,
not from this page.

| fact | source | ref |
|---|---|---|
| The host application reaches the controller over USB serial at 115200 baud | vendor_doc | README.md:18 |
| SerialThread opens the port with pyserial, a 0.1 s read timeout and a 0.5 s write timeout | upstream_code | software/common/hardware/serial_thread.py:123-125 |
| A string command is framed as 0x55, 0xAA, the UTF-8 command text and a newline | upstream_code | software/common/hardware/serial_thread.py:335 |
| A binary command is prefixed with 0x02 and its last byte is a CRC-8-CCITT of the preceding bytes | upstream_code | software/common/hardware/serial_thread.py:382-383 |
| The 24-byte status packet starts with cmd_id and status and carries X, Y, Z and W as big-endian int32 positions in bytes 2 to 17 | upstream_code | firmware/octoaxes/serial.cpp:139-164 |
| The host parses the 24-byte packet as X/Y/Z/W big-endian int32 and treats status 1 as moving | upstream_code | software/common/gui/main_window.py:1018-1027 |
| MOVETO_X, MOVETO_Y and MOVETO_Z are command ids 6, 7 and 8, and SET_AXIS_DISABLE_ENABLE is 32 | upstream_code | software/common/define.py:75-115 |
| SET_PORT_ILLUMINATION is command id 37 and TURN_OFF_ALL_PORTS is command id 39 | upstream_code | software/common/define.py:122-124 |
| An absolute move carries a signed int32 microstep target in payload bytes 2 to 5, converted from micrometres as position / 1000 / mm_per_step | upstream_code | software/common/gui/main_window.py:1220-1235 |
| The X travel is -10 to 115000 micrometres and the Y travel is -10 to 76000 micrometres | upstream_code | software/octoaxes/constants.py:55-72 |
| The five illumination ports D1 to D5 have port indexes 0 to 4 | upstream_code | software/octoaxes/constants.py:199-205 |
| The illumination control is a 0 to 100 percent slider and the host scales a percentage to a 0 to 65535 DAC value | upstream_code | software/common/gui/widgets.py:891-1167 |
| SET_PORT_ILLUMINATION writes the port, a 16-bit intensity and the on/off byte | upstream_code | firmware/octoaxes/commandprocessor.cpp:261-265 |
| SET_AXIS_DISABLE_ENABLE with byte 3 equal to 0 de-energises the addressed axis | upstream_code | firmware/octoaxes/commandprocessor.cpp:517-524 |
| TURN_OFF_ALL_PORTS switches every illumination port off | upstream_code | firmware/octoaxes/commandprocessor.cpp:278-280 |

Limits:

| parameter | limit | ref |
|---|---|---|
| x_um (um) | -10 to 115000 | software/octoaxes/constants.py:55 |
| y_um (um) | -10 to 76000 | software/octoaxes/constants.py:72 |
| intensity (%) | 0 to 100 | software/common/gui/widgets.py:891 |

Z is reported as a raw microstep count, not a length: the screw pitch depends on the
`Z_AXIS_VARIANT` switch (software/octoaxes/constants.py:16), so converting it would assume one of the
two configured variants.

Safety: the e-stop and the `x-cap.veerwang.safe_state.v1` action call the native stop, which de-energises
the X, Y, Z, W and Turret axes and switches all illumination ports off.  The package is model-authored
and unreviewed; the acceptance evidence is the fake backend only, never a hardware run.

Device shape: the card named the SerialDriver family, but the upstream command is an 8-byte binary
payload with a CRC-8 frame added by SerialThread, so the driver is a direct Driver over
`hardware.serial_thread:SerialThread`.

Tags: microscope, stage, motion, illumination, serial, teensy
