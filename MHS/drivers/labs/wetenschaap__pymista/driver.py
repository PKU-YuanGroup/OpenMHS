"""OpenMHS driver for gh.wetenschaap/pymista: a Zaber stage through the upstream Python object.

A direct Driver (decorated methods) over the upstream class ``pymista.zaber:ZaberStage``.  The upstream class wraps
the Zaber ASCII library: it opens the serial connection, builds one axis per detected device (pymista/zaber.py:17-33)
and sets the Zaber length unit to micrometres (pymista/zaber.py:14), so every position in this package is a
micrometre value (README.md:21).

* reads: the position of every axis, whether any axis is moving and which axes report themselves homed;
* actions: move all axes to absolute positions, move all axes by relative displacements, home every axis, and the
  catalogue stop class ``cap.motion.stop.v1``.  No text in the clone states the travel range of the stage or of the
  stage mounted on a controller, so both motion inputs are ``Limit.operator_required``: every call is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the permitted range (``site-limits.example.json`` shows the
  overlay);
* the native stop (``UniversalStage.stop``, pymista/universal.py:84-86) is the e-stop and, as ``stop_motion``, the
  safe-state action.

The clone's DummyStage (pymista/dummy.py:6-9) is a separate fake class with arbitrary four-axis settings; this
package uses the package fake in ``fake.py`` instead, because the gate checks the fake against the real
``ZaberStage`` surface.

Every Fact cites a line of the clone at the pinned commit (b30040a192c329b6144a120f0dfea2ca68060760).  This package
is model-authored and unreviewed: it is checked on the fake backend only and its hardware path was never run.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

_MOVE_LIMIT_REASON = (
    "no text in the clone states the travel range of the stage or of the stage mounted on the controller; "
    "the permitted target range depends on the installed stage and is a site decision (site-limits.example.json "
    "shows the overlay)"
)
_RELATIVE_LIMIT_REASON = (
    "no text in the clone states the travel range of the stage; the permitted relative displacement of the installed "
    "stage is a site decision, and a per-call bound cannot replace an absolute travel envelope"
)


class ZaberStageDriver(Driver):
    device_id = "pymista"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pymista.zaber:ZaberStage"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeZaberStage"}
    vendor, model = "Zaber Technologies", "Zaber ASCII stage"
    display_name = "Zaber microscopy stage (pymista.ZaberStage)"
    tags = ["stage", "motion", "zaber", "microscopy", "micrometre"]
    facts = [
        Fact("The README states that units of distance are always given in micrometres",
             source="vendor_doc", ref="README.md:21"),
        Fact("ZaberStage sets the Zaber library length unit to LENGTH_MICROMETRES",
             source="upstream_code", ref="pymista/zaber.py:14"),
        Fact("ZaberStage.connectStage opens the Zaber ASCII serial connection, enables alerts and builds one axis "
             "from every detected device", source="upstream_code", ref="pymista/zaber.py:17-33"),
        Fact("ZaberStage.move_absolute sends every axis its target position in the stage unit and, when "
             "wait_until_idle is true, waits until all axes are idle",
             source="upstream_code", ref="pymista/zaber.py:35-39"),
        Fact("ZaberStage.move_relative sends every axis its displacement in the stage unit and, when wait_until_idle "
             "is true, waits until all axes are idle", source="upstream_code", ref="pymista/zaber.py:41-45"),
        Fact("ZaberStage.get_position reads every axis position in the stage unit",
             source="upstream_code", ref="pymista/zaber.py:47-48"),
        Fact("UniversalStage.home homes every axis that is not homed, or every axis when force is true",
             source="upstream_code", ref="pymista/universal.py:13-19"),
        Fact("UniversalStage.stop calls stop() on every axis", source="upstream_code",
             ref="pymista/universal.py:84-86"),
        Fact("UniversalStage.is_moving is true when any axis reports is_busy",
             source="upstream_code", ref="pymista/universal.py:94-96"),
        Fact("UniversalStage.is_homed returns one entry per axis", source="upstream_code",
             ref="pymista/universal.py:21-25"),
        Fact("UniversalStage.close closes the stage connection", source="upstream_code",
             ref="pymista/universal.py:27-31"),
        Fact("The README says a stage typically has 2 or 3 axes (x, y, z)", source="vendor_doc",
             ref="README.md:68"),
        Fact("The clone provides DummyStage as a fake stage for troubleshooting", source="upstream_code",
             ref="pymista/dummy.py:6-9"),
    ]
    safe_state = "all axes stopped; the native stop() is called on every axis"

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _positions(self):
        return [float(value) for value in self.native.get_position()]

    def _target_vector(self, values):
        """One target per axis: missing trailing entries keep the current position, extra entries are refused."""
        current = self._positions()
        targets = [float(value) for value in values]
        if len(targets) > len(current):
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"the stage reports {len(current)} axes but {len(targets)} target positions were given",
            )
        return targets + current[len(targets):]

    def _relative_vector(self, values):
        """One displacement per axis: missing trailing entries are zero, extra entries are refused."""
        current = self._positions()
        moves = [float(value) for value in values]
        if len(moves) > len(current):
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"the stage reports {len(current)} axes but {len(moves)} displacements were given",
            )
        return moves + [0.0] * (len(current) - len(moves))

    def _wait_until_idle(self):
        while self.native.is_moving():
            self.check_cancelled()
            time.sleep(0.02)

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("position", type="array", items="number", unit="um",
          description="Position of every axis in micrometres, in the order the stage reports its axes")
    def position(self):
        return self._positions()

    @read("moving", type="boolean", description="True while any axis reports that it is moving")
    def moving(self):
        return bool(self.native.is_moving())

    @read("homed", type="array", items="boolean",
          description="One entry per axis: true when that axis reports itself homed")
    def homed(self):
        return [bool(value) for value in self.native.is_homed()]

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(
        name="x-cap.wetenschaap.move_absolute.v1",
        description="Move the axes to absolute positions in micrometres and wait until the stage is idle. "
                    "The array names the leading axes in order; trailing axes keep their current position.",
        input={"positions": Field(
            "array", items="number", unit="um",
            description="Absolute target position in micrometres for the leading axes, in axis order",
            limit=Limit.operator_required(_MOVE_LIMIT_REASON))},
        output={
            "positions": Field("array", items="number", unit="um",
                               description="Position of every axis in micrometres after the motion"),
            "moved": Field("boolean", description="True when the move reached the idle state"),
        },
    )
    def move_absolute(self, positions):
        targets = self._target_vector(positions)
        self.native.move_absolute(targets, wait_until_idle=False)
        self._wait_until_idle()
        return {"positions": self._positions(), "moved": not bool(self.native.is_moving())}

    @action(
        name="x-cap.wetenschaap.move_relative.v1",
        description="Move the axes by relative displacements in micrometres and wait until the stage is idle. "
                    "The array names the leading axes in order; trailing axes do not move.",
        input={"displacements": Field(
            "array", items="number", unit="um",
            description="Relative displacement in micrometres for the leading axes, in axis order",
            limit=Limit.operator_required(_RELATIVE_LIMIT_REASON))},
        output={
            "positions": Field("array", items="number", unit="um",
                               description="Position of every axis in micrometres after the motion"),
            "moved": Field("boolean", description="True when the move reached the idle state"),
        },
    )
    def move_relative(self, displacements):
        moves = self._relative_vector(displacements)
        self.native.move_relative(moves, wait_until_idle=False)
        self._wait_until_idle()
        return {"positions": self._positions(), "moved": not bool(self.native.is_moving())}

    @action(
        name="x-cap.wetenschaap.home_axes.v1",
        description="Home every axis with the native force homing and report whether every axis is homed. "
                    "It takes no input.",
        output={"homed": Field("boolean", description="True once every axis reports itself homed")},
    )
    def home_axes(self):
        self.native.home(force=True)
        self._wait_until_idle()
        return {"homed": all(bool(value) for value in self.native.is_homed())}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            input={"deceleration": Field(
                "number", unit="m/s2",
                description="Requested deceleration; the native stop takes no deceleration argument and uses the "
                            "device's configured stop profile, so the value is accepted but does not change the call")},
            description="Stop all axis motion with the native stop() and report whether the stage is idle")
    def stop_motion(self, deceleration=None):
        self.native.stop()
        return {"stopped": not bool(self.native.is_moving())}

    # -- safety -----------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then calls stop() on every axis."""
        self.native.stop()

    def teardown(self):
        self.native.close()
