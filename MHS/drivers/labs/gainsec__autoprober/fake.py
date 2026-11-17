"""Fake backend of the AutoProber CNC driver: an in-memory stand-in for autoprober.cnc:CNC.

Gate G7: every public method defined here exists on ``autoprober.cnc.CNC``
(autoprober/cnc.py:46-163).  The upstream class opens a USB serial line and speaks GRBL; this stand-in keeps the
machine state in memory and never imports the clone, opens a port or talks to hardware.

The stand-in models the parts of the native API the driver uses: a GRBL status document from ``get_status`` (state,
MPos, Pn), the ``$$`` settings map from ``read_settings``, ``$X`` unlock, ``$H`` homing, the ``!`` feed hold and the
G90/G91 move writers.  A move takes a few status polls before the position reaches its target so that a feed hold or
a cancellation can be observed; it does not model deceleration, the planner queue, limit switches, serial timing or
the controller's own alarm handling.  The parameter defaults ``feed=800``, ``timeout=60`` and ``poll_interval=0.2``
repeat the upstream method signatures (autoprober/cnc.py:121, 131, 148) and are not facts about a machine.  Every
other number below is test data, not a fact about a machine, and is marked placeholder where it is set.
"""

import time


class FakeCnc:
    def __init__(self, **_options):
        self._connected = True                  # placeholder: the stand-in is open when the backend constructs it
        self._state = "Idle"                   # placeholder
        self._mpos = [0.0, 0.0, 0.0]           # placeholder: X, Y and Z in millimetres
        self._pins = set()                     # placeholder: no real limit pin is active
        self._settings = {                     # placeholder: not a machine configuration
            "110": "500.000",
            "111": "500.000",
            "112": "500.000",
        }
        self._motion_ticks = 0                 # placeholder: status polls before a move completes
        self._target = None                    # placeholder
        self._hold_count = 0                   # placeholder: observability counter, not a device value

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def connect(self):
        self._connected = True

    def close(self):
        self._connected = False
        self._motion_ticks = 0
        self._target = None

    # -- native reads ------------------------------------------------------------------------------------------
    def get_status(self):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        if self._motion_ticks > 0:
            self._motion_ticks -= 1
            if self._motion_ticks == 0 and self._target is not None:
                self._mpos = list(self._target)
                self._target = None
                self._state = "Idle"
        raw_pn = "".join(sorted(self._pins))
        raw = "<{}|MPos:{:.3f},{:.3f},{:.3f}|Pn:{}>".format(
            self._state, self._mpos[0], self._mpos[1], self._mpos[2], raw_pn)
        return {
            "state": self._state,
            "mpos": (self._mpos[0], self._mpos[1], self._mpos[2]),
            "raw_pn": raw_pn,
            "pins": set(self._pins),
            "raw": raw,
        }

    def read_settings(self):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        return dict(self._settings)

    # -- native commands ---------------------------------------------------------------------------------------
    def unlock(self):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        # $X is an alarm clear, not a cycle-start command. Do not invent recovery from feed hold.
        if self._state.lower().startswith("alarm"):
            self._state = "Idle"

    def home(self):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        self._state = "Home"                   # placeholder: the homing cycle state
        self._motion_ticks = 5                 # placeholder: status polls before homing completes
        self._target = [0.0, 0.0, 0.0]         # placeholder: the stand-in machine origin

    def feed_hold(self):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        self._hold_count += 1                  # placeholder: test observability only
        self._state = "Hold"
        self._motion_ticks = 0
        self._target = None                    # the paused target is never resumed by this stand-in

    def move_absolute(self, x=None, y=None, z=None, feed=800):  # noqa: A002 - the upstream parameter name
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        target = list(self._mpos)
        for index, value in enumerate((x, y, z)):
            if value is not None:
                target[index] = float(value)
        self._start_motion(target)

    def move_relative(self, dx=0, dy=0, dz=0, feed=800):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        target = [self._mpos[0] + float(dx), self._mpos[1] + float(dy), self._mpos[2] + float(dz)]
        self._start_motion(target)

    def wait_for_idle(self, timeout=60, poll_interval=0.2):
        if not self._connected:
            raise RuntimeError("the stand-in CNC is not connected")
        deadline = time.time() + float(timeout)
        while time.time() < deadline:
            status = self.get_status()
            if status["state"] == "Idle":
                return status
            time.sleep(float(poll_interval))
        raise RuntimeError("the stand-in CNC did not become idle")

    # -- internal ----------------------------------------------------------------------------------------------
    def _start_motion(self, target):
        self._target = [float(value) for value in target]
        self._state = "Run"                    # placeholder: the GRBL run state
        self._motion_ticks = 5                 # placeholder: status polls before the target is applied
