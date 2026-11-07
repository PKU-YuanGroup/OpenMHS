"""OpenMHS driver for gh.jieunboy0516/newport-smc100-motor-controller-library-python: a Newport SMC100 axis.

A direct Driver (decorated methods) over the upstream class smc100_base:smc100.  The upstream class speaks the
SMC100 serial protocol and assembles every command at run time from a controller address and a mnemonic
(``'%02dTP'``, ``'%02dPA%f'``, ``'%02dST'``: smc100_base.py:121-224).  The card's PythonObjectDriver helper is not
used because the driver must keep that wire form and the upstream transport; RESULT.json records the deviation.

* reads: the reported position in mm (the TP query), the controller state (the TS query), the error strings (the TS
  query) and the velocity (the VA? query);
* one write: the velocity (the VA command).  No text file of the clone states a velocity range or its unit, and the
  README's 0-27 for the move position (README.md:28) has no unit and is the library author's example, so both the
  velocity and the move inputs are ``Limit.operator_required``: without a site overlay they are refused
  ``MHS.SAFETY.LIMITS_UNSET`` (``site-limits.example.json`` shows the overlay);
* actions: an absolute move (PA), a relative move (PR), starting homing (OR) and the stop (ST, also the safe-state
  action); the native stop is the e-stop and reset is the native recovery.

The upstream get_position, get_velocity and get_JOGGING_state parse but return None (smc100_base.py:145-151,
223-229, 237-243), so the two numeric reads go through the upstream send_rcv transport and parse its reply here.
Every Fact cites a line of the clone at the pinned commit b828102ddcc30495084606fd1634066c95c985a0.  This package is
model-authored and unreviewed: it is checked on the fake backend only and no hardware was run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset, write

#: The README calls the controller argument the motor number, usually 1 (README.md:27); this package drives one axis.
_CONTROLLER = 1

_POSITION = Limit.operator_required(
    "no text file of the clone states the travel of the configured stage; the README's 0-27 for the move position "
    "(README.md:28) has no unit and is the library author's example, so the site sets the absolute position range")
_OFFSET = Limit.operator_required(
    "a relative move can be positive or negative and no text file of the clone states a step or travel bound; the "
    "site sets the relative move range")
_VELOCITY = Limit.operator_required(
    "no text file of the clone states the velocity range or its unit; the site sets the native velocity range")


class Smc100(Driver):
    device_id = "smc100"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "smc100_base:smc100"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSmc100"}
    vendor, model = "Newport", "SMC100 motor controller"
    display_name = "Newport SMC100 motor controller (smc100_base.smc100)"
    tags = ["newport", "smc100", "motor controller", "motion axis", "serial"]
    facts = [
        Fact("The clone is a Python library for the Newport SMC100 motor controller",
             source="vendor_doc", ref="README.md:1-2"),
        Fact("The class smc100 talks to an SMC100 through a serial port", source="upstream_code",
             ref="smc100_base.py:73-74"),
        Fact("The constructor opens the serial port at 57600 baud with 8 data bits, no parity, one stop bit and a "
             "10 s timeout", source="upstream_code", ref="smc100_base.py:82-87"),
        Fact("A command is sent as the command text plus CRLF; a query returns the reply with the first len(command) "
             "characters removed", source="upstream_code", ref="smc100_base.py:103-112"),
        Fact("The controller state is queried with '%02dTS' and the last two characters of the reply are looked up "
             "in controller_state_map", source="upstream_code", ref="smc100_base.py:121-127"),
        Fact("controller_state_map names MOVING, READY from MOVING and DISABLE from READY",
             source="upstream_code", ref="smc100_base.py:6-28"),
        Fact("get_position queries '%02dTP' and its docstring says the value is in mm, but the parsed value is "
             "printed and the method returns None", source="upstream_code", ref="smc100_base.py:145-151"),
        Fact("get_errors queries '%02dTS', maps the error bits through error_names and returns [None] when there "
             "is no error", source="upstream_code", ref="smc100_base.py:131-143"),
        Fact("set_velocity writes '%02dVA%f' and get_velocity queries '%02dVA?', but the parsed velocity is printed "
             "and get_velocity returns None", source="upstream_code", ref="smc100_base.py:218-229"),
        Fact("move_absolute writes '%02dPA%f' and move_relative writes '%02dPR%f'", source="upstream_code",
             ref="smc100_base.py:176-182"),
        Fact("home writes '%02dOR'; home_until_done polls get_state with a 0.5 s sleep in an unbounded loop",
             source="upstream_code", ref="smc100_base.py:159-173"),
        Fact("stop_motion writes '%02dST'", source="upstream_code", ref="smc100_base.py:202-204"),
        Fact("reset writes '%02dRS'", source="upstream_code", ref="smc100_base.py:207-210"),
        Fact("kill closes the serial connection", source="upstream_code", ref="smc100_base.py:153-156"),
        Fact("The constructor sets motors_count to 1 and reads info for one controller",
             source="upstream_code", ref="smc100_base.py:97-101"),
        Fact("When the serial open fails the constructor prints that it uses a dummy motor controller but does not "
             "replace the serial object", source="upstream_code", ref="smc100_base.py:89-95"),
        Fact("The README calls the controller argument the motor number, usually 1", source="vendor_doc",
             ref="README.md:27"),
        Fact("The README describes the move position as between 0-27 without a unit", source="vendor_doc",
             ref="README.md:28"),
        Fact("The README links an external SMC100CC/SMC100PP user manual and says to refer to it",
             source="vendor_doc", ref="README.md:14-15"),
    ]
    safe_state = "motion stopped on the controller (the native ST command, smc100_base.py:202-204)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", unit="mm", description="Position reported by the controller (the TP query)")
    def position(self):
        return self._float_reply(f"{_CONTROLLER:02d}TP", "position")

    @read("state", type="string",
          description="Controller state from the TS query, for example READY from MOVING")
    def controller_state(self):
        return self.native.get_state(_CONTROLLER)

    @read("errors", type="array", items=Field("string"),
          description="Error strings from the TS query; empty when the controller reports no error")
    def errors(self):
        return [str(item) for item in self.native.get_errors(_CONTROLLER) if item is not None]

    @read("velocity", unit="1",
          description="Velocity in the controller's native velocity units (the clone states no unit)")
    def velocity(self):
        return self._float_reply(f"{_CONTROLLER:02d}VA?", "velocity")

    # -- the one write ------------------------------------------------------------------------------------------
    @write("velocity", unit="1",
           description="Velocity in the controller's native velocity units (the clone states no unit)",
           limit=_VELOCITY)
    def set_velocity(self, value):
        self.native.set_velocity(_CONTROLLER, value)
        return float(value)

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.jieunboy0516.move_absolute.v1",
            description="Move the axis to an absolute position in mm (the native PA command)",
            input={"position": Field("number", unit="mm",
                                     description="Absolute target position in mm; the site bounds the stage travel",
                                     limit=_POSITION)},
            output={"position": Field("number", unit="mm",
                                      description="Position reported immediately after the command")})
    def move_absolute(self, position):
        self.native.move_absolute(_CONTROLLER, position)
        return {"position": self._float_reply(f"{_CONTROLLER:02d}TP", "position")}

    @action(name="x-cap.jieunboy0516.move_relative.v1",
            description="Move the axis by a relative offset in mm (the native PR command)",
            input={"offset": Field("number", unit="mm",
                                   description="Relative move in mm; positive and negative values are accepted",
                                   limit=_OFFSET)},
            output={"position": Field("number", unit="mm",
                                      description="Position reported immediately after the command")})
    def move_relative(self, offset):
        self.native.move_relative(_CONTROLLER, offset)
        return {"position": self._float_reply(f"{_CONTROLLER:02d}TP", "position")}

    @action(name="x-cap.jieunboy0516.start_home.v1",
            description="Start the native home command (OR); it reports command acceptance, not homing completion",
            output={"started": Field("boolean",
                                     description="True once the native home command has been sent")})
    def start_home(self):
        self.native.home(_CONTROLLER)
        return {"started": True}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop motion with the native ST command",
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Optional class field; the native ST command has no deceleration setting, so the "
                            "controller stops immediately and this value is not applied")})
    def stop_motion(self, deceleration=None):
        self.native.stop_motion(_CONTROLLER)
        return {"stopped": True}

    # -- safety and recovery ------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends the ST command."""
        self.native.stop_motion(_CONTROLLER)

    @reset
    def reset_native(self):
        """The native recovery an accepted operator reset runs (the RS command)."""
        self.native.reset(_CONTROLLER)

    def teardown(self):
        """Close the serial connection through the upstream kill()."""
        self.native.kill()

    # -- transport helper ---------------------------------------------------------------------------------------
    def _float_reply(self, command, what):
        """Read a numeric reply through the upstream send_rcv transport (smc100_base.py:107-112)."""
        reply = self.native.send_rcv(command)
        if isinstance(reply, (bytes, bytearray)):
            reply = reply.decode("utf-8", "replace")
        try:
            return float(reply)
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the controller returned no {what} for {command!r}: {reply!r}") from exc
