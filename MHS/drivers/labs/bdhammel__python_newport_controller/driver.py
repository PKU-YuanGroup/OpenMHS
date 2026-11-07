"""OpenMHS driver for gh.bdhammel/python_newport_controller: a New Focus Picomotor controller over USB.

A direct Driver (decorated methods) over the upstream class newport:Controller.  The upstream API is one method,
``command(newfocus_command)``: it parses a NewFocus-style command (an optional one-digit driver number, a mnemonic
and an optional numeric parameter), builds the USB text ``1>{driver} {command} {parameter}\\r`` and writes it to the
first OUT endpoint (newport.py:138-235).  Because the upstream assembles each USB line from parts, this package is a
direct Driver with a native.py factory, not the card's PythonObjectDriver helper; RESULT.json records that deviation.

* read: the reported position of motor channels 1 to 4, queried with ``{axis}TP?`` (the wire text ``1>{axis} TP?``);
* action: x-cap.bdhammel.move_steps.v1, one relative move ``{axis}PR{steps}`` (the documented xPRnn command);
* action: cap.motion.stop.v1, the native ST command, also the safe-state action;
* e-stop: ST through the same native command method.

No text file of the clone states how many motor channels the installed controller drives or a travel/step range.
The upstream connect check polls four channels (newport.py:129-134) and the command regex accepts one digit
(newport.py:45), but those are library assumptions, not bounds of the device: both action inputs are
``Limit.operator_required`` and the site overlay supplies them (site-limits.example.json shows the shape).

This package is model-authored and unreviewed.  The gate checks only its fake backend; no hardware was run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: Motor channels the upstream connect check polls (newport.py:129); the site overlay bounds the installed set.
_AXIS = Limit.operator_required(
    "no text file of the clone states how many motor channels the installed controller drives; the upstream connect "
    "check polls four channels (newport.py:129-134), which is an assumption of that check, not a bound of the device, "
    "so the site sets the channel range")
_STEPS = Limit.operator_required(
    "no text file of the clone states a travel range or maximum step count; the README names xPRnn without a bound "
    "and links the full command list to an external PDF manual (README.md:118), so the site sets the step bound")


class Picomotor(Driver):
    device_id = "picomotor"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "newport:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePythonNewportController"}
    vendor, model = "New Focus (Newport)", "Picomotor controller 8742/8745"
    display_name = "New Focus Picomotor controller (newport.Controller)"
    tags = ["picomotor", "motion", "newfocus", "usb"]
    facts = [
        Fact("The clone is a Python driver for a New Focus Picomotor motion controller over USB",
             source="vendor_doc", ref="README.md:1"),
        Fact("The README says the script was tested with a single closed-loop Picomotor controller (model 8745)",
             source="vendor_doc", ref="README.md:6"),
        Fact("The NewFocus command grammar is an optional one-digit driver number, a two-or-more letter mnemonic "
             "and an optional numeric parameter", source="upstream_code", ref="newport.py:45"),
        Fact("parse_command builds the USB text '1>{driver} {command} {parameter}\\r' from a NewFocus command",
             source="upstream_code", ref="newport.py:178-189"),
        Fact("xPRnn moves motor x by nn steps", source="vendor_doc", ref="README.md:108"),
        Fact("ST stops all motor movement", source="vendor_doc", ref="README.md:107"),
        Fact("The connection check queries motor positions with '1>1 TP?' through '1>4 TP?'",
             source="upstream_code", ref="newport.py:33-36"),
        Fact("The connect check assumes four motor channels and asks each for its motor type with {m}QM?",
             source="upstream_code", ref="newport.py:129-134"),
        Fact("The motor-type reply maps 0 to no motor connected, 1 to motor unknown, 2 to 'Tiny' and 3 to "
             "'Standard'", source="upstream_code", ref="newport.py:46-51"),
        Fact("The console reads input with raw_input, which does not exist in Python 3, so start_console is not "
             "exposed as a capability", source="upstream_code", ref="newport.py:255"),
        Fact("The README directs the reader to section 6.2 of an external 8745 manual for the full command list",
             source="vendor_doc", ref="README.md:118"),
        Fact("The device is found by USB product and vendor ids through usb.core and uses its first IN and OUT "
             "endpoints", source="upstream_code", ref="newport.py:90-122"),
    ]
    safe_state = "all motor movement stopped (the native ST command)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("positions", type="array", items=Field("integer"), length=4, unit="1",
          description="Reported position of motor channels 1 to 4, in controller steps (the TP? query)")
    def positions(self):
        return [self._position(axis) for axis in (1, 2, 3, 4)]

    def _position(self, axis):
        reply = self.native.command(f"{axis}TP?")
        try:
            return int(reply.strip())
        except (AttributeError, TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the controller returned no position for channel {axis}: {reply!r}") from exc

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.bdhammel.move_steps.v1", risk="R1",
            description="Move one Picomotor channel by a relative number of steps (the native xPRnn command)",
            input={
                "axis": Field("integer", unit="1",
                              description="Motor channel number; the NewFocus command grammar takes one digit",
                              limit=_AXIS),
                "steps": Field("integer", unit="1",
                               description="Relative move in motor steps; positive and negative are accepted",
                               limit=_STEPS),
            },
            output={
                "axis": Field("integer", unit="1", description="Channel that received the relative move"),
                "steps": Field("integer", unit="1", description="Relative move in motor steps that was sent"),
            })
    def move_steps(self, axis, steps):
        axis, steps = int(axis), int(steps)
        if not 0 <= axis <= 9:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {axis} is not a one-digit NewFocus driver number")
        self.native.command(f"{axis}PR{steps}")
        return {"axis": axis, "steps": steps}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop all motor movement with the native ST command",
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Optional class field; the native ST command has no deceleration setting, so the "
                            "controller stops immediately and this value is not applied")})
    def stop_motion(self, deceleration=None):
        self.native.command("ST")
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop(native="command")
    def stop(self):
        """The native stop: the runtime latches first, then sends ST through newport.Controller.command()."""
        self.native.command("ST")
