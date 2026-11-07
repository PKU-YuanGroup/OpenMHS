# Facts, limits and tags for gh.mattgbiz/velmex-xyz-stagecontrol-python

The clone is one module, `XYZMotion.py`, whose `VXM` class drives a Velmex VXM controller over a serial line. This
package is a direct Driver over that class; the card's SerialDriver cannot reproduce commands assembled from a prefix
and a run-time number ("DEVIATION FROM THE CARD" in RESULT.json).

Every fact cites its source at commit `2e60447742855950c701d5627ee4c232407d633c`: `upstream_code` is a code or
comment line of the clone, `vendor_doc` a text file of it. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| XYZMotion.py is a VXM controller driver for a Velmex XYZ stage | upstream_code | XYZMotion.py:1-8 |
| The module fixes port = 'COM4' and baud = 9600 and gives the serial read a maxWaitTime timeout | upstream_code | XYZMotion.py:13-15 |
| defaultVelocity is 2000 steps/s (the comment says the manual calls 2000 steps/second good) | upstream_code | XYZMotion.py:19 |
| One motor step is 0.0050 mm: stepsTomm = 0.0050 and mmToSteps = 1/0.0050 | upstream_code | XYZMotion.py:20-21 |
| The constructor opens Serial(port, baud, timeout=maxWaitTime) and writes defaultVelocity to the X, Y and Z axes with setVelocity | upstream_code | XYZMotion.py:29-35 |
| home() calls moveToZero for X, Y and Z with a one-second sleep between them and then reads all positions | upstream_code | XYZMotion.py:37-44 |
| sendcmd appends a carriage return and writes the bytes; getresp reads one line and decodes it | upstream_code | XYZMotion.py:48-64 |
| waitReady sends 'V' and repeats until the reply is 'R'; the comment says B is busy, R is ready, J is jog/slew mode and b is jogging | upstream_code | XYZMotion.py:66-79 |
| getPosition asserts the axis is X, Y or Z, reads the reply as [axis, sign, seven digits], applies the sign and converts the steps to millimetres with 0.0050 | upstream_code | XYZMotion.py:84-94 |
| getAllPositions reads X, Y and Z in sequence and converts each reply by 0.0050 mm per step; the English Y value divides by 24.4 while getPosition divides by 25.4 | upstream_code | XYZMotion.py:116-141 |
| setVelocity asserts Speed > 0 and Speed <= 6000 and comments that the motor speed must be in range 1-6000 | upstream_code | XYZMotion.py:155 |
| setVelocity builds 'E,C,S1M<speed>,R', 'E,C,S2M<speed>,R' or 'E,C,S3M<speed>,R' for X, Y or Z | upstream_code | XYZMotion.py:156-167 |
| moveToZero builds 'E,C,IA1M0,R', 'E,C,IA2M0,R' or 'E,C,IA3M0,R' and then waits for ready | upstream_code | XYZMotion.py:171-183 |
| move_mm converts millimetres to steps with mmToSteps, builds 'E,C,I1M<steps>,R', 'E,C,I2M<steps>,R' or 'E,C,I3M<steps>,R' and then waits for ready | upstream_code | XYZMotion.py:185-199 |
| move_in converts inches to steps with inTomm * mmToSteps and builds the same I1M/I2M/I3M command | upstream_code | XYZMotion.py:201-215 |
| The VXM class defines __init__, home, sendcmd, getresp, waitReady, getPosition, getAllPositions, setVelocity, moveToZero, move_mm, move_in and __del__ (which closes the port), and no stop, abort, halt or disable method | upstream_code | XYZMotion.py:27-220 |
| The module creates XYZ = VXM(port, baud, maxWaitTime), homes it, moves each axis and deletes it, so importing XYZMotion performs serial and motion I/O | upstream_code | XYZMotion.py:224-236 |
| The README says the repository has the early coding used to communicate with the VXM controller from Velmex | vendor_doc | README.md:2 |

## Limits

| parameter / input | unit | limit | source |
|---|---|---|---|
| velocity_x (write) | steps/s | 1 to 6000 | upstream_code `XYZMotion.py:155` |
| velocity_y (write) | steps/s | 1 to 6000 | upstream_code `XYZMotion.py:155` |
| velocity_z (write) | steps/s | 1 to 6000 | upstream_code `XYZMotion.py:155` |
| position.x (cartesian_pose) | mm | operator_required: the clone states no X travel or soft limit, only the 0.0050 mm step | operator |
| position.y (cartesian_pose) | mm | operator_required: the clone states no Y travel or soft limit, only the 0.0050 mm step | operator |
| position.z (cartesian_pose) | mm | operator_required: the clone states no Z travel or soft limit, only the 0.0050 mm step | operator |

The velocity bound is the one range the clone states. The three axis travels are not in the clone: the module only
converts steps and millimetres (lines 20-23) and never names a soft limit or a travel. `site-limits.example.json`
supplies an example envelope; it may only narrow, and the operator owns the real one.

## The missing stop path (why this package is blocked)

The whole class is 194 lines (27-220). It defines exactly `__init__`, `home`, `sendcmd`, `getresp`, `waitReady`,
`getPosition`, `getAllPositions`, `setVelocity`, `moveToZero`, `move_mm`, `move_in` and `__del__`
(XYZMotion.py:27-220). There is **no stop, abort, halt, disable or free-run method**, and the only thing `waitReady`
can do is poll the controller with `V` until it reports ready (lines 66-79); that query does not cancel the move.
A move that `moveToZero`, `move_mm` or `move_in` started therefore cannot be cancelled through this library: the
driver contract requires the `@estop` method to reach the real native stop (DRV-012), and no honest implementation of
that exists here. Inventing a VXM stop command (the controller protocol has such a command outside this clone) would
be inventing wire syntax and a fact the clone does not support, so the package is reported blocked instead.

The clone also cannot be imported safely: the module executes `XYZ = VXM(port, baud, maxWaitTime)`, `XYZ.home()`,
`XYZ.move_in('X', 1)`, `XYZ.move_in('Y', 2)`, `XYZ.move_in('Z', 2.5)` and another `XYZ.home()` at import
(lines 224-236). Any `from XYZMotion import VXM` opens COM4 and moves the stage. For that reason this package does not
ship a hardware backend and declares only the fake backend; the gate never imports the clone.

`getAllPositions` divides the English Y position by 24.4 while `getPosition` divides by 25.4 (lines 94 and 140), so
its `english_units=True` result is inconsistent. The driver publishes millimetres only and does not expose the
English-unit path.

## Safety

* No safe state is reachable through this library (no stop, abort, halt or disable command); the physical stop of
  the controller/bench and the lab's own measures stay authoritative.
* Hardware is never attached in the acceptance run; the package has no hardware backend and nothing in it ran on a
  device.
* `driver.lock.json` `reviewed_by` is null: the package is model-authored and unreviewed.

## Tags

velmex, vxm, xyz stage, stepper, serial, motion, positioner
