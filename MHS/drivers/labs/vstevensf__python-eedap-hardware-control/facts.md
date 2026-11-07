# Facts and tags for gh.vstevensf/python-eedap-hardware-control

Every fact cites its source at commit `a4f9f918b6908eac7305cc4aa55f7a32bcc86e6b`: `vendor_doc` for a text file of
the clone or `upstream_code` for a code line or span.  The same facts are in `driver.py`; `REFERENCE.md` is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is titled Integrate_Microscope_eeDAP | vendor_doc | README.md:1 |
| The README says the rough drafts were written while creating the hardware control for the Prior ProScan III controller | vendor_doc | README.md:40 |
| The README's folder structure places proscan.py in hardware_control/prior_stage/ and base_stage.py in hardware_control/ | vendor_doc | README.md:11-21 |
| The README says PriorStage talks to the ProScan III controller through PySerial in messages composed of bytes and points at section 4 of the controller manual | vendor_doc | README.md:48 |
| The README says move_to accepts xy coordinates in JSON format and converts them to the byte string the controller understands | vendor_doc | README.md:50 |
| The README says its instructions run the test script in Python 3.8.10 in a virtual environment | vendor_doc | README.md:55 |
| BaseStage is an abstract class whose only abstract methods are move_to(delta) and close() | upstream_code | app/hardware_control/base_stage.py:8-30 |
| base_stage.py says BaseStage is based on the OpenFlexure base stage class and the Python-Microscope ProScanIII class | upstream_code | app/hardware_control/base_stage.py:5-8 |
| proscan.py appends the parent of its own folder to sys.path and then imports BaseStage from a top-level base_stage module | upstream_code | app/hardware_control/proscan.py:6-14 |
| proscan.py says _PriorConnection is based on the _ProScanIII connection of Python-Microscope | upstream_code | app/hardware_control/proscan.py:16-18 |
| proscan.py says PriorStage is also based on the _ProScanIII class of Python-Microscope and inspired by its Stage class | upstream_code | app/hardware_control/proscan.py:143-147 |
| PriorStage extends BaseStage and creates a _PriorConnection from the port in __init__ | upstream_code | app/hardware_control/proscan.py:147-150 |
| The serial connection is opened at 9600 baud with eight data bits, one stop bit, no parity, xonxoff, rtscts and dsrdtr off and timeout=3 | upstream_code | app/hardware_control/proscan.py:26-36 |
| The connection handshake writes '?' and requires the reply 'PROSCAN INFORMATION\r', then reads until '\rEND\r' | upstream_code | app/hardware_control/proscan.py:40-56 |
| A connection write appends a carriage return to the data | upstream_code | app/hardware_control/proscan.py:71-73 |
| validate_response writes a command, reads one reply with the serial timeout raised to ten times its value and prints the reply | upstream_code | app/hardware_control/proscan.py:79-84 |
| When the reply matches no expected response, validate_response prints a meaning for the replies E,1 to E,5 and E,8, calls read_until_timeout() and raises RuntimeError | upstream_code | app/hardware_control/proscan.py:85-115 |
| move_to reads x and y from the mapping, writes str() of each into b'G ' + x + b',' + y, prints the goal and passes the command to validate_response expecting b'R\r' | upstream_code | app/hardware_control/proscan.py:152-175 |
| A None x or y raises MissingCoordinate, which move_to catches and only prints | upstream_code | app/hardware_control/proscan.py:152-178 |
| The PriorStage class defines only __init__, move_to and close; it has no position query, stop, halt or abort method | upstream_code | app/hardware_control/proscan.py:147-186 |
| close() calls the connection's close() and prints 'Successfully closed'; a bare except only prints that the serial port cannot be closed | upstream_code | app/hardware_control/proscan.py:180-186 |
| The example test script is run as 'python move_stage_tester.py' and imports PriorStage from a top-level proscan module | upstream_code | app/hardware_control/move_stage_tester.py:1-4 |
| The example test script opens PriorStage('COM4'), calls move_to with -100000 and 100000 and then close() | upstream_code | app/hardware_control/move_stage_tester.py:10-19 |
| The Flask app constructs PriorStage('COM4') and moves to (-100000, -100000) and then (100000, 100000) on a request to /stage_test, and runs with debug=True on host 0.0.0.0 | upstream_code | app/hardware_control/app.py:11-31 |
| The Dockerfile copies app.py, proscan.py, base_stage.py and check_ports.py into the image root and runs app.py | upstream_code | app/hardware_control/Dockerfile:3-11 |
| The upstream requirements list pyserial==3.5 | upstream_code | app/hardware_control/requirements.txt:3 |
| The Micro-Manager configuration names a Prior XYStage on port COM4 with BaudRate 9600 and AnswerTimeout 500.0000 | upstream_code | micromanager_files/MMConfig_priorstage.cfg:8-15 |

## Shape and limits

The selected entry is the concrete `app.hardware_control.proscan:PriorStage` (proscan.py:147), whose interface is
`move_to(delta)` and `close()`; `BaseStage` is only its abstract parent (base_stage.py:8-30).  The card's hints
name `move_abs` and `move_rel`, but those methods belong to a mock PriorStage in the rough drafts, which only
sleeps and updates a Python list (`app/hardware_control/miscellaneous_rough_drafts/prior.py:127-164`); the
selected class does not have them, and this package does not import or call the draft.  The card's candidate class
`cap.motion.joint_position.v1` is specified in radians and a named joint order, while the clone states no unit or
axis convention for `move_to`; the package therefore uses the extension `x-cap.vstevensf.move_xy.v1` and serves
the native coordinate values as UCUM `1`, which stands for the unstated unit, not for a dimensionless quantity.

