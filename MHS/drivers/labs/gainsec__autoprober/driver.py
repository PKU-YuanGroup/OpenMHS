"""OpenMHS driver for gh.gainsec/autoprober: the GRBL CNC actuator of the AutoProber flying-probe stack.

A direct ``Driver`` (decorated methods) over the upstream class ``autoprober.cnc:CNC``
(autoprober/cnc.py:46), the first entry symbol of the card.  The card calls this repository a driver pack: the same
package also contains ``autoprober.scope:Scope`` (the oscilloscope whose Channel 4 carries the independent optical
endstop) and ``autoprober.microscope:Microscope`` (an mjpg_streamer snapshot client).  One OpenMHS driver binds one
native object, and the CNC is the actuator this package serves.  The scope endstop monitor and the microscope are
NOT COVERED (see facts.md and RESULT.json); the deployment must keep the upstream ``EndstopMonitor`` running
alongside this binding.

Covered:

* reads: the GRBL state, the three machine positions, the real X/Y/Z limit pins and the raw status line, all parsed
  from one fresh ``?`` status query in ``CNC.get_status`` and ``autoprober.cnc.parse_status``
  (autoprober/cnc.py:22-43, 90-101);
* actions: an extension home action ($H, then wait for the controller to report Idle), an absolute and a relative
  three-axis move (extensions; the catalogue has no linear Cartesian move for a ``motion.axis`` resource and its
  home class carries a numeric speed scale the native ``$H`` does not take), a ``$$`` settings read, and a declared
  re-enable that clears a GRBL alarm lock with ``$X``;
* safety: ``CNC.feed_hold`` writes the GRBL feed-hold byte ``!`` (autoprober/cnc.py:84-88) without acknowledgement
  or a standstill check. The ``@estop`` and ``cap.motion.stop.v1`` attempt this write and then report
  SAFE_STATE_UNREACHED; the capability is not a safe-state action. The Channel 4 monitor required by upstream
  is not integrated, so this hardware motion package remains blocked.

Travel and feed bounds are ``Limit.operator_required``: the clone names no number for the machine envelope
(AGENTS.md:117-118) and gives only recommended feed-rate ranges by operation (AGENTS.md:123-128).  The site supplies
them in its overlay (``site-limits.example.json`` is an example, not a statement about any machine).

The MHS e-stop is a software command to the controller, not an independent hardware stop; the clone documents no
hardware e-stop.  This package is model-authored and unreviewed, so the loader refuses its hardware backend at R2
until a human signs ``driver.lock.json`` ``reviewed_by``.  The acceptance gate ran the fake backend only.

Every Fact and Limit cites a line of the clone at commit ff0e01fe556c7e183d46462dbc1ebce7b6a10e74.
"""

import time

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

#: Implementation poll interval of the wait loops, not a device limit or a Fact.
POLL_S = 0.1
#: Implementation wait bound inside the class's 120 s move budget, not a device limit or a Fact.
MOVE_WAIT_S = 110.0
#: Implementation wait bound inside the class's 300 s homing budget, not a device limit or a Fact.
HOME_WAIT_S = 290.0

_TRAVEL_REASON = (
    "the clone names no travel envelope for the machine: AGENTS.md:117-118 says only to stay inside the known "
    "envelope and docs/devices/cnc.md:1-7 states no number, so the operator supplies the axis envelope of the "
    "installed machine in site-limits.json")
_RELATIVE_REASON = (
    "a relative delta is bounded by the current position and the same unstated travel envelope "
    "(AGENTS.md:117-118); the operator supplies the allowed delta of the installed machine in site-limits.json")
_FEED_REASON = (
    "the clone recommends feed-rate ranges by operation (AGENTS.md:123-128) but states no single feed bound for "
    "the installed machine; the operator supplies the allowed feed-rate range in site-limits.json")


def _operator_limit(reason):
    return Limit.operator_required(reason)


