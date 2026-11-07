"""OpenMHS driver for gh.vstevensf/python-eedap-hardware-control: a Prior ProScan III XY stage.

A direct Driver (decorated methods) over the upstream class
``app.hardware_control.proscan:PriorStage``.  The upstream interface is one absolute move:

* ``move_to(delta)`` reads ``x`` and ``y`` from a mapping, builds ``b'G ' + x + b',' + y`` and sends it through
  ``_PriorConnection.validate_response`` (proscan.py:152-175).  The method returns after the expected ``b'R\\r'``
  reply; an unexpected reply raises ``RuntimeError`` (proscan.py:88-115).
* ``close()`` closes the serial connection (proscan.py:180-186).

The class has no position query, no stop, abort or halt method and no motion status (proscan.py:147-186), and the
clone states no coordinate unit or travel range.  The action is therefore an extension in the controller's own
coordinate unit, which the clone does not state (served as UCUM ``1``, not a claim that it is dimensionless), with
both coordinates ``Limit.operator_required``: every move is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site's
overlay supplies the installed stage's envelope.

A genuine e-stop is not expressible.  The only native shutdown is ``close()``, which closes the serial link and
sends no stop command; a move already sent can continue.  The ``@estop`` calls that shutdown and then raises
``MHS.SAFETY.SAFE_STATE_UNREACHED`` so the runtime does not report a safe state that was not reached.  This is why
the package is blocked: the upstream has no stop command, so no stop can be shown without hardware or a source
outside the clone, and no SDK helper would supply one.  No hardware was attached, no upstream code was imported or
run, and this package is model-authored and unreviewed (reviewed_by is null).

The upstream prints every move goal, every reply and the result of close() with print() (proscan.py:84, 172, 184,
186): an MHS server that talks over standard input and output would receive those lines in its protocol stream.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop

X_REASON = (
    "no text file of the clone states the stage's coordinate unit or x travel range; the README only calls the "
    "move_to values xy coordinates (README.md:50) and the example test script uses unlabelled coordinates "
    "(move_stage_tester.py:15-16), so the site supplies the installed stage's x envelope")
Y_REASON = (
    "no text file of the clone states the stage's coordinate unit or y travel range; the README only calls the "
    "move_to values xy coordinates (README.md:50) and the example test script uses unlabelled coordinates "
    "(move_stage_tester.py:15-16), so the site supplies the installed stage's y envelope")


class ProScanStage(Driver):
    device_id = "prior-proscan"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "app.hardware_control.proscan:PriorStage"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePriorStage"}
    vendor, model = "Prior", "ProScan III"
    display_name = "Prior ProScan III XY stage (app.hardware_control.proscan:PriorStage)"
    tags = ["prior", "proscan-iii", "xy-stage", "microscope-stage", "serial", "eedap"]
    facts = [
        Fact("The repository is titled Integrate_Microscope_eeDAP", source="vendor_doc", ref="README.md:1"),
        Fact("The README says the rough drafts were written while creating the hardware control for the Prior "
             "ProScan III controller", source="vendor_doc", ref="README.md:40"),
        Fact("The README's folder structure places proscan.py in hardware_control/prior_stage/ and base_stage.py in "
             "hardware_control/", source="vendor_doc", ref="README.md:11-21"),
        Fact("The README says PriorStage talks to the ProScan III controller through PySerial in messages composed "
             "of bytes and points at section 4 of the controller manual", source="vendor_doc", ref="README.md:48"),
        Fact("The README says move_to accepts xy coordinates in JSON format and converts them to the byte string "
             "the controller understands", source="vendor_doc", ref="README.md:50"),
        Fact("The README says its instructions run the test script in Python 3.8.10 in a virtual environment",
             source="vendor_doc", ref="README.md:55"),
        Fact("BaseStage is an abstract class whose only abstract methods are move_to(delta) and close()",
             source="upstream_code", ref="app/hardware_control/base_stage.py:8-30"),
        Fact("base_stage.py says BaseStage is based on the OpenFlexure base stage class and the Python-Microscope "
             "ProScanIII class", source="upstream_code", ref="app/hardware_control/base_stage.py:5-8"),
        Fact("proscan.py appends the parent of its own folder to sys.path and then imports BaseStage from a "
             "top-level base_stage module", source="upstream_code", ref="app/hardware_control/proscan.py:6-14"),
        Fact("proscan.py says _PriorConnection is based on the _ProScanIII connection of Python-Microscope",
             source="upstream_code", ref="app/hardware_control/proscan.py:16-18"),
        Fact("proscan.py says PriorStage is also based on the _ProScanIII class of Python-Microscope and inspired "
             "by its Stage class", source="upstream_code", ref="app/hardware_control/proscan.py:143-147"),
        Fact("PriorStage extends BaseStage and creates a _PriorConnection from the port in __init__",
             source="upstream_code", ref="app/hardware_control/proscan.py:147-150"),
        Fact("The serial connection is opened at 9600 baud with eight data bits, one stop bit, no parity, xonxoff, "
             "rtscts and dsrdtr off and timeout=3", source="upstream_code",
             ref="app/hardware_control/proscan.py:26-36"),
        Fact("The connection handshake writes '?' and requires the reply 'PROSCAN INFORMATION\\r', then reads "
             "until '\\rEND\\r'", source="upstream_code", ref="app/hardware_control/proscan.py:40-56"),
        Fact("A connection write appends a carriage return to the data", source="upstream_code",
             ref="app/hardware_control/proscan.py:71-73"),
        Fact("validate_response writes a command, reads one reply with the serial timeout raised to ten times its "
             "value and prints the reply", source="upstream_code", ref="app/hardware_control/proscan.py:79-84"),
        Fact("When the reply matches no expected response, validate_response prints a meaning for the replies E,1 "
             "to E,5 and E,8, calls read_until_timeout() and raises RuntimeError", source="upstream_code",
             ref="app/hardware_control/proscan.py:85-115"),
        Fact("move_to reads x and y from the mapping, writes str() of each into b'G ' + x + b',' + y, prints the "
             "goal and passes the command to validate_response expecting b'R\\r'", source="upstream_code",
             ref="app/hardware_control/proscan.py:152-175"),
        Fact("A None x or y raises MissingCoordinate, which move_to catches and only prints", source="upstream_code",
             ref="app/hardware_control/proscan.py:152-178"),
        Fact("The PriorStage class defines only __init__, move_to and close; it has no position query, stop, halt "
             "or abort method", source="upstream_code", ref="app/hardware_control/proscan.py:147-186"),
        Fact("close() calls the connection's close() and prints 'Successfully closed'; a bare except only prints "
             "that the serial port cannot be closed", source="upstream_code",
             ref="app/hardware_control/proscan.py:180-186"),
        Fact("The example test script is run as 'python move_stage_tester.py' and imports PriorStage from a "
             "top-level proscan module", source="upstream_code",
             ref="app/hardware_control/move_stage_tester.py:1-4"),
        Fact("The example test script opens PriorStage('COM4'), calls move_to with -100000 and 100000 and then "
             "close()", source="upstream_code", ref="app/hardware_control/move_stage_tester.py:10-19"),
        Fact("The Flask app constructs PriorStage('COM4') and moves to (-100000, -100000) and then (100000, 100000) "
             "on a request to /stage_test, and runs with debug=True on host 0.0.0.0", source="upstream_code",
             ref="app/hardware_control/app.py:11-31"),
        Fact("The Dockerfile copies app.py, proscan.py, base_stage.py and check_ports.py into the image root and "
             "runs app.py", source="upstream_code", ref="app/hardware_control/Dockerfile:3-11"),
        Fact("The upstream requirements list pyserial==3.5", source="upstream_code",
             ref="app/hardware_control/requirements.txt:3"),
        Fact("The Micro-Manager configuration names a Prior XYStage on port COM4 with BaudRate 9600 and "
             "AnswerTimeout 500.0000", source="upstream_code",
             ref="micromanager_files/MMConfig_priorstage.cfg:8-15"),
    ]
    safe_state = ("serial connection closed; this driver can send no further command, but a move already sent "
                  "may continue because the clone has no stop command")
    estop_terminal = ("Upstream: PriorStage.close() only closes the serial port and sends no stop command "
                      "(proscan.py:180-186), and only constructing a new PriorStage opens a port (proscan.py:147-150, "
                      "25-36). Package policy: this driver never reopens the port inside an endpoint, so a new "
                      "endpoint, which repeats the connection handshake (proscan.py:40-56), is the only recovery. A "
                      "move already sent is not stopped; the clone has no stop, abort or position query.")

    @action(
        name="x-cap.vstevensf.move_xy.v1",
        risk="R1",
        description="Move the Prior ProScan III stage to an absolute XY coordinate with the native G command",
        input={
            "x": Field("number", unit="1",
                       description="Absolute x coordinate in the controller's own unit; the clone states no unit",
                       limit=Limit.operator_required(X_REASON)),
            "y": Field("number", unit="1",
                       description="Absolute y coordinate in the controller's own unit; the clone states no unit",
                       limit=Limit.operator_required(Y_REASON)),
        },
        output={
            "x": Field("number", unit="1",
                       description="X coordinate sent to the controller in its own unit"),
            "y": Field("number", unit="1",
                       description="Y coordinate sent to the controller in its own unit"),
        },
    )
    def move_xy(self, x, y):
        """Send the absolute G move and return the values sent.

        move_to writes ``str()`` of each value into the command (proscan.py:163-169), so the floats sent here read,
        for example, ``G 10.0,-20.0``; the upstream's own test sends integers (move_stage_tester.py:15-16), and the
        clone does not say whether the controller accepts a decimal point.  validate_response raises RuntimeError
        only after it has written the command and read something other than ``R`` within its read timeout (ten
        times timeout=3; proscan.py:29, 79-115): the controller may have accepted the move, so the outcome is
        unknown, not failed.  Other errors (raised by the serial library, outside the clone, possibly after the
        command was written) propagate and are reported failed.
        """
        target = {"x": float(x), "y": float(y)}
        try:
            self.native.move_to(target)
        except RuntimeError as exc:
            detail = " ".join(str(exc).split())
            raise OutcomeUnknown(
                "the G command was written but the controller's reply was not R (proscan.py:79-115); the stage may "
                f"be moving or have moved and the clone has no position query: {detail}") from None
        return target

    @estop(native="close")
    def stop(self):
        """The only native shutdown is close(); it does not stop a move, so the safe state is not reached."""
        self.native.close()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "PriorStage.close() closes the serial connection (proscan.py:180-186) and sends no stop command; "
            "the clone has no stop, abort, halt or position query, so an in-flight move cannot be stopped or "
            "confirmed",
        )

    def teardown(self):
        """Close the serial connection with the upstream close() (proscan.py:180-186)."""
        self.native.close()
