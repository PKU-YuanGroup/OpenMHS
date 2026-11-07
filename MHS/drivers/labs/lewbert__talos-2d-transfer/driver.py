"""OpenMHS driver for gh.lewbert/talos-2d-transfer: the Zolix ZC300 XYR sample stage.

A direct Driver over the upstream device class ``talos.hal.devices.zolix:ZolixXYRStage``
(talos/hal/devices/zolix.py:99).  The upstream speaks Modbus RTU over a serial port and builds every opcode frame from
an opcode, an axis selector, a direction and an exact register count (talos/hal/devices/zolix.py:70-81, 610-614); a
config-only one-call binding cannot reproduce that wire form.  The card's ``PythonObjectDriver`` helper is also a
one-call table and cannot express an absolute move that the upstream composes from validated fixed-length moves
and that this driver then polls to rest.  RESULT.json records the deviation.  The card's entry symbol is unchanged.
The repository's other devices (the SigmaKoki XYZ transfer stage, the focus axis, the Yudian hot-stage controller and
the cameras) are not served here; facts.md names them.

* reads: the X/Y position in micrometres, the R position in degrees, the moving flag, and the controller's
  hardware emergency-stop and alarm bits;
* one catalogue action: ``cap.motion.stop.v1``, the native stop, also the safe-state action;
* one extension action: an absolute move in the native engineering units (micrometres and degrees), because
  ``cap.motion.joint_position.v1`` is specified in radians and in joint order and no catalogue class binds a
  linear XYR stage's native units;
* the native stop is the e-stop and the safe-state action.  It sends the configured stop opcode to all axes,
  polls the status for a bounded time, escalates to the immediate stop and polls again
  (talos/hal/devices/zolix.py:347-365).  It never raises, and ``_wait_stopped`` treats a failed status read as
  stopped (talos/hal/devices/zolix.py:367-384), so the safe-state action re-reads the status itself and fails
  ``MHS.SAFETY.SAFE_STATE_UNREACHED`` while any axis still reports moving (and fails when that read fails).

The stage travel is not stated by any text file of the clone, so the move inputs are
``Limit.operator_required``: every move is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies its stage
envelope in site-limits.json (site-limits.example.json is an example overlay, not a device bound).  The envelope
bounds targets in the controller's own position frame, which the README calls session-relative (controllers can
forget their position on power-cycle, README.md:74-75); this package exposes no homing.

Every Fact cites a line of the clone at the pinned commit 2b85b6a9c74b194d4507e3d7713f343a00680a32.  This package
is model-authored and unreviewed: it is checked on the fake backend only, and no hardware was run.

Model review (claude-opus-5-5, a model and not a human, 2026-11-05): the author's safe-state action returned
``stopped: false`` as a completed result when the controller still reported motion after the stop, and the runtime
counts a safe-state action that returns as the safe state reached, so such an e-stop was reported ``completed`` with
the safe state achieved (a probe with a fake whose stop is ignored showed it).  The action now fails
``MHS.SAFETY.SAFE_STATE_UNREACHED`` in that case and a test covers it; the facts were narrowed to their cited lines
and the move's ``stopped`` output no longer claims a limit-switch check that the driver does not make.
"""

from __future__ import annotations

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, interlock, read

#: The one motion action.  cap.motion.joint_position.v1 takes joint positions in radians and a joint order; the
#: ZC300 addresses X and Y in micrometres and R in degrees (docs/DESIGN.md:53-58), and no catalogue class binds
#: those native units for a motion.axis.
MOVE = "x-cap.lewbert.stage_move_abs.v1"

#: Poll interval of the wait-for-rest loop.  This is control-loop pacing, not a device property or a safety bound.
POLL_S = 0.02

#: Why the travel envelope must come from the site.  The clone states the scale, not the travel.
_TRAVEL = (
    "no text file of the clone states the travel range of this XYR stage: docs/DESIGN.md:45-58 gives the register "
    "map and the scale but no end stops, so the site supplies the envelope of its stage"
)


