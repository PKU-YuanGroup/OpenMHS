# Facts and tags for gh.roesel/elliptec

Every fact cites its source at commit `5f86ca595f80397bca280347830339c832a7b0bc`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Shutter.get_slot() asks the motor for its position and converts the pulse position to a slot number | upstream_code | src/elliptec/shutter.py:20-24 |
| Shutter.set_slot(1) moves the slider backward and set_slot(2) moves it forward; any other slot value returns None without a move | upstream_code | src/elliptec/shutter.py:26-38 |
| Shutter.open() selects slot 2 and Shutter.close() selects slot 1 when the shutter was not created inverted; inverted=True swaps the two | upstream_code | src/elliptec/shutter.py:50-60 |
| Shutter.is_open() and Shutter.is_closed() compare the current slot with 2 and 1, swapped when the shutter was created inverted | upstream_code | src/elliptec/shutter.py:62-68 |
| pos_to_slot computes the slot as position / (range / (slots - 1)) + 1 from the slot count the device database holds for the motor type | upstream_code | src/elliptec/shutter.py:82-87 |
| The device database lists ELL6 as a Dual-Position Slider with 2 slots at positions 0 and 31 | upstream_code | src/elliptec/devices.py:5-12 |
| Shutter.jog(direction) accepts only 'forward' and 'backward' | upstream_code | src/elliptec/shutter.py:40-47 |
| Motor.home() moves the motor with the clockwise or anticlockwise homing command | upstream_code | src/elliptec/motor.py:93-98 |
| The movement instruction table maps 'home_clockwise' to ho0, 'home_anticlockwise' to ho1, 'forward' to fw, 'backward' to bw, 'absolute' to ma and 'relative' to mr | upstream_code | src/elliptec/cmd.py:20-27 |
| Motor.load_motor_info() queries the 'info' response when the object is created and stores the motor range, pulses per revolution, serial number and motor type | upstream_code | src/elliptec/motor.py:31-43 |
| The controller composes a command from the bus address, the instruction bytes and an optional signed 32-bit big-endian hex argument | upstream_code | src/elliptec/controller.py:115-138 |
| The README homes the shutter before use and opens and closes it with open() and close() | vendor_doc | README.md:48-53 |
| The README lists the Dual-Position Slider (ELL6) as useful as a shutter | vendor_doc | README.md:141 |

Limits: one, on the `slot` input of `x-cap.roesel.move_to_slot.v1`: 1 to 2, from
`src/elliptec/shutter.py:26-38`, where `Shutter.set_slot` moves for slot 1 and slot 2 only and returns None for any
other value. It is the only numeric write or invoke input of the package; the open/close action takes the catalogue
`state` enum and the other two actions take no input.

Safety: the e-stop and the safe-state action `x-cap.roesel.close_shutter.v1` both call the native `Shutter.close`
(`src/elliptec/shutter.py:56-60`), which blocks the optical path. No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware
driver. The runtime reads `is_open`/`is_closed`/`slot` from the device through `Shutter.get_slot`
(`src/elliptec/shutter.py:20-24`).

Not exposed: `Shutter.jog`, the relative and absolute moves of `Shutter.move`, and the motor's jog step, home offset,
address and frequency settings. Whether the shutter was created inverted is a hardware-factory option (`native.py`),
so the driver reports the raw slot and the open/closed state of the object. The hardware factory was never run: the
package is checked on the fake backend only.

Tags: shutter, beam-block, optical-path, elliptec, thorlabs, slider
