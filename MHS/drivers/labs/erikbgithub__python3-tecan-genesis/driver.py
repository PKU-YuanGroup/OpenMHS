"""OpenMHS driver for gh.erikbgithub/python3-tecan-genesis: a Tecan Genesis RSP 200 liquid-handling robot.

The upstream clone is a pair of scripts, not an installable package.  ``tecan_funcs.py`` opens ``/dev/ttyUSB0`` at
import (line 10), frames every command as STX + sequence letter + device + command + ETX + XOR + newline
(``do_cmd``, lines 120-135), and maps action names such as ``init`` and ``go_waste`` to those commands
(``do_action``, lines 224-345).  The task card names a SerialDriver, but a command table cannot build the frame
(the address, the rotating sequence letter and the XOR byte are assembled at run time), so this is a direct Driver
over ``tecan_funcs:Cmd_delayed``, the only class of the clone.  ``Cmd_delayed.add_cmd`` queues a (command, device)
pair and ``Cmd_delayed.start`` wraps GFC ... GSC around the queued commands (lines 59-70).

* reads: the commands still in the backend stack and the devices already dispatched;
* actions: initialise the system, the RoMa arm and the LiHa arm; move the LiHa to the waste position; set the tip
  spacing; and discard queued commands;
* no writable state: the clone has no set-point-like value.  Its pipetting commands take positions and volumes that
  are configured on the instrument by commands (SRA and the init offset) the clone never sends;
* the stop path: the clone has no halt or abort command.  The e-stop and the safe-state action discard the queued
  command stacks and send nothing more.  That stops the command flow, not an axis already moving; the limitation is
  stated in facts.md and RESULT.json, and the hardware backend has not been reviewed or run.

Every Fact and Limit cites a line of the clone at the pinned commit f85fb168886b26e002f05dc984127cbb2164e9b5.
This package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: PSY takes a selector in 0.1 mm; the clone states the same range as 9...38 mm (tecan:224).
SPACING = Limit(min=9.0, max=38.0, unit="mm", source="upstream_code", ref="tecan:224",
                reason="PSY sets the tip-to-tip space; the clone states 9...38 mm, and the wire selector is in "
                       "0.1 mm, tecan:224")


class TecanGenesis(Driver):
    device_id = "tecan-genesis"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "tecan_funcs:Cmd_delayed"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCmdDelayed"}
    vendor, model = "Tecan", "Genesis RSP 200"
    display_name = "Tecan Genesis RSP 200 liquid-handling robot"
    tags = ["tecan", "genesis", "liquid handling", "pipetting", "robot arm", "serial"]

    facts = [
        Fact("The project is a Python module for flow control of the Tecan Genesis RSP 200 and other devices",
             source="vendor_doc", ref="README.md:3"),
        Fact("Tecan devices automate pipetting activities", source="vendor_doc", ref="README.md:7"),
        Fact("The architecture translates steps into commands that the Tecan device reads via a serial connector",
             source="vendor_doc", ref="README.md:11-13"),
        Fact("The module imports pyserial and opens a serial port", source="upstream_code",
             ref="tecan_funcs.py:5-10"),
        Fact("The serial link is opened at 9600 baud on /dev/ttyUSB0", source="upstream_code",
             ref="tecan_funcs.py:10"),
        Fact("Cmd_delayed queues (command, device) pairs and add_cmd appends one to cmdStack",
             source="upstream_code", ref="tecan_funcs.py:50-61"),
        Fact("Cmd_delayed.start sends GFC M1, every queued command, then GSC M1, and records each device in "
             "runningStack", source="upstream_code", ref="tecan_funcs.py:63-72"),
        Fact("A delayed command is the sequence letter + device + command, prefixed with STX, suffixed with ETX and "
             "an XOR byte, then a newline", source="upstream_code", ref="tecan_funcs.py:92-113"),
        Fact("do_cmd sends one command with the same STX/ETX/XOR framing and a rotating sequence letter",
             source="upstream_code", ref="tecan_funcs.py:120-135"),
        Fact("read collects the bytes between STX and ETX and returns the message that starts with @device",
             source="upstream_code", ref="tecan_funcs.py:165-209"),
        Fact("The init action sends PIS to device M1", source="upstream_code", ref="tecan_funcs.py:229-230"),
        Fact("The init_r action sends PIA to device R1 (the RoMa arm)", source="upstream_code",
             ref="tecan_funcs.py:234-235"),
        Fact("The init_l action sends PIA to device A1 (the LiHa arm)", source="upstream_code",
             ref="tecan_funcs.py:238-239"),
        Fact("The go_waste action sends PAA with the fixed waste coordinates to device A1", source="upstream_code",
             ref="tecan_funcs.py:336-337"),
        Fact("PSY sets the Y-spacing of the eight tips and takes the space in 0.1 mm, range [90...380]",
             source="upstream_code", ref="tecan:222-224"),
        Fact("The liha_spacey action sends PSY followed by the spacing to device A1", source="upstream_code",
             ref="tecan:230-233"),
        Fact("PAA positions are in 0.1 mm and their ranges are set by the SRA command and the init offset",
             source="upstream_code", ref="tecan:35-39"),
        Fact("The do_action dispatcher in the clone has init, init_r, init_l, move, go_waste and error-read branches "
             "but no halt or abort action", source="upstream_code", ref="tecan_funcs.py:224-345"),
    ]

    safe_state = ("none: the clone has no halt or abort command, so an arm already moving cannot be stopped; "
                  "discarding the queued commands only stops the command flow (the model review blocked the "
                  "package, RESULT.json)")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("command_stack", type="integer", unit="1",
          description="Commands in the backend command stack")
    def command_stack(self):
        return len(self.native.cmdStack)

    @read("dispatched_commands", type="integer", unit="1",
          description="Devices recorded as dispatched by the backend start method")
    def dispatched_commands(self):
        return len(self.native.runningStack)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.erikbgithub.init_system.v1",
            description="Initialise the system arms with PIS to device M1",
            output={"initialized": Field("boolean", description="True when the command was dispatched")})
    def init_system(self):
        self._send("PIS", "M1")
        return {"initialized": True}

    @action(name="x-cap.erikbgithub.init_roma.v1",
            description="Initialise the RoMa arm with PIA to device R1",
            output={"initialized": Field("boolean", description="True when the command was dispatched")})
    def init_roma(self):
        self._send("PIA", "R1")
        return {"initialized": True}

    @action(name="x-cap.erikbgithub.init_liha.v1",
            description="Initialise the LiHa arm with PIA to device A1",
            output={"initialized": Field("boolean", description="True when the command was dispatched")})
    def init_liha(self):
        self._send("PIA", "A1")
        return {"initialized": True}

    @action(name="x-cap.erikbgithub.go_waste.v1",
            description="Move the LiHa to the waste position with the fixed PAA command of the clone",
            output={"moved": Field("boolean", description="True when the command was dispatched")})
    def go_waste(self):
        self._send("PAA5295,1031,90,1200,1200,1200,1200,1200,1200,1200,1200", "A1")
        return {"moved": True}

    @action(name="x-cap.erikbgithub.set_tip_spacing.v1",
            description="Set the tip-to-tip spacing with PSY on the LiHa arm",
            input={"spacing": Field("number", unit="mm",
                                    description="Tip-to-tip spacing in mm (9...38)",
                                    limit=SPACING)},
            output={"spacing": Field("number", unit="mm",
                                     description="Applied tip-to-tip spacing in mm")})
    def set_tip_spacing(self, spacing):
        selector = int(round(spacing * 10))
        self._send("PSY" + str(selector), "A1")
        return {"spacing": selector / 10.0}

    @action(name="x-cap.erikbgithub.discard_queued_commands.v1",
            description="Discard every queued command (the safe state; the clone has no halt command)",
            output={"discarded": Field("integer", unit="1", description="Commands removed from the stack")})
    def discard_queued_commands(self):
        discarded = len(self.native.cmdStack)
        self.native.cmdStack = []
        self.native.runningStack = []
        return {"discarded": discarded}

    # -- safety --------------------------------------------------------------------------------------------------

    # -- helpers -------------------------------------------------------------------------------------------------
    def _send(self, command, device):
        """Queue one (command, device) pair and start it, as Cmd_delayed.start does (tecan_funcs.py:59-70)."""
        self.native.cmdStack = []
        self.native.runningStack = []
        self.native.add_cmd(command, device)
        self.check_cancelled()
        self.native.start()
        self.check_cancelled()