class ZolixStage(Driver):
    device_id = "talos-zolix"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R2"
    native = "talos.hal.devices.zolix:ZolixXYRStage"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeZolixXYRStage"}
    vendor, model = "Zolix", "ZC300 XYR sample stage"
    display_name = "Zolix ZC300 XYR sample stage (talos.hal.devices.zolix:ZolixXYRStage)"
    tags = ["zolix", "zc300", "xyr stage", "motion", "modbus rtu", "serial"]
    facts = [
        Fact("The ZC300 XYR stage is driven over Modbus RTU at 115200 8N1 with function codes 0x03/0x04 for reads, "
             "0x06 for single-register writes and 0x10 only for the opcode block (three registers for a move, two "
             "for a stop)",
             source="vendor_doc", ref="docs/DESIGN.md:45-49"),
        Fact("Position X, Y and R is in registers 30016-30021 as IEEE-754 float32 big-endian pairs, and the status "
             "register 30012-30015 has bit 9 as the emergency stop",
             source="vendor_doc", ref="docs/DESIGN.md:51-54"),
        Fact("The opcode block is 30050: 0x0064 absolute, 0x0065 fixed-length, 0x0066 continuous, 0x0067 decel "
             "stop, 0x0068 immediate stop and 0x0069 home; axis 0x31 X, 0x32 Y, 0x33 R",
             source="vendor_doc", ref="docs/DESIGN.md:55-56"),
        Fact("The documented scale is 0.625 micrometres per pulse in X and Y and 0.00125 degrees per pulse in R",
             source="vendor_doc", ref="docs/DESIGN.md:58"),
        Fact("The absolute-move opcode silently does nothing on the real controller, so every absolute move is "
             "composed from fixed-length moves and each distance register is read back before the motion opcode",
             source="vendor_doc", ref="docs/DESIGN.md:60-64"),
        Fact("move_abs_um computes the relative delta from get_position and calls move_rel_um, which rounds the "
             "deltas to pulses with the configured scale",
             source="upstream_code", ref="talos/hal/devices/zolix.py:238-268"),
        Fact("stop() sends the configured stop opcode to AXIS_ALL, waits with _wait_stopped(0.3), and when that "
             "returns False sends the immediate stop and waits with _wait_stopped(0.2); it catches and logs every "
             "exception and never raises",
             source="upstream_code", ref="talos/hal/devices/zolix.py:347-365"),
        Fact("_wait_stopped returns True once no axis reports moving and also when a status read raises, and False "
             "when its timeout passes",
             source="upstream_code", ref="talos/hal/devices/zolix.py:367-384"),
        Fact("get_status reads 10 input registers from 30012 and returns a moving flag per axis (motion word equal "
             "to 1), the X and Y limit bits, the three home bits, the estop bit and an alarm flag set when any axis "
             "alarm bit is set",
             source="upstream_code", ref="talos/hal/devices/zolix.py:390-415"),
        Fact("The status word assigns limit bits 0, 1, 3, 4, 6 and 7, home bits 2, 5 and 8, the emergency-stop bit 9 "
             "and the axis alarm bits 10, 11 and 12",
             source="upstream_code", ref="talos/hal/devices/zolix.py:83-86"),
        Fact("get_position reads six input registers from 30016 and converts pulses to micrometres and degrees with "
             "the configured scale",
             source="upstream_code", ref="talos/hal/devices/zolix.py:417-431"),
        Fact("The constructor creates the driver's lock as a threading.RLock", source="upstream_code",
             ref="talos/hal/devices/zolix.py:123"),
        Fact("move_rel_um holds the lock while it calls _ensure_not_moving and then, axis by axis, calls "
             "_ensure_speed, writes the distance, reads it back and writes the fixed-length opcode",
             source="upstream_code", ref="talos/hal/devices/zolix.py:269-290"),
        Fact("connect() opens the port at 115200 8N1, reads the motion-state and model registers, and for each axis "
             "of _axes_here() writes 0x01 to its enable register and accel_pps2 to its acceleration register",
             source="upstream_code", ref="talos/hal/devices/zolix.py:136-164"),
        Fact("The constructor defaults include port COM3, slave_address 1, slow_speed_pps 500, fast_speed_pps 2000, "
             "accel_pps2 10_000_000 and stop_mode immediate",
             source="upstream_code", ref="talos/hal/devices/zolix.py:104-117"),
        Fact("TALOS is a desktop application that owns an entire 2D-material transfer bench: the camera, the XYR "
             "sample stage, the XYZ transfer stage, the focus axis and the hot stage",
             source="vendor_doc", ref="docs/DESIGN.md:25-31"),
        Fact("The README warns that controllers can forget their position on power-cycle and says to treat stored "
             "coordinates as session-relative and re-establish references after a reset",
             source="vendor_doc", ref="README.md:74-75"),
    ]
    safe_state = ("every axis reported stopped by a fresh read of the controller's motion-state registers after the "
                  "native stop opcode (the configured mode, escalated to the immediate stop while an axis still "
                  "moves); the stop writes no axis-enable register")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("x_um", unit="um", description="X position reported by the controller, converted with the configured scale")
    def x_um(self):
        return float(self.native.get_position().x_um)

    @read("y_um", unit="um", description="Y position reported by the controller, converted with the configured scale")
    def y_um(self):
        return float(self.native.get_position().y_um)

    @read("r_deg", unit="deg",
          description="Rotation position reported by the controller, converted with the configured scale")
    def r_deg(self):
        return float(self.native.get_position().r_deg)

    @read("moving", type="boolean", description="True while any of the three axes reports moving")
    def moving(self):
        return bool(self.native.get_status().any_moving)

    @read("estop_active", type="boolean",
          description="True while the controller's status word reports bit 9, the emergency stop")
    def estop_active(self):
        return bool(self.native.get_status().estop)

    @read("alarm", type="boolean", description="True while any axis alarm bit is set in the controller status")
    def alarm(self):
        return bool(self.native.get_status().alarm)

    # -- the move ----------------------------------------------------------------------------------------------
    @action(name=MOVE,
            description="Move the stage to an absolute X/Y position (and R when given) and wait, bounded by the "
                        "request deadline, until the controller reports no axis moving; the position it reports is "
                        "returned",
            cancellable=True,
            input={
                "x_um": Field("number", unit="um",
                              description="Absolute X target in micrometres; the site bounds the stage travel",
                              limit=Limit.operator_required(_TRAVEL)),
                "y_um": Field("number", unit="um",
                              description="Absolute Y target in micrometres; the site bounds the stage travel",
                              limit=Limit.operator_required(_TRAVEL)),
                "r_deg": Field("number", unit="deg",
                               description="Absolute rotation target in degrees; omitted leaves R where it is",
                               limit=Limit.operator_required(_TRAVEL)),
            },
            output={
                "stopped": Field("boolean",
                                 description="True when the controller reported no axis moving after the move; "
                                             "limit switches are not checked, so compare the position with the "
                                             "target"),
                "x_um": Field("number", unit="um", description="X position reported after the move came to rest"),
                "y_um": Field("number", unit="um", description="Y position reported after the move came to rest"),
                "r_deg": Field("number", unit="deg", description="R position reported after the move came to rest"),
            })
    def move_abs(self, x_um, y_um, r_deg=None):
        self.native.move_abs_um(float(x_um), float(y_um), None if r_deg is None else float(r_deg))
        status = self._wait_rest()
        position = self.native.get_position()
        return {
            "stopped": not status.any_moving,
            "x_um": float(position.x_um),
            "y_um": float(position.y_um),
            "r_deg": float(position.r_deg),
        }

    def _wait_rest(self):
        """Poll the controller's own status until no axis moves, bounded by the request deadline.

        The controller's status is the only quiescence evidence the upstream offers.  An alarm or e-stop bit, or the
        deadline, ends the wait with a failed receipt; no stop is sent then, so an axis that is still moving finishes
        its commanded fixed-length move unless the caller stops it.  Limit-switch bits are not checked.
        """
        ctx = self.ctx
        remaining_ms = ctx.remaining_ms() if ctx is not None else 30000
        deadline = time.monotonic() + max(0, int(remaining_ms)) / 1000.0
        while True:
            self.check_cancelled()
            status = self.native.get_status()
            if status.estop:
                raise DriverFailed("MHS.SAFETY.ESTOP_ENGAGED",
                                   "the controller reports its emergency-stop bit while the move is in flight")
            if status.alarm:
                raise DriverFailed("MHS.DEVICE.FAULTED", "an axis alarm bit is set while the move is in flight")
            if not status.any_moving:
                return status
            if time.monotonic() >= deadline:
                raise DriverFailed("MHS.OUTCOME.TIMEOUT",
                                   "the axes were still moving when the request deadline expired; no stop was "
                                   "sent, so the commanded fixed-length moves may still be running")
            time.sleep(POLL_S)

    # -- the stop ----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop all axes with the native controller stop and confirm it with a fresh status read; "
                        "fails MHS.SAFETY.SAFE_STATE_UNREACHED while an axis still reports moving.  The class's "
                        "optional deceleration value is accepted for schema compatibility but not applied because "
                        "the native stop takes no deceleration parameter (the controller uses its configured stop "
                        "mode)",
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Optional class field; the native stop has no deceleration parameter, so the controller's "
                            "configured stop mode is used and this value is not applied")})
    def stop_motion(self, deceleration=None):
        # The upstream stop never raises and its own wait counts a failed status read as stopped
        # (talos/hal/devices/zolix.py:347-384), so only this fresh read confirms the safe state.  The runtime counts
        # a safe-state action that returns as the safe state reached: an axis still moving must raise, never be
        # reported as ``stopped: false`` in a completed receipt.
        self.native.stop()
        status = self.native.get_status()
        if status.any_moving:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               "the controller still reports an axis moving after the native stop")
        position = self.native.get_position()
        return {
            "stopped": True,
            "stopped_position": {
                "x_um": float(position.x_um),
                "y_um": float(position.y_um),
                "r_deg": float(position.r_deg),
            },
        }

    # -- safety ------------------------------------------------------------------------------------------------
    @interlock("motion_fault", description="The controller reports no emergency-stop bit and no axis alarm",
               blocks=[MOVE])
    def motion_fault_closed(self):
        status = self.native.get_status()
        return not (status.estop or status.alarm)

    @estop(native="stop")
    def stop(self):
        """The native emergency halt: the runtime latches first, then sends the controller stop."""
        self.native.stop()

    def teardown(self):
        """Stop and close the serial port through the upstream disconnect()."""
        self.native.disconnect()
