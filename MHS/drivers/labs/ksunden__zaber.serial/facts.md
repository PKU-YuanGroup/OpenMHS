# Facts and tags for gh.ksunden/zaber.serial

Every fact cites its source at commit `4bd9e1103f6a057fd376edcdf574251637465fba`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a path of the clone and a line). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a library for controlling Zaber devices over a serial port | vendor_doc | README.rst:4 |
| AsciiAxis represents one axis of an ASCII device; the axis number is 1-9 | upstream_code | zaber/serial/ascii.py:22 |
| AsciiAxis.send sends an AsciiCommand through the parent device and checks that the reply came from this axis | upstream_code | zaber/serial/ascii.py:82-90 |
| home() sends the 'home' command and then polls the axis until it is idle | upstream_code | zaber/serial/ascii.py:92-105 |
| move_abs(position) sends 'move abs <position>' where position is an integer in microsteps, then polls until idle | upstream_code | zaber/serial/ascii.py:107-128 |
| move_rel(distance) sends 'move rel <distance>' where distance is an integer number of microsteps, then polls until idle | upstream_code | zaber/serial/ascii.py:130-151 |
| move_vel(speed) sends 'move vel <speed>' with an integer speed and returns immediately unless blocking is true | upstream_code | zaber/serial/ascii.py:153-179 |
| stop() sends the 'stop' command and polls until idle; the stop command pre-empts a movement command | upstream_code | zaber/serial/ascii.py:181-197 |
| get_status() returns the reply device status, which is either 'BUSY' or 'IDLE' | upstream_code | zaber/serial/ascii.py:199-210 |
| get_position() sends 'get pos' and returns the reply data, described as the absolute position in microsteps | upstream_code | zaber/serial/ascii.py:212-218 |
| poll_until_idle() blocks until the device reports that the axis is idle | upstream_code | zaber/serial/ascii.py:220-231 |
| AsciiDevice.address is 1-99 and axis(number) returns a new AsciiAxis for an axis number of 1-9 | upstream_code | zaber/serial/ascii.py:407-434 |
| AsciiSerial(port, ...) opens the serial port when the constructor is called | upstream_code | zaber/serial/ascii.py:839-855 |
| AsciiCommand.encode builds the protocol frame '/<device address> <axis number> [<message id>] <data>' terminated by CRLF | upstream_code | zaber/serial/ascii.py:347-376 |

## Limits

The clone gives no travel range, no speed range and no unit for the speed of ``move_vel``; the docstrings of
``move_abs`` (lines 112-113), ``move_rel`` (lines 135-136) and ``move_vel`` (lines 158-159) name only an integer
native value. No line of the clone states a force limit either. Every numeric motion input is therefore
``Limit.operator_required``:

| input | limit |
|---|---|
| ``x-cap.ksunden.move_abs.v1`` ``position`` | operator-required: the site supplies the travel of the installed stage |
| ``x-cap.ksunden.move_rel.v1`` ``distance`` | operator-required: the site supplies the permitted relative travel |
| ``x-cap.ksunden.move_vel.v1`` ``speed`` | operator-required: the site supplies the safe native speed range |

Until an operator overlay fills them, the runtime refuses every such call with ``MHS.SAFETY.LIMITS_UNSET``.
``site-limits.example.json`` supplies example numbers for the gate and for an operator to copy; those numbers are
placeholders, not a statement about any stage.

## Units

Positions and relative distances are integer microsteps (the clone's own word) and are exposed with the
dimensionless unit ``1``, because the clone names no conversion from microsteps to a length. ``move_vel`` takes an
integer native speed; the clone names neither a unit nor a range, so it is also exposed with unit ``1`` and a
description that says the unit is unnamed.

## Safety

The e-stop is the native ``AsciiAxis.stop()`` command (``zaber/serial/ascii.py:181-197``). The
``x-cap.ksunden.stop.v1`` action is declared ``safe_state=True`` and calls the same native stop. The declared safe
state is "axis motion stopped by the native stop command". No line of the clone documents an independent hardware
e-stop, so this package sets no ``estop_physical_ref`` and claims no hardware protection; the runtime latch and the
software stop command are all it provides. The package is model-authored and unreviewed and was checked on the fake
backend only.

Tags: zaber, serial, ascii, motion, axis
