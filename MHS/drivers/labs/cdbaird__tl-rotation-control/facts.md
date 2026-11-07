# Facts and tags for gh.cdbaird/tl-rotation-control

Every fact cites its source at commit `759dc3fc58efd975c37c7ee954fa6152618cd58e`: `upstream_code` is a line of the
clone, and `vendor_doc` is a text file of the clone. The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream controller drives a Thorlabs Elliptec rotation stage | vendor_doc | README.md:2 |
| Motor is a pyserial Serial subclass; its constructor opens the port and calls _get_motor_info | upstream_code | elliptec/rotation.py:8-24 |
| The information query is get_['info'] = b'in' | upstream_code | elliptec/cmd.py:3 |
| The motor information reply carries Motor Type, Serial No., Year, Firmware, Thread, Hardware, Range and Pulse/Rev | upstream_code | elliptec/helper.py:34-43 |
| The conversion factor is Range / Pulse/Rev | upstream_code | elliptec/rotation.py:22-24 |
| deg_to_hex uses the integer factor counts_per_rev // range and writes eight hexadecimal digits | upstream_code | elliptec/rotation.py:78-81 |
| A get_ query, a set_ setting and a do_ move are an address digit, a two-letter instruction and optional data | upstream_code | elliptec/rotation.py:28-76 |
| get_ and set_ store the parsed reply in Motor.status instead of returning it | upstream_code | elliptec/rotation.py:44-76 |
| A position reply is a PO or BO code and a 32-bit hexadecimal field | upstream_code | elliptec/helper.py:46-48 |
| s32 interprets the position field as a signed 32-bit integer | upstream_code | elliptec/helper.py:74-75 |
| A status reply is a GS code and a hexadecimal error code | upstream_code | elliptec/helper.py:50-52 |
| Error code 0 is Status OK, 5 is Module Isolated and 12 is Out of Range | upstream_code | elliptec/errcodes.py:2-17 |
| The stepsize query instruction is 'gj' and the setting instruction is 'sj' | upstream_code | elliptec/cmd.py:6-12 |
| The parser returns the code and data field of a reply that is not IN, PO, BO or GS | upstream_code | elliptec/helper.py:54-55 |
| The move commands are home 'ho', forward 'fw', backward 'bw', absolute 'ma' and relative 'mr' | upstream_code | elliptec/cmd.py:14-20 |
| The upstream GUI bounds the step-size slider to 1 to 359 degrees | upstream_code | td_gui.py:109-110 |
| The upstream GUI bounds the step-size spin box to 1 to 359 degrees | upstream_code | td_gui.py:128-129 |
| The upstream GUI labels the field Step Size (deg) | upstream_code | td_gui.py:202 |
| The upstream GUI sets both motors' step size from the slider value through deg_to_hex | upstream_code | main.py:13-16 |
| On slider release the upstream GUI writes the slider value through deg_to_hex and reads it back | upstream_code | main.py:66-72 |
| The upstream isolate action puts a motor in isolation with set_('isolate', '01') | upstream_code | main.py:56-58 |

Limits:

| parameter | command | limit | source | ref |
|---|---|---|---|---|
| position (deg) | ma | operator_required: the travel range is the Range field the motor reports at connect (elliptec/rotation.py:22-24), not a constant in the clone; the site overlay supplies the allowed angles | operator | site-limits.example.json |
| step_size (deg) | sj | 1 to 359 | upstream_code | td_gui.py:109-110 |

The step-size bound is the range of the upstream GUI control (td_gui.py:109-110), the only numeric bound on the
step-size control in the clone. The position bound is not stated as a number anywhere in the clone: the motor
reports a Range and a Pulse/Rev at connect, and the conversion is derived from them. Until an operator supplies the
range in `site-limits.json`, every position write is refused with `MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop sends `set_('isolate', '01')`, which puts the module in isolation (elliptec/cmd.py:11,
elliptec/errcodes.py:8, main.py:56-58). There is no hardware e-stop in the vendor text to cite and none is required
at R1. This package is model-authored and unreviewed, and no hardware backend was run.

The driver is a direct `Driver` rather than the card's `SerialDriver`: every command is assembled at run time from
an address digit, a two-letter instruction and a hexadecimal data field (elliptec/rotation.py:28-76), which a
command table cannot reproduce.

Tags: rotation stage, elliptec, thorlabs, serial, motion, homing, isolate
