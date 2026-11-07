# Facts and tags for gh.beniroquai/opentrons-microscope-platereader

This package covers the serial controller class `PYTHON.opentrons_neje_laser2_controler:pyGraver` at commit
`867f54163da7e8d17db1e6aac0bbdb0105905f22`. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| pyGraver opens the controller's serial port at 57600 baud | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:32 |
| A three-byte command is sent as 0xFF followed by the three command bytes | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:67 |
| A command array is sent as 0xFF followed by the array | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:74 |
| A reply is read up to the 0x55 terminator | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:128 |
| Byte 2 of a reply selects the parser: 8 upload info, 11 status, 14 carving progress, 16 after upload | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:136-143 |
| A carving-progress reply carries a percentage in byte 6 and stores it in carvingPercentProgress | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:158-169 |
| moveXY sends an absolute XY target with each coordinate split into high and low bytes | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:195-200 |
| setPWD sends the laser power p and the idle value i as single bytes | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:205-209 |
| stopCarving sends the stop-carving frame 0xAA 0x08 0x02 0x01 0x01 0x02 0x55 | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:211-215 |
| pauseCarving sends the pause frame 0xAA 0x08 0x02 0x01 0x01 0x00 0x55 | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:217-221 |
| MAX_WIDTH and MAX_HEIGHT are 490 | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:15-16 |
| The class starts with location at [MAX_WIDTH//2, MAX_HEIGHT//2] | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:33 |
| The module-level test block opens pyGraver on COM7 and runs a 10 by 10 move loop when the module is imported | upstream_code | PYTHON/opentrons_neje_laser2_controler.py:239-257 |

## Limits

Every numeric action input is `Limit.operator_required`: the clone states the byte width of each field but not the
travel range or the laser settings of the machine. The site supplies the bounds in `site-limits.json`
(`site-limits.example.json` shows the shape; its numbers are examples, not device limits).

| capability | input | why the clone cannot bound it |
|---|---|---|
| x-cap.beniroquai.move_xy.v1 | x, y | each coordinate is encoded in two bytes (line 198-199); the clone states no travel range |
| x-cap.beniroquai.set_laser.v1 | power, idle | each byte is sent in the setPWD frame (line 209); the clone states no optical power range |

## Safety

The clone does not state a laser class. The controller drives a laser output, and the Grbl laser documentation in
the clone warns that lasers can cause fires and permanently damage vision
(`ARDUINO/library/grbl-master/doc/markdown/laser_mode.md:3`). The device is declared R3, above the card's R1
floor: no text of the clone states the laser class, but an engraving laser burns material, which only a class 4
source does (a model review raised it from R2; MHS/spec/04-safety.md).

The native stop is `stopCarving` (line 211-215); the same frame is the safe-state action
`x-cap.beniroquai.stop_carving.v1`. The catalogue class `cap.motion.stop.v1` is not bound: its optional
deceleration field has no counterpart in the upstream stop frame, so the stop is an extension with no input. The
clone documents no independent hardware emergency stop for this controller, so there
is no `estop_physical_ref`; the package relies on the safe-state action and the runtime latch. The stop frame only
asks the controller to stop; the driver cannot read back a confirmation (the clone parses carving progress, not a
stop acknowledgement).

The upstream module opens a serial port in its module-level test block (line 240), so `native.py` executes only
the class definition and the constants it uses, not the block. This was not run on hardware.

Tags: laser, engraver, neje, serial, motion