The driver sends each coordinate as a float, so the upstream writes, for example, `G 10.0,-20.0`
(proscan.py:163-169); the upstream's own test sends integers (move_stage_tester.py:15-16), and the clone does not
say whether the controller accepts a decimal point.  A reply other than `R` raises RuntimeError after the command
was written (proscan.py:79-115); the driver reports it `unknown` (`MHS.OUTCOME.UNKNOWN`), because the controller
may have accepted the move and the clone has no position query.  Errors of the serial library (outside the clone)
propagate as `failed`, although one raised after the write leaves the motion just as unknown.

No text file of the clone states the stage's coordinate unit, travel range, maximum speed or homing behaviour.
The README only calls the values xy coordinates (README.md:50), and the example test script uses unlabelled
values (move_stage_tester.py:15-16).  Both action inputs are therefore `Limit.operator_required`; without an
operator overlay every move is refused `MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` is an illustrative
overlay for this package, not a device bound; its numbers are the operator's example and must be replaced with the
installed stage's measured envelope.

## Safety and the blocked e-stop

The class has no stop, abort, halt, position query or motion status (proscan.py:147-186), and no file of the clone
sends a stop command (the rough drafts, the Micro-Manager remnants and the stale bytecode included).  `close()`
closes the serial connection (proscan.py:180-186); it sends no stop command, and a `G` move already sent can
continue.  The `@estop` calls `close()` (the only native shutdown) and then raises
`MHS.SAFETY.SAFE_STATE_UNREACHED`; the runtime latches, does not report an achieved safe state and retries the
e-stop in the background, about once a second on the fake, and every retry calls `close()` again (which prints,
proscan.py:184).  `estop_terminal` separates the upstream facts (close() only closes the port; only a new
PriorStage opens one) from the package policy (the driver never reopens the port inside an endpoint): every reset
after the e-stop is refused `terminal_estop`, and a new endpoint is the only recovery.  There is no `@reset` and no
re-enable action.  The clone names the ProScan III manual only by URL (proscan.py:95), so no stop can be shown
without hardware or a source outside the clone; the model review records the block as `NO_HARDWARE_FREE_PATH`
(the author proposed `HELPER_MISSING`, but no SDK helper would supply a stop).  The package does not claim a
physical e-stop, a hardware run or any protection beyond the runtime latch.

## Fake and coverage

`fake.py` defines only the native public surface `move_to(delta)`, `close()` and the BaseStage attributes `port` and
`lock`.  It is an in-memory stand-in, not a recording: its move timing, port and recorded target are placeholders,
it models no stage physics and it does not stop an in-flight move on `close()`.  Two failure paths follow the
upstream's shape: a reply other than `R` (the private `_reply`) raises RuntimeError after the move is counted as
written, as validate_response does (proscan.py:79-115), and a move after `close()` raises OSError, a placeholder
for the serial library's error on a closed port.  It proves the contract shape only.
The real serial transport and pyserial were not exercised; the controller's motion, the actual coordinate unit and
travel, the external ProScan III manual and every hardware path were not exercised, and the manual was not read.
No hardware was attached and no upstream code was imported or run.

## Install and licence

The card's install block is empty (no Python pin, no commands).  The upstream README documents Python 3.8.10
(README.md:55) and `app/hardware_control/requirements.txt:3` lists pyserial==3.5; a hardware deployment must provide
that dependency, but `native.py` is never imported by the gate.

`native.py` puts `app/hardware_control/` on `sys.path` and imports the top-level `proscan` module, as the clone's
own scripts do (move_stage_tester.py:1-4, app.py:3).  proscan.py appends the parent of its own folder before it
imports `base_stage` (proscan.py:6-14); that parent held base_stage.py in the README's layout (README.md:11-21), but
at the pin it is `app/`, so importing `app.hardware_control.proscan` from the clone root, as the author's factory
did, fails with `No module named 'base_stage'`.  The factory refuses to go on when `proscan` or `base_stage` would
be loaded from another file.  The model review checked it on stand-in files that copy only those import lines,
never against the clone, pyserial or a controller.  The upstream prints every move goal, every reply and every
close result (proscan.py:84, 172, 184, 186), which would corrupt an MHS server that talks over standard input and
output.

The card records licence `NOASSERTION` and the clone has no licence file.  proscan.py and base_stage.py say they
are based on Python-Microscope and OpenFlexure code (proscan.py:16-18, 143-147; base_stage.py:5-8); the licences of
those projects are not in the clone.  The card requires a publication review: the owner decides, and this package
makes no publication or licence claim.

## Other code in the clone

A Flask app moves the stage to (-100000, -100000) and then (100000, 100000) on any request to `/stage_test` and
runs with `debug=True` on host 0.0.0.0 (app.py:11-31); the Dockerfile starts it (Dockerfile:3-11).  It drives the
same controller outside this driver.  The rough drafts hold the mock PriorStage above and raw serial tests that send
`COMP 0`, `G` and `Z` (miscellaneous_rough_drafts/test.py:18-35); `micromanager_files/` and `CoreLogs/` are
remnants of a Micro-Manager attempt (README.md:33); `grasshopper_cam_usb/` is where future scripts for the Point
Grey Grasshopper cameras will live (README.md:38), a different device that this package does not serve.

Tags: prior, proscan-iii, xy-stage, microscope-stage, serial, eedap.