class AutoProberCnc(Driver):
    device_id = "autoprober-cnc"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R2"
    native = "autoprober.cnc:CNC"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCnc"}
    vendor = "GainSec"
    model = "AutoProber flying probe (GRBL CNC actuator)"
    display_name = "AutoProber GRBL CNC (autoprober.cnc.CNC)"
    tags = ["autoprober", "cnc", "grbl", "motion", "flying-probe", "serial"]
    facts = [
        Fact("CNC is the GRBL CNC wrapper; its constructor takes port, baud and log_source and leaves the serial "
             "object unset", source="upstream_code", ref="autoprober/cnc.py:46-53"),
        Fact("connect opens serial.Serial on port and baud, waits, resets the input buffer, writes CRLF and resets "
             "again", source="upstream_code", ref="autoprober/cnc.py:55-64"),
        Fact("parse_status parses a GRBL status line into state, an MPos tuple of three floats, the raw Pn field and "
             "the subset of X, Y and Z pins", source="upstream_code", ref="autoprober/cnc.py:22-43"),
        Fact("get_status writes '?' and returns the first parsed status line before its 2 s deadline",
             source="upstream_code", ref="autoprober/cnc.py:90-101"),
        Fact("read_settings writes '$$' and collects $N=value lines until 'ok' or its 10 s deadline",
             source="upstream_code", ref="autoprober/cnc.py:103-119"),
        Fact("home writes '$H' and returns without waiting for the homing cycle", source="upstream_code",
             ref="autoprober/cnc.py:81-82"),
        Fact("feed_hold writes the single GRBL feed-hold byte '!' and returns without waiting for motion to stop",
             source="upstream_code", ref="autoprober/cnc.py:84-88"),
        Fact("unlock writes '$X' and sleeps 0.2 s; it has no acknowledgement read", source="upstream_code",
             ref="autoprober/cnc.py:77-79"),
        Fact("move_absolute builds G90 G1 with the supplied X, Y and Z words and an F feed word",
             source="upstream_code", ref="autoprober/cnc.py:131-146"),
        Fact("move_relative builds G91 G1 with the supplied X, Y and Z deltas and an F feed word",
             source="upstream_code", ref="autoprober/cnc.py:148-163"),
        Fact("wait_for_idle polls get_status and returns only when the state is exactly Idle",
             source="upstream_code", ref="autoprober/cnc.py:121-129"),
        Fact("_write raises CNCError when no serial object is open",
             source="upstream_code", ref="autoprober/cnc.py:71-73"),
        Fact("The independent safety endstop is oscilloscope Channel 4; below 1.0 V is triggered, 1.0 to 4.5 V is a "
             "fault and 4.5 V or more is clear", source="vendor_doc", ref="docs/safety.md:3-10"),
        Fact("STOP means feed hold has been sent if possible, the workflow ends and the operator must inspect and "
             "explicitly restart", source="vendor_doc", ref="docs/safety.md:12"),
        Fact("GRBL Pn:P is ignored for safety; real limit flags are X, Y and Z, including the X/Y/Z part of Pn:PX, "
             "Pn:PY and Pn:PZ", source="vendor_doc", ref="AGENTS.md:8-22"),
        Fact("Channel 4 must be monitored continuously during motion and a trigger must issue feed hold immediately",
             source="vendor_doc", ref="AGENTS.md:47-51"),
        Fact("On a trigger the operator must stop and report; automatic back-off, jog, retry or continued scanning "
             "is forbidden", source="vendor_doc", ref="AGENTS.md:84-93"),
        Fact("The clone says to stay inside the known travel envelope and that a hard limit alarm is not a safety "
             "strategy, but states no travel number", source="vendor_doc", ref="AGENTS.md:117-118"),
        Fact("The clone recommends feed-rate ranges by operation but states no single device feed bound",
             source="vendor_doc", ref="AGENTS.md:123-128"),
        Fact("All motion workflows must create an EndstopMonitor before motion starts and stop it after motion has "
             "ended; if the monitor enters STOP, the app exits without more motion", source="vendor_doc",
             ref="docs/operations.md:13"),
        Fact("CNC's public methods are connect, close, unlock, home, feed_hold, get_status, read_settings, "
             "wait_for_idle, move_absolute and move_relative; the class has no cycle-start or resume method",
             source="upstream_code", ref="autoprober/cnc.py:46-163"),
    ]
    safe_state = ("unconfirmed: the driver attempts GRBL feed hold ('!') but has no acknowledgement or standstill "
                  "confirmation and does not enforce the required Channel 4 endstop monitor; the e-stop reports "
                  "SAFE_STATE_UNREACHED with the endpoint latch engaged")

    # -- reads -------------------------------------------------------------------------------------------------
    def _status(self):
        return self.native.get_status()

    @read("state", type="string", description="GRBL machine state from a fresh status query (Idle, Run, Hold, Alarm, ...)")
    def state(self):
        return str(self._status()["state"])

    @read("position_x", unit="mm", description="Machine X position (MPos) from a fresh status query")
    def position_x(self):
        return float(self._status()["mpos"][0])

    @read("position_y", unit="mm", description="Machine Y position (MPos) from a fresh status query")
    def position_y(self):
        return float(self._status()["mpos"][1])

    @read("position_z", unit="mm", description="Machine Z position (MPos) from a fresh status query")
    def position_z(self):
        return float(self._status()["mpos"][2])

    @read("limit_pins", type="array", items="string",
          description="Real X, Y and Z limit pins reported in Pn by a fresh status query; P is ignored")
    def limit_pins(self):
        return sorted(str(pin) for pin in (self._status().get("pins") or ()))

    @read("status_line", type="string", description="Raw GRBL status line from a fresh status query")
    def status_line(self):
        return str(self._status()["raw"])

    # -- action helpers ----------------------------------------------------------------------------------------
    def _require_idle(self, command):
        status = self._status()
        state = str(status["state"])
        if state != "Idle":
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"{command}: the controller reports {state!r}, not Idle; the driver sends no motion in that state")
        pins = sorted(str(pin) for pin in (status.get("pins") or ()))
        if pins:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"{command}: real limit pins {pins} are active; a limit pin is a stop condition "
                "(AGENTS.md:116-117)")
        return status

    def _wait_idle(self, command, timeout_s):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.cancelled():
                self.native.feed_hold()
                raise Cancelled(f"{command} was cancelled; feed hold written")
            status = self._status()
            state = str(status["state"])
            if state == "Idle":
                return status
            if state == "Hold":
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"{command}: the controller reports Hold after the command; motion is paused and this driver "
                    "sends no cycle start")
            if state.lower().startswith("alarm"):
                raise DriverFailed("MHS.DEVICE.FAULTED", f"{command}: the controller reports {state!r}")
            pins = sorted(str(pin) for pin in (status.get("pins") or ()))
            if pins:
                self.native.feed_hold()
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"{command}: real limit pins {pins} became active; feed hold written and no recovery motion "
                    "is automatic (AGENTS.md:84-93)")
            time.sleep(POLL_S)
        self.native.feed_hold()
        raise OutcomeUnknown(
            f"{command}: the controller did not report Idle within the wait bound; feed hold written, the outcome "
            "of the commanded motion is unknown")

    def _positions(self, status):
        positions = status["mpos"]
        return float(positions[0]), float(positions[1]), float(positions[2])

    # -- actions -----------------------------------------------------------------------------------------------
    @action(name="x-cap.gainsec.home.v1", risk="R2",
            description="Home all axes with GRBL $H and wait for the controller to report Idle. Homing is motion; "
                        "this binding does not send the upstream EndstopMonitor's Channel 4 poll. The catalogue "
                        "cap.motion.home.v1 is not used: its numeric speed_scale has no equivalent in the native "
                        "$H command.",
            output={
                "homed": Field("boolean",
                               description="True when a fresh status query after $H reports Idle; GRBL has no "
                                           "separate homed flag"),
                "axes": Field("array", items=Field("string"),
                              description="Axes the native $H homes: x, y and z together"),
                "state": Field("string", description="GRBL state of the status line the result came from"),
            })
    def home(self):
        self._require_idle("home")
        self.native.home()
        status = self._wait_idle("home", HOME_WAIT_S)
        return {"homed": True, "axes": ["x", "y", "z"], "state": str(status["state"])}

    @action(name="x-cap.gainsec.move_absolute.v1", risk="R2", long_running=True, max_duration_ms=120000,
            description="Move X, Y and Z to absolute machine positions with G90/G1 and wait for Idle. The "
                        "controller's own travel envelope is not in the clone; the site overlay bounds each axis. "
                        "This binding does not send the upstream EndstopMonitor's Channel 4 poll.",
            input={
                "x_mm": Field("number", unit="mm", description="Absolute X target in millimetres",
                              limit=_operator_limit(_TRAVEL_REASON)),
                "y_mm": Field("number", unit="mm", description="Absolute Y target in millimetres",
                              limit=_operator_limit(_TRAVEL_REASON)),
                "z_mm": Field("number", unit="mm", description="Absolute Z target in millimetres",
                              limit=_operator_limit(_TRAVEL_REASON)),
                "feed_mm_min": Field("integer", unit="mm/min",
                                     description="GRBL F feed word in millimetres per minute; required so every "
                                                 "move is bounded by the site overlay",
                                     limit=_operator_limit(_FEED_REASON)),
            },
            output={
                "x_mm": Field("number", unit="mm", description="X position reported after the controller went Idle"),
                "y_mm": Field("number", unit="mm", description="Y position reported after the controller went Idle"),
                "z_mm": Field("number", unit="mm", description="Z position reported after the controller went Idle"),
                "state": Field("string", description="GRBL state of the status line the positions came from"),
                "feed_mm_min": Field("integer", unit="mm/min", description="Feed word sent with this move"),
            })
    def move_absolute(self, x_mm, y_mm, z_mm, feed_mm_min):
        self._require_idle("move_absolute")
        self.native.move_absolute(x=float(x_mm), y=float(y_mm), z=float(z_mm), feed=int(feed_mm_min))
        status = self._wait_idle("move_absolute", MOVE_WAIT_S)
        x, y, z = self._positions(status)
        return {"x_mm": x, "y_mm": y, "z_mm": z, "state": str(status["state"]),
                "feed_mm_min": int(feed_mm_min)}

    @action(name="x-cap.gainsec.move_relative.v1", risk="R2", long_running=True, max_duration_ms=120000,
            description="Move relative to the current machine position with G91/G1 and wait for Idle. At least "
                        "one non-zero delta is required. This binding does not send the upstream EndstopMonitor's "
                        "Channel 4 poll.",
            input={
                "dx_mm": Field("number", unit="mm", description="Relative X delta in millimetres",
                               limit=_operator_limit(_RELATIVE_REASON)),
                "dy_mm": Field("number", unit="mm", description="Relative Y delta in millimetres",
                               limit=_operator_limit(_RELATIVE_REASON)),
                "dz_mm": Field("number", unit="mm", description="Relative Z delta in millimetres",
                               limit=_operator_limit(_RELATIVE_REASON)),
                "feed_mm_min": Field("integer", unit="mm/min",
                                     description="GRBL F feed word in millimetres per minute; required so every "
                                                 "move is bounded by the site overlay",
                                     limit=_operator_limit(_FEED_REASON)),
            },
            output={
                "x_mm": Field("number", unit="mm", description="X position reported after the controller went Idle"),
                "y_mm": Field("number", unit="mm", description="Y position reported after the controller went Idle"),
                "z_mm": Field("number", unit="mm", description="Z position reported after the controller went Idle"),
                "state": Field("string", description="GRBL state of the status line the positions came from"),
                "feed_mm_min": Field("integer", unit="mm/min", description="Feed word sent with this move"),
            })
    def move_relative(self, dx_mm, dy_mm, dz_mm, feed_mm_min):
        deltas = [float(dx_mm), float(dy_mm), float(dz_mm)]
        if not any(deltas):
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "move_relative: all three deltas are zero; the driver refuses an empty move")
        self._require_idle("move_relative")
        self.native.move_relative(dx=deltas[0], dy=deltas[1], dz=deltas[2], feed=int(feed_mm_min))
        status = self._wait_idle("move_relative", MOVE_WAIT_S)
        x, y, z = self._positions(status)
        return {"x_mm": x, "y_mm": y, "z_mm": z, "state": str(status["state"]),
                "feed_mm_min": int(feed_mm_min)}

    @action(name="x-cap.gainsec.read_settings.v1", risk="R0", verb="read",
            description="Read GRBL $$ settings as a map of $N to the controller's value string; only while Idle "
                        "so the settings exchange cannot interleave with motion",
            output={"settings": Field("object",
                                      description="GRBL settings keyed by the number after '$', values as the "
                                                  "controller returned them")})
    def read_settings(self):
        self._require_idle("read_settings")
        return {"settings": {str(key): str(value) for key, value in self.native.read_settings().items()}}

    @action(name="x-cap.gainsec.unlock.v1", risk="R2", reenable=True,
            description="Clear a GRBL alarm lock with $X (the upstream unlock), then read one fresh status. This "
                        "is the declared re-enable after a safety reset; it does not resume a feed hold and it "
                        "does not home the machine.",
            output={"unlocked": Field("boolean",
                                      description="True after the $X write; GRBL sends no acknowledgement for $X"),
                    "state": Field("string", description="GRBL state of the first status query after $X")})
    def unlock(self):
        self.native.unlock()
        status = self._status()
        return {"unlocked": True, "state": str(status["state"])}

    @action(cap="cap.motion.stop.v1", risk="R2",
            description="Attempt the GRBL feed-hold byte '!' (the upstream feed_hold), then fail "
                        "SAFE_STATE_UNREACHED: this write does not confirm that motion stopped.",
            input={"deceleration": Field(
                "number", unit="m/s2", required=False,
                description="Optional class field; the GRBL feed-hold byte carries no deceleration value, so the "
                            "controller's own deceleration profile applies and this value is not applied")})
    def stop_motion(self, deceleration=None):
        self.native.feed_hold()
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "the feed-hold byte was written without acknowledgement or standstill confirmation")

    # -- safety ------------------------------------------------------------------------------------------------
    @estop(native="feed_hold")
    def stop(self):
        """Attempt feed hold, without promoting a serial write into a confirmed stop."""
        self.native.feed_hold()
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "feed hold is an unacknowledged serial write; the required Channel 4 monitor and "
                           "a confirmed physical stop are not provided by this package")

    def teardown(self):
        self.native.close()     # autoprober/cnc.py:66-69
