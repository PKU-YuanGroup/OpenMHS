"""OpenMHS driver for gh.simonmeersschaut/stagecontroller: a Phytron stepper over a framed serial protocol.

A direct Driver over the upstream class ``stage:Serial``.  The card names a ``SerialDriver``, but the upstream
transport frames every request as STX (0x02), the address byte ``'0'``, the ASCII command and ETX (0x03), and the
upstream script writes the commands ``XS``, ``XL+`` and ``X0-`` from its ``__main__`` block (stage.py:73-75,
82-99).  A line-oriented SerialDriver cannot reproduce that frame or the address byte, so this package sends the
bare commands through the upstream ``send`` method, which owns the framing and the reply read.  The hardware
backend is ``native.py``; the gate runs only the fake backend.

* one extension action starts the rotation with ``XL+`` (stage.py:98-100);
* a second extension action stops it with ``XS`` (stage.py:93-97); it is also the safe-state action the runtime
  runs after an e-stop;
* the e-stop sends the same ``XS`` stop command through the upstream ``send``.

No catalogue class fits: ``cap.motion.stop.v1`` is the only stop class, and it exposes a ``deceleration`` input
that the upstream ``XS`` command does not take (stage.py:93-97).  The upstream command has no numeric input, so
both actions are extensions and the package declares no Limit.

Every Fact cites a line of the clone at the pinned commit 7edb1ac137a0cfedba78966815421fbfd5e73b38.  The package is
model-authored and unreviewed; nothing here was tried on a controller.
"""

from mhs.driver import Driver, Fact, Field, action, estop


class StageController(Driver):
    device_id = "stagecontroller"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "stage:Serial"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeStage"}
    vendor = "Phytron"
    model = "stepper motor controller"
    display_name = "StageController (Phytron stepper over serial)"
    tags = ["stage", "stepper", "motion", "phytron", "serial"]
    facts = [
        Fact("The script toggles a Phytron stepper motor on the press of a button", source="vendor_doc",
             ref="README.md:3"),
        Fact("The serial line is /dev/ttyUSB0 at 9600 baud, no parity, eight data bits and one stop bit",
             source="upstream_code", ref="stage.py:25-31"),
        Fact("A request is framed as STX (0x02), the address byte '0', the ASCII command and ETX (0x03)",
             source="upstream_code", ref="stage.py:73-75"),
        Fact("A reply is the bytes between STX (0x02) and ETX (0x03)", source="upstream_code",
             ref="stage.py:58-67"),
        Fact("The script sends XS once when it starts", source="upstream_code", ref="stage.py:82"),
        Fact("The script stops the motor with XS, waits one second, then sends X0-", source="upstream_code",
             ref="stage.py:93-97"),
        Fact("The script starts the motor with XL+ and marks it as rotating", source="upstream_code",
             ref="stage.py:98-100"),
        Fact("The button that toggles the rotation is wired to GPIO 2", source="upstream_code",
             ref="stage.py:84"),
        Fact("The README points to the Phytron PhyLogic manual for the serial commands", source="vendor_doc",
             ref="README.md:10-11"),
    ]
    safe_state = "stepper stopped (XS sent to the controller)"

    @action(name="x-cap.simonmeersschaut.start_rotation.v1",
            description="Start the stepper rotation by sending the upstream XL+ command",
            output={"started": Field("boolean", description="True once the XL+ command was sent")})
    def start_rotation(self):
        self.native.send("XL+")
        return {"started": True}

    @action(name="x-cap.simonmeersschaut.stop_rotation.v1", safe_state=True,
            description="Stop the stepper by sending the upstream XS stop command",
            output={"stopped": Field("boolean", description="True once the XS command was sent")})
    def stop_rotation(self):
        self.native.send("XS")
        return {"stopped": True}

    @estop(native="send")
    def stop(self):
        """The native stop: send the upstream XS command through the framed transport."""
        self.native.send("XS")
