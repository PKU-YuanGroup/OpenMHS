# Facts, limits and tags for gh.quantumquadrate/k10cr1

The clone is one module, `K10CR1/k10cr1.py`, a driver for a Thorlabs K10CR1 motorized rotation stage over the
Thorlabs APT protocol on a serial (FTDI) port. This package is a direct Driver over that class; the card's
SerialDriver cannot express the framed APT bytes ("DEVIATION FROM THE CARD" in RESULT.json).

Every fact cites its source at commit `2ffdc284da575e525f96ef27b99e5e260bbe415d`: `upstream_code` is a code or
docstring line of the clone, `vendor_doc` a text file of it. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The class is the Thorlabs K10CR1 rotation stage driver | upstream_code | K10CR1/k10cr1.py:6-7 |
| The constructor takes the serial number, searches the serial ports for that device, and zeroes the backlash when the connection succeeded | upstream_code | K10CR1/k10cr1.py:9-18 |
| connect() scans every serial port and matches the device by the serial number inside the port description, then opens the port at 115200 baud with a 0.1 s timeout | upstream_code | K10CR1/k10cr1.py:20-33 |
| The FTDI chip of the controller has VID:PID 0403:faf0 according to the comment of connect() | upstream_code | K10CR1/k10cr1.py:27-29 |
| The class converts an angle to its encoder unit as angle * 24576000 / 180 and back as counts * 180 / 24576000 | upstream_code | K10CR1/k10cr1.py:35-39 |
| The protocol commands are fixed byte frames written as hex text, for example the homing frame '430401005001' and the jog frame '6a0401015001' | upstream_code | K10CR1/k10cr1.py:150-152, 180-182 |
| home() writes the homing frame and reads 6 bytes of response | upstream_code | K10CR1/k10cr1.py:150-152 |
| moverel() and moveabs() assemble the frame from the header, the channel word '0100' and the 4-byte encoder position; they do not read a response | upstream_code | K10CR1/k10cr1.py:154-170 |
| jog() writes the jog frame and reads 20 bytes of response | upstream_code | K10CR1/k10cr1.py:180-182 |
| getpos() writes the position query frame, reads 12 bytes, takes the last 4 as the position and returns degrees rounded to three decimals | upstream_code | K10CR1/k10cr1.py:184-189 |
| identify() only writes the information frame and returns the byte count of the serial write, not an identity | upstream_code | K10CR1/k10cr1.py:147-148 |
| zerobacklash() writes the backlash parameter with the position of 0 degrees | upstream_code | K10CR1/k10cr1.py:172-177 |
| The clone README describes the repository as a Thorlabs K10CR1 rotation stage python driver | vendor_doc | README.md:2 |
| The clone's own test opens the stage by serial number and makes a relative move of -10 degrees | vendor_doc | test.py:3-4 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| position (read) | deg | none declared | - |
| move_absolute angle | deg | operator_required: no text file of the clone states the travel range; the class only converts degrees to encoder counts (k10cr1.py:35-39) | operator |
| move_relative delta | deg | operator_required: same reason | operator |

The clone states no travel limits, no velocity, no acceleration and no soft limits: the operator overlay in
`site-limits.example.json` supplies the allowed angle range of one bench.

## The missing stop path (why this package is blocked)

The whole module is 189 lines and defines exactly these methods: `__init__`, `connect`, `angle_to_DU`, `DU_to_angle`,
`dth`, `btd`, `htb`, `rd`, `write`, `identify`, `home`, `moverel`, `moveabs`, `zerobacklash`, `jog`, `getpos`
(K10CR1/k10cr1.py:9-189). There is **no stop, abort, halt, disable, close or free-run command**, and the class never
reads the device status or the moving state. A move that `moverel` or `moveabs` started cannot be cancelled through
this library: the driver contract requires the `@estop` method to reach the real native stop (DRV-012), and no honest
implementation of that exists here. Inventing an APT stop frame (the protocol has a stop command outside this clone)
would be inventing wire syntax and a fact the clone does not support, so the package is reported blocked instead.

`identify()` cannot serve as an identity check either: it returns the byte count of `serial.write`, not an identity
(k10cr1.py:147-148).

## Safety

* No safe state is reachable through this library (no stop, abort or disable command); the physical button of the
  stage/controller and the lab's own measures stay authoritative.
* Hardware is never attached in the acceptance run; the package's hardware backend (`native.py`) was never opened.

## Tags

rotation stage, motor, thorlabs, k10cr1, apt, serial, motion
