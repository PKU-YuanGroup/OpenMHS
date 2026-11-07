"""OpenMHS driver for gh.lando1784/pyagilis: the Newport Agilis agUC2 piezo controller.

The upstream package is a Python object API, not a command table: it opens the serial line itself and assembles
each wire command from parts (``<axis>PR<steps>``, ``<axis>ST``, ``MR``).  A direct Driver is therefore used over
``pyagilis.controller:AGUC2``; native.py opens the upstream transport on the hardware backend.  This is a deviation
from the task card's ``SerialDriver`` family decision (the card's static scan guessed a serial command table).

* reads: the accumulated step counter and the limit-switch state of both axes, plus the last operation recorded by
  each axis;
* no writable state: the upstream class has no setter for a device setting, and the step amplitudes are constructor
  options of AGUC2/Axis;
* actions: a relative two-axis jog, return the counters to zero, reset the counters, and stop motion;
* the e-stop and the safe-state action both call the upstream stop path, which sends ``ST`` to each axis.

Every Fact cites a line of the clone at the pinned commit (7d27bd1571aa6b4187e2e0d40c9f34feb45456f2).  This package is
model-authored and unreviewed; the acceptance gate runs the fake backend only.  No hardware run is claimed.  The step
range is not stated in the clone, so it is ``Limit.operator_required``: every jog is refused until the operator's
site-limits.json supplies the travel bound.  This package is R1: the card floor is R0 and the catalogue's motion
capabilities for a single axis are R1; the loader does not gate an unreviewed R1 hardware backend, so the operator
must not attach hardware without a human review.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The relative steps a jog may take are not stated in the clone.  The upstream jog() passes any integer to PR
#: (pyagilis/channel.py:83) and its docstring names no bound (pyagilis/channel.py:75-77).
STEPS_REASON = ("the clone states no travel or step bound: jog() forwards any integer to the PR command "
                "(pyagilis/channel.py:75-83); the operator sets the travel allowed on the installed stage")


class AgilisAgUC2(Driver):
    device_id = "agilis-aguc2"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pyagilis.controller:AGUC2"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAGUC2"}
    vendor, model = "Newport", "Agilis agUC2 piezo motion controller"
    display_name = "Newport Agilis agUC2"
    tags = ["newport", "agilis", "piezo", "motion-controller", "serial"]
    facts = [
        Fact("The package is a Python library for Newport Agilis piezo motion controllers (agUC2 and agUC8)",
             source="vendor_doc", ref="README.md:2"),
        Fact("AGUC2 resets with 'MR' and then installs axis 1 and axis 2",
             source="upstream_code", ref="pyagilis/controller.py:30-33"),
        Fact("AGUC2.move jogs axis 1 and waits until it is still, then jogs axis 2 and waits",
             source="upstream_code", ref="pyagilis/controller.py:41-46"),
        Fact("goToZero reads both axis counters and jogs each axis by the negative of its counter",
             source="upstream_code", ref="pyagilis/controller.py:81-89"),
        Fact("setZero resets the counter of both axes",
             source="upstream_code", ref="pyagilis/controller.py:92-95"),
        Fact("A jog of n steps sends '<axis>PR<n>'",
             source="upstream_code", ref="pyagilis/channel.py:75-83"),
        Fact("The stop command of an axis is '<axis>ST'",
             source="upstream_code", ref="pyagilis/channel.py:45-48"),
        Fact("queryCounter sends '<axis>TP' and returns the accumulated steps since power-on or the last reset",
             source="upstream_code", ref="pyagilis/channel.py:64-67"),
        Fact("amIatMyLimit reads the 'PH' limit-switch status",
             source="upstream_code", ref="pyagilis/channel.py:59-62"),
        Fact("A counter reset sends '<axis>ZP'",
             source="upstream_code", ref="pyagilis/channel.py:69-72"),
        Fact("The serial port is opened at 921600 baud with 8 data bits, no parity and one stop bit",
             source="upstream_code", ref="pyagilis/agPort.py:38"),
        Fact("The step amplitude of an axis is stated as 0 to 50",
             source="upstream_code", ref="pyagilis/channel.py:24"),
    ]
    safe_state = "both axes stopped (the native stop sends ST to each axis)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("x_steps", type="integer", unit="1",
          description="Accumulated steps of axis 1 since power-on or the last counter reset")
    def x_steps(self):
        return self._axis(0).queryCounter()

    @read("y_steps", type="integer", unit="1",
          description="Accumulated steps of axis 2 since power-on or the last counter reset")
    def y_steps(self):
        return self._axis(1).queryCounter()

    @read("x_at_limit", type="boolean", description="True when the axis 1 limit switch reports the axis at its limit")
    def x_at_limit(self):
        return bool(self._axis(0).amIatMyLimit())

    @read("y_at_limit", type="boolean", description="True when the axis 2 limit switch reports the axis at its limit")
    def y_at_limit(self):
        return bool(self._axis(1).amIatMyLimit())

    @read("x_last_operation", type="string", description="Last operation recorded by axis 1")
    def x_last_operation(self):
        return self._axis(0).whatDidIdo()

    @read("y_last_operation", type="string", description="Last operation recorded by axis 2")
    def y_last_operation(self):
        return self._axis(1).whatDidIdo()

    # -- actions -----------------------------------------------------------------------------------------------
    @action(name="x-cap.lando1784.jog.v1",
            description="Jog axis 1 and axis 2 by signed step counts (relative motion)",
            input={
                "x_steps": Field("integer", unit="1",
                                 description="Signed steps for axis 1; positive is the forward direction",
                                 limit=Limit.operator_required(STEPS_REASON)),
                "y_steps": Field("integer", unit="1",
                                 description="Signed steps for axis 2; positive is the forward direction",
                                 limit=Limit.operator_required(STEPS_REASON)),
            },
            output={
                "x_steps": Field("integer", unit="1",
                                 description="Axis 1 counter after the jog (steps since power-on or reset)"),
                "y_steps": Field("integer", unit="1",
                                 description="Axis 2 counter after the jog (steps since power-on or reset)"),
                "x_at_limit": Field("boolean", description="Axis 1 limit-switch state after the jog"),
                "y_at_limit": Field("boolean", description="Axis 2 limit-switch state after the jog"),
            })
    def jog(self, x_steps, y_steps):
        self.native.move(x_steps, y_steps)
        return self._position()

    @action(name="x-cap.lando1784.go_to_zero.v1",
            description="Move both axes back to counter zero (the upstream goToZero)",
            output={
                "x_steps": Field("integer", unit="1", description="Axis 1 counter after the move"),
                "y_steps": Field("integer", unit="1", description="Axis 2 counter after the move"),
            })
    def go_to_zero(self):
        self.native.goToZero()
        return self._counters()

    @action(name="x-cap.lando1784.set_zero.v1",
            description="Reset both axis counters to zero without moving (the upstream setZero)",
            output={
                "x_steps": Field("integer", unit="1", description="Axis 1 counter after the reset"),
                "y_steps": Field("integer", unit="1", description="Axis 2 counter after the reset"),
            })
    def set_zero(self):
        self.native.setZero()
        return self._counters()

    @action(name="x-cap.lando1784.stop.v1", safe_state=True,
            description="Stop both axes (the native stop); the device's safe state",
            output={"stopped": Field("boolean", description="True once the native stop has reached both axes")})
    def stop_motion(self):
        self.native.stop()
        return {"stopped": True}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop path: AGUC2.stop, which sends ST to each axis."""
        self.native.stop()

    # -- helpers -----------------------------------------------------------------------------------------------
    def _axis(self, index):
        """The upstream Axis object for controller axis 1 (index 0) or 2 (index 1)."""
        return self.native.axis[self.native.aliases[index]]

    def _position(self):
        return {"x_steps": self._axis(0).queryCounter(), "y_steps": self._axis(1).queryCounter(),
                "x_at_limit": bool(self._axis(0).amIatMyLimit()),
                "y_at_limit": bool(self._axis(1).amIatMyLimit())}

    def _counters(self):
        return {"x_steps": self._axis(0).queryCounter(), "y_steps": self._axis(1).queryCounter()}

    def teardown(self):
        """Close the upstream serial port when the backend created one."""
        close = getattr(self.native.port, "close", None)
        if callable(close):
            close()
