"""OpenMHS driver for gh.bec-project/ophyd_devices: the PSI simple EPICS positioner.

This package is a direct ``Driver`` over ``ophyd_devices.devices.simple_positioner:PSISimplePositioner``
(ophyd_devices/devices/simple_positioner.py:7), not the card's ``OphydDriver``.  The card's helper was tried first:
the upstream class is a direct ``Component(EpicsSignal, ...)`` declaration, but its local base carries
``SIGNAL_NAMES = _SIMPLE_SIGNAL_NAMES`` and other executable class-body values, so the Ophyd source proof refuses the
selected class and its ancestry.  The direct driver exposes the same primary interface: the position readback, the
setpoint, velocity, the done flag, ``move()`` and ``stop()``.

The move capability is the extension ``x-cap.bec-project.axis_move.v1`` because no catalogue motion class fits the
source: the clone states no engineering unit and no travel range, while ``cap.motion.joint_position.v1`` publishes
radians and requires per-binding joint limits.  The stop capability is the extension
``x-cap.bec-project.axis_stop.v1``; ``cap.motion.stop.v1`` is not used because its optional ``deceleration`` input
would be inherited by the binding, and the native stop has no deceleration parameter to apply it to.  The site overlay
supplies the travel envelope; until it does, every move is refused with ``MHS.SAFETY.LIMITS_UNSET``.

The stop route is the upstream ``PSISimplePositionerBase.stop()`` (ophyd_devices/interfaces/base_classes/
psi_positioner_base.py:316-322).  PSISimplePositioner declares no ``motor_stop`` Signal (simple_positioner.py:7-11),
and ``override_suffixes`` cannot add one: it re-initialises only Signals the class implements and merely logs a
warning for a sentinel such as ``motor_stop`` (psi_positioner_base.py:133-146).  ``stop()`` therefore always takes
the fallback: it writes the value read by ``user_readback.get()`` into ``user_setpoint`` (a new target for the axis,
not a stop) and ``PSIDeviceBase.stop()`` sets ``stopped`` and fails the registered move status.  Model review
(2026-11-05): the author described a configurable ``motor_stop`` route that cannot exist for this class and bound
the setpoint rewrite as the e-stop and as a safe-state action.  The @estop still sends it and then reports
``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held; the stop action is an ordinary hold request.  The package is
blocked: the selected class has no source-backed stop.

Every Fact cites the pinned clone at commit 2141d541b915562deb9d530d6d41ebb8e4585b1d.  The package is model-authored
and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and has never connected to an EPICS
IOC.
"""

import time

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The selected upstream module, relative to the clone root.
SOURCE = "ophyd_devices/devices/simple_positioner.py"
#: The local base class that implements move, stop and the Signal contract.
BASE = "ophyd_devices/interfaces/base_classes/psi_positioner_base.py"
#: The PSI base class that owns stop(), the stopped flag and status cancellation.
DEVICE_BASE = "ophyd_devices/interfaces/base_classes/psi_device_base.py"
#: The move extension: the source states neither an engineering unit nor a travel range.
MOVE = "x-cap.bec-project.axis_move.v1"
#: The stop extension: no catalogue stop class fits because the native stop has no deceleration parameter.
STOP = "x-cap.bec-project.axis_stop.v1"
#: Execution bound of a move action in milliseconds (it bounds the wait, not the axis travel).
MAX_MOVE_MS = 120000


