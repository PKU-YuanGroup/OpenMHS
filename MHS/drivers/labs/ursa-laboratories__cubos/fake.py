"""Fake backend of the CubOS gantry driver: an in-memory stand-in for Gantry.

Gate G7: every public method defined here exists on
``cubos.gantry.gantry:Gantry``.  The fake keeps the work position and the
controller status in memory, refuses motion while the emulated feed hold is
engaged, and makes both the native stop and the native resume observable.  It
is an analytic stand-in, not a recording: the starting position and the canned
status strings are test data (marked as placeholders), not device facts, and
nothing here talks to hardware or imports the upstream clone.
"""


class FakeGantry:
    def __init__(self, **_options):
        self._coords = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder: test start position
        self._status = "Idle"                           # placeholder: canned status
        self._held = False                              # placeholder: feed hold start state
        self._connected = True                          # placeholder: the fake starts connected
        self._stops = 0
        self._resumes = 0
        self._homes = 0

    # -- connection -----------------------------------------------------------------------------------------
    def connect(self, port=None):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def is_healthy(self):
        return self._connected

    # -- motion ---------------------------------------------------------------------------------------------
    def home(self):
        self._require_idle("home")
        self._coords = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder: reference position after homing
        self._status = "Idle"                           # placeholder: canned status after homing
        self._homes += 1

    def move_to(self, x, y, z, travel_z=None):
        self._require_idle("move")
        self._coords = {"x": float(x), "y": float(y), "z": float(z)}
        self._status = "Idle"                           # placeholder: canned status once the move completes

    # -- status and position --------------------------------------------------------------------------------
    def get_status(self):
        return self._status

    def get_coordinates(self):
        return dict(self._coords)

    def get_position_info(self):
        return {"coords": dict(self._coords), "work_pos": dict(self._coords), "status": self._status}

    # -- stop and recovery ----------------------------------------------------------------------------------
    def stop(self):
        self._held = True
        self._status = "Hold"                           # placeholder: canned status after the feed hold
        self._stops += 1

    def feed_hold_realtime(self):
        self._held = True
        self._status = "Hold"                           # placeholder: canned status after the feed hold

    def resume(self):
        self._held = False
        if self._status == "Hold":
            self._status = "Idle"                       # placeholder: canned status after cycle start
        self._resumes += 1

    # -- helpers --------------------------------------------------------------------------------------------
    def _require_idle(self, what):
        if self._held:
            raise RuntimeError(f"fake gantry: cannot {what} while the feed hold is engaged")
