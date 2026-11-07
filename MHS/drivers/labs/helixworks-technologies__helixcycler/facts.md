# Facts and tags for gh.helixworks-technologies/helixcycler

Every fact cites its source at commit `29bcd934a8d5289021fb774de17ecdf578ff92f7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| HardwareController is the low-level serial communication class for the Opentrons hardware | upstream_code | tc_send_code.py:6-9 |
| The lid set command is M140 and the plate set command is M104 | upstream_code | tc_send_code.py:14-17 |
| The lid read command is M141 and the plate read command is M105 | upstream_code | tc_send_code.py:15-18 |
| deactivate_all is M18 and the shake set command is M3 | upstream_code | tc_send_code.py:20-22 |
| open_lid is M126 and close_lid is M127 | upstream_code | tc_send_code.py:11-12 |
| Each command is framed by CRLF on both sides | upstream_code | tc_send_code.py:63-64 |
| The controller opens the serial port at 115200 baud with 2 s read and write timeouts | upstream_code | tc_send_code.py:44 |
| get_lid_temperature sends the lid read command and parses the C: field after a T line | upstream_code | tc_send_code.py:92-101 |
| get_plate_info sends the plate read command and parses the C: temperature and H: seconds from a T line | upstream_code | tc_send_code.py:115-124 |
| get_plate_info returns the plate temperature and the seconds left as a two-element list | upstream_code | tc_send_code.py:137 |
| set_lid_temperature appends S and the target to the lid set command | upstream_code | tc_send_code.py:139-140 |
| set_plate_temperature appends S target and optional H duration and V well volume to the plate set command | upstream_code | tc_send_code.py:142-146 |
| set_shake_speed appends S and the target to the shake command | upstream_code | tc_send_code.py:152-153 |
| deactivate_all sends the deactivate-all command | upstream_code | tc_send_code.py:161-162 |
| deactivate_shaker sends the deactivate-shake and deactivate-heating commands | upstream_code | tc_send_code.py:148-150 |
| The controller returns False instead of raising when the serial port cannot be opened | upstream_code | tc_send_code.py:43-49 |
| The GUI emergency stop calls deactivate_all | upstream_code | helixcycler.py:466-471 |
| The HelixShaker deactivate-all button calls deactivate_shaker | upstream_code | helixshaker.py:130-131 |
| The lid target temperature entry accepts 37 to 105 Cel | vendor_doc | README.md:97 |
| The plate target temperature entry accepts 4 to 99 Cel | vendor_doc | README.md:98 |
| The lid heats passively and cools ambiently; it has no active cooling | vendor_doc | README.md:97 |
| Deactivate all stops heating and cooling for both the lid and the plate | vendor_doc | README.md:99 |
| The actual lid and plate temperatures are updated automatically every few seconds while idle | vendor_doc | README.md:101 |
| A STEP hold time is in seconds and a blank hold time means an infinite hold | vendor_doc | README.md:145 |

Limits:

- `lid_setpoint` 37 to 105 Cel (`README.md:97`, the target range of the GUI entry).
- `plate_setpoint` and the `target_temperature` input of `cap.thermal.setpoint.v1` 4 to 99 Cel (`README.md:98`).
- `shake_speed` is `Limit.operator_required`: no text file of the clone states a shake speed range, and the
  controller sends `M3 S<target>` without a readback (`tc_send_code.py:152-153`). The site supplies the range
  (`site-limits.example.json` shows the overlay; its numbers are an example, not a device fact).

Safety: the e-stop and the safe-state action `x-cap.helixworks-technologies.deactivate_all.v1` both call the native
`deactivate_shaker()` (`tc_send_code.py:148-150`: G28 stops the shaker and M106 deactivates heating) and then
`deactivate_all()` (`tc_send_code.py:161-162`: M18, which the GUI emergency stop also sends, `helixcycler.py:466-471`).
The HelixShaker application's deactivate-all button calls `deactivate_shaker()` too (`helixshaker.py:130-131`).
No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the safe-state
action satisfies SAFE-045 for this R2 hardware driver.

Tags: thermocycler, pcr, thermal block, serial, heater, shaker