class PSISimplePositionerAxis(Driver):
    device_id = "psi-simple-positioner"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "ophyd_devices.devices.simple_positioner:PSISimplePositioner"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePSISimplePositioner"}
    vendor = "bec-project"
    model = "PSISimplePositioner (ophyd_devices)"
    display_name = "PSI simple EPICS positioner"
    tags = ["ophyd", "epics", "motion", "positioner", "bec", "psi"]
    safe_state = (
        "No safe state is certified: PSISimplePositioner has no motor_stop Signal, so the native stop() writes the "
        "value read from user_readback into user_setpoint, a new target that the axis then moves to (a motor record "
        "may overshoot and return), and fails the running move status; the e-stop sends it and reports "
        "SAFE_STATE_UNREACHED with the latch held, and nothing senses that the axis is quiescent"
    )
    facts = [
        Fact(
            "PSISimplePositioner subclasses PSISimplePositionerBase and declares user_readback, user_setpoint, "
            "velocity and motor_done_move as ophyd EpicsSignal Components at suffixes R, S, V and D, and no "
            "motor_stop",
            source="upstream_code", ref=f"{SOURCE}:7-11",
        ),
        Fact(
            "PSISimplePositionerBase declares user_readback and user_setpoint as required Signals, velocity, "
            "motor_stop and motor_done_move as optional Signals, stop_value=1, done_value=1 and "
            "use_put_complete=False",
            source="upstream_code", ref=f"{BASE}:76-84",
        ),
        Fact(
            "The constructor accepts prefix, name, optional limits, deadband and override_suffixes",
            source="upstream_code", ref=f"{BASE}:86-97",
        ),
        Fact(
            "override_suffixes re-initialises a named Signal with prefix + suffix only when the class implements it; "
            "for a Signal still set to the optional sentinel it only logs that the class does not implement it",
            source="upstream_code", ref=f"{BASE}:133-146",
        ),
        Fact(
            "move() calls super().move(position, timeout=..., moved_cb=...), calls _setup_move(position), waits only "
            "when wait is true, and returns the MoveStatus",
            source="upstream_code", ref=f"{BASE}:232-276",
        ),
        Fact(
            "stop() writes stop_value to motor_stop when motor_stop is not the optional sentinel; otherwise it reads "
            "user_readback.get() and puts that value to user_setpoint, then calls super().stop",
            source="upstream_code", ref=f"{BASE}:316-322",
        ),
        Fact(
            "PSIDeviceBase.stop() calls on_stop(), sets stopped=True, cancels registered stoppable status objects "
            "and calls super().stop",
            source="upstream_code", ref=f"{DEVICE_BASE}:158-168",
        ),
        Fact(
            "stage() sets stopped back to False when the device is not staged", source="upstream_code",
            ref=f"{DEVICE_BASE}:109-118",
        ),
        Fact(
            "_stop_stoppable_status_objects sets a DeviceStoppedError on every registered status that is not done",
            source="upstream_code", ref=f"{DEVICE_BASE}:201-211",
        ),
        Fact(
            "_setup_move puts the target to user_setpoint without waiting and resolves the move through a "
            "TransitionStatus on motor_done_move from 0 to 1 that is registered to be cancelled on stop",
            source="upstream_code", ref=f"{BASE}:191-230",
        ),
        Fact(
            "The device has no built-in travel range: limits is an optional constructor argument; when it is None, "
            "check_value delegates to user_setpoint.check_value",
            source="upstream_code", ref=f"{BASE}:118-174",
        ),
        Fact(
            "The constructor takes an egu keyword and stores kwargs.get('egu') or an empty string in _egu",
            source="upstream_code", ref=f"{BASE}:123",
        ),
        Fact(
            "The egu property returns _egu",
            source="upstream_code", ref=f"{BASE}:162-165",
        ),
    ]

    @read("position", unit="1", description="Fresh user_readback value; the clone states no engineering unit")
    def position(self):
        return self.native.user_readback.get(use_monitor=False)

    @read("setpoint", unit="1", description="Fresh user_setpoint value; the clone states no engineering unit")
    def setpoint(self):
        return self.native.user_setpoint.get(use_monitor=False)

    @read("velocity", unit="1", description="Fresh velocity value; the clone states no engineering unit")
    def velocity(self):
        return self.native.velocity.get(use_monitor=False)

    @read("done_moving", type="boolean",
          description="Fresh motor_done_move value compared with the device's done_value constant")
    def done_moving(self):
        return bool(self.native.motor_done_move.get(use_monitor=False) == self.native.done_value)

    @action(
        name=MOVE,
        description="Move the axis to an absolute target and wait for the device's motor_done_move flag",
        input={
            "target": Field(
                "number", unit="1",
                description="Absolute target in the signal's engineering unit (the clone states none)",
                limit=Limit.operator_required(
                    "the clone states no travel range for PSISimplePositioner; the site must supply the axis "
                    "envelope before a move"
                ),
            ),
        },
        output={
            "target": Field("number", unit="1", description="Target the driver sent to native move()"),
            "position": Field("number", unit="1",
                              description="Fresh user_readback value after the done flag was observed"),
            "reached": Field("boolean",
                             description="Whether the native MoveStatus completed successfully (it fails when a "
                                         "stop cancels the move)"),
        },
        long_running=True, cancellable=True, max_duration_ms=MAX_MOVE_MS, risk="R1",
    )
    def move_axis(self, target, ctx=None):
        target = float(target)
        status = self.native.move(target, wait=False)
        remaining_s = (ctx.remaining_ms() / 1000.0) if ctx is not None else (MAX_MOVE_MS / 1000.0)
        deadline = time.monotonic() + max(0.1, remaining_s)
        while self.native.motor_done_move.get(use_monitor=False) != self.native.done_value:
            if self.cancelled():
                self.native.stop()
                raise Cancelled("the move was cancelled or the device was stopped")
            if time.monotonic() >= deadline:
                self.native.stop()
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   "the axis did not report motor_done_move before the move deadline")
            time.sleep(0.01)
        position = self.native.user_readback.get(use_monitor=False)
        # The MoveStatus fails when stop() cancels the move (psi_device_base.py:201-211).  The stopped flag is not
        # used: upstream it stays true after any earlier stop until stage() (psi_device_base.py:113).
        reached = bool(getattr(status, "done", False) and getattr(status, "success", False))
        return {"target": target, "position": position, "reached": reached}

    @action(
        name=STOP,
        description="Request a hold through native stop(): it writes the value read from user_readback into "
                    "user_setpoint (a new target, not a hardware stop) and reports the fresh done flag and readback",
        output={
            "stopped": Field("boolean",
                             description="Whether the fresh motor_done_move flag equals the device's done_value "
                                         "right after the hold request; false while the axis still moves"),
            "position": Field("number", unit="1",
                              description="Fresh user_readback value after the hold request"),
        },
        risk="R1",
    )
    def stop_axis(self):
        self.native.stop()
        done = self.native.motor_done_move.get(use_monitor=False)
        position = self.native.user_readback.get(use_monitor=False)
        return {
            "stopped": bool(done == self.native.done_value),
            "position": position,
        }

    @estop
    def stop(self):
        """Send the upstream hold request, then refuse to certify it (model review, 2026-11-05).

        PSISimplePositioner has no motor_stop Signal, so stop() writes the read-back value into user_setpoint: a new
        target for the axis, not a stop, and nothing senses quiescence.
        """
        self.native.stop()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "PSISimplePositioner has no motor_stop Signal: stop() wrote the read-back value into user_setpoint, a "
            "new target rather than a stop, and nothing confirms that the axis stopped",
        )
