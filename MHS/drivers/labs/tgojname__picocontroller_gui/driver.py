"""OpenMHS driver for gh.tgojname/picocontroller_gui: a Newport 8742 picomotor controller.

The card's helper is ``PythonObjectDriver``, but the upstream interface is not a plain object with named
methods: every operation is built by ``picomotor_terminal_based.Controller.command`` from a New Focus command
string (``parse_command`` assembles ``1><axis> <command> <parameter>\\r``, picomotor_terminal_based.py:163-205).
A family command table cannot reproduce that assembled wire text, so this package uses a direct Driver over the
upstream class with a native factory.  That is the "DEVIATION FROM THE CARD" recorded in RESULT.json.

Reads:
  * ``version``: the upstream ``VE?`` query;
  * ``motor_types``: the four ``QM?`` replies mapped through the clone's MOTOR_TYPE table;
  * ``motion_done``: the four ``MD?`` replies (the joystick loop starts a move when the reply ends in ``1``).

Actions:
  * ``x-cap.tgojname.jog_axis.v1``: set one channel's velocity with ``VA`` and, when the channel reports
    motion done, start a continuous jog with ``MV+`` or ``MV-`` (the upstream start sequence);
  * ``cap.motion.stop.v1``: stop every channel with the native ``ST``; it is also the safe-state action.

The native stop is ``Controller.command("ST")``, used by the upstream before its control loop.  This package is
model-authored and unreviewed; the fake backend is the only path that was exercised here, and the hardware path
(``native.py``) was never run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

_AXES = (1, 2, 3, 4)

# picomotor_terminal_based.py:53-58
_MOTOR_TYPES = {
    "0": "No motor connected",
    "1": "Motor Unknown",
    "2": "'Tiny' Motor",
    "3": "'Standard' Motor",
}


class PicoController(Driver):
    device_id = "picocontroller"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "picomotor_terminal_based:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeController"}
    vendor, model = "Newport", "8742"
    display_name = "Newport 8742 picomotor controller"
    tags = ["picomotor", "motion", "usb", "newfocus"]

    facts = [
        Fact("Controller.command sends a New Focus style command through the USB endpoints and returns a parsed "
             "reply only when the command contains '?'", source="upstream_code",
             ref="picomotor_terminal_based.py:221-243"),
        Fact("parse_command builds '1><driver> <command> <parameter>\\r' from the New Focus command text",
             source="upstream_code", ref="picomotor_terminal_based.py:163-205"),
        Fact("The connection check queries QM? for motor channels 1 to 4", source="upstream_code",
             ref="picomotor_terminal_based.py:137-142"),
        Fact("MOTOR_TYPE maps the QM? reply code 0 to 3 to a motor description", source="upstream_code",
             ref="picomotor_terminal_based.py:53-58"),
        Fact("The joystick loop starts a move only when the MD? reply ends in 1", source="upstream_code",
             ref="picomotor_terminal_based.py:296-304"),
        Fact("An axis is moved by writing its velocity with VA and then sending MV+ or MV-", source="upstream_code",
             ref="picomotor_terminal_based.py:294-304"),
        Fact("The comment calls 2000 the maximal speed for the New Focus 8821-L motor", source="upstream_code",
             ref="picomotor_terminal_based.py:294"),
        Fact("The terminal program sends ST before the control loop and stops one axis with <axis>ST",
             source="upstream_code", ref="picomotor_terminal_based.py:278-291"),
    ]

    safe_state = "motor channels stopped (native ST)"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("version", type="string", description="Firmware version reply to the native VE? query")
    def version(self):
        reply = self.native.command("VE?")
        if not isinstance(reply, str) or not reply.strip():
            raise DriverFailed("MHS.DEVICE.FAULTED", "VE? returned no version text")
        return reply.strip()

    @read("motor_types", type="array", length=4,
          items=Field("string", description="QM? motor description for one channel"),
          description="Motor type reported for each of the four channels")
    def motor_types(self):
        return [self._motor_type(axis) for axis in _AXES]

    @read("motion_done", type="array", length=4,
          items=Field("boolean", description="True when MD? reports that the channel is motion done"),
          description="Motion-done state of each of the four channels")
    def motion_done(self):
        return [self._motion_done(axis) for axis in _AXES]

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.tgojname.jog_axis.v1", risk="R1",
            description="Set one channel's velocity and start a continuous jog when the channel is motion done",
            input={
                "axis": Field("integer", unit="1", description="Motor channel number",
                              limit=Limit(allowed=[1, 2, 3, 4], source="upstream_code",
                                          ref="picomotor_GUI.py:85")),
                "direction": Field("string", description="Jog direction, '+' or '-'",
                                   limit=Limit(allowed=["+", "-"], source="upstream_code",
                                               ref="picomotor_terminal_based.py:299-304")),
                "velocity": Field("integer", unit="1",
                                  description="Native velocity setting (unitless; the clone's 2000 maximum)",
                                  limit=Limit(min=0, max=2000, source="upstream_code",
                                              ref="picomotor_terminal_based.py:294")),
            },
            output={
                "axis": Field("integer", unit="1", description="Channel that was addressed"),
                "direction": Field("string", description="Direction that was requested"),
                "velocity": Field("integer", unit="1", description="Velocity that was written"),
                "move_started": Field("boolean",
                                      description="True when MV was sent; False when only the velocity changed"),
            })
    def jog_axis(self, axis, direction, velocity):
        idle = self._motion_done(axis)
        self.native.command(f"{axis}VA{velocity}")
        if idle:
            self.native.command(f"{axis}MV{direction}")
        return {"axis": axis, "direction": direction, "velocity": velocity, "move_started": idle}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop all motion with the native ST command",
            input={
                "deceleration": Field("number", unit="m/s2",
                                      description="Accepted for the catalogue class; the 8742 ST command has no "
                                                  "deceleration setting and this driver ignores it"),
            })
    def stop_motion(self, deceleration=None):
        self.native.command("ST")
        return {"stopped": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="command")
    def emergency_stop(self):
        """Stop every channel through the native command path (the upstream ST command)."""
        self.native.command("ST")

    # -- helpers -------------------------------------------------------------------------------------------------
    def _motion_done(self, axis):
        code = self._last_char(self.native.command(f"{axis}MD?"), "MD?", axis)
        if code not in ("0", "1"):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"MD? for motor {axis} returned {code!r}")
        return code == "1"

    def _motor_type(self, axis):
        code = self._last_char(self.native.command(f"{axis}QM?"), "QM?", axis)
        if code not in _MOTOR_TYPES:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"QM? for motor {axis} returned {code!r}")
        return _MOTOR_TYPES[code]

    @staticmethod
    def _last_char(reply, query, axis):
        text = str(reply).strip() if reply is not None else ""
        if not text:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"{query} for motor {axis} returned no reply")
        return text[-1]
