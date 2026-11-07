# Facts and tags for gh.freespace/pyapt

Every fact cites its source at commit `914a6f618cacce6aa9ce42d371a895989e092b59`: `vendor_doc` (README.md) or
`upstream_code` (a file and line of the clone). The same facts are written into `facts = [...]` in `driver.py`; the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The Controller opens the FTDI device and sets its baud rate to 115200 | upstream_code | pyAPT/controller.py:26-28 |
| The FTDI line is configured for 8 data bits, 1 stop bit and no parity | upstream_code | pyAPT/controller.py:34-37 |
| MTS50, PRM1 and LTS300 are subclasses of Controller that set the stage scales and travel range | upstream_code | pyAPT/mts50.py:4-31 |
| The base Controller defines linear_range as the linear distance range in mm with a conservative (0, 50) default | upstream_code | pyAPT/controller.py:71-73 |
| LTS300 sets its linear range to 0 to 300 mm | upstream_code | pyAPT/lts300.py:31 |
| PRM1 sets its linear range to -180 to 180, the rotation range in degrees | upstream_code | pyAPT/prm1.py:35 |
| status() returns the position and velocity of the controller, and its docstring says those are in mm and mm/s | upstream_code | pyAPT/controller.py:163-169 |
| position() converts the raw encoder count with position_scale and returns the real-world position | upstream_code | pyAPT/controller.py:285-303 |
| goto() raises OutOfRangeError when soft limits are enabled and the target is outside linear_range | upstream_code | pyAPT/controller.py:325-326 |
| move() reads the current position and calls goto() with the relative target | upstream_code | pyAPT/controller.py:358-381 |
| home() reuses the current homing parameters, changes the velocity and offset, sends SET_HOMEPARAMS and MOVE_HOME, and waits for MOVE_HOMED when wait is true | upstream_code | pyAPT/controller.py:245-282 |
| set_soft_limits() sets whether the controller observes range limits in software | upstream_code | pyAPT/controller.py:383-387 |
| set_velocity_parameters() clamps acceleration and maximum velocity to the controller attributes and sends SET_VELPARAMS | upstream_code | pyAPT/controller.py:398-420 |
| velocity_parameters() returns minimum velocity, acceleration and maximum velocity in real-world units | upstream_code | pyAPT/controller.py:422-455 |
| stop() sends MOVE_STOP; immediate true stops immediately, otherwise it stops in a profiled manner, and wait false returns after sending | upstream_code | pyAPT/controller.py:499-530 |
| The upstream README warns that stage limits quoted on the Thorlabs website or user manuals often do not agree with reality and recommends the APT User software limits | vendor_doc | README.md:15-19 |
| reset_parameters() restores the EEPROM defaults and only the BPC30x series appears to support it | upstream_code | pyAPT/controller.py:183-191 |
| keepalive() sends the server-alive message, which must be sent at least once a second over USB | upstream_code | pyAPT/controller.py:532-543 |

## Limits

The driver is generic over the three Controller subclasses, and the stage unit differs: millimetres for MTS50 and
LTS300, degrees for PRM1. The clone states a travel range per subclass (pyAPT/mts50.py:31, pyAPT/lts300.py:31,
pyAPT/prm1.py:35) but no single range for the generic Controller; the upstream README also warns that the quoted stage
limits often differ from reality (README.md:15-19). Position, maximum velocity, acceleration, the relative distance and
the homing `speed_scale` are therefore `Limit.operator_required`: every call that sets one is refused
`MHS.SAFETY.LIMITS_UNSET` until the site supplies the bound of the installed stage. `site-limits.example.json` is an
example overlay, not a statement about any stage. The boolean software-limit switch needs no numeric limit.

The `deceleration` input of `cap.motion.stop.v1` carries no numeric limit because the APT MOVE_STOP message has no
deceleration field (pyAPT/controller.py:499-530): a positive value only selects the controller's profiled stop and zero
or no value selects the immediate stop, so the number is never sent to the device. The stop class's own notes say a
stop must not be rate-limited or permit-gated, and the runtime serves the safe-state action with an empty input.

## Safety

The e-stop sends the native immediate stop, and the safe-state action `cap.motion.stop.v1` sends the native stop with
`wait=False` (`immediate=True` when no deceleration is supplied) (pyAPT/controller.py:499-530). No line of the clone
documents an independent hardware e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045
for this R1 hardware driver. The controller also has a hardware limit-switch status bit
(pyAPT/controller.py:603-608), which the reads expose but the driver does not claim as an independent stop.

## Fake backend

The fake is an in-memory stand-in, not a recording: it does not model the FTDI/USB framing, the binary APT message
sequence, motion kinematics, the controller's own travel-range check or the status bits beyond the values the driver
reads. All starting values and the wide internal range are test data and are marked `# placeholder` in `fake.py`.
This package is model-authored and unreviewed; it was checked on the fake backend only and no hardware was attached or
run.

Tags: thorlabs, apt, motion, stage, usb, ftdi
